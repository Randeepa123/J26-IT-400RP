# Multi-seed robustness (SYNTHETIC scenarios)

Training seeds: hybrid [3, 11, 12, 13, 14], plain DQN [2, 21, 22, 23]
(same hyper-parameters per method). Each run chose its checkpoint on held-out validation scenarios; evaluation = 9 stress scenarios x 3 forecast-noise seeds = 27 cases.
Baselines have no training randomness (n=1 row; their +-0 is not an estimate of anything).

## Mean +- std across training seeds (seed-level means over 27 cases)
| method | n_seeds | episode_score | storage_adjusted_energy_gwh | weighted_energy_gwh | unmet_mandatory_days | spill_avoidable_mcm | terminal_storage_mcm | reserve_breach_pct | constraint_satisfaction_pct |
|---|---|---|---|---|---|---|---|---|---|
| reference_gauge | 1 | 17.35 +- 0.00 | 191.44 +- 0.00 | 190.87 +- 0.00 | 6.89 +- 0.00 | 0.00 +- 0.00 | 0.33 +- 0.00 | 5.81 +- 0.00 | 98.11 +- 0.00 |
| rolling_lp | 1 | 27.05 +- 0.00 | 189.56 +- 0.00 | 190.72 +- 0.00 | 4.26 +- 0.00 | 4.87 +- 0.00 | 0.81 +- 0.00 | 2.49 +- 0.00 | 98.83 +- 0.00 |
| dqn | 4 | 24.46 +- 3.60 | 189.89 +- 0.49 | 189.33 +- 0.45 | 4.76 +- 1.12 | 3.53 +- 1.02 | 0.38 +- 0.05 | 3.58 +- 0.81 | 98.70 +- 0.31 |
| hybrid | 5 | 29.10 +- 0.87 | 190.20 +- 0.26 | 190.17 +- 0.51 | 3.76 +- 0.19 | 2.84 +- 0.56 | 0.76 +- 0.26 | 1.83 +- 0.20 | 98.97 +- 0.05 |
| omniscient_lp | 1 | 37.38 +- 0.00 | 192.27 +- 0.00 | 194.29 +- 0.00 | 2.56 +- 0.00 | 0.00 +- 0.00 | 0.83 +- 0.00 | 0.82 +- 0.00 | 99.30 +- 0.00 |

## Paired difference vs rolling LP (positive = better, except unmet days where negative = better)
| method | metric | mean_diff_vs_rolling_lp | seed_std | 95%CI_across_seeds_+- | t_test_p(seeds) | wilcoxon_p(27 cases) | bootstrap95%CI_cases | win_rate_cases_% | seeds_better_than_LP |
|---|---|---|---|---|---|---|---|---|---|
| dqn | episode_score | -2.592 | 3.596 | 5.721 | 0.245 | 0.000 | [-4.36, -1.08] | 18.519 | 1 |
| dqn | storage_adjusted_energy_gwh | 0.331 | 0.485 | 0.772 | 0.266 | 0.313 | [-0.24, 0.92] | 62.963 | 2 |
| dqn | unmet_mandatory_days | 0.500 | 1.123 | 1.787 | 0.439 | 0.109 | [0.00, 1.19] | 0.000 | 2 |
| hybrid | episode_score | 2.051 | 0.867 | 1.077 | 0.006 | 0.258 | [0.07, 4.87] | 51.852 | 5 |
| hybrid | storage_adjusted_energy_gwh | 0.646 | 0.264 | 0.328 | 0.005 | 0.001 | [0.34, 0.97] | 81.481 | 5 |
| hybrid | unmet_mandatory_days | -0.504 | 0.186 | 0.231 | 0.004 | 0.109 | [-1.19, 0.00] | 11.111 | 5 |

## Composite score excluding the drought scenario (mean +- std across seeds)
| method | mean_score | std_across_seeds |
|---|---|---|
| reference_gauge | 48.57 | nan |
| rolling_lp | 48.59 | nan |
| dqn | 47.42 | 0.51 |
| hybrid | 48.70 | 0.57 |
| omniscient_lp | 52.53 | nan |

## Composite score by scenario (seed-averaged)
| base | reference_gauge | rolling_lp | dqn | hybrid | omniscient_lp |
|---|---|---|---|---|---|
| double_outage | 49.30 | 48.90 | 47.90 | 49.20 | 53.10 |
| drought_el_nino | -232.40 | -145.30 | -159.20 | -127.70 | -83.80 |
| dry_christmas | 45.90 | 47.00 | 45.70 | 47.20 | 50.50 |
| flood_year | 34.70 | 34.90 | 32.20 | 34.20 | 38.60 |
| forecast_bias_high | 56.20 | 56.00 | 55.50 | 56.20 | 60.00 |
| forecast_bias_low | 54.50 | 51.90 | 52.60 | 53.20 | 58.40 |
| test_year_real_sim | 54.50 | 54.30 | 54.10 | 55.00 | 58.30 |
| vesak_flood | 39.50 | 39.90 | 38.90 | 40.10 | 43.50 |
| wide_forecast_spread | 54.10 | 55.80 | 52.30 | 54.50 | 57.80 |

## Checkpoints used
| kind | seed | run | checkpoint | holdout_val_score |
|---|---|---|---|---|
| dqn | 2 | a_800k_s2_20261020_202600 | dqn_best_val.zip | -1.53 |
| dqn | 21 | msd_600k_s21_20261020_230132 | dqn_best_val.zip | -8.59 |
| dqn | 22 | msd_600k_s22_20261020_230132 | dqn_best_val.zip | -0.45 |
| dqn | 23 | msd_600k_s23_20261020_230132 | dqn_best_val.zip | -3.64 |
| hybrid | 3 | h3_hyb_400k_s3_20261020_205856 | dqn_best_val.zip | 8.19 |
| hybrid | 11 | msh_hyb_400k_s11_20261020_230132 | dqn_best_val.zip | 6.18 |
| hybrid | 12 | msh_hyb_400k_s12_20261020_230132 | dqn_best_val.zip | 3.87 |
| hybrid | 13 | msh_hyb_400k_s13_20261020_230132 | dqn_best_val.zip | 5.72 |
| hybrid | 14 | msh_hyb_400k_s14_20261020_230132 | dqn_best_val.zip | 7.55 |

