"""
multiseed_eval.py
=================
Statistical robustness of the learned methods across TRAINING SEEDS.

Protocol (no test leakage):
  1. Every training run (same hyper-parameters, different seed) picks its own checkpoint (best-on-training-callback vs final)
     on validation scenarios 20-39 at two starting storage levels.
  2. Each chosen model is evaluated on the 9 stress scenarios x 3 forecast-noise seeds (27 cases), identical to evaluate_all.py.
  3. Baselines (rolling LP, reference, perfect-foresight LP) are computed once on the same 27 cases.
Statistics:
  * mean +- std and 95% t-interval across training seeds (seed-level means over the 27 cases);
  * paired difference vs rolling LP: per-seed mean difference -> one-sample t-test across seeds;
    per-case difference averaged over seeds -> Wilcoxon signed-rank + bootstrap 95% CI + win rate over the 27 cases.
Writes outputs/multiseed/{runs_metrics.csv, seed_summary.csv, MULTISEED_REPORT.md}
Synthetic scenarios only.
"""
import os
import glob
import json
import numpy as np
import pandas as pd
from scipy import stats

import paths
import scenario_generator as sg
import sim_core as sm
import rolling_lp as rl
import rl_common as rc
from hydro_core import HydroParams
from dqn_policy import DQNPolicy
from hybrid_policy import HybridPolicy
from train_dqn_v2 import validation_score
from evaluate_all import resample_forecast, run_all

OUT = str(paths.MULTISEED_DIR)
METRICS = ["episode_score", "storage_adjusted_energy_gwh", "weighted_energy_gwh", "unmet_mandatory_days",
           "spill_avoidable_mcm", "terminal_storage_mcm", "reserve_breach_pct", "constraint_satisfaction_pct"]
TR = str(paths.TRAINING_RUNS_DIR)
GROUPS = {"dqn": (TR + "/a_800k_s*", TR + "/msd_*"),
          "hybrid": (TR + "/h3_hyb_*", TR + "/msh_hyb_*")}


def seed_of(path):
    return json.load(open(os.path.join(path, "train_config.json")))["args"]["seed"]


def choose_checkpoint(p, cls, run_dir, val):
    best = None
    for ck in ("dqn_best_val.zip", "dqn_final.zip"):
        f = os.path.join(run_dir, ck)
        if os.path.exists(f):
            s, _ = validation_score(p, cls(f), val, n_scen=20, s0_fracs=(0.5, 1.0))
            if best is None or s > best[0]:
                best = (s, f, ck)
    return best


def ci95(x):
    x = np.asarray(x, float)
    if len(x) < 2:
        return float("nan")
    return float(stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)))


def fmt_table(df, nd=2):
    df = df.reset_index()
    h = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "|".join(["---"] * len(df.columns)) + "|\n"
    for _, r in df.iterrows():
        h += "| " + " | ".join(f"{v:.{nd}f}" if isinstance(v, float) else str(v) for v in r) + " |\n"
    return h


def main():
    os.makedirs(OUT, exist_ok=True)
    p = HydroParams.from_config()
    val = sg.load_bank(os.path.join(sg.BANK_DIR, "val_bank.pkl"))[20:40]
    suite = sg.load_stress_suite()
    cases = [suite[n] if k == 0 else resample_forecast(suite[n], k) for n in suite for k in range(3)]

    frames = []
    base_pols = {"reference_gauge": sm.ReferenceRulePolicy(gauge=True), "rolling_lp": rl.RollingLPPolicy(),
                 "omniscient_lp": rl.OmniscientLPPolicy()}
    b, _ = run_all(p, cases, base_pols, 0.5)
    b["seed"] = -1; b["run"] = "baseline"; frames.append(b)

    chosen = []
    for kind, pats in GROUPS.items():
        cls = DQNPolicy if kind == "dqn" else HybridPolicy
        runs = sorted({d for pat in pats for d in glob.glob(pat) if os.path.exists(os.path.join(d, "train_config.json"))
                       and os.path.exists(os.path.join(d, "dqn_final.zip"))})
        for d in runs:
            sc_, f, ck = choose_checkpoint(p, cls, d, val)
            seed = seed_of(d)
            print(f"[{kind}] seed {seed:>3} {os.path.basename(d)[:28]:28s} -> {ck:18s} holdout-val {sc_:6.2f}", flush=True)
            r, _ = run_all(p, cases, {kind: cls(f)}, 0.5)
            r["seed"] = seed; r["run"] = os.path.basename(d); frames.append(r)
            chosen.append({"kind": kind, "seed": seed, "run": os.path.basename(d), "checkpoint": ck, "holdout_val_score": sc_})
    allr = pd.concat(frames, ignore_index=True)
    allr["case"] = allr["scenario"]
    allr.to_csv(f"{OUT}/runs_metrics.csv", index=False)

    seed_means = allr.groupby(["method", "seed"])[METRICS].mean().reset_index()
    seed_means.to_csv(f"{OUT}/seed_summary.csv", index=False)

    lp = allr[allr.method == "rolling_lp"].set_index("case")
    rows, tests = [], []
    for m in ["reference_gauge", "rolling_lp", "dqn", "hybrid", "omniscient_lp"]:
        sm_m = seed_means[seed_means.method == m]
        row = {"method": m, "n_seeds": len(sm_m)}
        for c in METRICS:
            row[c] = f"{sm_m[c].mean():.2f} +- {sm_m[c].std(ddof=1) if len(sm_m) > 1 else 0:.2f}"
        rows.append(row)
        if m in ("dqn", "hybrid"):
            for c in ("episode_score", "storage_adjusted_energy_gwh", "unmet_mandatory_days"):
                per_seed = []
                for s, g in allr[allr.method == m].groupby("seed"):
                    g = g.set_index("case")
                    per_seed.append((g[c] - lp[c].reindex(g.index)).mean())
                per_seed = np.array(per_seed)
                case_diff = (allr[allr.method == m].groupby("case")[c].mean() - lp[c].groupby(level=0).mean()).dropna()
                try:
                    w = stats.wilcoxon(case_diff.values).pvalue if np.any(case_diff.values != 0) else 1.0
                except ValueError:
                    w = float("nan")
                rng = np.random.default_rng(0)
                boots = [rng.choice(case_diff.values, len(case_diff)).mean() for _ in range(5000)]
                better = (case_diff > 0) if c != "unmet_mandatory_days" else (case_diff < 0)
                tt = stats.ttest_1samp(per_seed, 0.0) if len(per_seed) > 2 else None
                tests.append({"method": m, "metric": c, "mean_diff_vs_rolling_lp": per_seed.mean(),
                              "seed_std": per_seed.std(ddof=1) if len(per_seed) > 1 else float("nan"),
                              "95%CI_across_seeds_+-": ci95(per_seed),
                              "t_test_p(seeds)": tt.pvalue if tt is not None else float("nan"),
                              "wilcoxon_p(27 cases)": w,
                              "bootstrap95%CI_cases": f"[{np.percentile(boots, 2.5):.2f}, {np.percentile(boots, 97.5):.2f}]",
                              "win_rate_cases_%": 100.0 * better.mean(), "seeds_better_than_LP": int((per_seed > 0).sum() if c != "unmet_mandatory_days" else (per_seed < 0).sum())})
    summ, ts = pd.DataFrame(rows).set_index("method"), pd.DataFrame(tests)
    ts.to_csv(f"{OUT}/paired_tests_vs_rolling_lp.csv", index=False)

    # per-scenario win rates (hybrid and dqn vs rolling LP, composite score), seed-averaged
    base = allr.assign(base=allr.case.str.split("#").str[0])
    pv = base.groupby(["method", "base"])["episode_score"].mean().unstack(0)
    ex = base[base.base != "drought_el_nino"].groupby(["method", "seed"])["episode_score"].mean().reset_index()
    ex_s = ex.groupby("method")["episode_score"].agg(["mean", "std"]).reindex(["reference_gauge", "rolling_lp", "dqn", "hybrid", "omniscient_lp"])

    md = f"""# Multi-seed robustness (SYNTHETIC scenarios)

Training seeds: hybrid {sorted(c['seed'] for c in chosen if c['kind']=='hybrid')}, plain DQN {sorted(c['seed'] for c in chosen if c['kind']=='dqn')}
(same hyper-parameters per method). Each run chose its checkpoint on held-out validation scenarios; evaluation = 9 stress scenarios x 3 forecast-noise seeds = 27 cases.
Baselines have no training randomness (n=1 row; their +-0 is not an estimate of anything).

## Mean +- std across training seeds (seed-level means over 27 cases)
{fmt_table(summ.reset_index().set_index('method'))}
## Paired difference vs rolling LP (positive = better, except unmet days where negative = better)
{fmt_table(ts.set_index('method'), 3)}
## Composite score excluding the drought scenario (mean +- std across seeds)
{fmt_table(ex_s.rename(columns={'mean':'mean_score','std':'std_across_seeds'}))}
## Composite score by scenario (seed-averaged)
{fmt_table(pv[['reference_gauge','rolling_lp','dqn','hybrid','omniscient_lp']].round(1))}
## Checkpoints used
{fmt_table(pd.DataFrame(chosen).set_index('kind'))}
"""
    open(f"{OUT}/MULTISEED_REPORT.md", "w", encoding="utf-8").write(md)
    print(md[:3000])


if __name__ == "__main__":
    main()
