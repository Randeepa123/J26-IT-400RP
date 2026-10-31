import numpy as np
import json
from pathlib import Path
from fastapi.testclient import TestClient

from src.live_demo import DemoStream, app


def test_detects_and_retrains_from_observed_errors_and_recovers():
    stream = DemoStream(scenario='abrupt', anomalies=False)
    static_coef = stream.static.coef_.copy()
    rows = [stream.step() for _ in range(190)]
    assert all(row['detections_total'] == 0 for row in rows[:40])
    assert stream.detections >= 1
    assert stream.retrains >= 2
    assert any(event['event'] == 'drift_detected' for event in stream.events)
    detected = next(e['sequence'] for e in stream.events if e['event'] == 'drift_detected')
    first_fit = next(e['sequence'] for e in stream.events if e['event'] == 'retrained')
    assert detected >= 40
    assert first_fit == detected + 24
    assert rows[first_fit]['prediction_model_version'] < rows[first_fit]['model_version']
    assert rows[-1]['adaptive_mape_percent'] < rows[-1]['static_mape_percent'] / 5
    np.testing.assert_array_equal(static_coef, stream.static.coef_)
    assert all(np.isfinite(value) for row in rows for value in row.values())


def test_recovers_after_repeated_changes():
    stream = DemoStream(scenario='abrupt', anomalies=False)
    for _ in range(510):
        stream.step()
    assert stream.detections >= 3
    assert stream.retrains >= 6
    assert stream.latest['adaptive_mape_percent'] < 3


def test_api_and_prometheus_contract():
    with TestClient(app) as client:
        # Explicit step makes this independent of background task scheduling.
        client.app.state.stream.step()
        assert client.get('/health').status_code == 200
        state = client.get('/state').json()
        assert state['synthetic'] is True
        assert state['interval_seconds'] == 3
        metrics = client.get('/metrics')
        assert metrics.status_code == 200
        assert '# TYPE grid_demo_retrains_total counter' in metrics.text
        assert 'grid_demo_adaptive_prediction_mw ' in metrics.text
        assert len(client.get('/samples').json()['data']) > 0


def test_dashboard_queries_match_exported_metrics():
    dashboard = json.loads((Path(__file__).parents[1] /
                           'monitoring/grafana/dashboards/live-drift.json').read_text())
    stream = DemoStream()
    stream.step()
    exported = {line.split()[0] for line in stream.prometheus().splitlines()
                if line and not line.startswith('#')}
    assert dashboard['refresh'] == '3s'
    for panel in dashboard['panels']:
        for target in panel.get('targets', []):
            expr = target.get('expr', '')
            if expr.startswith('grid_demo_'):
                assert expr in exported


def test_json_panels_receive_a_matched_input_output_pair():
    stream = DemoStream()
    assert stream.io_payload() == []
    for _ in range(85):
        stream.step()
    row = stream.io_payload()[0]
    inputs, outputs = json.loads(row['input_json']), json.loads(row['output_json'])
    assert inputs['sample'] == outputs['sample'] == stream.latest['sample']
    assert inputs['timestamp'] == outputs['timestamp'] == row['timestamp']
    assert inputs['synthetic'] is outputs['synthetic'] is True
    assert 'observed_actual_mw' not in inputs
    assert inputs['model_features']['solar_scaled'] == inputs['inputs']['solar_mw']/550
    assert outputs['predictions']['adaptive_mw'] == stream.latest['adaptive_prediction_mw']
    assert outputs['adaptation']['active_model_version'] >= 2
    with TestClient(app) as client:
        client.app.state.stream.step()
        response = client.get('/io')
        assert response.headers['cache-control'] == 'no-store'
        pair = response.json()[0]
        assert json.loads(pair['input_json'])['sample'] == json.loads(pair['output_json'])['sample']


def test_mixed_scenarios_and_anomalies_are_generated_and_observable():
    stream = DemoStream()
    rows = [stream.step() for _ in range(680)]
    assert {r['injected_drift_type'] for r in rows} == {0, 1, 2, 3, 4}
    assert {r['injected_anomaly_type'] for r in rows} == {0, 1, 2, 3, 4}
    assert stream.detections >= 1
    assert stream.retrains >= 2
    assert stream.anomalies_total >= 16
    assert stream.excluded_total >= stream.anomalies_total
    assert all(np.isfinite(v) for row in rows for v in row.values() if v is not None)
    assert any(row['injected_solar_coefficient_change'] < 0 for row in rows)
    for row in rows:
        if row['injected_anomaly_type'] == 2:
            assert row['raw_temperature_c'] is None
            assert row['temperature_c'] == 28
            assert row['quality_flag'] == 1
        if row['injected_anomaly_type'] == 3:
            assert row['raw_solar_mw'] < 0
            assert row['solar_mw'] == 0
            assert row['quality_flag'] == 1


def test_bad_readings_do_not_enter_training_and_json_is_valid():
    stream = DemoStream()
    for _ in range(35):
        previous = [(x.copy(), y) for x, y in stream.history]
        row = stream.step()
        if row['quality_flag']:
            for (old_x, old_y), (new_x, new_y) in zip(previous, stream.history):
                np.testing.assert_array_equal(old_x, new_x)
                assert old_y == new_y
        if row['injected_anomaly_type'] == 2:
            pair = stream.io_payload()[0]
            assert json.loads(pair['input_json'])['raw_inputs']['temperature_c'] is None
            assert json.loads(pair['output_json'])['data_quality']['excluded_from_learning']
            assert 'None' not in stream.prometheus()
