"""Synthetic fixtures are isolated test data, never production replacements."""
import json
import joblib
import pandas as pd
import numpy as np
import pytest
from fastapi.testclient import TestClient
from src.config import Settings
from src.data_loader import digest
from src.prepare import source_signature, FLAGS
from drift_project.src.baseline import train_baseline
from backend import create_app

@pytest.fixture
def setup(tmp_path):
    dates=pd.date_range('2021-12-29',periods=6*96,freq='15min')
    frame=pd.DataFrame({'date':dates,'total_generation_mw':1000+100*np.sin(np.arange(len(dates))/10),
                        'temperature_2m_mean':27.,'precipitation_sum':2.,'solar_generation_mw':100.,'is_holiday':0})
    dataset=tmp_path/'test_only.csv'; frame.to_csv(dataset,index=False)
    artifacts=tmp_path/'models'; artifacts.mkdir()
    drifts=artifacts/'classified_drift_points.csv'
    pd.DataFrame([{'date':'2022-01-03','label':'gradual'}, {'date':'2022-01-01','label':'abrupt'}]).to_csv(drifts,index=False)
    train=frame[frame.date<'2022-01-01']
    model,names=train_baseline(train,**FLAGS)
    test=frame[frame.date>='2022-01-01']
    from drift_project.src.baseline import predict
    values=predict(model,test,**FLAGS)
    pd.DataFrame({'timestamp':test.date,'static':values,'adapted':values}).to_csv(artifacts/'predictions.csv',index=False)
    entry=dict(model=model,flags=FLAGS,means={'temperature_2m_mean':27.,'precipitation_sum':2.},strategy='Static Baseline')
    joblib.dump({'static':entry,'adapted':[]},artifacts/'bundle.joblib')
    manifest=dict(dataset_sha256=digest(dataset),column_map={},source_sha256=source_signature(),
        protocol='delayed-classification-v1',artifact_sha256={n:digest(artifacts/n) for n in ['predictions.csv','bundle.joblib']},
        drifts_sha256=digest(drifts),assumptions=[],test_start=str(test.date.min()),test_end=str(test.date.max()),
        train_start=str(train.date.min()),train_end=str(train.date.max()))
    (artifacts/'manifest.json').write_text(json.dumps(manifest))
    return Settings(dataset=dataset,drifts=drifts,artifacts=artifacts),frame

@pytest.fixture
def client(setup):
    with TestClient(create_app(setup[0])) as client:
        yield client
