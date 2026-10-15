# Model card - deployable checkpoints

| File | What it is | Source run | Selection score* |
|---|---|---|---|
| `hybrid_selected.zip` | Residual hybrid LP-DQN (DQN adjusts the rolling-LP release by -30..+30% of turbine capacity); 26-feature input (23 state + 3 LP-plan features), 7 actions | `outputs/training_runs/h3_hyb_400k_s3_20261020_205856/dqn_best_val.zip` | 8.19 (rolling LP: 4.54) |
| `dqn_selected.zip` | Plain DQN; 23-feature input, 11 release-fraction actions | `outputs/training_runs/a_800k_s2_20261020_202600/dqn_best_val.zip` | -1.53 (rolling LP: 4.54) |

*Held-out validation score: validation scenarios 20-39 (never used by the training callback), two starting storage levels; higher is better.
Full provenance: `outputs/selected_models.json`.

**Load them with** `dqn_policy.DQNPolicy(path)` / `hybrid_policy.HybridPolicy(path)` (they import `torch_compat`, required for `DQN.load` on newer PyTorch).
The hybrid also needs the rolling LP (`rolling_lp.py`) at run time. Both models act only through the safety layer in `hydro_core.HydroParams.step`
(hard floor, enforced reserve, mandatory weir release), so they cannot breach those constraints.

**Training data:** 300 modelled scenario-years (`data/scenario_bank/train_bank.pkl`) - not observed CEB telemetry.
**Intended use:** decision support for a daily reservoir release plan on the modelled Kukule Ganga system. **Not** validated against operator practice.
**Performance (multi-seed, 27 test cases per seed):** see `docs/FINAL_RESULTS_REPORT_V2.md`, section 10. Hybrid: better than the rolling LP on energy and
unmet environmental/irrigation release in 5/5 training seeds; composite score advantage comes mainly from the drought scenario. Plain DQN is below the rolling LP.
