import pytest

def payload(client):
    specs=client.get('/simulation/features').json()['data']
    return {'timestamp':'2022-01-02T12:00:00','features':{s['name']:s['default'] for s in specs}}

def test_real_model_interface(client):
    body=payload(client)
    response=client.post('/simulate',json=body)
    assert response.status_code==200
    from drift_project.src.baseline import predict
    import pandas as pd
    from src.data_loader import model_frame
    entry=client.app.state.service.bundle['static']
    row=model_frame(pd.DataFrame([{'timestamp':pd.Timestamp(body['timestamp']),**body['features']}]))
    expected=predict(entry['model'],row,**entry['flags'])[0]
    assert response.json()['static_generation_mw']==pytest.approx(expected)
    assert response.json()['difference_mw']==0

def test_validation(client):
    body=payload(client)
    body['features']['temperature']=10000
    assert client.post('/simulate',json=body).status_code==422
    body=payload(client); body['features'].pop('temperature')
    assert client.post('/simulate',json=body).status_code==422

def test_read_only(client):
    before=client.get('/predict',params={'limit':1}).json()
    client.post('/simulate',json=payload(client))
    assert before==client.get('/predict',params={'limit':1}).json()
