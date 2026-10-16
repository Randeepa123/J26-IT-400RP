"""make_final_report.py - builds FINAL_RESULTS_REPORT_V2.md from the saved evaluation / adaptation / training files."""
import json
import glob
import os
import pandas as pd

import paths

E = str(paths.EVALUATION_DIR / "final")
d = pd.read_csv(f"{E}/metrics_all.csv")
order = ["reference", "reference_gauge", "rolling_lp", "dqn", "hybrid", "omniscient_lp"]
sel = json.load(open(paths.SELECTED_MODELS_JSON))


def tbl(df, nd=2):
    df = df.reset_index()
    h = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "|".join(["---"] * len(df.columns)) + "|\n"
    for _, r in df.iterrows():
        h += "| " + " | ".join(f"{v:.{nd}f}" if isinstance(v, float) else str(v) for v in r) + " |\n"
    return h


cols = ["energy_gwh", "weighted_energy_gwh", "storage_adjusted_energy_gwh", "water_utilization_pct", "spill_mcm",
        "spill_avoidable_mcm", "spill_energy_equiv_gwh", "constraint_satisfaction_pct", "reserve_breach_pct",
        "min_storage_pct", "terminal_storage_mcm", "level_std_m", "decision_latency_ms_mean", "episode_score"]
summ = d.groupby("method")[cols].mean().reindex(order)


def piv(c, nd=1):
    return tbl(d.pivot_table(index="base_scenario", columns="method", values=c)[order], nd)


tm = (d.groupby("method")["terminal_target_met"].mean().reindex(order) * 100).round(0).to_dict()
viol = d.groupby("method")[["floor_breach_days", "mass_balance_violation_days"]].sum().reindex(order)
ad = pd.read_csv(paths.ADAPTATION_DIR / "hybrid_h3_shift_year_tol6" / "adaptation_comparison.csv", index_col=0)
ev = pd.read_csv(paths.ADAPTATION_DIR / "hybrid_h3_shift_year_tol6" / "adaptation_events.csv")
rows = []
for p in sorted(glob.glob(str(paths.TRAINING_RUNS_DIR) + "/*/")):
    f = os.path.join(p, "train_config.json")
    if os.path.exists(f) and not os.path.basename(p.rstrip("/\\")).startswith("smoke"):
        c = json.load(open(f))
        a = c["args"]
        rows.append(f"| {os.path.basename(p.rstrip('/\\'))} | {a['timesteps']:,} | {a['lr']} | {a['gamma']} | "
                    f"{a['shaping_beta']} | {a['seed']} | {c['best_val_score']:.1f} |")
tr = "\n".join(rows)
n_acc = int(ev.accepted.sum())

R = f"""# Component 3 - Final results report (progress presentation 1)

**Hydropower Generation & Reservoir Release Optimisation - Kukule Ganga.**
> **Data provenance:** the study dataset is simulation-based (CEB station specifications + a rainfall-runoff model driven by Ratnapura rainfall; demand,
> forecasts and irrigation are modelled). It is not observed CEB telemetry, so the numbers below describe performance on this modelled system.
> The pipeline reads observed data through the same files whenever it becomes available.

## 1. What was built
LP baselines (a perfect-foresight upper bound and a causal rolling-horizon LP with online forecast-bias correction), a DQN, a residual
hybrid LP-DQN, a policy-adaptation loop, a demand-weighted objective (Vesak / Christmas peaks), a scenario bank (El Nino drought,
La Nina, flash floods, monsoon shifts, outages, forecast error), a unified evaluator and a forecast-driven command (`run_component3.py`).
See the project `README.md`.

## 2. Operating rules (identical for every method)
Hard floor 204.00 masl; operating reserve 20% of active storage enforced for turbine release; year-end target 50% (soft);
environmental (2 m3/s) + assumed irrigation release served first at the weir and never counted as spill; spill split into avoidable /
unavoidable; energy valued with a daily demand weight. **Reserve %, year-end %, irrigation figures, festival uplifts and MOL are confirmed project parameters.**

## 3. Data / experiment design
- Train bank 300 synthetic scenario-years, validation bank 40 (disjoint seeds), 9 named stress cases built on the held-out year (2025-10-19..2026-10-18).
- Checkpoints were chosen on validation scenarios only (training callback: scenarios 0-19; final choice: scenarios 20-39 at two starting storage levels).
  The stress suite was never used for training or selection.
- Evaluation: 9 scenarios x 3 forecast-noise seeds, initial storage 50%, 365 days, same physics and safety layer for all methods.

Selected models: plain DQN `{sel['dqn']['path']}` (held-out validation score {sel['dqn']['holdout_val_score']:.2f}); hybrid `{sel['hybrid']['path']}`
(held-out validation score {sel['hybrid']['holdout_val_score']:.2f}); rolling LP on the same scenarios: {sel['hybrid']['rolling_lp_holdout_val_score']:.2f}.

| run | steps | lr | gamma | shaping beta | seed | best val score (training callback) |
|---|---|---|---|---|---|---|
{tr}

## 4. Results - mean over 9 scenarios x 3 seeds
`episode_score` = sum of the unshaped daily rewards (demand-weighted energy minus spill-energy loss, reserve shortfall, unmet mandatory release, year-end shortfall).
`storage_adjusted_energy_gwh` = energy + k_e x change in storage. Operating cost: N/A (no reliable tariff data).

{tbl(summ)}
Year-end target met (% of runs): {tm}

Hard-constraint audit (sum over all runs):

{tbl(viol, 0)}
### Composite score by scenario
{piv('episode_score')}
### Storage-adjusted energy (GWh) by scenario
{piv('storage_adjusted_energy_gwh')}
### Unmet environmental / irrigation release (days) by scenario
{piv('unmet_mandatory_days')}
### Avoidable spill (MCM) by scenario
{piv('spill_avoidable_mcm')}
### Year-end storage (MCM) by scenario (target 0.835)
{piv('terminal_storage_mcm', 2)}

## 5. Policy adaptation (regime shift at day 150: drought + forecasts biased 1.8x wet)
Final hybrid, safety tolerance 6.0 (accept a fine-tuned model only if it helps on the last 60 days and the guard-set score drops by less than 6):

{tbl(ad)}
Updates accepted: {n_acc} of {len(ev)}.

{tbl(ev.set_index('day'), 2)}
An earlier run with the first hybrid and tolerance 1.5 accepted 0/10 updates (adapted == frozen). Interpretation: the safety guard works; the single accepted
update improved the shifted-regime score by about 23 points. This is one run on one scenario, so treat it as indicative, not proven.

## 6. Reading the results honestly
- Raw energy differs by less than 1% among the good methods (the pond holds about 0.4 day of full-load flow). The differences that matter are year-end storage, drought handling (unmet mandatory release), avoidable spill and robustness.
- The hybrid has the best composite score among the non-perfect-foresight methods and beats the rolling LP in 8 of 9 scenarios, with the largest gain in the El Nino drought. It loses slightly in the wide-forecast-spread scenario.
- The plain DQN is safe (zero constraint violations) but ends each year at the reserve and is below the LP; the LP supplies most of the hybrid's value.
- The reference that reads today's gauge is a strong energy baseline but ignores the year-end target and does worst in droughts.
- Margins are modest and come from single training seeds per configuration; more seeds are needed to claim statistical significance.

## 7. Limitations
Modelled (not observed) study dataset; rated discharge (47.5 vs 48.0 m3/s) not yet confirmed with the station; daily time step (no intraday peaking);
operating cost not computed; the solar-surplus input is an optional stub; simulated forecasts (the real Component-1 forecasts are much wider, partly covered by the wide-spread stress case);
adaptation shown on one synthetic shift only; no operator validation.

## 8. Optional extension
If observed station data becomes available: replace the dataset files, refit the weather generator, rebuild banks, retrain (several seeds), re-evaluate, re-run `run_component3.py`.

## 9. Multi-seed robustness
See `outputs/multiseed/MULTISEED_REPORT.md` (training-seed mean +- std, 95% CIs, paired tests against the rolling LP).
"""
ms_path = str(paths.MULTISEED_DIR / "MULTISEED_REPORT.md")
if os.path.exists(ms_path):
    ms = open(ms_path, encoding="utf-8").read().replace("# Multi-seed robustness (SYNTHETIC scenarios)", "").replace("\n## ", "\n### ")
    R += """
## 10. Multi-seed robustness (training-seed variation)
The headline tables above use one selected model per method. The tables below repeat the evaluation for **5 hybrid seeds and 4 plain-DQN seeds**
(same hyper-parameters; every run picks its checkpoint on held-out validation scenarios; 27 test cases each). Note: hybrid seed 3 is the model whose
hyper-parameters were chosen among three configurations on validation data, so it carries slight selection optimism; the other four seeds do not.

**Take-aways (read together with the tables):**
- Hybrid vs rolling LP: all 5 seeds are better on energy (+0.65 GWh, paired t-test across seeds p = 0.005; Wilcoxon over cases p = 0.001; wins 81% of cases) and on unmet environmental/irrigation release days (-0.5 days).
- Composite score: hybrid +2.05 vs rolling LP (95% interval across seeds +-1.1, p = 0.006, 5/5 seeds), but excluding the drought scenario hybrid and rolling LP are practically tied (48.7 vs 48.6); the composite advantage comes mainly from drought handling. Over the 27 cases the composite difference is not significant by Wilcoxon (p = 0.26).
- Plain DQN: significantly worse than the rolling LP on the composite score (-2.6, Wilcoxon p < 0.001) with statistically equal energy; it is not recommended on its own.
""" + ms
open(paths.DOCS_DIR / "FINAL_RESULTS_REPORT_V2.md", "w", encoding="utf-8").write(R)
print("written", len(R))
