"""Regenerate the provisioned dashboard using only the Python standard library."""
import json
from pathlib import Path

DS = {'type': 'prometheus', 'uid': 'demo-prometheus'}
panels = []


def panel(title, queries, x, y, w=12, h=8, unit='short', kind='timeseries', description=''):
    item = dict(id=len(panels)+1, title=title, type=kind,
                gridPos=dict(x=x, y=y, w=w, h=h), datasource=DS,
                description=description, interval='3s', maxDataPoints=1800,
                targets=[dict(refId=chr(65+i), expr=expr, legendFormat=label,
                              datasource=DS, interval='3s', range=kind != 'stat',
                              instant=kind == 'stat') for i, (expr, label) in enumerate(queries)],
                fieldConfig=dict(defaults=dict(unit=unit, decimals=2,
                    color=dict(mode='palette-classic'),
                    custom=dict(drawStyle='line', lineInterpolation='linear',
                                lineWidth=2, fillOpacity=5, showPoints='always', pointSize=3)),
                    overrides=[]),
                options=dict(legend=dict(displayMode='list', placement='bottom'),
                             tooltip=dict(mode='multi', sort='none')))
    if kind == 'stat':
        item['options'] = dict(reduceOptions=dict(calcs=['lastNotNull'], fields='', values=False),
                               colorMode='value', graphMode='none', textMode='auto')
    panels.append(item)
    return item


def metric(name):
    return 'grid_demo_' + name


panels.append(dict(id=1, type='text', title='SYNTHETIC DEMO · actual ADWIN detection and Ridge fitting',
    gridPos=dict(x=0, y=0, w=24, h=4), options=dict(mode='markdown', content=(
    '**One new synthetic labeled sample every 3 seconds.** Predictions are made before the label is used. '
    'First injected relationship change: **sample 41 (~2 minutes)**; then every 160 samples (~8 minutes): '
    '**abrupt → gradual → incremental → structural**, repeating. Isolated generation spikes, missing temperature, '
    'negative solar readings and demand surges are also injected. '
    'ADWIN watches prediction error, not the injected regime flag. After detection, collect 24 new labels '
    '(72 seconds), fit Ridge on the latest 48 observations, then refit 24 labels later to complete recovery.\n\n'
    '**Separate demonstration model: no PUCSL live feed, no production-model updates, no 30-day classification protocol.** '
    'Metrics use the latest 20 pre-update predictions. Refresh/scrape: 3 seconds; display can lag by two cycles. '
    'Injection labels are generator truth; ADWIN does not classify drift types. '
    'Flagged samples are excluded from training/detection, but remain in error metrics. Restart stream to replay.'))))

for x, title, name, unit in [
    (0, 'Samples received', 'sample', 'short'),
    (4, 'ADWIN detections', 'detections_total', 'short'),
    (8, 'Completed Ridge fits', 'retrains_total', 'short'),
    (12, 'Active model version', 'model_version', 'short'),
    (16, 'Adaptive rolling MAPE', 'adaptive_mape_percent', 'percent'),
    (20, 'Age of latest sample', 'seconds_since_update', 's')]:
    panel(title, [(metric(name), title)], x, 4, 4, 4, unit, 'stat')

panel('Generation: actual vs frozen vs adaptive', [
    (metric('actual_mw'), 'Actual synthetic generation'),
    (metric('static_prediction_mw'), 'Frozen Ridge prediction'),
    (metric('adaptive_prediction_mw'), 'Adaptive Ridge prediction')], 0, 8, 16, 9, 'powerMW')
status = panel('Adaptation state', [(metric('status'), 'State')], 16, 8, 8, 9,
               description='1: waiting for labels after ADWIN detection. 2: first fit activated; collecting labels for final recovery fit. Training itself lasts milliseconds; completed fits and version record it.')
status['fieldConfig']['defaults'].update(dict(min=0, max=2, decimals=0,
    mappings=[dict(type='value', options={
        '0': dict(text='Monitoring', color='green'),
        '1': dict(text='Collecting labels', color='orange'),
        '2': dict(text='Recovery', color='blue')})]))
status['fieldConfig']['defaults']['custom'].update(dict(lineInterpolation='stepAfter', fillOpacity=25))

for x, title, names, unit in [
    (0, 'Rolling MAPE · last 20 predictions', ['static_mape_percent', 'adaptive_mape_percent'], 'percent'),
    (12, 'Rolling RMSE · last 20 predictions', ['static_rmse_mw', 'adaptive_rmse_mw'], 'powerMW')]:
    panel(title, [(metric(n), 'Frozen' if n.startswith('static') else 'Adaptive') for n in names], x, 17, unit=unit)

panel('Per-sample absolute prediction error', [
    (metric('static_absolute_error_mw'), 'Frozen error'),
    (metric('adaptive_absolute_error_mw'), 'Adaptive error')], 0, 25, unit='powerMW')
panel('Detector evidence · bounded absolute error / 1000', [
    (metric('detector_mean_error'), 'ADWIN mean error')], 12, 25,
    description='ADWIN detects distribution changes; this mean is not a probability or a classification confidence score. Recovery resets the detector on the new model residuals.')
panel('Synthetic temperature input', [(metric('temperature_c'), 'Temperature')], 0, 33, 8, 7, 'celsius')
panel('Synthetic solar input', [(metric('solar_mw'), 'Solar')], 8, 33, 8, 7, 'powerMW')
panel('Synthetic demand input', [(metric('demand_index'), 'Demand index')], 16, 33, 8, 7)
panel('Model version and injected regime', [
    (metric('model_version'), 'Active model version'),
    (metric('prediction_model_version'), 'Version used for this prediction'),
    (metric('synthetic_regime'), 'Injected regime (generator only)')], 0, 40,
    description='Regime is shown for explanation only and is never passed to the model or detector.')
panel('Training execution time', [(metric('training_ms'), 'Last completed fit')], 12, 40, unit='ms',
      description='Actual measured Ridge fitting duration; held until the next fit. No fabricated multi-second training animation.')
panel('Stream availability', [
    ('up{job="synthetic-grid"}', 'Prometheus scrape successful'),
    ('(time() - grid_demo_last_sample_timestamp_seconds) < bool 12', 'Producer fresh (<12s)')], 0, 48,
    description='Both should be 1. A missing series means the target is unavailable or has not been scraped yet.')
panel('ADWIN window and training observations', [
    (metric('detector_window_samples'), 'ADWIN observations'),
    (metric('training_window_samples'), 'Training window')], 12, 48)

# Keep existing panel IDs stable; move charts down to place JSON under KPIs.
for item in panels:
    if item['gridPos']['y'] >= 8:
        item['gridPos']['y'] += 16

JSON_DS = {'type': 'yesoreyeram-infinity-datasource', 'uid': 'demo-json'}
for x, title, field in [(0, 'Latest input · JSON', 'input_json'),
                         (12, 'Latest output · JSON', 'output_json')]:
    panels.append(dict(id=len(panels)+1, title=title, type='logs',
        gridPos=dict(x=x, y=8, w=12, h=16), datasource=JSON_DS,
        description='Latest sample fetched every 3 seconds. Match sample and timestamp across panels. Inputs include the exact normalized model features; output metrics use pre-update predictions.',
        targets=[dict(refId='A', datasource=JSON_DS, type='json', source='url',
                      url='http://stream:8010/io', url_options=dict(method='GET'),
                      parser='backend', format='logs', root_selector='',
                      columns=[dict(selector='timestamp', text='timestamp', type='timestamp'),
                               dict(selector=field, text='body', type='string')])],
        options=dict(showTime=False, showLabels=False, showCommonLabels=False,
                     wrapLogMessage=True, prettifyLogMessage=True,
                     enableLogDetails=True, dedupStrategy='none', sortOrder='Descending'),
        fieldConfig=dict(defaults={}, overrides=[])))

for item in panels:
    if item['gridPos']['y'] >= 24:
        item['gridPos']['y'] += 5

drift = panel('Injected drift type · generator truth', [(metric('injected_drift_type'), 'Injected type')],
              0, 24, 8, 5, kind='stat')
drift['fieldConfig']['defaults']['mappings'] = [dict(type='value', options={
    str(i): dict(text=label, color=color) for i, label, color in [
        (0, 'Stable', 'green'), (1, 'Abrupt', 'red'), (2, 'Gradual', 'orange'),
        (3, 'Incremental', 'yellow'), (4, 'Structural', 'purple')]})]
unusual = panel('Latest unusual reading · generator truth', [(metric('injected_anomaly_type'), 'Injected anomaly')],
                8, 24, 8, 5, kind='stat')
unusual['fieldConfig']['defaults']['mappings'] = [dict(type='value', options={
    str(i): dict(text=label) for i, label in enumerate([
        'None', 'Generation spike', 'Missing temperature', 'Negative solar', 'Demand surge'])})]
panel('Samples excluded from learning · quality checks', [(metric('learning_excluded_total'), 'Excluded samples')],
      16, 24, 8, 5, kind='stat')
panel('Unusual samples and quality flags', [
    (metric('injected_anomaly_type'), 'Injected anomaly code'),
    (metric('quality_flag'), 'Observed quality flag')], 0, 77,
    description='Anomaly codes: 1 generation spike; 2 missing temperature; 3 negative solar; 4 demand surge. Flagging uses observations, not generator labels.')
panel('Injected concept change · generator truth', [
    (metric('injected_offset_mw'), 'Generation offset'),
    (metric('injected_solar_coefficient_change'), 'Solar coefficient change')], 12, 77,
    description='Gradual drift mixes old/new concepts over 64 samples; incremental drift ramps over 120. Structural drift changes the solar relationship.', unit='powerMW')

dashboard = dict(uid='grid-live-drift', title='Grid · Synthetic Live Drift & Adaptation',
    tags=['synthetic', 'ADWIN', 'Ridge', 'live-demo'], schemaVersion=40, version=3,
    timezone='Asia/Colombo', editable=False, refresh='3s',
    time=dict(**{'from': 'now-15m', 'to': 'now'}),
    timepicker=dict(refresh_intervals=['3s', '6s', '15s', '30s', '1m']),
    annotations=dict(list=[dict(name=title, enable=True, iconColor=color,
        datasource=DS, expr=expr, step='3s', titleFormat=title,
        textFormat='Synthetic stream event; see /state for exact event records.')
        for title, color, expr in [
            ('ADWIN drift detected', 'orange', 'changes(grid_demo_detections_total[6s]) > 0'),
            ('Ridge model retrained', 'cyan', 'changes(grid_demo_retrains_total[6s]) > 0')]]),
    panels=panels)
path = Path(__file__).parent / 'grafana/dashboards/live-drift.json'
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(dashboard, indent=2) + '\n', encoding='utf-8')
print(f'Wrote {len(panels)} panels to {path}')
