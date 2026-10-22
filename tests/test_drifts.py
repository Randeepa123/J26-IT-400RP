def test_sorted_authoritative_drifts(client):
    rows=client.get('/drifts').json()['data']
    assert rows[0]['drift_date']<rows[1]['drift_date']
    assert rows[0]['drift_type']=='abrupt'
    assert rows[0]['event_match'] is None
    assert len(client.get('/drifts',params={'drift_type':'gradual'}).json()['data'])==1

def test_lag_endpoint(client):
    rows=client.get('/metrics/adaptation-lag').json()['data']
    assert len(rows)==2
    assert all(r['lag_days'] is None for r in rows)
