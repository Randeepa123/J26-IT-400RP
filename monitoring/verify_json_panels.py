"""Validate live JSON through Grafana's datasource API (run with stack up)."""
import json
import time
from urllib.request import Request, urlopen

BASE = 'http://localhost:3000'


def request(path, data=None):
    req = Request(BASE + path, data=json.dumps(data).encode() if data else None,
                  headers={'Content-Type': 'application/json'})
    with urlopen(req, timeout=20) as response:
        return json.load(response)


dashboard = request('/api/dashboards/uid/grid-live-drift')['dashboard']
panels = [p for p in dashboard['panels'] if p['type'] == 'logs']
assert len(panels) == 2
now = int(time.time()*1000)
for panel in panels:
    query = dict(panel['targets'][0], intervalMs=3000, maxDataPoints=1)
    result = request('/api/ds/query', dict(queries=[query],
                     **{'from': str(now-900000), 'to': str(now)}))['results']['A']
    assert not result.get('error'), result
    frame = result['frames'][0]
    fields = frame['schema']['fields']
    body_index = next(i for i, field in enumerate(fields) if field['name'] == 'body')
    payload = json.loads(frame['data']['values'][body_index][0])
    assert payload['synthetic'] is True
    assert payload['sample'] > 0
    print(f"{panel['title']}: valid JSON, sample {payload['sample']}")
