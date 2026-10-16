"""
evaluate_all.py
===============
Unified evaluation of ALL methods on identical scenarios, physics and constraints (proposal Phase 6):

    reference (causal)   reference_gauge (legacy, reads today's gauge)   omniscient_lp (perfect-foresight bound)
    rolling_lp (causal MPC)   dqn   hybrid (residual LP-DQN)   [hybrid_adapted from policy_adaptation.py]

Scenarios : the named stress suite (+ real-simulation test year), optionally many forecast-noise seeds.
Metrics   : energy, demand-weighted energy, storage-adjusted energy, water utilisation, spill (total / avoidable /
            energy-equivalent), constraint satisfaction %, reserve breaches, terminal storage, level stability,
            decision latency; operating cost = N/A (no reliable tariff data).

Usage:
  python evaluate_all.py --dqn <dqn.zip> --hybrid <hybrid.zip> [--forecast-seeds 3] [--s0 0.5] [--out-dir DIR]
All results are on SYNTHETIC scenarios and must be reported as such.
"""
import os
import argparse
from datetime import datetime

import numpy as np
import pandas as pd

import paths
import scenario_generator as sg
import sim_core as sm
import rolling_lp as rl
import rl_common as rc
from hydro_core import HydroParams

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
METHOD_ORDER = ["reference", "reference_gauge", "rolling_lp", "dqn", "hybrid", "hybrid_adapted", "omniscient_lp"]
KEY_COLS = ["energy_gwh", "weighted_energy_gwh", "storage_adjusted_energy_gwh", "water_utilization_pct", "spill_mcm",
            "spill_avoidable_mcm", "spill_energy_equiv_gwh", "constraint_satisfaction_pct", "unmet_mandatory_days",
            "reserve_breach_pct", "min_storage_pct", "terminal_storage_mcm", "terminal_target_met",
            "level_std_m", "projected_actions", "decision_latency_ms_mean", "episode_score"]


def resample_forecast(sc, seed):
    """Same scenario/inflow, different forecast-noise realisation (keeps the scenario's forecast bias)."""
    rng = np.random.default_rng([4242, seed])
    bias = sc.meta.get("forecast_bias", 1.0)
    f50, f90, dwf = sg.make_forecasts(sc.inflow_m3, sc.weight, rng, bias=bias, p90_width=sc.meta.get('p90_width', 1.0))
    s = sg.Scenario(f"{sc.name}#f{seed}", sc.dates, sc.inflow_m3, sc.units, sc.weight, f50, f90, dwf, dict(sc.meta))
    return s


def build_policies(args):
    pols = {"reference": sm.ReferenceRulePolicy(), "reference_gauge": sm.ReferenceRulePolicy(gauge=True),
            "rolling_lp": rl.RollingLPPolicy(), "omniscient_lp": rl.OmniscientLPPolicy()}
    if args.dqn:
        from dqn_policy import DQNPolicy
        pols["dqn"] = DQNPolicy(args.dqn)
    if args.hybrid:
        from hybrid_policy import HybridPolicy
        pols["hybrid"] = HybridPolicy(args.hybrid)
    if getattr(args, "hybrid_adapted", None):
        from hybrid_policy import HybridPolicy
        pols["hybrid_adapted"] = HybridPolicy(args.hybrid_adapted, name="hybrid_adapted")
    return pols


def run_all(p, scenarios, policies, s0_frac, days=365):
    rows, trajs = [], {}
    for sc in scenarios:
        for name, pol in policies.items():
            df, m = sm.simulate(p, sc, pol, 0, days, S0=s0_frac * p.S_max)
            m["episode_score"] = rc.episode_score(p, df)
            m["method"] = name
            rows.append(m)
            trajs[(sc.name, name)] = df
    return pd.DataFrame(rows), trajs


def fmt_table(df, cols, floatfmt=2):
    h = "| " + " | ".join(cols) + " |\n|" + "|".join(["---"] * len(cols)) + "|\n"
    for _, r in df.iterrows():
        h += "| " + " | ".join((f"{r[c]:.{floatfmt}f}" if isinstance(r[c], (float, np.floating)) else str(r[c])) for c in cols) + " |\n"
    return h


def make_plots(p, trajs, scenarios, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"reference": "#999999", "reference_gauge": "#555555", "rolling_lp": "#1f77b4", "dqn": "#d62728",
              "hybrid": "#2ca02c", "hybrid_adapted": "#17becf", "omniscient_lp": "#ff7f0e"}
    for scn in scenarios:
        fig, ax = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
        for (s, m), df in trajs.items():
            if s != scn:
                continue
            ax[0].plot(pd.to_datetime(df["date"]), df["end_storage_m3"] / 1e6, label=m, color=colors.get(m), lw=1.2)
            ax[1].plot(pd.to_datetime(df["date"]), df["generation_mwh"].rolling(7, min_periods=1).mean(), color=colors.get(m), lw=1.2)
        ax[0].axhline(p.S_reserve / 1e6, color="k", ls="--", lw=0.8, label="operating reserve")
        ax[0].axhline(p.S_terminal / 1e6, color="g", ls=":", lw=0.8, label="terminal target")
        ax[0].set_ylabel("end storage (MCM)"); ax[0].legend(ncol=4, fontsize=7); ax[0].set_title(f"{scn} (synthetic scenario)")
        ax[1].set_ylabel("generation, 7-day mean (MWh/day)")
        fig.tight_layout(); fig.savefig(os.path.join(out_dir, f"traj_{scn.replace('#','_')}.png"), dpi=110); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dqn"); ap.add_argument("--hybrid"); ap.add_argument("--hybrid-adapted", dest="hybrid_adapted")
    ap.add_argument("--s0", type=float, default=0.5)
    ap.add_argument("--forecast-seeds", type=int, default=1)
    ap.add_argument("--scenarios", default="all", help="comma list or 'all'")
    ap.add_argument("--bank", default=None, help="evaluate on first N scenarios of val bank instead (e.g. val:20)")
    ap.add_argument("--out-dir")
    args = ap.parse_args()

    p = HydroParams.from_config()
    if args.bank:
        bank = sg.load_bank(os.path.join(sg.BANK_DIR, "val_bank.pkl"))[: int(args.bank.split(":")[1])]
        base = {s.name: s for s in bank}
    else:
        base = sg.load_stress_suite()
    names = list(base) if args.scenarios == "all" else args.scenarios.split(",")
    scenarios = []
    for n in names:
        for k in range(args.forecast_seeds):
            scenarios.append(base[n] if k == 0 else resample_forecast(base[n], k))
    out = args.out_dir or os.path.join(str(paths.EVALUATION_DIR), f"eval_{datetime.now():%Y%m%d_%H%M%S}")
    os.makedirs(out, exist_ok=True)

    pols = build_policies(args)
    df, trajs = run_all(p, scenarios, pols, args.s0)
    df["base_scenario"] = df["scenario"].str.split("#").str[0]
    df.to_csv(os.path.join(out, "metrics_all.csv"), index=False)

    summ = (df.groupby("method")[KEY_COLS].mean(numeric_only=True)
            .reindex([m for m in METHOD_ORDER if m in df["method"].unique()]).reset_index())
    summ.to_csv(os.path.join(out, "summary_by_method.csv"), index=False)
    make_plots(p, trajs, [s.name for s in scenarios if "#" not in s.name], out)

    lines = ["# Component 3 v2 - Unified evaluation (SYNTHETIC scenarios)\n",
             f"Generated {datetime.now():%Y-%m-%d %H:%M}. Initial storage {args.s0*100:.0f}% of active storage. "
             f"Hard floor {p.floor_level:.2f} masl, reserve {p.reserve_fraction*100:.0f}%, terminal target "
             f"{p.terminal_fraction*100:.0f}%. Operating cost: N/A (no reliable tariff data).\n",
             "> All inflows, demand weights, forecasts and irrigation requirements are synthetic or assumed. "
             "Results characterise performance on simulated scenarios, not observed CEB operation.\n",
             "## Mean over scenarios\n", fmt_table(summ, ["method"] + KEY_COLS), "\n## Per scenario\n"]
    for bs, g in df.groupby("base_scenario", sort=False):
        g = g.groupby("method")[KEY_COLS].mean(numeric_only=True).reindex(
            [m for m in METHOD_ORDER if m in g["method"].unique()]).reset_index()
        lines += [f"\n### {bs}\n", fmt_table(g, ["method"] + KEY_COLS)]
    viol = df.groupby("method")[["floor_breach_days", "mass_balance_violation_days"]].sum().reset_index()
    lines += ["\n## Hard-constraint audit (sum over all scenarios)\n",
              fmt_table(viol, ["method", "floor_breach_days", "mass_balance_violation_days"], 0) + "\n"]
    with open(os.path.join(out, "evaluation_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(summ[["method", "energy_gwh", "storage_adjusted_energy_gwh", "spill_mcm", "spill_avoidable_mcm",
                "constraint_satisfaction_pct", "reserve_breach_pct", "terminal_storage_mcm", "episode_score",
                "decision_latency_ms_mean"]].round(2).to_string(index=False))
    print("report:", out)


if __name__ == "__main__":
    main()
