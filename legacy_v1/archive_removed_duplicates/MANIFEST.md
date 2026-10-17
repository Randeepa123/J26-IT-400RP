# Archive of superseded / duplicate v1 files

Nothing was deleted. Paths below are relative to the OLD project root (before the 2026-10-21 reorganisation); the corresponding new folders are listed in `docs/REORGANIZATION_MAP.md`. To restore an item, copy it back to the matching new location (v1 material now lives under `legacy_v1/Waterlevel_And_Demand/`, rainfall material under `data_pipelines/rainfall_forecast/`).

| Item | Why archived |
|---|---|
| `Temp` | exact (md5) duplicates of the 5 PDFs in "Rainfall data" |
| `lp_results.csv` | stale root-level copy; differs from Waterlevel_And_Demand/lp_results.csv which is the one scripts use |
| `requirements.txt` | stale root-level copy; the maintained file is Waterlevel_And_Demand/requirements.txt |
| `Waterlevel_And_Demand\recommended_config_changes.json` | not referenced by any script or document |
| `Waterlevel_And_Demand\outputs\test_slice` | unreferenced scratch plots from an LP test slice |
| `Waterlevel_And_Demand\outputs\dqn\smoke_test_20261020_114345` | v1 DQN smoke test (1,000 steps), superseded |
| `Waterlevel_And_Demand\outputs\dqn\run_1000steps_20261020_114619` | v1 DQN 1,000-step trial, superseded |
| `Waterlevel_And_Demand\outputs\dqn_b_s2.log` | log of an aborted training run on the pre-reserve environment |
| `Waterlevel_And_Demand\outputs\dqn_c_s3.log` | log of an aborted training run on the pre-reserve environment |
| `Waterlevel_And_Demand\outputs\dqn_v2_a_s1.log` | log of the first v2 DQN run, trained before the hard reserve rule (obsolete) |
| `Waterlevel_And_Demand\outputs\hyb_h1_s1.log` | log of an aborted hybrid run on the pre-reserve environment |

Kept in place on purpose (still read by v1 scripts/reports): lp_results*.csv, reference_results_*.csv, simulation_config*.json, synthetic_kukule_dataset_baseline_backup/, outputs/future_*, outputs/test_validation_viz, outputs/dqn/run_50000steps_*.
