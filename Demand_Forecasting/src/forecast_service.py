"""Future inference using frozen research models and explicit exogenous estimates.

No future weather observations are available locally. Recent weather averages
and an intraday solar profile are assumptions, never observed future inputs.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import holidays
import numpy as np
import pandas as pd
from drift_project.src.baseline import predict
from .data_loader import model_frame


def local_now():
    return pd.Timestamp(datetime.now(ZoneInfo('Asia/Colombo'))).tz_localize(None)


def forecast(service, horizon_hours=24, origin='now', now=None):
    if horizon_hours not in (24, 168):
        raise ValueError('Supported horizons are 24 or 168 hours')
    if origin not in ('now', 'dataset_end'):
        raise ValueError('origin must be now or dataset_end')
    data_end = service.data.timestamp.max()
    clock = pd.Timestamp(now) if now is not None else local_now()
    if clock.tzinfo is not None:
        clock = clock.tz_convert('Asia/Colombo').tz_localize(None)
    issued = max(clock, data_end) if origin == 'now' else data_end
    start = issued.floor('15min') + pd.Timedelta(minutes=15)
    times = pd.date_range(start, periods=horizon_hours*4, freq='15min')
    future = pd.DataFrame({'timestamp': times})
    recent = service.data[service.data.timestamp > data_end-pd.Timedelta(days=28)]
    week = recent[recent.timestamp > data_end-pd.Timedelta(days=7)]
    if week.empty:
        raise ValueError('No recent observations available for future feature estimation')
    warnings = []
    assumed = []
    for name in ['temperature', 'precipitation', 'shortwave_radiation', 'solar_mw']:
        if name not in service.data:
            continue
        if name in ('solar_mw', 'shortwave_radiation'):
            values = recent.dropna(subset=[name]).copy()
            if values.empty:
                raise ValueError(f'Cannot estimate future {name}: no recent valid observations')
            slots = values.timestamp.dt.hour*60 + values.timestamp.dt.minute
            profile = values.groupby(slots)[name].mean()
            future[name] = pd.Series(times.hour*60+times.minute).map(profile).to_numpy()
            missing = future[name].isna()
            if missing.any():
                future.loc[missing, name] = float(values[name].mean())
                warnings.append(f'{name}: {int(missing.sum())} missing intraday slots use the recent mean.')
        else:
            # Daily aggregates are repeated across intervals in the supplied data;
            # equal-weight daily means avoid bias toward better-covered days.
            daily = week.set_index('timestamp')[name].resample('D').mean().dropna()
            if daily.empty:
                raise ValueError(f'Cannot estimate future {name}: no valid observations in the last seven days')
            future[name] = float(daily.mean())
        assumed.append(name)
    if 'is_holiday' in service.data:
        calendar = holidays.country_holidays('LK', years=sorted(set(times.year)))
        future['is_holiday'] = [float(t.date() in calendar) for t in times]
        assumed.append('is_holiday')

    model_input = model_frame(future.copy())
    if 'solar_generation_mw' in model_input:
        model_input['solar_generation_mw'] = model_input.solar_generation_mw.clip(0, 1000)
    # Hold the deployment state fixed at issuance, not at each future timestamp.
    # Even a bundle with later model states must not reveal them in a forecast.
    state_at = min(issued, data_end)
    strategy = ''
    for adapted, column in [(False, 'static_generation_mw'), (True, 'adapted_generation_mw')]:
        entry = service.selected_model(state_at, adapted)
        filled = model_input.fillna(entry['means'])
        for name, value in entry['means'].items():
            if name not in filled: filled[name] = value
        values = predict(entry['model'], filled, **entry['flags'])
        if not np.isfinite(values).all():
            raise ValueError('Model returned non-finite future predictions')
        if (values < 0).any():
            warnings.append(f'{column}: model produced negative values; raw estimates are retained for review.')
        future[column] = values
        if adapted: strategy = entry['strategy']
    age_days = (issued-data_end).total_seconds()/86400
    if age_days > 1:
        warnings.append(f'Latest valid observation is {age_days:.1f} days before forecast origin. Refresh data and prepare artifacts for current conditions.')
    if issued < clock:
        warnings.append('This forecast starts after the dataset end and may be in the past relative to today.')
    rows = [dict(timestamp=row.timestamp, static_generation_mw=row.static_generation_mw,
                 adapted_generation_mw=row.adapted_generation_mw,
                 assumed_features={name: float(row[name]) for name in assumed})
            for _, row in future.iterrows()]
    return dict(horizon_hours=horizon_hours, count=len(rows), forecast_origin=issued,
                data_as_of=data_end, start=times[0], end=times[-1], adapted_strategy=strategy,
                feature_method='recent-history scenario v1', warnings=warnings,
                assumptions=[
                    'Future electricity estimates use the real frozen Ridge models; no retraining or online updates occur.',
                    'Weather is an assumed persistence scenario: equal-weight mean of daily values from the latest seven observed days, not a meteorological forecast.',
                    'Solar and radiation use a mean intraday profile from the latest 28 observed days; missing slots use the recent mean. These are estimates, not future measurements.',
                    'Holiday flags use the Sri Lankan calendar; original time encodings and solar model-input clipping are retained.',
                    'No future drift events are assumed. The latest available adaptation state stays fixed across the horizon.',
                    'Future actual values, MAPE, RMSE and calibrated uncertainty intervals are unavailable. Forecast accuracy for these horizons has not been backtested.',
                ], data=rows)
