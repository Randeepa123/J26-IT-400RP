"""Aligned evaluation and explicit sustained recovery methodology."""
import numpy as np
import pandas as pd
from .config import REGIMES
from .prediction_service import ape

def scores(frame, column):
    if frame.empty:
        return dict(mape=None, rmse=None, excluded=0)
    errors = ape(frame.actual_generation_mw, frame[column])
    return dict(mape=float(np.nanmean(errors)) if np.isfinite(errors).any() else None,
                rmse=float(np.sqrt(np.mean((frame.actual_generation_mw-frame[column])**2))),
                excluded=int((~np.isfinite(errors)).sum()))

def metrics(frame):
    rows = []
    for name, _, _ in REGIMES:
        sub = frame[frame.regime == name]
        aligned = sub[np.isfinite(sub[['actual_generation_mw','static','adapted']]).all(axis=1)]
        static, adapted = scores(aligned, 'static'), scores(aligned, 'adapted')
        improvement = static['mape']-adapted['mape'] if len(aligned) else None
        rows.append(dict(regime=name, observations=len(aligned), static_mape=static['mape'], adapted_mape=adapted['mape'],
                         static_rmse_mw=static['rmse'], adapted_rmse_mw=adapted['rmse'], improvement_pp=improvement,
                         relative_improvement_percent=improvement/static['mape']*100 if improvement is not None and static['mape'] else None,
                         excluded=len(sub)-len(aligned), excluded_ape=static['excluded'],
                         start=str(aligned.timestamp.min()) if len(aligned) else None,
                         end=str(aligned.timestamp.max()) if len(aligned) else None,
                         status='available' if len(aligned) else 'unavailable'))
    return rows

def recovery(frame, drifts, settings):
    """Trailing time-aware window, then N consecutive daily checks with adequate coverage.

    All observations in a recovery window must be after model availability;
    confirmation timestamp is the last observation of the final successful day.
    """
    rows = []
    for index, event in drifts.iterrows():
        dt = event.drift_date
        available = pd.Timestamp(event.get('available_at', dt+pd.Timedelta(days=30)))
        next_event = drifts.iloc[index+1].drift_date if index+1 < len(drifts) else frame.timestamp.max()+pd.Timedelta(nanoseconds=1) if len(frame) else available
        sub = frame[(frame.timestamp >= available) & (frame.timestamp < next_event)].copy()
        sub['error'] = ape(sub.actual_generation_mw, sub.adapted)
        found = None
        observations = 0
        if not sub.empty:
            series = sub.set_index('timestamp').error
            rolling = series.rolling(f'{settings.rolling_days}D', min_periods=settings.recovery_min).mean()
            # Daily checks require actual observations; missing calendar days break a streak.
            checks = rolling.resample('D').last()
            counts = series.resample('D').count().reindex(checks.index, fill_value=0)
            eligible = (checks <= settings.threshold) & (counts >= settings.recovery_min)
            eligible &= checks.index >= available + pd.Timedelta(days=settings.rolling_days)
            streak = eligible.astype(int).rolling(settings.sustained_days, min_periods=settings.sustained_days).sum()
            successful = streak[streak == settings.sustained_days]
            if len(successful):
                day = successful.index[0]
                found = sub.loc[sub.timestamp.dt.normalize() == day, 'timestamp'].max()
                window_start = day-pd.Timedelta(days=settings.sustained_days-1+settings.rolling_days)
                observations = int(sub.loc[(sub.timestamp > window_start) & (sub.timestamp <= found), 'error'].count())
        rows.append(dict(drift_date=str(dt), drift_type=event.drift_type, strategy=event.strategy,
                         regime=event.regime, available_at=str(available), recovery_timestamp=str(found) if found is not None else None,
                         lag_days=(found-dt).total_seconds()/86400 if found is not None else None,
                         status='recovered' if found is not None else 'not_observed', threshold_percent=settings.threshold,
                         rolling_days=settings.rolling_days, sustained_days=settings.sustained_days,
                         minimum_daily_observations=settings.recovery_min, verification_observations=observations))
    return rows
