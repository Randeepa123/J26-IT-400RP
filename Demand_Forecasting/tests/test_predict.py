import numpy as np
from src.prediction_service import ape

def test_dates_and_alignment(client,setup):
    response=client.get('/predict',params={'start_date':'2022-01-02','end_date':'2022-01-02','model_type':'static'})
    assert response.status_code==200
    data=response.json()['data']
    assert len(data)==96
    assert all(r['timestamp'].startswith('2022-01-02') for r in data)
    actual=setup[1].set_index('date').total_generation_mw
    import pandas as pd
    for row in data: assert abs(row['actual_generation_mw']-actual[pd.Timestamp(row['timestamp'])])<1e-6

def test_invalid(client):
    for params in [{'start_date':'2022-02-01','end_date':'2022-01-01'}, {'model_type':'imaginary'},
                   {'start_date':'broken'}, {'regimes':'bogus'}, {'limit':0}, {'start_date':'NaT'}]:
        assert client.get('/predict',params=params).status_code==422

def test_zero_ape():
    values=ape([0,-100,np.nan],[10,-90,10])
    assert np.isnan(values[0]) and values[1]==10 and np.isnan(values[2])

def test_pagination(client):
    first=client.get('/predict',params={'limit':2}).json()
    second=client.get('/predict',params={'limit':2,'offset':2}).json()
    assert first['total']==288 and first['data'][-1]['timestamp']<second['data'][0]['timestamp']
