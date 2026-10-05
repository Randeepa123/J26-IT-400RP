"""
sim_core.py
===========
One simulator + one metric set for EVERY method (reference, omniscient LP, rolling LP, DQN, hybrid), so that
all comparisons use identical physics, constraints and scenarios.

A policy is any object with:
    name : str
    reset(scenario, start, n_days, params, S0)  -> None
    act(t, storage)                              -> turbine release REQUEST [m3] for day t (abs. index)
The simulator (hydro_core.HydroParams.step) enforces mandatory releases, the hard floor and the storage cap
(safety projection), so no policy can breach a physical constraint; projected requests are counted.

Causality: act() may use storage, units[t], weight[t], forecasts fc50/fc90/dwf[t] and observed inflow
inflow_m3[:t] (yesterday and before). It must NOT read inflow_m3[t:] (the omniscient LP is the one labelled
exception).
"""

import time
import numpy as np
import pandas as pd

from hydro_core import HydroParams, SECONDS_PER_DAY


class Policy:
    name = "policy"

    def reset(self, scenario, start, n_days, params, S0):
        self.sc, self.start, self.n_days, self.p = scenario, start, n_days, params

    def act(self, t, storage):
        raise NotImplementedError


class ReferenceRulePolicy(Policy):
    """
    Causal reference rule curve (v2). Same logic as reference_release_policy.KukuleReferencePolicy
    (run at full capacity when water allows, otherwise keep a buffer of 35% of active storage /
    25% of available water) but with a PERSISTENCE estimate of today's inflow (yesterday's observed
    inflow) instead of the legacy same-day inflow, so it is genuinely causal.
    """
    name = "reference"

    def __init__(self, gauge=False):
        """gauge=True: operator reads TODAY's inflow at the river gauge (legacy v1 behaviour, a stronger
        baseline that is not causal at daily resolution). gauge=False: persistence estimate (causal)."""
        self.gauge = gauge
        if gauge:
            self.name = "reference_gauge"

    def act(self, t, storage):
        p, sc = self.p, self.sc
        if self.gauge:
            est_in = sc.inflow_m3[t]
        else:
            est_in = sc.inflow_m3[t - 1] if t > 0 else sc.inflow_m3[0]
        mand = p.mandatory_m3(sc.month(t))
        w_avail = max(0.0, storage + est_in - p.evap_m3 - mand)
        cap = p.turbine_cap_m3(sc.units[t])
        if w_avail >= cap:
            return cap
        s_target = min(0.35 * p.S_max, max(0.0, w_avail * 0.25))
        return min(cap, max(0.0, w_avail - s_target))


class FixedPlanPolicy(Policy):
    """Plays back a precomputed turbine plan (used for the omniscient LP upper bound)."""
    name = "omniscient_lp"

    def __init__(self, plan, name="omniscient_lp"):
        self.plan, self.name = np.asarray(plan, float), name

    def act(self, t, storage):
        return float(self.plan[t - self.start])


def simulate(params, scenario, policy, start=0, n_days=365, S0=None, record_latency=True):
    """Run one episode and return (daily DataFrame, metrics dict)."""
    n_days = min(n_days, scenario.n_days - start)
    S = params.S_max if S0 is None else float(S0)
    policy.reset(scenario, start, n_days, params, S)
    rows, lat = [], []
    for k in range(n_days):
        t = start + k
        t0 = time.perf_counter()
        req = policy.act(t, S)
        lat.append((time.perf_counter() - t0) * 1000.0)
        d = params.step(S, float(scenario.inflow_m3[t]), int(scenario.units[t]), scenario.month(t), req,
                        float(scenario.weight[t]))
        d.update({"date": str(scenario.dates[t])[:10], "inflow_volume_m3": float(scenario.inflow_m3[t]),
                  "beginning_storage_m3": S, "request_m3": req, "weight": float(scenario.weight[t]),
                  "units": int(scenario.units[t])})
        rows.append(d); S = d["end_storage_m3"]
    df = pd.DataFrame(rows)
    return df, compute_metrics(params, df, np.array(lat), policy.name, scenario.name)


def compute_metrics(params, df, lat_ms, method, scenario_name):
    p = params
    n = len(df)
    turb, spill = df["turbine_release_m3"].sum(), df["spill_volume_m3"].sum()
    s_end = df["end_storage_m3"].values
    breach_floor = (s_end < p.S_floor - 1e-6).sum()
    unmet_days = (df["unmet_mandatory_m3"] > 1.0).sum()
    wb_bad = (df["water_balance_residual_m3"] > 1e-4).sum()
    any_viol = ((s_end < p.S_floor - 1e-6) | (df["unmet_mandatory_m3"] > 1.0) |
                (df["water_balance_residual_m3"] > 1e-4) |
                (df["turbine_release_m3"] > df["turbine_cap_m3"] + 1e-6)).sum()
    util = 100.0 * turb / (turb + spill) if (turb + spill) > 0 else 100.0
    lvl = df["pond_level_masl"].values
    return {
        "method": method, "scenario": scenario_name, "days": n,
        "energy_gwh": df["generation_mwh"].sum() / 1e3,
        "weighted_energy_gwh": df["weighted_generation_mwh"].sum() / 1e3,
        "capacity_factor_pct": 100.0 * df["generation_mwh"].sum() / (n * p.max_daily_mwh),
        # energy + value of the storage change (k_e * dS): stops policies "winning" by draining the pond
        "storage_adjusted_energy_gwh": (df["generation_mwh"].sum()
                                        + p.k_e * (s_end[-1] - df["beginning_storage_m3"].iloc[0])) / 1e3,
        "turbine_mcm": turb / 1e6, "spill_mcm": spill / 1e6,
        "spill_avoidable_mcm": df["spill_avoidable_m3"].sum() / 1e6,
        "spill_energy_equiv_gwh": df["spill_energy_equiv_mwh"].sum() / 1e3,
        "spill_days": int((df["spill_volume_m3"] > 1.0).sum()),
        "water_utilization_pct": util,
        "mwh_per_mcm_turbined": (df["generation_mwh"].sum() / (turb / 1e6)) if turb > 0 else 0.0,
        "floor_breach_days": int(breach_floor),
        "unmet_mandatory_days": int(unmet_days), "unmet_mandatory_mcm": df["unmet_mandatory_m3"].sum() / 1e6,
        "mass_balance_violation_days": int(wb_bad),
        "constraint_satisfaction_pct": 100.0 * (1.0 - any_viol / n),
        "projected_actions": int(df["action_projected"].sum()),
        "reserve_breach_days": int((s_end < p.S_reserve - 1e-6).sum()),
        "reserve_breach_pct": 100.0 * (s_end < p.S_reserve - 1e-6).mean(),
        "mean_storage_pct": 100.0 * s_end.mean() / p.S_max,
        "min_storage_pct": 100.0 * s_end.min() / p.S_max,
        "level_std_m": float(lvl.std()), "min_level_masl": float(lvl.min()),
        "initial_storage_mcm": float(df["beginning_storage_m3"].iloc[0]) / 1e6,
        "terminal_storage_mcm": float(s_end[-1]) / 1e6,
        "terminal_target_met": bool(s_end[-1] >= p.S_terminal - 1.0),
        "opportunity_loss_proxy_gwh": (df["weighted_spill_energy_equiv_mwh"].sum()) / 1e3,
        "operating_cost_lkr": None,           # N/A: no reliable tariff / O&M data (proposal: 'where reliable cost data are available')
        "decision_latency_ms_mean": float(lat_ms.mean()), "decision_latency_ms_p95": float(np.percentile(lat_ms, 95)),
    }
