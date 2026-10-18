# Component 3 v2 - Unified evaluation (SYNTHETIC scenarios)

Generated 2026-10-20 22:35. Initial storage 50% of active storage. Hard floor 204.00 masl, reserve 20%, terminal target 50%. Operating cost: N/A (no reliable tariff data).

> All inflows, demand weights, forecasts and irrigation requirements are synthetic or assumed. Results characterise performance on simulated scenarios, not observed CEB operation.

## Mean over scenarios

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 165.84 | 165.50 | 165.63 | 49.91 | 424.91 | 58.46 | 181.46 | 98.02 | 7.22 | 5.84 | 16.94 | 0.33 | 0.00 | 0.60 | 258.11 | 0.00 | -9.71 |
| reference_gauge | 191.65 | 190.87 | 191.44 | 57.57 | 364.71 | 0.00 | 155.75 | 98.11 | 6.89 | 5.81 | 16.94 | 0.33 | 0.00 | 0.53 | 237.67 | 0.00 | 17.35 |
| rolling_lp | 189.57 | 190.72 | 189.56 | 56.77 | 370.05 | 4.87 | 158.03 | 98.83 | 4.26 | 2.49 | 17.78 | 0.81 | 0.44 | 0.62 | 76.41 | 2.16 | 27.05 |
| dqn | 190.76 | 189.94 | 190.55 | 57.25 | 366.91 | 2.13 | 156.69 | 98.37 | 5.96 | 4.72 | 16.94 | 0.33 | 0.00 | 0.57 | 275.56 | 0.31 | 21.07 |
| hybrid | 190.49 | 190.43 | 190.54 | 57.15 | 367.05 | 2.05 | 156.75 | 99.00 | 3.67 | 1.79 | 17.78 | 0.95 | 0.52 | 0.61 | 156.56 | 2.93 | 30.22 |
| omniscient_lp | 192.27 | 194.29 | 192.27 | 57.55 | 364.37 | 0.00 | 155.60 | 99.30 | 2.56 | 0.82 | 17.78 | 0.83 | 1.00 | 0.68 | 0.00 | 0.00 | 37.38 |


## Per scenario


### test_year_real_sim

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 178.78 | 178.38 | 178.56 | 51.18 | 393.62 | 64.70 | 168.09 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.61 | 265.00 | 0.00 | 25.00 |
| reference_gauge | 207.01 | 206.11 | 206.80 | 59.34 | 327.84 | 0.00 | 140.00 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.54 | 239.00 | 0.00 | 54.48 |
| rolling_lp | 204.88 | 206.07 | 204.86 | 58.60 | 333.67 | 5.36 | 142.49 | 100.00 | 0.00 | 0.00 | 20.00 | 0.79 | 0.33 | 0.61 | 73.67 | 2.14 | 54.27 |
| dqn | 207.10 | 206.16 | 206.89 | 59.37 | 327.58 | 0.00 | 139.89 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.55 | 285.33 | 0.32 | 54.58 |
| hybrid | 206.17 | 206.05 | 206.21 | 59.08 | 329.68 | 1.84 | 140.79 | 100.00 | 0.00 | 0.00 | 20.00 | 0.92 | 0.67 | 0.61 | 174.67 | 2.89 | 55.38 |
| omniscient_lp | 207.86 | 209.98 | 207.86 | 59.35 | 327.58 | 0.00 | 139.89 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.68 | 0.00 | 0.00 | 58.35 |


### drought_el_nino

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 73.51 | 73.15 | 73.30 | 66.07 | 86.95 | 18.22 | 37.13 | 82.19 | 65.00 | 49.86 | 0.00 | 0.33 | 0.00 | 0.50 | 238.00 | 0.00 | -245.12 |
| reference_gauge | 82.19 | 81.55 | 81.98 | 73.91 | 66.85 | 0.00 | 28.55 | 83.01 | 62.00 | 49.59 | 0.00 | 0.33 | 0.00 | 0.38 | 245.00 | 0.00 | -232.41 |
| rolling_lp | 79.77 | 80.07 | 79.75 | 72.20 | 70.55 | 3.87 | 30.13 | 89.50 | 38.33 | 22.37 | 0.00 | 0.79 | 0.33 | 0.63 | 33.67 | 2.16 | -145.26 |
| dqn | 80.29 | 79.50 | 80.08 | 72.51 | 70.12 | 3.75 | 29.94 | 85.30 | 53.67 | 39.73 | 0.00 | 0.33 | 0.00 | 0.58 | 249.33 | 0.31 | -194.20 |
| hybrid | 79.83 | 79.62 | 79.92 | 72.58 | 69.32 | 2.78 | 29.60 | 90.96 | 33.00 | 16.07 | 0.00 | 1.05 | 0.33 | 0.61 | 84.00 | 2.90 | -121.89 |
| omniscient_lp | 80.96 | 81.66 | 80.96 | 73.68 | 66.36 | 0.00 | 28.34 | 93.70 | 23.00 | 7.40 | 0.00 | 0.83 | 1.00 | 0.67 | 0.00 | 0.00 | -83.81 |


### flood_year

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 200.14 | 200.20 | 199.92 | 34.50 | 877.70 | 68.48 | 374.82 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.66 | 247.00 | 0.00 | 4.65 |
| reference_gauge | 230.38 | 229.80 | 230.17 | 39.78 | 806.94 | 0.00 | 344.60 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.59 | 217.00 | 0.00 | 34.66 |
| rolling_lp | 228.36 | 229.87 | 228.43 | 39.34 | 812.52 | 4.83 | 346.98 | 100.00 | 0.00 | 0.00 | 20.00 | 0.99 | 1.00 | 0.63 | 73.67 | 2.17 | 34.88 |
| dqn | 226.06 | 225.34 | 225.84 | 38.98 | 817.74 | 10.23 | 349.21 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.61 | 258.67 | 0.31 | 31.81 |
| hybrid | 229.42 | 229.46 | 229.58 | 39.58 | 809.16 | 1.72 | 345.55 | 100.00 | 0.00 | 0.00 | 20.00 | 1.22 | 1.00 | 0.63 | 167.00 | 3.00 | 35.42 |
| omniscient_lp | 231.31 | 233.61 | 231.31 | 39.80 | 806.41 | 0.00 | 344.38 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.69 | 0.00 | 0.00 | 38.57 |


### vesak_flood

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 178.56 | 178.18 | 178.34 | 43.16 | 542.99 | 64.25 | 231.88 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.63 | 258.00 | 0.00 | 11.15 |
| reference_gauge | 206.68 | 205.78 | 206.46 | 50.02 | 477.48 | 0.00 | 203.91 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.55 | 234.00 | 0.00 | 39.45 |
| rolling_lp | 205.06 | 206.34 | 205.04 | 49.51 | 482.12 | 4.16 | 205.89 | 100.00 | 0.00 | 0.00 | 20.00 | 0.79 | 0.33 | 0.62 | 79.00 | 2.21 | 39.94 |
| dqn | 206.26 | 205.37 | 206.05 | 49.87 | 478.94 | 1.84 | 204.53 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.58 | 279.33 | 0.32 | 39.21 |
| hybrid | 206.38 | 206.25 | 206.36 | 49.91 | 478.28 | 0.97 | 204.25 | 100.00 | 0.00 | 0.00 | 20.00 | 0.79 | 0.33 | 0.61 | 168.33 | 3.00 | 40.82 |
| omniscient_lp | 207.63 | 209.83 | 207.63 | 50.05 | 476.98 | 0.00 | 203.69 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.68 | 0.00 | 0.00 | 43.50 |


### dry_christmas

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 152.09 | 151.52 | 151.87 | 51.08 | 335.75 | 52.99 | 143.38 | 100.00 | 0.00 | 2.74 | 12.45 | 0.33 | 0.00 | 0.57 | 273.00 | 0.00 | 22.19 |
| reference_gauge | 175.28 | 174.43 | 175.06 | 58.96 | 281.68 | 0.00 | 120.29 | 100.00 | 0.00 | 2.74 | 12.45 | 0.33 | 0.00 | 0.49 | 252.00 | 0.00 | 45.90 |
| rolling_lp | 173.41 | 174.74 | 173.42 | 58.18 | 286.82 | 4.84 | 122.48 | 100.00 | 0.00 | 0.00 | 20.00 | 0.85 | 0.67 | 0.60 | 75.00 | 2.18 | 47.00 |
| dqn | 175.19 | 174.24 | 174.97 | 58.94 | 281.80 | 0.26 | 120.34 | 100.00 | 0.00 | 2.74 | 12.45 | 0.33 | 0.00 | 0.51 | 296.33 | 0.31 | 45.76 |
| hybrid | 174.73 | 174.55 | 174.70 | 58.74 | 282.97 | 1.22 | 120.84 | 100.00 | 0.00 | 0.00 | 20.00 | 0.79 | 0.33 | 0.59 | 166.33 | 2.98 | 47.73 |
| omniscient_lp | 175.91 | 178.13 | 175.91 | 58.96 | 281.43 | 0.00 | 120.18 | 100.00 | 0.00 | 0.00 | 20.00 | 0.84 | 1.00 | 0.68 | 0.00 | 0.00 | 50.48 |


### wide_forecast_spread

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 177.31 | 177.04 | 177.10 | 50.79 | 396.81 | 65.58 | 169.46 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.62 | 261.00 | 0.00 | 23.47 |
| reference_gauge | 206.42 | 205.72 | 206.20 | 59.23 | 328.77 | 0.00 | 140.40 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.55 | 241.00 | 0.00 | 54.10 |
| rolling_lp | 206.00 | 207.04 | 205.96 | 59.04 | 330.14 | 1.26 | 140.98 | 100.00 | 0.00 | 0.00 | 20.00 | 0.75 | 0.00 | 0.59 | 127.33 | 2.12 | 55.79 |
| dqn | 206.22 | 205.44 | 206.00 | 59.12 | 329.62 | 0.60 | 140.76 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.57 | 280.00 | 0.31 | 53.72 |
| hybrid | 204.97 | 205.11 | 205.32 | 58.87 | 331.10 | 1.34 | 141.39 | 100.00 | 0.00 | 0.00 | 20.00 | 1.66 | 1.00 | 0.59 | 167.33 | 2.87 | 54.69 |
| omniscient_lp | 207.28 | 209.48 | 207.28 | 59.20 | 328.76 | 0.00 | 140.40 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.67 | 0.00 | 0.00 | 57.85 |


### forecast_bias_high

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 179.11 | 178.82 | 178.90 | 51.29 | 392.74 | 65.58 | 167.72 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.62 | 263.00 | 0.00 | 25.54 |
| reference_gauge | 208.23 | 207.51 | 208.02 | 59.72 | 324.76 | 0.00 | 138.69 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.54 | 240.00 | 0.00 | 56.18 |
| rolling_lp | 206.22 | 207.53 | 206.18 | 59.04 | 330.09 | 4.67 | 140.97 | 100.00 | 0.00 | 0.00 | 20.00 | 0.75 | 0.33 | 0.61 | 87.67 | 2.16 | 56.00 |
| dqn | 207.72 | 207.00 | 207.50 | 59.57 | 325.97 | 0.52 | 139.21 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.56 | 286.00 | 0.31 | 55.69 |
| hybrid | 207.47 | 207.36 | 207.40 | 59.49 | 326.54 | 1.21 | 139.45 | 100.00 | 0.00 | 0.00 | 20.00 | 0.66 | 0.33 | 0.61 | 182.00 | 2.82 | 56.54 |
| omniscient_lp | 209.12 | 211.33 | 209.12 | 59.73 | 324.50 | 0.00 | 138.58 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.68 | 0.00 | 0.00 | 60.01 |


### forecast_bias_low

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 178.82 | 178.42 | 178.60 | 51.18 | 393.62 | 64.70 | 168.09 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.61 | 264.00 | 0.00 | 25.02 |
| reference_gauge | 207.02 | 206.11 | 206.80 | 59.34 | 327.84 | 0.00 | 140.00 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.53 | 238.00 | 0.00 | 54.48 |
| rolling_lp | 203.13 | 204.30 | 203.08 | 58.06 | 338.04 | 9.25 | 144.36 | 100.00 | 0.00 | 0.00 | 20.00 | 0.72 | 0.33 | 0.61 | 64.33 | 2.15 | 51.91 |
| dqn | 206.97 | 206.02 | 206.76 | 59.31 | 328.06 | 0.37 | 140.10 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.55 | 279.67 | 0.30 | 54.37 |
| hybrid | 205.21 | 205.17 | 205.16 | 58.74 | 332.56 | 4.60 | 142.02 | 100.00 | 0.00 | 0.00 | 20.00 | 0.72 | 0.33 | 0.61 | 147.33 | 2.94 | 53.80 |
| omniscient_lp | 207.87 | 210.00 | 207.87 | 59.35 | 327.58 | 0.00 | 139.89 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.68 | 0.00 | 0.00 | 58.36 |


### double_outage

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 174.24 | 173.83 | 174.03 | 49.89 | 404.05 | 61.65 | 172.55 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.63 | 254.00 | 0.00 | 20.74 |
| reference_gauge | 201.65 | 200.86 | 201.44 | 57.80 | 340.26 | 0.00 | 145.31 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.56 | 233.00 | 0.00 | 49.31 |
| rolling_lp | 199.29 | 200.54 | 199.29 | 57.00 | 346.52 | 5.62 | 147.98 | 100.00 | 0.00 | 0.00 | 20.00 | 0.86 | 0.67 | 0.61 | 73.33 | 2.16 | 48.94 |
| dqn | 201.05 | 200.35 | 200.84 | 57.55 | 342.32 | 1.56 | 146.19 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.59 | 265.33 | 0.32 | 48.70 |
| hybrid | 200.26 | 200.29 | 200.24 | 57.34 | 343.81 | 2.79 | 146.82 | 100.00 | 0.00 | 0.00 | 20.00 | 0.79 | 0.33 | 0.62 | 152.00 | 2.98 | 49.48 |
| omniscient_lp | 202.47 | 204.54 | 202.47 | 57.84 | 339.75 | 0.00 | 145.09 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.67 | 0.00 | 0.00 | 53.13 |


## Hard-constraint audit (sum over all scenarios)

| method | floor_breach_days | mass_balance_violation_days |
|---|---|---|
| dqn | 0 | 0 |
| hybrid | 0 | 0 |
| omniscient_lp | 0 | 0 |
| reference | 0 | 0 |
| reference_gauge | 0 | 0 |
| rolling_lp | 0 | 0 |

