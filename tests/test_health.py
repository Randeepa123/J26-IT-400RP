from fastapi.testclient import TestClient
from backend import create_app
from src.data_loader import load_data
import pytest

def test_health(client):
    body=client.get('/health').json()
    assert body['ready'] and body['observations']==576

def test_missing_dataset(setup):
    settings,_=setup
    settings.dataset=settings.dataset.parent/'missing.csv'
    with TestClient(create_app(settings)) as c:
        response=c.get('/health')
        assert response.status_code==503
        assert response.json()['alive'] is True
        assert 'Dataset missing' in str(response.json()['warnings'])
        assert c.get('/predict').status_code==503

def test_missing_columns(setup):
    settings,_=setup
    settings.dataset.write_text('other\n1\n')
    with pytest.raises(ValueError,match='Missing required columns'): load_data(settings)

def test_quality(setup):
    settings,frame=setup
    import pandas as pd
    extra=frame.iloc[:3].copy(); extra['date']=extra.date.astype(object)
    extra.loc[extra.index[0],'date']='bad'; extra.loc[extra.index[1],'total_generation_mw']=0
    pd.concat([frame,extra]).to_csv(settings.dataset,index=False)
    result,report=load_data(settings)
    assert result.timestamp.is_monotonic_increasing
    assert report['invalid']==1 and report['duplicated']==2

def test_artifact_tampering_not_ready(setup):
    settings,_=setup
    with (settings.artifacts/'predictions.csv').open('a') as f: f.write('\n')
    with TestClient(create_app(settings)) as c:
        assert c.get('/health').status_code==503
        assert 'Artifact changed' in str(c.get('/health').json())
