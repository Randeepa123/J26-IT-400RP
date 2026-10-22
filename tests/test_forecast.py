"""Future prediction tests use isolated synthetic training fixtures only."""
import numpy as np
import pandas as pd
import pytest
from src.forecast_service import forecast
from src.prediction_service import PredictionService
from src.data_loader import load_data, model_frame
from drift_project.src.baseline import predict


@pytest.mark.parametrize('hours,count',[(24,96),(168,672)])
def test_horizons_and_real_model(client,hours,count):
    response=client.get('/forecast',params={'horizon_hours':hours,'origin':'dataset_end'})
    assert response.status_code==200
    body=response.json()
    assert body['count']==count and len(body['data'])==count
    times=pd.DatetimeIndex([row['timestamp'] for row in body['data']])
    assert times[0]==pd.Timestamp(body['data_as_of'])+pd.Timedelta(minutes=15)
    assert times[-1]==pd.Timestamp(body['data_as_of'])+pd.Timedelta(hours=hours)
    assert (times.to_series().diff().dropna()==pd.Timedelta(minutes=15)).all()
    first=body['data'][0]
    assert 'actual_generation_mw' not in first and 'ape_percent' not in first
    service=client.app.state.service
    features=first['assumed_features']
    expected,_=service.infer(pd.Timestamp(first['timestamp']),features)
    assert first['static_generation_mw']==pytest.approx(expected)
    assert np.isfinite([r['adapted_generation_mw'] for r in body['data']]).all()


def test_now_forecast_and_stale_warning(client):
    service=client.app.state.service
    now=pd.Timestamp('2026-10-20 17:07:00')
    result=forecast(service,168,now=now)
    assert result['start']==pd.Timestamp('2026-10-20 17:15:00')
    assert result['end']==pd.Timestamp('2026-10-27 17:00:00')
    assert any('Refresh data' in warning for warning in result['warnings'])


def test_invalid_forecast_parameters(client):
    for params in [{'horizon_hours':48},{'horizon_hours':0},{'origin':'tomorrow'}]:
        assert client.get('/forecast',params=params).status_code==422


def test_no_mutation_or_future_model_state(client):
    service=client.app.state.service
    before=service.frame.copy(deep=True)
    original=forecast(service,24,origin='dataset_end')
    # A state not available at issuance must never affect any horizon row.
    entry=dict(service.bundle['static'])
    entry['available_at']=service.data.timestamp.max()+pd.Timedelta(hours=1)
    entry['strategy']='Must not become available during the forecast'
    service.bundle['adapted'].append(entry)
    after=forecast(service,24,origin='dataset_end')
    assert after['data']==original['data']
    assert after['adapted_strategy']=='Static Baseline'
    pd.testing.assert_frame_equal(before,service.frame)


def test_future_calendar_and_explicit_inputs(client):
    service=client.app.state.service
    result=forecast(service,24,now=pd.Timestamp('2022-01-13 23:59:00'))
    # Thai Pongal is computed with the installed Sri Lankan holiday calendar.
    import holidays
    calendar=holidays.country_holidays('LK',years=[2022])
    for row in result['data']:
        assert row['assumed_features']['is_holiday']==float(row['timestamp'].date() in calendar)
        assert row['assumed_features']['temperature']==27.
        assert row['assumed_features']['precipitation']==2.
        assert row['assumed_features']['solar_mw']==100.
    assert 'not a meteorological forecast' in ' '.join(result['assumptions'])


def test_missing_recent_weather_is_explicit(client):
    service=client.app.state.service
    service.data.loc[:,'temperature']=np.nan
    with pytest.raises(ValueError,match='no valid observations'):
        forecast(service)
