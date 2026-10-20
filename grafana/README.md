# Grafana dashboards - Kukule Ganga (Component 3)

Three linked dashboards show the project visually. **Type values into the top bar and the model re-runs live** (what-if), or drop files into the daily-runner inbox (live mode).
All numbers describe the modelled study dataset (not observed CEB telemetry); outputs are decision support, not control signals.

## Start / stop
```powershell
scripts\start_dashboard.ps1                    # API + Grafana (Docker) + opens the browser; add -WithDailyRunner to also watch data\live_inputs
scripts\stop_dashboard.ps1
```
- Open **http://localhost:3000** (anonymous viewer, nothing to log in). Editing login: `admin` / `kukule-demo`.
- First start takes about 1-2 minutes (Docker Desktop start, plugin install). Later starts take ~20 s. A page full of panels needs ~5-10 s to fill after a change, and the very first page load after a restart can take ~20 s: **open the dashboard a minute before you present** so it is warm.
- Presentation mode: add `&kiosk` to the URL (hides the side menu), e.g. `http://localhost:3000/d/kg-live?kiosk`. Press F11 for full screen.
- Why Docker: Windows Smart App Control blocks the unsigned native `grafana.exe`, so Grafana runs as the official Linux container (`grafana/grafana:13.2.4-slim`).
  The API stays on this PC (127.0.0.1:8765); the container reaches it through `host.docker.internal`.

## Dashboard 1 - Live plan & what-if (`/d/kg-live`)
**Inputs (top bar):** Starting storage % (type any 0-100) - Inflow vs forecast (0.3 very dry ... 2.5 very wet) - Forecast spread - Demand vs forecast - Units available (2/1/0) - Method (Hybrid LP-DQN / DQN / Rolling LP / Reference) - Source (*What-if inputs* or *Live files (inbox)*).
| Block | What it shows |
|---|---|
| Today's decision | turbine release (m3/s), generation (MWh), storage at end of day (%), pond level (masl), mandatory river release, **alert status** (OK / WATCH / ALERT) and the reason |
| Plan summary tiles | energy over 15 days, lowest storage, days below the 20% reserve, **hard-floor breaches (must be 0)** |
| 15-day plan | release vs forecast inflow - storage vs 20% reserve and 50% year-end target - daily generation with demand weight - pond level vs 204.00 floor and 206.00 full supply level |
| Method comparison | day-1 release, 15-day energy and end storage for every method on the SAME inputs, plus a safety table (floor breaches, reserve days, river shortfall) |
| 15-day schedule | the exact numbers per day |
| Live operations | daily-runner health: input validity, minutes since last plan, plans made/rejected, last recommendation, per-plan bars and the decision log (PLANNED/REJECTED with reasons) |

## Dashboard 2 - Results & robustness (`/d/kg-results`)
Headline tiles (hybrid 30.2, rolling LP 27.1, perfect-foresight bound 37.4, year-end storage, constraints met, safety violations = 0) - six bar charts with a fixed colour per method (composite score, year-end storage, avoidable spill, river shortfall days, days below reserve, decision time) -
full scoreboard - **scenario x method heat-map** (the El Nino drought separates the methods most) - multi-seed mean/spread, paired tests vs the rolling LP, one bar per trained model - policy-adaptation result and fine-tuning rounds - training curves - hard-constraint audit.

## Dashboard 3 - Scenario explorer (`/d/kg-scen`)
Pick a **scenario** (normal year, El Nino drought, flood year, flood over Vesak, dry Christmas, biased forecasts, wide forecast spread, unit outages), the **methods** to overlay and a **moving average** (none / 3 / 7 / 14 days).
Shows the year summary table, river inflow, demand weight (festival peaks), storage with the 20% reserve and 50% target lines, generation, turbine release, spill and river-release shortfall.

## Suggested 5-minute demo
1. Dashboard 1 with defaults: explain today's decision, the 15-day plan and the alert.
2. Change **Inflow vs forecast** to 0.5 (dry) and **Units available** to 1: watch release, energy and alerts change; set **Starting storage** to 20.
3. Switch **Method** between Hybrid and Reference: day-1 release and end storage differ.
4. Dashboard 2: heat-map (drought), seed bars (hybrid steady across seeds), safety audit = 0 violations.
5. Dashboard 3: choose *El Nino drought*, overlay Hybrid / Rolling LP / Reference gauge, point at the storage chart and the river-shortfall chart.
6. (Optional) `start_dashboard.ps1 -WithDailyRunner`, edit `data\live_inputs\state.json`, set **Source = Live files**: the plan follows the file; a bad value shows REJECTED in the log.

## How it works / maintenance
- `src/component3/api_server.py` serves JSON; `src/component3/build_dashboard_data.py` precomputes year-long trajectories and result tables into `outputs/dashboard_cache/` (re-run after retraining or re-evaluating, or `start_dashboard.ps1 -Rebuild`).
- `grafana/build_dashboards.py` generates the three dashboard JSON files (colours, units, thresholds in one place); Grafana reloads them automatically (provisioned from `grafana/dashboards/`).
- Tests: `python tests/test_api.py` and `python tests/test_dashboards.py` (every panel query returns data).
- Method colours: Hybrid LP-DQN green, Rolling LP blue, DQN red, Reference (causal) grey, Reference (reads gauge) amber, Perfect-foresight bound purple.
- What-if planning uses the deterministic planner (median forecast, smoothed release) so the 15-day plan is self-consistent; the hedged policies used in the evaluations are shown on dashboards 2 and 3. At extreme inputs (e.g. inflow 2.5x) the learned hybrid is outside its training range; compare it with Rolling LP via the Method switch.
- `tools/` holds a Windows Grafana download that Smart App Control blocks (about 1.4 GB); it is not used and can be deleted.
