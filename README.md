# Kukule Ganga - Hydropower Generation & Reservoir Release Optimisation (Component 3)

LP + rolling-horizon LP + DQN + residual hybrid LP-DQN + policy adaptation, evaluated on one simulator, for the Kukule Ganga
70 MW run-of-river station (1.67 MCM active pondage).

**Study dataset:** simulation-based (CEB station specifications + a rainfall-runoff model driven by Ratnapura rainfall; demand, forecasts and
irrigation are modelled). It is not observed CEB telemetry. The pipeline reads observed data through the same files whenever it becomes available.

Results and conclusions: [docs/FINAL_RESULTS_REPORT_V2.md](docs/FINAL_RESULTS_REPORT_V2.md) (multi-seed robustness in section 10).

## Folder structure
```
Kukule_Ganga Demo/
├── README.md                  this file
├── requirements.txt           Python dependencies
├── configs/                   scenarios_config.json  (station data, operating rules, reward weights, irrigation schedule)
├── src/component3/            all Python modules (see table below) + paths.py (central file locations)
├── grafana/                   Grafana dashboards (generator, provisioning templates, README with the demo script)
├── scripts/                   start_dashboard.ps1 / stop_dashboard.ps1 (API + Grafana in Docker), setup_grafana.ps1 (native download - blocked by Smart App Control, unused)
├── tests/                     test_v2_suite.py (22), test_api.py (10), test_dashboards.py (4)
├── data/
│   ├── live_inputs/           inbox for the daily mode (forecast CSVs + state.json)
│   ├── station_dataset/       modelled 5-year daily station dataset (rainfall, inflow, level, generation)
│   ├── demand/                Ratnapura demand series, event-aware v2 series + weights, 15-day demand forecast
│   └── scenario_bank/         train_bank.pkl (300), val_bank.pkl (40), stress_suite.pkl (9 named cases)
├── data_pipelines/
│   └── rainfall_forecast/     rainfall / inflow-forecast / generation-history pipelines and their outputs (self-contained)
├── models/                    dqn_selected.zip, hybrid_selected.zip  (deployable checkpoints) + MODEL_CARD.md
├── outputs/
│   ├── training_runs/         every training run (checkpoints, monitor, train_config.json)
│   ├── evaluation_v2/         unified evaluations (final/ = reported results)
│   ├── adaptation/            policy-adaptation experiments
│   ├── multiseed/             multi-seed robustness analysis and significance tests
│   ├── run_component3/        one-shot forecast-driven schedule, recommendation, HTML status report
│   ├── live/                  daily mode: latest/ plan, history/ of every plan, decision_log.csv, status.json
│   ├── tuning/                rolling-LP parameter tuning record
│   ├── logs/                  training / experiment logs
│   └── selected_models.json   which checkpoints were selected and why
├── docs/                      final results report, hand-off notes, open engineering questions, reorganisation map
└── legacy_v1/                 frozen v1 snapshot (single-year LP / DQN work, audits, v1 datasets) + archive of removed duplicates
```

## Source modules (`src/component3/`)
| File | Purpose |
|---|---|
| `paths.py` | single source of truth for every file location |
| `hydro_core.py` | parameters, storage-elevation curve, generation, authoritative daily step (floor, reserve, mandatory release, spill split) |
| `demand_events.py` | festival calendar (Vesak, Poson, Christmas/year-end, Deepavali, Avurudu) and demand weights |
| `scenario_generator.py` | weather generator + regimes (El Nino drought, La Nina, floods, monsoon shift, outages), simulated forecasts, scenario banks |
| `sim_core.py` | simulator, metrics, reference rule policies |
| `rolling_lp.py` | LP solver, rolling-horizon LP (forecast-driven, online bias correction), perfect-foresight LP (upper bound) |
| `rl_common.py`, `kukule_env_v2.py` | 23-feature state, reward, Gymnasium environment |
| `hybrid_policy.py` | residual hybrid: the DQN adjusts the LP release by -30..+30% of turbine capacity |
| `train_dqn_v2.py`, `select_model.py`, `finalize_models.py`, `dqn_policy.py`, `torch_compat.py` | training, held-out checkpoint selection, publishing to `models/`, loading |
| `policy_adaptation.py` | online fine-tuning with a safety guard |
| `evaluate_all.py`, `multiseed_eval.py`, `make_final_report.py` | evaluation, multi-seed statistics, report generation |
| `run_component3.py` | one-shot: forecast CSVs + state -> 15-day schedule CSV + recommendation JSON + HTML status report (`run_plan()` is reused by the daily mode) |
| `api_server.py`, `build_dashboard_data.py` | local JSON API + precomputed tables that feed the Grafana dashboards |
| `daily_runner.py` | daily / continuous mode: watches `data/live_inputs/`, validates, re-plans when inputs change, logs every decision |

## Operating rules (identical for every method; confirmed project parameters)
| Rule | Value |
|---|---|
| Hard floor | 204.00 masl (= MOL, `operational_v2` in `configs/scenarios_config.json`) |
| Operating reserve | 20% of active storage, enforced for turbine release (only the mandatory weir release may dip below it) |
| Year-end target | 50% of active storage (soft; penalised in reward / LP; reported as `terminal_target_met`) |
| Mandatory weir release | environmental 2 m3/s + irrigation schedule (`operations_v2`) - served first, never counted as spill |
| Spill | water over the weir when the pond is full; reported total, *avoidable* (turbines below capacity) and as energy equivalent |
| Demand | daily demand weight multiplies the energy value in the LP objective, DQN reward and metrics |

## Quick start (run from the project root; scripts can be started from any directory)
```bash
pip install -r requirements.txt
python tests/test_v2_suite.py                                         # 18 tests
python src/component3/demand_events.py                                # event-aware demand + weights
python src/component3/scenario_generator.py                           # scenario banks + stress suite (rebuilds data/scenario_bank/)
python src/component3/train_dqn_v2.py --timesteps 800000 --tag a --seed 2
python src/component3/train_dqn_v2.py --hybrid --timesteps 400000 --tag h3 --seed 3 --lr 2e-4 --expl-frac 0.15 --gamma 0.995 --shaping-beta 1.0
python src/component3/select_model.py dqn ; python src/component3/select_model.py hybrid
python src/component3/finalize_models.py                              # copy selected checkpoints to models/
python src/component3/evaluate_all.py --dqn models/dqn_selected.zip --hybrid models/hybrid_selected.zip --forecast-seeds 3
python src/component3/multiseed_eval.py                               # multi-seed statistics
python src/component3/policy_adaptation.py --kind hybrid --model models/hybrid_selected.zip --scenario shift_year --guard-tol 6
python src/component3/run_component3.py --hybrid models/hybrid_selected.zip   # uses the 15-day inflow + demand forecasts in data/
python src/component3/make_final_report.py                            # regenerate docs/FINAL_RESULTS_REPORT_V2.md
```

## Grafana dashboards (visual demo with live inputs)
```powershell
scripts\start_dashboard.ps1          # API + Grafana (Docker) + browser;  -WithDailyRunner  also watches data\live_inputs
scripts\stop_dashboard.ps1
```
Open http://localhost:3000. Three linked dashboards: **1 Live plan & what-if** (type starting storage, wet/dry inflow, demand, units, method - every panel re-runs the model),
**2 Results & robustness** (scoreboard, scenario heat-map, multi-seed statistics, adaptation, training curves, safety audit), **3 Scenario explorer** (year-long drought / flood / Vesak / Christmas curves per method).
Details, demo script and maintenance: [grafana/README.md](grafana/README.md). Grafana runs in Docker because Windows Smart App Control blocks the unsigned native `grafana.exe`.

## Daily / continuous mode
```bash
python src/component3/daily_runner.py --init-demo             # write example inputs into data/live_inputs/
python src/component3/daily_runner.py --once                  # check the inbox once; re-plans only if the inputs changed (--force to re-plan anyway)
python src/component3/daily_runner.py --watch --interval 60   # keep running, check every 60 s (Ctrl+C to stop)
python src/component3/daily_runner.py --demo-days 5           # demo: 5 consecutive days, forecasts roll forward, storage carried over (separate demo folders)
```
- **Inputs** (see `data/live_inputs/README.md`): `inflow_forecast.csv`, `demand_forecast.csv`, `state.json` (measured level/storage), optional `solar_surplus.csv`.
- **What it does each check:** waits until the files stop changing -> skips if nothing changed -> validates (columns, consecutive dates, no negative/missing values, storage or level inside physical limits,
  state date within 3 days of the first forecast day) -> plans with the hybrid (rolling LP if no model) -> publishes to `outputs/live/latest/` -> copies the plan and its exact inputs to `outputs/live/history/<timestamp>/` -> appends a row to `outputs/live/decision_log.csv`.
- **Bad inputs are rejected, not used:** the reason is logged (`decision_log.csv`, `status.json`), the previous good plan stays in `latest/`, and the process keeps running.
- **Always provide the measured state:** each plan starts from `state.json`; the previous plan's predicted storage is never carried over automatically (only the `--demo-days` demo does that).
- Run it permanently with Windows Task Scheduler (daily `--once`) or leave `--watch` running. Outputs are decision support, not control signals.
- `outputs/live_demo/` and `data/live_inputs_demo/` are only demo products and can be deleted.

## Input contract for `run_component3.py`
- Inflow forecast CSV (Component 1): `date, inflow_median_m3s, inflow_p90_m3s` (or `*_m3` volumes).
- Demand forecast CSV (Component 2): `date, forecast_energy_consumption` (MWh/day).
- Optional solar surplus CSV (Component 4): `date, solar_surplus_mwh` - logged; only affects the plan if `--solar-discount > 0` (unvalidated heuristic, default off).
- State JSON: `{"date": "...", "pond_level_masl": 205.4}` or `{"storage_m3": ...}`, optional `"units_available": [...]`.

## Using observed data later (optional)
Replace the files in `data/station_dataset/` (and the demand / rainfall inputs), refit the weather generator (`scenario_generator.Generators`), rebuild the
banks, retrain, re-evaluate (commands above). Confirm rated discharge (47.5 vs 48.0 m3/s) with the station (`docs/unresolved_engineering_questions.md`).

## Known limitations
Modelled (not observed) dataset; operating cost not computed (no tariff data); the pond holds about 0.4 day of full-load flow so energy gains over a good
operating rule are small; daily time step (no intraday peaking); hybrid weaker than the LP in extreme regime shifts; adaptation shown on one regime-shift
scenario only; old v1 run logs inside `legacy_v1/` contain historical absolute `G:\SLIIT\...` paths.

## Legacy
`legacy_v1/` is a frozen snapshot of the earlier single-year LP / DQN work (its own README inside). It is self-contained and kept for reproducibility of the v1 results.
`legacy_v1/archive_removed_duplicates/` holds duplicate or stale files removed earlier (see its MANIFEST.md); nothing was deleted.
Full old -> new location map: [docs/REORGANIZATION_MAP.md](docs/REORGANIZATION_MAP.md).
