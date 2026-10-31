import pandas as pd
import pytest
from src.metrics_service import metrics,recovery
from src.config import Settings

def test_aligned_metrics():
    frame=pd.DataFrame({'timestamp':pd.date_range('2022-01-01',periods=3),'actual_generation_mw':[100,200,300],
        'static':[110,220,float('nan')],'adapted':[100,200,300],'regime':['pre_crisis']*3})
    rows=metrics(frame)
    assert rows[0]['observations']==2 and rows[0]['excluded']==1
    assert rows[0]['static_mape']==pytest.approx(10)
    assert rows[0]['static_rmse_mw']==pytest.approx(250**.5)
    assert rows[1]['status']=='unavailable' and rows[1]['adapted_mape'] is None

def test_lag_requires_sustained_recovery():
    frame=pd.DataFrame({'timestamp':pd.date_range('2022-01-01',periods=20*24,freq='h'),
                        'actual_generation_mw':1000.,'adapted':1200.})
    events=pd.DataFrame([dict(drift_date=pd.Timestamp('2022-01-01'),available_at='2022-01-01',drift_type='abrupt',strategy='Hard Reset',regime='pre_crisis')])
    assert recovery(frame,events,Settings())[0]['lag_days'] is None
    frame['adapted']=1000.
    row=recovery(frame,events,Settings())[0]
    assert row['lag_days']>=9 and row['verification_observations']>=24*3

def test_metrics_endpoint(client):
    rows=client.get('/metrics').json()['data']
    assert rows[0]['observations']==288
    assert rows[0]['static_mape']==rows[0]['adapted_mape']
