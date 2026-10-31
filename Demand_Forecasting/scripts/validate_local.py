"""Live smoke checks against the running API and actual research artifacts.

Run from root: python scripts/validate_local.py
No browser or data modifications required. Backend must already be running.
"""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
import numpy as np
from src.api_client import call
from src.config import Settings
from src.data_loader import load_data
from src.prediction_service import PredictionService

base=os.getenv('API_URL','http://127.0.0.1:8000')
health=call(base,'/health')
assert health['ready']
print('Live health:',health['observations'],'observations')
for path in ['/predict','/metrics','/drifts','/regimes','/simulation/features','/metrics/adaptation-lag']:
    result=call(base,path)
    print(path,'OK',len(result['data']),'records')
for hours in [24,168]:
    result=call(base,'/forecast',{'horizon_hours':hours})
    assert len(result['data'])==hours*4
    assert pd.Timestamp(result['start'])>pd.Timestamp(result['data_as_of'])
    print('Future forecast',hours,'hours:',result['count'],'intervals')
settings=Settings()
data,_=load_data(settings)
service=PredictionService(settings,data)
for entry in service.bundle['adapted']:
    assert entry['trained_through']<entry['available_at']
    after=service.frame[service.frame.timestamp>=entry['available_at']].iloc[0]
    specs=call(base,'/simulation/features')['data']
    values={spec['name']:float(after[spec['name']]) for spec in specs}
    result=call(base,'/simulate',payload={'timestamp':after.timestamp.isoformat(),'features':values})
    assert np.isclose(result['adapted_generation_mw'],after.adapted)
print('All active adapted snapshots match historical predictions and train before activation.')

from streamlit.testing.v1 import AppTest
dashboard=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=120).run()
assert not dashboard.exception and not dashboard.error
assert len(dashboard.tabs)==5
dashboard.radio(key='forecast_horizon').set_value('Next 7 days').run()
assert not dashboard.exception and not dashboard.error
dashboard.selectbox(key='forecast_origin').set_value('Latest dataset observation').run()
assert not dashboard.exception and not dashboard.error
dashboard.selectbox(key='model').set_value('Static Baseline').run()
assert not dashboard.exception
dashboard.selectbox(key='drift_class').set_value('structural').run()
assert not dashboard.exception
dashboard.multiselect(key='regimes').set_value([]).run()
assert not dashboard.exception
assert any('at least one regime' in entry.value for entry in dashboard.info)
print('Dashboard default view, model selection, event filtering and empty-regime state: OK')
