# Kukule Ganga — Hydropower Generation & Reservoir Release Optimisation

**SLIIT Final Year Research Project · IT23175952 · PCJ Kumara · 4th Year Undergraduate, Faculty of Computing**

> **Component 3 of a multi-component smart hydropower management system** for the Kukule Ganga 70 MW run-of-river station (1.67 MCM active pondage, Sri Lanka).

---

## Project Overview

This repository contains the full implementation of **Component 3: Energy Optimising and Water Release System** — an intelligent decision-support engine that combines Linear Programming (LP), Deep Reinforcement Learning (DQN), and a residual Hybrid LP-DQN policy to produce daily hydropower dispatch schedules for the Kukule Ganga power station.

The system integrates seamlessly with:
- **Component 1** — Rainfall & inflow forecast pipeline (provides `inflow_forecast.csv`)
- **Component 2** — Demand forecast pipeline (provides `demand_forecast.csv`)
- **Component 4** — Solar surplus integration (optional `solar_surplus.csv`)

**Study dataset:** Simulation-based (CEB station specifications + a rainfall-runoff model driven by Ratnapura rainfall; demand, forecasts, and irrigation are modelled). This is not observed CEB telemetry. The pipeline reads observed data through the same files whenever it becomes available.

Full results and conclusions → [docs/FINAL_RESULTS_REPORT_V2.md](docs/FINAL_RESULTS_REPORT_V2.md) (multi-seed robustness in section 10).

---

## Key Features

- **Multi-method dispatch engine** — Rolling-Horizon LP, DQN, Residual Hybrid LP-DQN, reference rule, and perfect-foresight (upper bound) LP
- **Deep Q-Network (DQN)** trained over 800,000 timesteps with 300 synthetic scenario years
- **Hybrid LP-DQN** — DQN adjusts LP release by ±30% of turbine capacity; achieves best composite score (30.22) among learned policies
- **Festival-aware demand weighting** — Vesak, Poson, Christmas/year-end, Deepavali, Avurudu uplift calendars
- **Scenario stress testing** — El Niño drought, La Niña, flash floods, monsoon shifts, turbine outages, and forecast-bias scenarios
- **Policy adaptation** — Online fine-tuning with safety guard for regime shifts
- **Live Browser Dashboard** — Fully interactive HTML/JS/CSS dashboard served via a local FastAPI/Uvicorn server
- **Daily / continuous mode** — Watches `data/live_inputs/`, re-plans when inputs change, logs every decision to `outputs/live/`
- **Hard safety constraints** — 0 hard-floor breaches and 0 mass-balance violations across all methods in the full evaluation

---

## Folder Structure

```
Energy Optimizing and Water Release System/
├── README.md                    this file
├── requirements.txt             Python dependencies
├── configs/                     scenarios_config.json (station data, operating rules,
│                                reward weights, irrigation schedule)
├── src/component3/              all Python modules (see table below) + paths.py
│   └── dashboard/               Live browser dashboard (index.html, dashboard.css, dashboard.js)
├── scripts/                     start_dashboard.ps1 / stop_dashboard.ps1
├── tests/                       test_v2_suite.py (22 tests), test_api.py (10), test_dashboards.py (4)
├── data/
│   ├── live_inputs/             inbox for daily mode (forecast CSVs + state.json)
│   ├── station_dataset/         modelled 5-year daily station dataset
│   ├── demand/                  Ratnapura demand series, event-aware v2 series + weights
│   └── scenario_bank/           train_bank.pkl (300), val_bank.pkl (40), stress_suite.pkl (9 cases)
├── data_pipelines/
│   └── rainfall_forecast/       rainfall / inflow-forecast / generation-history pipelines
├── models/                      dqn_selected.zip, hybrid_selected.zip (deployable checkpoints)
│                                + MODEL_CARD.md
├── outputs/
│   ├── training_runs/           every training run (checkpoints, monitor, train_config.json)
│   ├── evaluation_v2/           unified evaluations (final/ = reported results)
│   ├── adaptation/              policy-adaptation experiments
│   ├── multiseed/               multi-seed robustness analysis and significance tests
│   ├── run_component3/          one-shot forecast-driven schedule, recommendation, HTML report
│   ├── live/                    daily mode: latest/ plan, history/, decision_log.csv, status.json
│   ├── tuning/                  rolling-LP parameter tuning record
│   └── logs/                    training / experiment logs
├── docs/                        final results report, hand-off notes, open engineering questions
└── legacy_v1/                   frozen v1 snapshot (single-year LP / DQN + audits)
```

---

## Source Modules (`src/component3/`)

| File | Purpose |
|---|---|
| `paths.py` | Single source of truth for every file location |
| `hydro_core.py` | Parameters, storage–elevation curve, generation, authoritative daily step (floor, reserve, mandatory release, spill split) |
| `demand_events.py` | Festival calendar (Vesak, Poson, Christmas/year-end, Deepavali, Avurudu) and demand weights |
| `scenario_generator.py` | Weather generator + regimes (El Niño drought, La Niña, floods, monsoon shift, outages), simulated forecasts, scenario banks |
| `sim_core.py` | Simulator, metrics, reference rule policies |
| `rolling_lp.py` | LP solver, rolling-horizon LP (forecast-driven, online bias correction), perfect-foresight LP (upper bound) |
| `rl_common.py`, `kukule_env_v2.py` | 23-feature state, reward shaping, Gymnasium environment |
| `hybrid_policy.py` | Residual hybrid: DQN adjusts LP release by −30..+30% of turbine capacity |
| `train_dqn_v2.py`, `select_model.py`, `finalize_models.py`, `dqn_policy.py`, `torch_compat.py` | Training, held-out checkpoint selection, publishing to `models/`, loading |
| `policy_adaptation.py` | Online fine-tuning with a safety guard |
| `evaluate_all.py`, `multiseed_eval.py`, `make_final_report.py` | Evaluation, multi-seed statistics, report generation |
| `run_component3.py` | One-shot: forecast CSVs + state → 15-day schedule CSV + recommendation JSON + HTML report |
| `api_server.py`, `build_dashboard_data.py` | Local JSON API + precomputed tables powering the live browser dashboard |
| `run_dashboard.py` | Starts the FastAPI/Uvicorn API server and opens the live browser dashboard |
| `daily_runner.py` | Daily / continuous mode: watches `data/live_inputs/`, re-plans when inputs change, logs every decision |

---

## Operating Rules

These rules are identical for every method and are confirmed project parameters.

| Rule | Value |
|---|---|
| Hard floor | 204.00 masl (= MOL, `operational_v2` in `configs/scenarios_config.json`) |
| Operating reserve | 20% of active storage, enforced for turbine release |
| Year-end target | 50% of active storage (soft; penalised in reward / LP) |
| Mandatory weir release | Environmental 2 m³/s + irrigation schedule — served first, never counted as spill |
| Spill | Water over the weir when pond is full; reported as total, *avoidable*, and energy equivalent |
| Demand | Daily demand weight multiplies energy value in LP objective, DQN reward, and metrics |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run test suite (22 tests)
python tests/test_v2_suite.py

# 3. Build event-aware demand series
python src/component3/demand_events.py

# 4. Generate scenario banks
python src/component3/scenario_generator.py

# 5. Train DQN
python src/component3/train_dqn_v2.py --timesteps 800000 --tag a --seed 2

# 6. Train Hybrid LP-DQN
python src/component3/train_dqn_v2.py --hybrid --timesteps 400000 --tag h3 --seed 3 \
    --lr 2e-4 --expl-frac 0.15 --gamma 0.995 --shaping-beta 1.0

# 7. Select best checkpoints
python src/component3/select_model.py dqn
python src/component3/select_model.py hybrid

# 8. Publish to models/
python src/component3/finalize_models.py

# 9. Full evaluation (9 scenarios x 3 forecast seeds)
python src/component3/evaluate_all.py \
    --dqn models/dqn_selected.zip \
    --hybrid models/hybrid_selected.zip \
    --forecast-seeds 3

# 10. Multi-seed robustness
python src/component3/multiseed_eval.py

# 11. Policy adaptation experiment
python src/component3/policy_adaptation.py \
    --kind hybrid --model models/hybrid_selected.zip \
    --scenario shift_year --guard-tol 6

# 12. One-shot forecast-driven plan
python src/component3/run_component3.py --hybrid models/hybrid_selected.zip

# 13. Regenerate final report
python src/component3/make_final_report.py
```

---

## Live Browser Dashboard

A fully interactive **native web dashboard** built as part of this project using HTML, CSS, and JavaScript — served through a local FastAPI/Uvicorn API server with no external dependencies required.

```bash
# Start the dashboard (opens automatically in your browser)
python src/component3/run_dashboard.py
```

Then open **http://localhost:8000** in your browser.

### Dashboard Views

| Tab | Description |
|---|---|
| **Live Plan & What-If** | Interactive sliders to adjust starting storage, inflow scale (0.2x–2.5x), P90 spread, demand scale, units online, and policy method. Every panel re-runs the model instantly. |
| **Results & Robustness Benchmark** | Scoreboard comparing all methods across 300 test scenarios, El Niño drought, and stress suites. Shows energy, avoidable spill, reserve breach days, hard floor breaches, and decision speed. |
| **Scenario Explorer** | Descriptions and outcomes for named stress tests: El Niño drought, flood year, festival seasons (Vesak/Poson), and single-turbine outages. |

### Dashboard Features

- **KPI Scorecards** — Today's turbine release (m³/s), generation (MWh), reservoir storage & level, 15-day plan energy, and operating safety guard (floor breach audit)
- **Live Charts (Chart.js)** — 15-day hydro discharge & inflow forecast, storage & elevation trajectory, daily generation & demand uplift, and cross-method energy comparison bar chart
- **Method Comparison Matrix** — Side-by-side benchmark of all 4 policies on the same inputs
- **15-Day Operational Schedule Table** — Day-by-day dispatch table with discharge, volume, inflow P50, generation, storage %, level, net head, demand weight, and online units
- **Auto-Poll** — Optional 10-second auto-refresh to track live inbox updates
- **Export Schedule CSV** — Download the current plan as a CSV
- **Simulate Inflow Spike** — One-click stress test shortcut
- **Runs entirely on local Python** — No external service dependencies required

> The dashboard is implemented in `src/component3/dashboard/` (`index.html`, `dashboard.css`, `dashboard.js`) and served via `api_server.py` + `run_dashboard.py`.

---

## Daily / Continuous Mode

```bash
# Write example inputs into data/live_inputs/
python src/component3/daily_runner.py --init-demo

# Check inbox once (re-plans only if inputs changed; --force to re-plan anyway)
python src/component3/daily_runner.py --once

# Keep running, check every 60 s (Ctrl+C to stop)
python src/component3/daily_runner.py --watch --interval 60

# Demo: 5 consecutive days, forecasts roll forward, storage carried over
python src/component3/daily_runner.py --demo-days 5
```

**Input files** (`data/live_inputs/`):

| File | Columns |
|---|---|
| `inflow_forecast.csv` | `date, inflow_median_m3s, inflow_p90_m3s` (or `*_m3` volumes) |
| `demand_forecast.csv` | `date, forecast_energy_consumption` (MWh/day) |
| `state.json` | `{"date": "...", "pond_level_masl": 205.4}` or `{"storage_m3": ...}` |
| `solar_surplus.csv` *(optional)* | `date, solar_surplus_mwh` |

Each cycle: waits for files to stop changing → skips if nothing changed → validates → plans with the hybrid (rolling LP if no model) → publishes to `outputs/live/latest/` → archives to `outputs/live/history/<timestamp>/` → appends to `outputs/live/decision_log.csv`.

Bad inputs are **rejected, not used** — the reason is logged and the previous valid plan remains in `latest/`.

> Run permanently with Windows Task Scheduler (`--once` daily) or leave `--watch` running. Outputs are decision support, not control signals.

---

## Evaluation Results Summary

Results are the mean across **9 scenarios × 3 forecast-noise seeds**, 365-day episodes, 50% initial storage.

| Method | Energy (GWh) | Avoidable Spill (MCM) | Reserve Breach % | Hard Floor Breaches | Composite Score |
|---|---|---|---|---|---|
| Reference (causal rule) | 165.84 | 58.46 | 5.84% | **0** | -9.71 |
| Rolling-Horizon LP | 189.57 | 4.87 | 2.49% | **0** | 27.05 |
| DQN | 190.76 | 2.13 | 4.72% | **0** | 21.07 |
| **Hybrid LP-DQN** *(selected)* | **190.49** | **2.05** | **1.79%** | **0** | **30.22** |
| Omniscient LP *(upper bound)* | 192.27 | 0.00 | 0.82% | **0** | 37.38 |

**All methods recorded zero hard-floor breaches and zero mass-balance violations** across all runs.

- Year-end target met (%): Rolling LP 44%, **Hybrid 52%**, Omniscient LP 100%
- El Niño drought composite: Hybrid (−121.9) significantly outperforms plain DQN (−194.2) and Reference (−245.1)

Full detailed results → [docs/FINAL_RESULTS_REPORT_V2.md](docs/FINAL_RESULTS_REPORT_V2.md)

---

## Input Contract for `run_component3.py`

| Input | Source | Format |
|---|---|---|
| Inflow forecast CSV | Component 1 | `date, inflow_median_m3s, inflow_p90_m3s` |
| Demand forecast CSV | Component 2 | `date, forecast_energy_consumption` (MWh/day) |
| Solar surplus CSV *(optional)* | Component 4 | `date, solar_surplus_mwh` |
| State JSON | Measured | `{"date": "...", "pond_level_masl": 205.4}` |

---

## Dependencies

```
numpy>=1.24.0
pandas>=2.0.0
scipy>=1.10.0
matplotlib>=3.7.0
seaborn>=0.12.0
scikit-learn>=1.3.0
statsmodels>=0.14.0
gymnasium>=1.0.0
stable-baselines3>=2.3.0
torch>=2.2.0          # CPU build: pip install torch --index-url https://download.pytorch.org/whl/cpu
fastapi / uvicorn     # for local API server + dashboard
```

Install all at once:
```bash
pip install -r requirements.txt
```

---

## Known Limitations

- Modelled (not observed) dataset — conclusions describe performance on a simulated system
- Operating cost not computed (no reliable CEB tariff data available)
- The pond holds ~0.4 day of full-load flow, so energy gains over a good rule are inherently small
- Daily time step — no intraday peaking or sub-daily dispatch
- Hybrid policy is weaker than LP in extreme, unseen regime shifts
- Policy adaptation demonstrated on one regime-shift scenario only
- Legacy v1 run logs inside `legacy_v1/` contain historical absolute `G:\SLIIT\...` paths

---

## Legacy

`legacy_v1/` is a frozen snapshot of the earlier single-year LP / DQN work (its own README inside). It is self-contained and kept for reproducibility of v1 results.
`legacy_v1/archive_removed_duplicates/` holds duplicate or stale files removed during the v2 reorganisation (see its `MANIFEST.md`); nothing was deleted.

Full old → new location map: [docs/REORGANIZATION_MAP.md](docs/REORGANIZATION_MAP.md)

---

## Using Observed Data Later (Optional)

Replace the files in `data/station_dataset/` (and demand / rainfall inputs), refit the weather generator (`scenario_generator.Generators`), rebuild the scenario banks, retrain, and re-evaluate using the commands in the Quick Start section. Confirm rated discharge (47.5 vs 48.0 m³/s) with the station before retraining — see [docs/unresolved_engineering_questions.md](docs/unresolved_engineering_questions.md).

---

## Author

| Field | Detail |
|---|---|
| **Name** | PCJ Kumara |
| **Student ID** | IT23175952 |
| **Programme** | BSc (Hons) in Information Technology |
| **Year** | 4th Year Undergraduate |
| **Institution** | Sri Lanka Institute of Information Technology (SLIIT) |
| **Research Module** | IT4010 — Research Project |

---

*Kukule Ganga Hydropower Generation & Reservoir Release Optimisation · Component 3 · Decision support system — outputs are advisory, not control signals.*
