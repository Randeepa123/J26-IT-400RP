# PUCSL Grid Drift Adaptation System

For a **live synthetic demonstration** with inputs every three seconds, actual
ADWIN detection, Ridge retraining, and a provisioned Grafana dashboard, see
[monitoring/README.md](monitoring/README.md). This runs separately from the
historical research models.

Local research dashboard for Sri Lankan electricity generation, ADWIN drift detection and cause-matched Ridge adaptation. FastAPI loads immutable CSV/model snapshots; Streamlit uses HTTP and Plotly. No database, cloud hosting or startup training.

**Primary interface:** a React + TypeScript dashboard now lives in [frontend/](frontend/README.md), using Tailwind CSS, shadcn/ui and Apache ECharts. It connects to the same FastAPI services and model artifacts. Streamlit remains available as an alternative.

Start the API as documented below, then launch React in another terminal:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open **http://127.0.0.1:5173**. See [frontend/README.md](frontend/README.md) for responsive views, API integration, production builds and browser tests. On Linux/macOS use `npm` instead of `npm.cmd`.

Read [AUDIT.md](AUDIT.md) for repository findings, leakage issues, evaluation timing and scientific limitations. Original ML source remains in `drift_project/src`.

## Installation

Use **64-bit CPython 3.15** for this pinned dependency set. The local `python` Store alias and unregistered `py` launcher do not work; use the installed interpreter directly or fix PATH. Earlier Python releases need a separately resolved dependency set.

`requirements.lock.txt` records the resolved transitive environment; use `pip install -r requirements.lock.txt` for that complete snapshot. See [VALIDATION.md](VALIDATION.md) for executed checks and remaining platform limits.

Windows PowerShell, from repository root:

```powershell
& "$env:LOCALAPPDATA/Programs/Python/Python315/python.exe" -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv/Scripts/python.exe -m src.prepare
```

Linux/macOS with Python 3.15 installed:

```bash
python3.15 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m src.prepare
```

Preparation explicitly fits original models and detects/classifies drift using the actual dataset. It saves outputs in `models/` and can take several minutes. Re-run after dataset, feature mapping or research-source changes. Stop the API during preparation; restart afterward to load the new snapshot. Preparation overwrites its own generated files, never research input CSVs.

## Run in two terminals

Backend:

```powershell
.venv/Scripts/python.exe -m uvicorn backend:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```powershell
.venv/Scripts/python.exe -m streamlit run app.py
```

Linux/macOS: use `.venv/bin/python`. In an activated environment use `uvicorn backend:app --host 127.0.0.1 --port 8000 --reload` and `streamlit run app.py`.

Open [dashboard](http://localhost:8501), [API docs](http://127.0.0.1:8000/docs), or [readiness](http://127.0.0.1:8000/health). Processes start independently. Missing backend shows a friendly frontend message; missing/stale inputs keep the API alive but not ready (503). No fallback predictions exist.

## Configuration and data contracts

`.env.example` lists settings. Paths are relative to repository root or absolute. `DATA_PATH` defaults to the existing nested CSV; `DRIFT_PATH` and `MODEL_DIR` select generated outputs; `API_URL` configures Streamlit. `COLUMN_MAP` is JSON mapping source names to canonical names.

Required canonical columns: `timestamp,actual_generation_mw`. Optional: `temperature,precipitation,solar_mw,is_holiday,shortwave_radiation`. Existing CSV names map automatically; original extra features are retained. Invalid timestamps/targets are dropped, records stably sorted, first duplicate timestamp retained, all counts reported. Numeric infinity becomes missing. Existing <200 MW exclusion is retained. No target interpolation. Missing feature values use training-context means. Observed solar remains unchanged for the peak KPI; model input retains original clipping.

Drift CSV requires `date,label` or `drift_date,drift_type`; labels abrupt, gradual, incremental, structural, unclassified. Preparation also outputs `tau,delta,structural_reduction,available_at,regime`. Optional `historical_event,event_match,event_source,confidence,notes` metadata may be integrated through the drift service. Confirmation requires explicit match and evidence. No verified historical catalogue is bundled. Hash validation rejects modified outputs; external prediction files without established manifest provenance are not accepted.

## API contracts

Dates use local Asia/Colombo time. Date-only end dates include the entire day; full timestamps include up to that instant. Offset-bearing range parameters are rejected. Invalid dates, ranges, regimes, models and simulation features return 422. Failures use `{"error":{"code":422,"message":"..."}}`; health returns a structured readiness object even on 503.

| Route | Contract |
|---|---|
| `GET /health` | Alive/readiness, valid rows/date ranges, drift count, model configuration, quality and warnings |
| `GET /predict` | `start_date,end_date,model_type=static|adapted`, repeated `regimes`; pagination `offset,limit` (maximum 50,000); count and total |
| `GET /forecast` | `horizon_hours=24|168`, `origin=now|dataset_end` (default now); future estimates from both frozen models, assumed features and freshness warnings |
| `GET /metrics` | Paired regime results for selected dates/regimes; nulls for empty regimes |
| `GET /dashboard/series` | Full-sample error KPIs and trailing 14-day MAPE, with visual sampling only; `max_points=100..10000` |
| `GET /evaluation/regimes` | Browser-friendly alias of `/metrics`, same function and results |
| `GET /evaluation/recovery` | Browser-friendly alias of `/metrics/adaptation-lag`, same function and results |
| `GET /drifts` | Sorted events; date/regime, `drift_type`, `match_status` filters |
| `GET /regimes` | Existing experimental identifiers, exclusive date boundaries |
| `GET /simulation/features` | Required inputs, units, observed ranges and defaults |
| `POST /simulate` | `{"timestamp":"2023-01-01T12:00:00","features":{...}}`; all discovered inputs required; returns both models |
| `GET /metrics/adaptation-lag` | Sustained recovery against full evaluation history; date/regime filters select events |

The dashboard pages through and aligns predictions by timestamp. Charts render at most 6,000 samples per trace; metrics/downloads use all selected observations. Caching avoids repeated transfers. Event filters affect annotations, drift counts and event/recovery tables; evaluation observations remain selected by date and regime. The 14-day rolling MAPE chart requires 96 observations, starts at the selected range and may have partial initial windows. It is an aggregation window, not a forecast horizon.

## Evaluation and simulation

The expanded **Future generation forecast** section supports **Next 24 hours** and **Next 7 days**, with 96 or 672 predictions at 15-minute intervals, charts, assumed input tables and CSV downloads. It defaults to the next quarter-hour after the current Asia/Colombo time (or after the dataset end if later). The alternative dataset-end origin reproduces the horizon immediately after the last observation and explicitly warns if that period is already past. Historical date, regime and model filters do not change these forecasts; both models are always shown.

Future feature method `recent-history scenario v1` uses equal-weight daily weather means over the latest seven observed days and intraday mean solar/radiation profiles over the latest 28 days. Missing profile slots explicitly use the recent mean. Sri Lankan holiday flags are generated with the installed holiday calendar. These are transparent exogenous assumptions, **not live meteorological forecasts or future measurements**. No new external service is called. The original Ridge models produce every generation estimate; the latest model available at issuance stays fixed throughout the horizon. Future drift events and online adaptation are not predicted.

For a current 24-hour forecast, call `/forecast?horizon_hours=24`; for seven days use `/forecast?horizon_hours=168`. The response includes exact start/end/origin, data timestamp, strategy, all assumed input values and warnings. Data more than one day behind issuance produces a freshness warning; update data and explicitly prepare artifacts to incorporate newer conditions. There are no future ground-truth values, accuracy metrics or invented confidence intervals. These horizons have not yet been validated by a rolling-origin forecasting experiment, so regard outputs as model forecasts conditional on the disclosed input estimates.

APE = `abs(actual-predicted)/abs(actual)*100`; zero/invalid actual yields null. MAPE averages valid APE values; RMSE is square root of mean squared error in MW. Metrics compare identical finite paired samples and disclose exclusions. Improvement = static minus adapted MAPE in percentage points; relative improvement divides by static MAPE. Empty regimes are unavailable.

The original experiment uses future labels during adaptation. This app's **delayed-classification-v1** makes labels actionable at drift +30 days, after their evidence is available; original adaptation training windows are then entirely past. Previous state persists until activation. This changes the experiment and must not be presented as the original retrospective scores. No validation split exists.

Recovery defaults to trailing seven-day MAPE <=9.5% for three consecutive daily checks with >=24 valid observations each, following a full window after model availability. Missing days break recovery; next drift censors it. Lag ends at the final confirmation timestamp, and is null if not observed. Threshold/window/duration/coverage are environment settings. This extends the existing criterion and is explicitly a research assumption.

Simulation applies original feature transforms to the frozen model active at the scenario date. It never trains or mutates historical data. Solar only affects structural adaptation, with original clipping to [0,1000] MW. Weather here is observed daily aggregate; contemporaneous solar contributes to the target total. These are conditional estimates, not proven advance forecasts. Per-feature observed ranges do not guarantee a meaningful joint scenario.

## Tests and troubleshooting

```powershell
.venv/Scripts/python.exe -m pytest -q
```

Tests use temporary synthetic fixtures only: health/data failures, provenance, alignment, date/pagination, metrics/zero APE, drift sorting, sustained recovery, real Ridge simulation and frontend helpers. See `VALIDATION.md` for measured results and verification limits.

- **503 / stale artifacts:** inspect health warnings, run `python -m src.prepare`, restart API.
- **Missing dataset:** configure `DATA_PATH`; startup never downloads or fabricates it.
- **Wheel unavailable:** confirm 64-bit Python 3.15 and a fresh virtual environment. The Store alias is not the installed interpreter.
- **Connection refused:** start backend separately and check `API_URL`/port; refresh.
- **Empty chart:** choose test dates and a populated regime. Last valid timestamp may precede raw CSV end.
- **No confirmed events:** expected without a verified catalogue. Proximity is insufficient evidence.

Load only locally generated trusted joblib files. Collection/preprocessing scripts are retained and never run automatically. Upstream zero filling, observed daily weather and absent verified event sources limit research conclusions.
