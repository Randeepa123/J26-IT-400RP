# Live synthetic drift demo

This is an isolated demonstration with real Ridge model fits and real ADWIN
drift detection. It does not update the historical research model or claim a
live PUCSL connection. Synthetic inputs and immediate synthetic ground truth
arrive every three seconds. The source, Prometheus scrape, and Grafana refresh
each run at three-second intervals, so display latency can span two cycles.

## Start Grafana, Prometheus, and the stream

Install/start Docker Desktop with Linux containers, then from repository root:

```powershell
docker compose -f monitoring/compose.yaml up --build -d
```

Open <http://localhost:3000/d/grid-live-drift>. Anonymous access has Viewer
permissions; no login is required to present the dashboard. All exposed ports
bind to localhost. Initial image downloads/build require internet access.
This demo pins container/dependency versions independently of the existing
Python 3.15 research environment.

The **Latest input · JSON** and **Latest output · JSON** panels beneath the
summary tiles show formatted, copyable JSON and refresh every three seconds.
Input includes temperature, solar, demand, and the normalized features actually
passed to Ridge. Output includes both predictions, observed actual generation,
rolling error metrics, drift status, and model versions. Use `sample` and
`timestamp` to correlate the panels if separate requests straddle a sampling tick.
The Infinity datasource plugin (pinned to 3.11.1, compatible with this Grafana
version) is installed automatically at container startup and fetches `/io` from
the stream inside the Docker network. This startup download needs internet.
The native Logs panels have **Prettify JSON** enabled; expand a record to copy it.

After updating an existing stack, rebuild the stream and recreate Grafana:

```powershell
docker compose -f monitoring/compose.yaml up --build -d
```

- Grafana: <http://localhost:3000/d/grid-live-drift>
- Prometheus: <http://localhost:9090/targets>
- Latest inputs, outputs and exact detection/training events: <http://localhost:8010/state>
- Paired JSON input/output records used by Grafana: <http://localhost:8010/io>
- Latest 600 samples as JSON: <http://localhost:8010/samples>
- Prometheus exposition: <http://localhost:8010/metrics>
- Producer health: <http://localhost:8010/health>

## Presentation sequence

1. The baseline starts already trained on 240 synthetic observations. Both
   models initially predict accurately; the frozen model never retrains.
2. At sample 41 (~120 seconds), the generator changes the relationship between
   inputs and actual generation. Both models' errors rise. This repeats every
   160 samples (~8 minutes), cycling through abrupt, gradual, incremental,
   and structural drift. The injected type is generator truth; ADWIN detects
   changes in error and does not infer these type labels.
3. ADWIN sees increased **observed pre-update prediction error** and detects
   drift. Timing is determined by the detector; no scheduled detection signal
   is fabricated and the detector never reads the injected regime flag.
4. After 24 further labeled observations (~72 seconds), Ridge really fits on
   the trailing 48 observations. The model version and completed-fit count
   increase; exact measured fitting duration is displayed.
5. Another fit 24 observations later completes the recovery policy, using a
   cleaner window of the new regime. The detector is reset and warmed with
   residuals of the new model. Adaptive MAPE/RMSE should fall while the frozen
   baseline remains inaccurate in the changed regime.

Metrics use the last 20 pre-update predictions, so they settle gradually after
activation. On a fitting tick, the current prediction still belongs to the
previous model version; the newly trained version serves the **next** sample.
Ridge fitting takes milliseconds: the state chart shows waiting/recovery,
not a fabricated long-running training state. The model is refit in full on a
sliding window, rather than updated with `partial_fit`. ADWIN operates on
clipped absolute error / 1000 and this demo only acts on increased-error
changes (mean error >0.08). This is a demonstration policy, not the research
app's drift classification or 30-day delayed-classification protocol.

## Drift patterns and unusual data

The default mixed scenario repeats this schedule (times relative to stream start):

| Start | Injected pattern | Generated change |
|---|---|---|
| 2 minutes | Abrupt | Generation relationship jumps by +650 MW |
| 10 minutes | Gradual | Probability of switching from +650 to -450 MW increases over 64 samples |
| 18 minutes | Incremental | Generation offset ramps from -450 to +450 MW over 120 samples |
| 26 minutes | Structural | Solar's generation coefficient changes by -900 MW per normalized unit |
| 34 minutes | Repeat | Return to abrupt, then repeat the sequence |

Within every 160-sample block, isolated unusual readings are also generated:

| Sample offset (zero based) | Unusual observation | Handling |
|---|---|---|
| 18 (~54 seconds) | Generation spike of +1800 MW | Large observed residual (>1400 MW) flags it |
| 27 (~81 seconds) | Missing temperature (`null` in raw JSON) | Use 28 C for inference; exclude from learning |
| 34 (~102 seconds) | Negative solar reading (-250 MW) | Use 0 MW for inference; exclude from learning |
| 120 (~6 minutes) | Demand index surge to 3.5 | Flag outside nominal bounds; exclude from learning |

Quality rules use actual readings and observed residuals, not the generator's
anomaly labels. All flagged samples are excluded from Ridge training and ADWIN
updates; their errors still contribute to MAPE/RMSE. Missing raw values remain
`null` in JSON and are omitted from numeric Prometheus exposition. Raw inputs,
cleaned inputs, generator truth, and quality decisions appear in the JSON
panels. Extra panels show the injected drift type, unusual-reading type,
excluded-sample count, and their timeline. Exact injection events appear in
`/state`. A large real change could also exceed the quality threshold: this is
a disclosed demonstration policy, not a general anomaly classifier.

For the original alternating abrupt experiment in Python, use
`DemoStream(scenario='abrupt', anomalies=False)`.

Replay from the beginning (historical Prometheus samples remain):

```powershell
docker compose -f monitoring/compose.yaml restart stream
```

Stop the stack (keep dashboard and metric history):

```powershell
docker compose -f monitoring/compose.yaml down
```

## Run just the stream without Docker

```powershell
.venv/Scripts/python.exe -m uvicorn src.live_demo:app --host 127.0.0.1 --port 8010
```

This exposes the JSON/metrics endpoints above; it does not start Grafana.
The default Compose stack runs its own stream, so stop the local stream before
launching Compose to avoid a port conflict. Use one Uvicorn worker: each worker
would create its own independent demo state. Restarting resets in-memory models,
events, and RNG seed; Prometheus retains historical scraped metrics for two days.

Dashboard regeneration and model-loop checks:

```powershell
.venv/Scripts/python.exe monitoring/build_dashboard.py
.venv/Scripts/python.exe -m pytest tests/test_live_demo.py -q
```

With the stack running, verify both JSON panels through Grafana's actual
datasource query API:

```powershell
.venv/Scripts/python.exe monitoring/verify_json_panels.py
```

JSON display uses Infinity's [Logs output](https://grafana.com/docs/plugins/yesoreyeram-infinity-datasource/latest/advanced-features/logs/)
and the native Logs panel's [Prettify JSON option](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/visualizations/logs/).

The dashboard and datasource are provisioned automatically using Grafana's
[file provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/).
Three-second refresh is allowed explicitly through
[`min_refresh_interval`](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/).
Prometheus uses a two-second timeout below its
[three-second scrape interval](https://prometheus.io/docs/prometheus/latest/configuration/configuration/).
