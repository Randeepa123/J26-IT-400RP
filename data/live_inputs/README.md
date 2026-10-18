# live_inputs/ - inbox for the daily mode
Drop the day's files here; `python src/component3/daily_runner.py --watch` (or `--once`) picks them up.

| File | Required | Columns / content |
|---|---|---|
| `inflow_forecast.csv` | yes | `date, inflow_median_m3s, inflow_p90_m3s` (consecutive daily rows; or `inflow_median_m3, inflow_p90_m3` in m3/day) - from Component 1 |
| `demand_forecast.csv` | yes | `date, forecast_energy_consumption` (MWh/day) - from Component 2 |
| `state.json` | yes | `{"date": "YYYY-MM-DD", "pond_level_masl": 205.4}` or `{"storage_m3": 1100000}`; optional `"units_available": [2, 2, 1, ...]` - measured at the station |
| `solar_surplus.csv` | no | `date, solar_surplus_mwh` - from Component 4 (logged; changes the plan only if enabled) |

Results appear in `outputs/live/` (`latest/`, `history/<timestamp>/`, `decision_log.csv`, `status.json`).
Create example files with `python src/component3/daily_runner.py --init-demo`. Always supply the MEASURED `state.json` - the plan starts from it.
