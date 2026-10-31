"""Isolated synthetic stream: predict, observe, detect, then fit on past labels.

Start with: python -m uvicorn src.live_demo:app --port 8010
No production datasets or model artifacts are read or modified.
"""
import asyncio
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
import math
from threading import RLock
import time

from fastapi import FastAPI
from fastapi.responses import Response
import numpy as np
from river.drift import ADWIN
from sklearn.linear_model import Ridge

log = logging.getLogger(__name__)
INTERVAL_SECONDS = 3
DRIFT_TYPES = {0: 'stable', 1: 'abrupt', 2: 'gradual', 3: 'incremental', 4: 'structural'}
ANOMALY_TYPES = {0: 'none', 1: 'generation_spike', 2: 'missing_temperature',
                 3: 'negative_solar', 4: 'demand_surge'}


class DemoStream:
    """Deterministic synthetic data; detection never reads the regime flag.

    ADWIN monitors bounded pre-update absolute errors. A detected increase
    schedules retraining after 24 more observed labels. A second fit 24 labels
    later completes recovery as the trailing window sheds the old regime.
    """

    def __init__(self, seed=42, drift_every=160, scenario='mixed', anomalies=True):
        self.lock = RLock()
        self.rng = np.random.default_rng(seed)
        self.drift_every = drift_every
        self.scenario = scenario
        self.anomalies = anomalies
        self.anomalies_total = 0
        self.excluded_total = 0
        warm_x = np.array([self.features(i)[0] for i in range(-240, 0)])
        warm_y = np.array([self.target(x, 0) for x in warm_x])
        self.static = Ridge(alpha=1).fit(warm_x, warm_y)
        self.adaptive = Ridge(alpha=1).fit(warm_x, warm_y)
        self.history = deque(zip(warm_x[-48:], warm_y[-48:]), maxlen=48)
        self.errors = deque(maxlen=20)
        self.records = deque(maxlen=600)
        self.events = deque(maxlen=100)
        self.detector = self.new_detector()
        for x, y in zip(warm_x[-128:], warm_y[-128:]):
            self.detector.update(min(abs(y - self.adaptive.predict([x])[0]) / 1000, 1))
        self.sequence = 0
        self.version = 1
        self.detections = 0
        self.retrains = 0
        self.pending_at = None
        self.followup_at = None
        self.last_detection = None
        self.last_training_ms = 0.0
        self.latest = {}
        self.started_at = time.time()

    @staticmethod
    def new_detector():
        return ADWIN(delta=0.01, clock=1, min_window_length=8, grace_period=16)

    @staticmethod
    def features(i):
        phase = i * 2 * math.pi / 32
        temperature = 28 + 4 * math.sin(phase / 2)
        solar = max(0, 550 * math.sin(phase))
        demand = math.cos(phase)
        return np.array([(temperature - 28) / 4, solar / 550, demand]), temperature, solar

    def target(self, x, regime):
        # A recurring abrupt relationship change, independent of detector state.
        return float(1900 + 90*x[0] + 220*x[1] + 180*x[2]
                     + regime * (650 + 170*x[1]) + self.rng.normal(0, 9))

    def drift_profile(self, i):
        if i < 40:
            return 0, 0.0, 0.0
        stage, position = divmod(i-40, self.drift_every)
        if self.scenario == 'abrupt':
            regime = (stage+1) % 2
            return 1, regime*650.0, regime*170.0
        kind = stage % 4 + 1
        if kind == 1:
            return kind, 650.0, 0.0
        if kind == 2:
            # Blend old/new concepts probabilistically rather than one jump.
            probability = min(position/64, 1)
            return kind, -450.0 if self.rng.random() < probability else 650.0, 0.0
        if kind == 3:
            return kind, -450.0 + 900*min(position/120, 1), 0.0
        return kind, 450.0, -900.0

    def fit(self, reason):
        started = time.perf_counter()
        x, y = zip(*self.history)
        candidate = Ridge(alpha=1).fit(np.array(x), np.array(y))
        self.adaptive = candidate
        self.version += 1
        self.retrains += 1
        self.last_training_ms = (time.perf_counter() - started) * 1000
        self.events.append(dict(timestamp=time.time(), sequence=self.sequence,
                                event='retrained', reason=reason, version=self.version,
                                training_samples=len(y), training_ms=self.last_training_ms))

    def step(self):
        with self.lock:
            i = self.sequence
            # Generator truth is diagnostic only; it is never given to ADWIN.
            kind, offset, solar_change = self.drift_profile(i)
            regime = 0 if i < 40 else 1 + (i-40)//self.drift_every
            x, temperature, solar = self.features(i)
            raw_temperature, raw_solar = temperature, solar
            anomaly = 0
            if self.anomalies:
                anomaly = {18: 1, 27: 2, 34: 3, 120: 4}.get(i % self.drift_every, 0)
            if i == 40 or (i > 40 and (i-40) % self.drift_every == 0):
                self.events.append(dict(timestamp=time.time(), sequence=i,
                                        event='synthetic_drift_injected',
                                        injected_type=DRIFT_TYPES[kind]))
            if anomaly:
                self.events.append(dict(timestamp=time.time(), sequence=i,
                                        event='synthetic_anomaly_injected',
                                        injected_type=ANOMALY_TYPES[anomaly]))
            if anomaly == 2:
                raw_temperature = None
                temperature = 28.0  # Explicit neutral imputation, shown in JSON.
                x[0] = 0
            elif anomaly == 3:
                raw_solar = -250.0
                solar = 0.0
                x[1] = 0
            elif anomaly == 4:
                x[2] = 3.5
            version_used = self.version
            static = float(self.static.predict([x])[0])
            adaptive = float(self.adaptive.predict([x])[0])
            # Ground truth becomes available AFTER predictions; never fit first.
            actual = self.target(x, 0) + offset + solar_change*x[1]
            if anomaly == 1:
                actual += 1800.0
            static_error, adaptive_error = abs(actual-static), abs(actual-adaptive)
            # Quality checks use observed values/errors, never injection labels.
            quality_flag = (raw_temperature is None or raw_solar < 0 or abs(x[2]) > 2
                            or adaptive_error > 1400)
            if anomaly:
                self.anomalies_total += 1
            if quality_flag:
                self.excluded_total += 1
            else:
                self.history.append((x, actual))
            self.errors.append((actual, static-actual, adaptive-actual))
            if not quality_flag:
                self.detector.update(min(adaptive_error / 1000, 1))
            detected = (not quality_flag and self.detector.drift_detected and self.pending_at is None
                        and self.followup_at is None and self.detector.estimation > 0.08)
            if detected:
                self.detections += 1
                self.last_detection = i
                self.pending_at = i + 24
                self.events.append(dict(timestamp=time.time(), sequence=i,
                                        event='drift_detected', version=self.version))
            if self.pending_at is not None and i >= self.pending_at:
                self.fit('ADWIN detected increased prediction error')
                self.pending_at = None
                self.followup_at = i + 24
            elif self.followup_at is not None and i >= self.followup_at:
                self.fit('Complete scheduled recovery with 48 recent labeled samples')
                self.followup_at = None
                self.detector = self.new_detector()
                for hx, hy in self.history:
                    self.detector.update(min(abs(hy-self.adaptive.predict([hx])[0])/1000, 1))
            arr = np.array(self.errors)
            status = 1 if self.pending_at is not None else 2 if self.followup_at is not None else 0
            self.latest = dict(
                timestamp=time.time(), sample=i+1, temperature_c=temperature,
                solar_mw=solar, demand_index=float(x[2]), synthetic_regime=regime,
                raw_temperature_c=raw_temperature, raw_solar_mw=raw_solar,
                injected_drift_type=kind, injected_offset_mw=offset,
                injected_solar_coefficient_change=solar_change,
                injected_anomaly_type=anomaly, anomalies_total=self.anomalies_total,
                quality_flag=int(quality_flag), learning_excluded_total=self.excluded_total,
                actual_mw=actual, static_prediction_mw=static, adaptive_prediction_mw=adaptive,
                static_absolute_error_mw=static_error, adaptive_absolute_error_mw=adaptive_error,
                static_mape_percent=float(np.mean(abs(arr[:, 1])/arr[:, 0])*100),
                adaptive_mape_percent=float(np.mean(abs(arr[:, 2])/arr[:, 0])*100),
                static_rmse_mw=float(np.sqrt(np.mean(arr[:, 1]**2))),
                adaptive_rmse_mw=float(np.sqrt(np.mean(arr[:, 2]**2))),
                detector_mean_error=float(self.detector.estimation),
                detector_window_samples=float(self.detector.width),
                drift_detected=int(detected), detections_total=self.detections,
                retrains_total=self.retrains, model_version=self.version,
                prediction_model_version=version_used, status=status,
                training_ms=self.last_training_ms, training_window_samples=len(self.history),
                seconds_since_update=0,
            )
            self.records.append(self.latest.copy())
            self.sequence += 1
            return self.latest.copy()

    def snapshot(self):
        with self.lock:
            return dict(synthetic=True, interval_seconds=INTERVAL_SECONDS,
                        scenario=self.scenario, anomalies_enabled=self.anomalies,
                        injected_drift_labels=DRIFT_TYPES, injected_anomaly_labels=ANOMALY_TYPES,
                        status_labels={'0': 'monitoring', '1': 'collecting labels', '2': 'recovery'},
                        latest=self.latest.copy(), events=list(self.events))

    def io_payload(self):
        """One atomic input/output pair for Grafana's JSON log panels."""
        with self.lock:
            row = self.latest.copy()
        if not row:
            return []
        timestamp = datetime.fromtimestamp(row['timestamp'], timezone.utc).isoformat()
        common = dict(synthetic=True, sample=row['sample'], timestamp=timestamp)
        input_payload = dict(**common, raw_inputs=dict(
            temperature_c=row['raw_temperature_c'], solar_mw=row['raw_solar_mw'],
            demand_index=row['demand_index']), inputs=dict(
            temperature_c=row['temperature_c'], solar_mw=row['solar_mw'],
            demand_index=row['demand_index']), model_features=dict(
                temperature_scaled=(row['temperature_c']-28)/4,
                solar_scaled=row['solar_mw']/550, demand_index=row['demand_index']))
        output_payload = dict(**common,
            generator_truth=dict(drift_type=DRIFT_TYPES[row['injected_drift_type']],
                                 anomaly=ANOMALY_TYPES[row['injected_anomaly_type']],
                                 note='Injected labels; not detector classifications'),
            data_quality=dict(flagged=bool(row['quality_flag']),
                              excluded_from_learning=bool(row['quality_flag']),
                              policy='Missing temperature -> 28 C; negative solar -> 0. Flagged samples excluded from training and ADWIN; errors still scored.'),
            predictions=dict(static_mw=row['static_prediction_mw'],
                             adaptive_mw=row['adaptive_prediction_mw'],
                             prediction_model_version=row['prediction_model_version']),
            observed_actual_mw=row['actual_mw'],
            metrics=dict(window_samples=min(row['sample'], 20),
                         static_mape_percent=row['static_mape_percent'],
                         adaptive_mape_percent=row['adaptive_mape_percent'],
                         static_rmse_mw=row['static_rmse_mw'],
                         adaptive_rmse_mw=row['adaptive_rmse_mw']),
            adaptation=dict(drift_detected=bool(row['drift_detected']),
                            detections_total=row['detections_total'],
                            retrains_total=row['retrains_total'],
                            active_model_version=row['model_version'],
                            status={0: 'monitoring', 1: 'collecting labels', 2: 'recovery'}[row['status']]))
        return [dict(timestamp=timestamp,
                     input_json=json.dumps(input_payload, allow_nan=False),
                     output_json=json.dumps(output_payload, allow_nan=False))]

    def prometheus(self):
        with self.lock:
            values = self.latest.copy()
            if values:
                values['seconds_since_update'] = max(0, time.time()-values['timestamp'])
            lines = []
            for name, value in values.items():
                if value is None:
                    continue
                if name == 'timestamp':
                    name = 'last_sample_timestamp_seconds'
                metric = 'grid_demo_' + name
                kind = 'counter' if name.endswith('_total') else 'gauge'
                lines.extend([f'# HELP {metric} Synthetic demonstration {name}.',
                              f'# TYPE {metric} {kind}', f'{metric} {value}'])
            return '\n'.join(lines) + '\n'


@asynccontextmanager
async def lifespan(app):
    app.state.stream = DemoStream()
    app.state.failure = None

    async def produce():
        try:
            while True:
                started = time.monotonic()
                await asyncio.to_thread(app.state.stream.step)
                await asyncio.sleep(max(0, INTERVAL_SECONDS-(time.monotonic()-started)))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            app.state.failure = str(exc)
            log.exception('Synthetic producer stopped')

    task = asyncio.create_task(produce())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title='Synthetic live drift demonstration', lifespan=lifespan)


@app.get('/health')
def health():
    snapshot = app.state.stream.snapshot()
    last = snapshot['latest'].get('timestamp', 0)
    ok = app.state.failure is None and time.time()-last < 12
    return Response(content='ready' if ok else 'producer unavailable', status_code=200 if ok else 503)


@app.get('/state')
def state():
    return app.state.stream.snapshot()


@app.get('/samples')
def samples():
    with app.state.stream.lock:
        return dict(synthetic=True, data=list(app.state.stream.records))


@app.get('/io')
def input_output():
    return Response(json.dumps(app.state.stream.io_payload(), allow_nan=False),
                    media_type='application/json', headers={'Cache-Control': 'no-store'})


@app.get('/metrics')
def prometheus():
    return Response(app.state.stream.prometheus(), media_type='text/plain; version=0.0.4')
