# Component 3 v2 - Unified evaluation (SYNTHETIC scenarios)

Generated 2026-10-20 20:59. Initial storage 50% of active storage. Hard floor 204.00 masl, reserve 20%, terminal target 50%. Operating cost: N/A (no reliable tariff data).

> All inflows, demand weights, forecasts and irrigation requirements are synthetic or assumed. Results characterise performance on simulated scenarios, not observed CEB operation.

## Mean over scenarios

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 165.84 | 165.50 | 165.63 | 49.91 | 424.91 | 58.46 | 181.46 | 98.02 | 7.22 | 5.84 | 16.94 | 0.33 | 0.00 | 0.60 | 258.11 | 0.01 | -9.71 |
| reference_gauge | 191.65 | 190.87 | 191.44 | 57.57 | 364.71 | 0.00 | 155.75 | 98.11 | 6.89 | 5.81 | 16.94 | 0.33 | 0.00 | 0.53 | 237.67 | 0.01 | 17.35 |
| rolling_lp | 189.82 | 190.96 | 189.79 | 56.85 | 369.57 | 4.26 | 157.82 | 98.81 | 4.33 | 2.51 | 17.78 | 0.76 | 0.22 | 0.61 | 72.28 | 2.66 | 27.17 |
| dqn | 190.65 | 189.84 | 190.44 | 57.23 | 367.14 | 2.36 | 156.79 | 98.37 | 5.94 | 4.75 | 16.94 | 0.33 | 0.00 | 0.57 | 276.17 | 0.42 | 20.96 |
| hybrid | 190.93 | 190.39 | 190.83 | 57.31 | 366.11 | 1.52 | 156.35 | 98.65 | 4.94 | 4.05 | 17.76 | 0.60 | 0.00 | 0.58 | 186.72 | 4.11 | 25.08 |
| omniscient_lp | 192.27 | 194.29 | 192.27 | 57.55 | 364.37 | 0.00 | 155.60 | 99.30 | 2.56 | 0.82 | 17.78 | 0.83 | 1.00 | 0.68 | 0.00 | 0.00 | 37.38 |


## Per scenario


### test_year_real_sim

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 178.78 | 178.38 | 178.56 | 51.18 | 393.62 | 64.70 | 168.09 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.61 | 265.00 | 0.00 | 25.00 |
| reference_gauge | 207.01 | 206.11 | 206.80 | 59.34 | 327.84 | 0.00 | 140.00 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.54 | 239.00 | 0.00 | 54.48 |
| rolling_lp | 205.32 | 206.50 | 205.27 | 58.71 | 332.75 | 4.37 | 142.10 | 100.00 | 0.00 | 0.00 | 20.00 | 0.72 | 0.00 | 0.61 | 67.00 | 2.55 | 54.64 |
| dqn | 207.08 | 206.18 | 206.87 | 59.37 | 327.58 | 0.00 | 139.89 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.55 | 286.50 | 0.40 | 54.59 |
| hybrid | 206.46 | 205.81 | 206.41 | 59.20 | 328.80 | 0.98 | 140.41 | 100.00 | 0.00 | 0.00 | 20.00 | 0.72 | 0.00 | 0.56 | 203.50 | 3.98 | 55.22 |
| omniscient_lp | 207.86 | 209.98 | 207.86 | 59.35 | 327.58 | 0.00 | 139.89 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.68 | 0.00 | 0.00 | 58.35 |


### drought_el_nino

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 73.51 | 73.15 | 73.30 | 66.07 | 86.95 | 18.22 | 37.13 | 82.19 | 65.00 | 49.86 | 0.00 | 0.33 | 0.00 | 0.50 | 238.00 | 0.01 | -245.12 |
| reference_gauge | 82.19 | 81.55 | 81.98 | 73.91 | 66.85 | 0.00 | 28.55 | 83.01 | 62.00 | 49.59 | 0.00 | 0.33 | 0.00 | 0.38 | 245.00 | 0.00 | -232.41 |
| rolling_lp | 80.10 | 80.35 | 80.06 | 72.48 | 69.84 | 3.10 | 29.83 | 89.32 | 39.00 | 22.60 | 0.00 | 0.74 | 0.00 | 0.63 | 33.00 | 2.60 | -145.33 |
| dqn | 80.33 | 79.57 | 80.12 | 72.57 | 69.98 | 3.62 | 29.89 | 85.34 | 53.50 | 40.00 | 0.00 | 0.33 | 0.00 | 0.57 | 251.00 | 0.42 | -194.63 |
| hybrid | 80.71 | 80.22 | 80.56 | 73.03 | 68.61 | 2.18 | 29.30 | 87.81 | 44.50 | 36.30 | 0.00 | 0.50 | 0.00 | 0.57 | 152.50 | 3.94 | -165.98 |
| omniscient_lp | 80.96 | 81.66 | 80.96 | 73.68 | 66.36 | 0.00 | 28.34 | 93.70 | 23.00 | 7.40 | 0.00 | 0.83 | 1.00 | 0.67 | 0.00 | 0.00 | -83.81 |


### flood_year

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 200.14 | 200.20 | 199.92 | 34.50 | 877.70 | 68.48 | 374.82 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.66 | 247.00 | 0.01 | 4.65 |
| reference_gauge | 230.38 | 229.80 | 230.17 | 39.78 | 806.94 | 0.00 | 344.60 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.59 | 217.00 | 0.01 | 34.66 |
| rolling_lp | 228.71 | 230.21 | 228.79 | 39.38 | 811.86 | 4.10 | 346.70 | 100.00 | 0.00 | 0.00 | 20.00 | 1.02 | 1.00 | 0.63 | 67.50 | 2.63 | 35.24 |
| dqn | 225.34 | 224.60 | 225.13 | 38.85 | 819.47 | 11.90 | 349.95 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.61 | 260.50 | 0.42 | 31.35 |
| hybrid | 230.08 | 229.69 | 229.87 | 39.71 | 807.89 | 1.23 | 345.01 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.61 | 195.00 | 4.00 | 34.40 |
| omniscient_lp | 231.31 | 233.61 | 231.31 | 39.80 | 806.41 | 0.00 | 344.38 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.69 | 0.00 | 0.00 | 38.57 |


### vesak_flood

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 178.56 | 178.18 | 178.34 | 43.16 | 542.99 | 64.25 | 231.88 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.63 | 258.00 | 0.01 | 11.15 |
| reference_gauge | 206.68 | 205.78 | 206.46 | 50.02 | 477.48 | 0.00 | 203.91 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.55 | 234.00 | 0.00 | 39.45 |
| rolling_lp | 205.55 | 206.82 | 205.51 | 49.62 | 481.12 | 3.00 | 205.46 | 100.00 | 0.00 | 0.00 | 20.00 | 0.73 | 0.00 | 0.62 | 76.00 | 2.60 | 40.37 |
| dqn | 206.33 | 205.46 | 206.12 | 49.90 | 478.65 | 1.57 | 204.40 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.58 | 281.00 | 0.42 | 39.31 |
| hybrid | 206.60 | 206.01 | 206.56 | 50.01 | 477.37 | 0.22 | 203.86 | 100.00 | 0.00 | 0.00 | 20.00 | 0.73 | 0.00 | 0.57 | 196.00 | 4.17 | 40.82 |
| omniscient_lp | 207.63 | 209.83 | 207.63 | 50.05 | 476.98 | 0.00 | 203.69 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.68 | 0.00 | 0.00 | 43.50 |


### dry_christmas

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 152.09 | 151.52 | 151.87 | 51.08 | 335.75 | 52.99 | 143.38 | 100.00 | 0.00 | 2.74 | 12.45 | 0.33 | 0.00 | 0.57 | 273.00 | 0.00 | 22.19 |
| reference_gauge | 175.28 | 174.43 | 175.06 | 58.96 | 281.68 | 0.00 | 120.29 | 100.00 | 0.00 | 2.74 | 12.45 | 0.33 | 0.00 | 0.49 | 252.00 | 0.01 | 45.90 |
| rolling_lp | 173.80 | 175.10 | 173.79 | 58.28 | 286.10 | 4.02 | 122.18 | 100.00 | 0.00 | 0.00 | 20.00 | 0.82 | 0.50 | 0.61 | 69.50 | 2.65 | 47.33 |
| dqn | 175.10 | 174.16 | 174.88 | 58.91 | 281.98 | 0.39 | 120.42 | 100.00 | 0.00 | 2.74 | 12.45 | 0.33 | 0.00 | 0.51 | 297.50 | 0.42 | 45.66 |
| hybrid | 174.63 | 173.99 | 174.58 | 58.75 | 282.92 | 1.36 | 120.82 | 100.00 | 0.00 | 0.14 | 19.83 | 0.72 | 0.00 | 0.55 | 176.50 | 4.30 | 47.39 |
| omniscient_lp | 175.91 | 178.13 | 175.91 | 58.96 | 281.43 | 0.00 | 120.18 | 100.00 | 0.00 | 0.00 | 20.00 | 0.84 | 1.00 | 0.68 | 0.00 | 0.00 | 50.48 |


### wide_forecast_spread

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 177.31 | 177.04 | 177.10 | 50.79 | 396.81 | 65.58 | 169.46 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.62 | 261.00 | 0.01 | 23.47 |
| reference_gauge | 206.42 | 205.72 | 206.20 | 59.23 | 328.77 | 0.00 | 140.40 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.55 | 241.00 | 0.01 | 54.10 |
| rolling_lp | 206.08 | 207.10 | 206.03 | 59.07 | 329.88 | 1.07 | 140.88 | 100.00 | 0.00 | 0.00 | 20.00 | 0.72 | 0.00 | 0.59 | 129.00 | 2.78 | 55.79 |
| dqn | 206.25 | 205.45 | 206.03 | 59.13 | 329.53 | 0.67 | 140.73 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.57 | 281.00 | 0.43 | 53.75 |
| hybrid | 205.94 | 205.49 | 205.81 | 59.07 | 329.94 | 0.82 | 140.90 | 100.00 | 0.00 | 0.00 | 20.00 | 0.53 | 0.00 | 0.57 | 213.00 | 4.32 | 54.26 |
| omniscient_lp | 207.28 | 209.48 | 207.28 | 59.20 | 328.76 | 0.00 | 140.40 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.67 | 0.00 | 0.00 | 57.85 |


### forecast_bias_high

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 179.11 | 178.82 | 178.90 | 51.29 | 392.74 | 65.58 | 167.72 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.62 | 263.00 | 0.00 | 25.54 |
| reference_gauge | 208.23 | 207.51 | 208.02 | 59.72 | 324.76 | 0.00 | 138.69 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.54 | 240.00 | 0.01 | 56.18 |
| rolling_lp | 206.64 | 207.94 | 206.57 | 59.17 | 329.09 | 3.50 | 140.54 | 100.00 | 0.00 | 0.00 | 20.00 | 0.66 | 0.00 | 0.61 | 87.50 | 2.73 | 56.32 |
| dqn | 207.63 | 206.94 | 207.41 | 59.55 | 326.14 | 0.69 | 139.28 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.56 | 287.50 | 0.43 | 55.65 |
| hybrid | 208.05 | 207.44 | 207.92 | 59.68 | 325.04 | 0.34 | 138.81 | 100.00 | 0.00 | 0.00 | 20.00 | 0.53 | 0.00 | 0.57 | 213.00 | 4.14 | 56.64 |
| omniscient_lp | 209.12 | 211.33 | 209.12 | 59.73 | 324.50 | 0.00 | 138.58 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.68 | 0.00 | 0.00 | 60.01 |


### forecast_bias_low

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 178.82 | 178.42 | 178.60 | 51.18 | 393.62 | 64.70 | 168.09 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.61 | 264.00 | 0.01 | 25.02 |
| reference_gauge | 207.02 | 206.11 | 206.80 | 59.34 | 327.84 | 0.00 | 140.00 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.53 | 238.00 | 0.00 | 54.48 |
| rolling_lp | 202.67 | 203.82 | 202.58 | 57.91 | 339.30 | 10.21 | 144.90 | 100.00 | 0.00 | 0.00 | 20.00 | 0.62 | 0.00 | 0.61 | 52.50 | 2.71 | 51.09 |
| dqn | 206.89 | 205.94 | 206.67 | 59.28 | 328.30 | 0.55 | 140.20 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.56 | 275.00 | 0.40 | 54.26 |
| hybrid | 204.55 | 204.05 | 204.46 | 58.60 | 333.71 | 5.93 | 142.51 | 100.00 | 0.00 | 0.00 | 20.00 | 0.62 | 0.00 | 0.59 | 150.00 | 4.09 | 52.66 |
| omniscient_lp | 207.87 | 210.00 | 207.87 | 59.35 | 327.58 | 0.00 | 139.89 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 1.00 | 0.68 | 0.00 | 0.00 | 58.36 |


### double_outage

| method | energy_gwh | weighted_energy_gwh | storage_adjusted_energy_gwh | water_utilization_pct | spill_mcm | spill_avoidable_mcm | spill_energy_equiv_gwh | constraint_satisfaction_pct | unmet_mandatory_days | reserve_breach_pct | min_storage_pct | terminal_storage_mcm | terminal_target_met | level_std_m | projected_actions | decision_latency_ms_mean | episode_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference | 174.24 | 173.83 | 174.03 | 49.89 | 404.05 | 61.65 | 172.55 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.63 | 254.00 | 0.00 | 20.74 |
| reference_gauge | 201.65 | 200.86 | 201.44 | 57.80 | 340.26 | 0.00 | 145.31 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.56 | 233.00 | 0.01 | 49.31 |
| rolling_lp | 199.51 | 200.76 | 199.51 | 57.04 | 346.18 | 5.00 | 147.84 | 100.00 | 0.00 | 0.00 | 20.00 | 0.83 | 0.50 | 0.61 | 68.50 | 2.73 | 49.10 |
| dqn | 200.91 | 200.29 | 200.70 | 57.50 | 342.65 | 1.86 | 146.33 | 100.00 | 0.00 | 0.00 | 20.00 | 0.33 | 0.00 | 0.59 | 265.50 | 0.44 | 48.66 |
| hybrid | 201.33 | 200.79 | 201.28 | 57.72 | 340.73 | 0.63 | 145.51 | 100.00 | 0.00 | 0.00 | 20.00 | 0.72 | 0.00 | 0.59 | 181.00 | 4.09 | 50.31 |
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

