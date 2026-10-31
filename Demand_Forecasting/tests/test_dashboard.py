import pytest

def test_dashboard_sampling_does_not_change_metrics(client):
    result=client.get('/dashboard/series',params={'max_points':100}).json()
    full=client.get('/dashboard/series',params={'max_points':1000}).json()
    assert result['observations']==288 and result['displayed_points']==100
    assert result['summary']==full['summary']
    assert result['data'][0]['timestamp']==full['data'][0]['timestamp']
    assert result['data'][-1]['timestamp']==full['data'][-1]['timestamp']
    metric=client.get('/metrics').json()['data'][0]
    assert result['summary']['adapted']['mape']==pytest.approx(metric['adapted_mape'])

def test_dashboard_date_filter_empty_and_validation(client):
    body=client.get('/dashboard/series',params={'start_date':'2022-01-02','end_date':'2022-01-02'}).json()
    assert body['observations']==96
    assert all(row['timestamp'].startswith('2022-01-02') for row in body['data'])
    empty=client.get('/dashboard/series',params={'regimes':'crisis'}).json()
    assert empty['data']==[] and empty['summary']['adapted']['mape'] is None
    assert client.get('/dashboard/series',params={'max_points':10}).status_code==422

def test_browser_evaluation_aliases_preserve_research_results(client):
    assert client.get('/evaluation/regimes').json()==client.get('/metrics').json()
    assert client.get('/evaluation/recovery').json()==client.get('/metrics/adaptation-lag').json()
