"""Exercise every real adaptation strategy with isolated test-only observations."""
import pandas as pd
import numpy as np
import pytest
from src.config import Settings
from src.prepare import prepare
from src.data_loader import load_data
from src.prediction_service import PredictionService
import src.prepare as builder

@pytest.mark.parametrize('label',['abrupt','gradual','structural'])
def test_real_strategies_activate_only_after_evidence(tmp_path,monkeypatch,label):
    dates=pd.date_range('2021-07-01','2022-05-01',freq='h')
    df=pd.DataFrame({'date':dates,'total_generation_mw':1000+np.sin(np.arange(len(dates)))*50,
        'solar_generation_mw':np.maximum(0,100*np.sin(np.arange(len(dates))/4)),
        'temperature_2m_mean':27.,'precipitation_sum':2.,'is_holiday':0})
    path=tmp_path/'synthetic_test_only.csv'; df.to_csv(path,index=False)
    settings=Settings(dataset=path,drifts=tmp_path/'drifts.csv',artifacts=tmp_path/'artifacts')
    drift=pd.Timestamp('2022-02-01'); available=drift+pd.Timedelta(days=30)
    monkeypatch.setattr(builder,'detect_drift_points',lambda *args,**kwargs:[drift])
    monkeypatch.setattr(builder,'classify_point',lambda *args:(label,1,1.))
    monkeypatch.setattr(builder,'confirm_structural',lambda *args:(None,0.))
    prepare(settings)
    data,_=load_data(settings)
    service=PredictionService(settings,data)
    entry=service.bundle['adapted'][0]
    assert entry['available_at']==available
    assert entry['trained_through']<available
    before=service.frame[service.frame.timestamp<available]
    assert np.allclose(before.static,before.adapted)
    for stamp in [available-pd.Timedelta(hours=1),available,available+pd.Timedelta(days=1)]:
        row=service.frame[service.frame.timestamp==stamp].iloc[0]
        values={c:row[c] for c in ['solar_mw','temperature','precipitation','is_holiday']}
        simulation,_=service.infer(stamp,values,adapted=True)
        assert simulation==pytest.approx(row.adapted)
