import pandas as pd
import pytest
import requests
from src.api_client import align,rolling,call,APIError

def test_empty_and_missing_solar():
    assert align({'static':pd.DataFrame()}).empty
    frame=pd.DataFrame({'timestamp':pd.date_range('2022-01-01',periods=100,freq='h'),
        'actual_generation_mw':1000.,'predicted_generation_mw':990.,'ape_percent':1.,'regime':'pre_crisis'})
    result=align({'static':frame,'adapted':frame})
    assert len(result)==100 and 'solar_mw' not in result
    assert rolling(result,['static']).static.iloc[-1]==1

def test_connection_failure(monkeypatch):
    def fail(*args,**kwargs): raise requests.ConnectionError('offline')
    monkeypatch.setattr(requests,'get',fail)
    with pytest.raises(APIError,match='Backend unavailable'): call('http://localhost','/health')
