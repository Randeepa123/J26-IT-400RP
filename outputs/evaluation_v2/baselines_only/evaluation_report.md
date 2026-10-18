# Component 3 v2 - Unified evaluation (SYNTHETIC scenarios)

Generated 2026-10-20 20:24. Initial storage 50% of active storage. Hard floor 204.00 masl, reserve 20%, terminal target 50%. Operating cost: N/A (no reliable tariff data).

> All inflows, demand weights, forecasts and irrigation requirements are synthetic or assumed. Results characterise performance on simulated scenarios, not observed CEB operation.

## Mean over scenarios

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 165.84 | 165.50 | 165.63 | 49.91 | 424.91 | 58.46 | 181.46 | 98.02 | 7.22 | 5.84 | 16.94 | 0.33 | 0.00 | 0.60 | 258.11 | 0.00 | -9.71 |
| reference_gauge | 191.65 | 190.87 | 191.44 | 57.57 | 364.71 | 0.00 | 155.75 | 98.11 | 6.89 | 5.81 | 16.94 | 0.33 | 0.00 | 0.53 | 237.67 | 0.00 | 17.35 |
| rolling_lp | 189.09 | 190.15 | 189.07 | 56.61 | 371.31 | 5.76 | 158.57 | 98.96 | 3.78 | 2.53 | 17.78 | 0.79 | 0.33 | 0.62 | 75.00 | 2.12 | 27.79 |
| omniscient_lp | 192.27 | 194.29 | 192.27 | 57.55 | 364.37 | 0.00 | 155.60 | 99.30 | 2.56 | 0.82 | 17.78 | 0.83 | 1.00 | 0.68 | 0.00 | 0.00 | 37.38 |


## Per scenario


### test_year_real_sim

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 178.78 | 178.38 | 178.56 | 51.18 | 393.62 | 64.70 | 168.09 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.61 | 265.00 | 0.00 | 25.00 |
| reference_gauge | 207.01 | 206.11 | 206.80 | 59.34 | 327.84 | 0.00 | 140.00 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.54 | 239.00 | 0.00 | 54.48 |
| rolling_lp | 204.85 | 205.96 | 204.80 | 58.57 | 333.93 | 5.48 | 142.60 | 100.00 | 0.00 | 0.00 | 20.00 | 0.72 | 0.00 | 0.61 | 63.00 | 2.19 | 54.00 |
| omniscient_lp | 207.86 | 209.98 | 207.86 | 59.35 | 327.58 | 0.00 | 139.89 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.68 | 0.00 | 0.00 | 58.35 |


### drought_el_nino

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 73.51 | 73.15 | 73.30 | 66.07 | 86.95 | 18.22 | 37.13 | 82.19 | 65.00 | 49.86 | 0.00 | 0.33 | 0.00 | 0.50 | 238.00 | 0.00 | -245.12 |
| reference_gauge | 82.19 | 81.55 | 81.98 | 73.91 | 66.85 | 0.00 | 28.55 | 83.01 | 62.00 | 49.59 | 0.00 | 0.33 | 0.00 | 0.38 | 245.00 | 0.00 | -232.41 |
| rolling_lp | 79.56 | 79.77 | 79.55 | 72.09 | 70.74 | 4.38 | 30.21 | 90.68 | 34.00 | 22.74 | 0.00 | 0.81 | 0.00 | 0.63 | 40.00 | 2.08 | -131.97 |
| omniscient_lp | 80.96 | 81.66 | 80.96 | 73.68 | 66.36 | 0.00 | 28.34 | 93.70 | 23.00 | 7.40 | 0.00 | 0.83 | 1.00 | 0.67 | 0.00 | 0.00 | -83.81 |


### flood_year

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 200.14 | 200.20 | 199.92 | 34.50 | 877.70 | 68.48 | 374.82 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.66 | 247.00 | 0.00 | 4.65 |
| reference_gauge | 230.38 | 229.80 | 230.17 | 39.78 | 806.94 | 0.00 | 344.60 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.59 | 217.00 | 0.00 | 34.66 |
| rolling_lp | 228.18 | 229.64 | 228.32 | 39.30 | 812.91 | 4.67 | 347.15 | 100.00 | 0.00 | 0.00 | 20.00 | 1.17 | 1.00 | 0.63 | 72.00 | 2.06 | 34.69 |
| omniscient_lp | 231.31 | 233.61 | 231.31 | 39.80 | 806.41 | 0.00 | 344.38 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.69 | 0.00 | 0.00 | 38.57 |


### vesak_flood

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 178.56 | 178.18 | 178.34 | 43.16 | 542.99 | 64.25 | 231.88 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.63 | 258.00 | 0.00 | 11.15 |
| reference_gauge | 206.68 | 205.78 | 206.46 | 50.02 | 477.48 | 0.00 | 203.91 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.55 | 234.00 | 0.00 | 39.45 |
| rolling_lp | 205.41 | 206.66 | 205.37 | 49.58 | 481.49 | 3.31 | 205.62 | 100.00 | 0.00 | 0.00 | 20.00 | 0.73 | 0.00 | 0.63 | 84.00 | 2.09 | 40.20 |
| omniscient_lp | 207.63 | 209.83 | 207.63 | 50.05 | 476.98 | 0.00 | 203.69 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.68 | 0.00 | 0.00 | 43.50 |


### dry_christmas

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 152.09 | 151.52 | 151.87 | 51.08 | 335.75 | 52.99 | 143.38 | 100.00 | 0.00 | 2.74 | 12.45 | 0.33 | 0.00 | 0.57 | 273.00 | 0.00 | 22.19 |
| reference_gauge | 175.28 | 174.43 | 175.06 | 58.96 | 281.68 | 0.00 | 120.29 | 100.00 | 0.00 | 2.74 | 12.45 | 0.33 | 0.00 | 0.49 | 252.00 | 0.00 | 45.90 |
| rolling_lp | 173.53 | 174.78 | 173.57 | 58.15 | 286.99 | 4.83 | 122.56 | 100.00 | 0.00 | 0.00 | 20.00 | 0.92 | 1.00 | 0.62 | 74.00 | 2.00 | 47.09 |
| omniscient_lp | 175.91 | 178.13 | 175.91 | 58.96 | 281.43 | 0.00 | 120.18 | 100.00 | 0.00 | 0.00 | 20.00 | 0.84 | 1.00 | 0.68 | 0.00 | 0.00 | 50.48 |


### wide_forecast_spread

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 177.31 | 177.04 | 177.10 | 50.79 | 396.81 | 65.58 | 169.46 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.62 | 261.00 | 0.00 | 23.47 |
| reference_gauge | 206.42 | 205.72 | 206.20 | 59.23 | 328.77 | 0.00 | 140.40 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.55 | 241.00 | 0.00 | 54.10 |
| rolling_lp | 206.16 | 207.15 | 206.10 | 59.07 | 329.87 | 1.10 | 140.87 | 100.00 | 0.00 | 0.00 | 20.00 | 0.71 | 0.00 | 0.59 | 135.00 | 2.38 | 55.80 |
| omniscient_lp | 207.28 | 209.48 | 207.28 | 59.20 | 328.76 | 0.00 | 140.40 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.67 | 0.00 | 0.00 | 57.85 |


### forecast_bias_high

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 179.11 | 178.82 | 178.90 | 51.29 | 392.74 | 65.58 | 167.72 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.62 | 263.00 | 0.00 | 25.54 |
| reference_gauge | 208.23 | 207.51 | 208.02 | 59.72 | 324.76 | 0.00 | 138.69 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.54 | 240.00 | 0.00 | 56.18 |
| rolling_lp | 206.31 | 207.45 | 206.21 | 59.10 | 329.70 | 3.74 | 140.80 | 100.00 | 0.00 | 0.00 | 20.00 | 0.60 | 0.00 | 0.61 | 106.00 | 2.06 | 55.68 |
| omniscient_lp | 209.12 | 211.33 | 209.12 | 59.73 | 324.50 | 0.00 | 138.58 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.68 | 0.00 | 0.00 | 60.01 |


### forecast_bias_low

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 178.82 | 178.42 | 178.60 | 51.18 | 393.62 | 64.70 | 168.09 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.61 | 264.00 | 0.00 | 25.02 |
| reference_gauge | 207.02 | 206.11 | 206.80 | 59.34 | 327.84 | 0.00 | 140.00 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.53 | 238.00 | 0.00 | 54.48 |
| rolling_lp | 199.52 | 200.56 | 199.39 | 56.95 | 347.03 | 17.15 | 148.20 | 100.00 | 0.00 | 0.00 | 20.00 | 0.52 | 0.00 | 0.61 | 34.00 | 2.12 | 46.89 |
| omniscient_lp | 207.87 | 210.00 | 207.87 | 59.35 | 327.58 | 0.00 | 139.89 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.68 | 0.00 | 0.00 | 58.36 |


### double_outage

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 174.24 | 173.83 | 174.03 | 49.89 | 404.05 | 61.65 | 172.55 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.63 | 254.00 | 0.00 | 20.74 |
| reference_gauge | 201.65 | 200.86 | 201.44 | 57.80 | 340.26 | 0.00 | 145.31 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.56 | 233.00 | 0.00 | 49.31 |
| rolling_lp | 198.27 | 199.40 | 198.31 | 56.67 | 349.10 | 7.20 | 149.08 | 100.00 | 0.00 | 0.00 | 20.00 | 0.93 | 1.00 | 0.61 | 67.00 | 2.11 | 47.74 |
| omniscient_lp | 202.47 | 204.54 | 202.47 | 57.84 | 339.75 | 0.00 | 145.09 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.67 | 0.00 | 0.00 | 53.13 |


## Hard-constraint audit (sum over all scenarios)

| method | floor_breach_days | mass_balance_violation_days |
|---|---|---|
| omniscient_lp | 0 | 0 |
| reference | 0 | 0 |
| reference_gauge | 0 | 0 |
| rolling_lp | 0 | 0 |

