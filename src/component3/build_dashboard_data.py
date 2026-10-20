"""
build_dashboard_data.py - precompute the tables the Grafana dashboards (via api_server.py) read.

Writes outputs/dashboard_cache/*.csv from the saved evaluation / multi-seed / adaptation / training outputs and from
year-long simulations of every method on the 9 stress scenarios (so the dashboard never has to run a model for those views).
Re-run after retraining or re-evaluating:   python src/component3/build_dashboard_data.py
All numbers describe the MODELLED study dataset.
"""
import os
import json
import glob
import numpy as np
import pandas as pd

import paths
import scenario_generator as sg
import sim_core as sm
import rolling_lp as rl
import rl_common as rc
from hydro_core import HydroParams, SECONDS_PER_DAY

CACHE = paths.DASHBOARD_CACHE_DIR
NAMES = {"reference": "Reference rule (causal)", "reference_gauge": "Reference rule (reads gauge)",
         "rolling_lp": "Rolling LP", "dqn": "DQN", "hybrid": "Hybrid LP-DQN", "omniscient_lp": "Perfect-foresight LP (bound)"}
ORDER = list(NAMES)
SCEN_NAMES = {"test_year_real_sim": "1 Normal year (held-out)", "drought_el_nino": "2 El Nino drought (270 days)",
              "flood_year": "3 Flood year (3 extreme storms)", "vesak_flood": "4 Flood over Vesak week",
              "dry_christmas": "5 Dry spell over Christmas", "forecast_bias_high": "6 Forecasts 40% too wet",
              "forecast_bias_low": "7 Forecasts 40% too dry", "wide_forecast_spread": "8 Very wide forecast spread",
              "double_outage": "9 Unit outages (60 d one unit, 3 d none)"}


def pretty(df, col="method"):
    df = df.copy()
    df[col] = df[col].map(NAMES).fillna(df[col])
    return df


def build_trajectories(p):
    suite = sg.load_stress_suite()
    pols = {"reference": sm.ReferenceRulePolicy(), "reference_gauge": sm.ReferenceRulePolicy(gauge=True),
            "rolling_lp": rl.RollingLPPolicy(), "omniscient_lp": rl.OmniscientLPPolicy()}
    models = json.load(open(paths.SELECTED_MODELS_JSON))
    from dqn_policy import DQNPolicy
    from hybrid_policy import HybridPolicy
    pols["dqn"] = DQNPolicy(str(paths.resolve(models["dqn"]["path"])))
    pols["hybrid"] = HybridPolicy(str(paths.resolve(models["hybrid"]["path"])))
    rows, kpis = [], []
    for sname, sc in suite.items():
        for m in ORDER:
            df, met = sm.simulate(p, sc, pols[m], 0, 365, S0=0.5 * p.S_max)
            met["episode_score"] = rc.episode_score(p, df)
            kpis.append({"scenario_id": sname, "scenario": SCEN_NAMES.get(sname, sname), "method_id": m, "method": NAMES[m],
                         **{k: met[k] for k in ("energy_gwh", "weighted_energy_gwh", "storage_adjusted_energy_gwh",
                                                "spill_mcm", "spill_avoidable_mcm", "unmet_mandatory_days", "terminal_storage_mcm",
                                                "reserve_breach_pct", "constraint_satisfaction_pct", "min_storage_pct",
                                                "water_utilization_pct", "episode_score")}})
            t = pd.DataFrame({
                "scenario_id": sname, "method_id": m, "method": NAMES[m],
                "time": pd.to_datetime(df["date"]).astype("int64") // 10 ** 6 if False else pd.to_datetime(df["date"]).map(lambda x: int(x.timestamp() * 1000)),
                "date": df["date"].values,
                "inflow_m3s": df["inflow_volume_m3"].values / SECONDS_PER_DAY,
                "release_m3s": df["turbine_release_m3"].values / SECONDS_PER_DAY,
                "spill_m3s": df["spill_volume_m3"].values / SECONDS_PER_DAY,
                "storage_pct": df["end_storage_m3"].values / p.S_max * 100.0,
                "level_masl": df["pond_level_masl"].values,
                "generation_mwh": df["generation_mwh"].values,
                "weight": df["weight"].values,
                "unmet_release_m3s": df["unmet_mandatory_m3"].values / SECONDS_PER_DAY,
                "reserve_pct": p.reserve_fraction * 100.0, "target_pct": p.terminal_fraction * 100.0})
            rows.append(t)
        print("  trajectories:", sname, flush=True)
    return pd.concat(rows, ignore_index=True), pd.DataFrame(kpis)


def main():
    os.makedirs(CACHE, exist_ok=True)
    p = HydroParams.from_config()
    E = paths.EVALUATION_DIR / "final"

    # 1. year-long trajectories + per-scenario KPIs (simulated now with the selected models)
    traj, kpis = build_trajectories(p)
    traj.round(4).to_csv(CACHE / "trajectories.csv", index=False)
    kpis.round(4).to_csv(CACHE / "scenario_kpis.csv", index=False)

    # 2. scoreboard, heatmap, constraint audit (saved evaluation, 9 scenarios x 3 forecast seeds)
    m = pd.read_csv(E / "metrics_all.csv")
    sb = m.groupby("method").mean(numeric_only=True).reindex(ORDER).reset_index()
    sb["terminal_target_met_pct"] = (m.groupby("method")["terminal_target_met"].mean().reindex(ORDER) * 100).values
    pretty(sb).round(4).to_csv(CACHE / "scoreboard.csv", index=False)
    hm = m.groupby(["base_scenario", "method"])[["episode_score", "storage_adjusted_energy_gwh", "unmet_mandatory_days",
                                                 "spill_avoidable_mcm", "terminal_storage_mcm"]].mean().reset_index()
    hm["scenario"] = hm["base_scenario"].map(SCEN_NAMES).fillna(hm["base_scenario"])
    pretty(hm).round(4).to_csv(CACHE / "heatmap.csv", index=False)
    audit = m.groupby("method")[["floor_breach_days", "mass_balance_violation_days"]].sum().reindex(ORDER).reset_index()
    audit["runs"] = m.groupby("method").size().reindex(ORDER).values
    pretty(audit).to_csv(CACHE / "constraint_audit.csv", index=False)

    # 3. multi-seed (training-seed) statistics
    ss = pd.read_csv(paths.MULTISEED_DIR / "seed_summary.csv")
    agg = ss.groupby("method").agg(n_seeds=("seed", "count"), **{f"{c}_mean": (c, "mean") for c in
                                   ["episode_score", "storage_adjusted_energy_gwh", "unmet_mandatory_days", "spill_avoidable_mcm",
                                    "terminal_storage_mcm", "reserve_breach_pct"]},
                                   score_std=("episode_score", lambda x: x.std(ddof=1) if len(x) > 1 else 0.0),
                                   energy_std=("storage_adjusted_energy_gwh", lambda x: x.std(ddof=1) if len(x) > 1 else 0.0)).reindex(
        ["reference_gauge", "rolling_lp", "dqn", "hybrid", "omniscient_lp"]).reset_index()
    for c in ("score_std", "energy_std"):                  # spread is only meaningful for methods trained with several seeds
        agg.loc[agg["n_seeds"] < 2, c] = np.nan
    pretty(agg).round(4).to_csv(CACHE / "multiseed.csv", index=False)
    pt = pd.read_csv(paths.MULTISEED_DIR / "paired_tests_vs_rolling_lp.csv")
    pt = pretty(pt)
    pt["significant_5pct"] = np.where(pt["t_test_p(seeds)"] < 0.05, "yes", "no")
    pt["metric"] = pt["metric"].map({"episode_score": "Composite score", "storage_adjusted_energy_gwh": "Energy (GWh)",
                                     "unmet_mandatory_days": "River shortfall days (lower = better)"}).fillna(pt["metric"])
    pt.round(4).to_csv(CACHE / "paired_tests.csv", index=False)
    ss_p = pretty(ss).round(4)
    ss_p["seed_label"] = ss_p["seed"].map(lambda x: "no training" if x < 0 else f"seed {int(x):02d}")
    ss_p.to_csv(CACHE / "seed_points.csv", index=False)

    # 4. adaptation experiment (final hybrid, regime shift)
    ad_dir = paths.ADAPTATION_DIR / "hybrid_h3_shift_year_tol6"
    ac = pd.read_csv(ad_dir / "adaptation_comparison.csv", index_col=0).reset_index().rename(columns={"index": "method"})
    ac["method"] = ac["method"].map({"frozen": "Hybrid (frozen)", "adapted": "Hybrid (adapted)", "rolling_lp": "Rolling LP",
                                     "omniscient_lp": "Perfect-foresight LP (bound)"}).fillna(ac["method"])
    ac.round(4).to_csv(CACHE / "adaptation.csv", index=False)
    pd.read_csv(ad_dir / "adaptation_events.csv").round(3).to_csv(CACHE / "adaptation_events.csv", index=False)

    # 5. training / validation curves
    cur = []
    for f in sorted(glob.glob(str(paths.TRAINING_RUNS_DIR / "*" / "train_config.json"))):
        c = json.load(open(f))
        run = os.path.basename(os.path.dirname(f))
        kind = "Hybrid LP-DQN" if "_hyb_" in run else "DQN"
        label = f"{kind} seed {c['args']['seed']} ({run.split('_')[0]})"
        for h in c.get("val_history", []):
            cur.append({"run": run, "label": label, "kind": kind, "seed": c["args"]["seed"], "steps": h["timesteps"], "val_score": h["val_score"],
                        "reserve_breach_pct": h.get("reserve_breach_pct"), "terminal_storage_mcm": h.get("terminal_storage_mcm")})
    cur = pd.DataFrame(cur)
    cur.round(4).to_csv(CACHE / "training_curves.csv", index=False)
    # aggregated per method: mean and min-max range across training seeds at every validation checkpoint (wide table)
    agg = cur.groupby(["kind", "steps"])["val_score"].agg(["mean", "min", "max"]).reset_index()
    wide = pd.DataFrame({"steps": sorted(agg["steps"].unique())})
    for kind in ("Hybrid LP-DQN", "DQN"):
        a = agg[agg["kind"] == kind].set_index("steps")
        for stat_, lab in (("mean", "mean"), ("min", "lowest seed"), ("max", "highest seed")):
            wide[f"{kind} ({lab})"] = wide["steps"].map(a[stat_])
    wide.round(3).to_csv(CACHE / "training_summary.csv", index=False)

    # 6. reference lines for the dashboards
    json.dump({"floor_masl": p.floor_level, "fsl_masl": p.FSL, "reserve_pct": p.reserve_fraction * 100,
               "terminal_pct": p.terminal_fraction * 100, "installed_mw": p.installed_mw, "max_daily_mwh": p.max_daily_mwh,
               "active_storage_mcm": p.S_max / 1e6, "rolling_lp_val_score": json.load(open(paths.SELECTED_MODELS_JSON))["hybrid"]["rolling_lp_holdout_val_score"]},
              open(CACHE / "constants.json", "w"), indent=1)
    print("dashboard cache written to", CACHE, "->", sorted(os.listdir(CACHE)))


if __name__ == "__main__":
    main()
