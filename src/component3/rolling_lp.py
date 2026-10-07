"""
rolling_lp.py
=============
v2 Linear-Programming layer for Component 3.

* solve_lp()            : one multi-period LP (HiGHS) with
                            - water balance incl. mandatory (environmental + irrigation) weir release
                              with a penalised slack (always feasible, shortfall reported),
                            - hard storage floor / cap, turbine cap (units),
                            - SOFT operating reserve (penalised slack) and terminal-storage target (penalised slack),
                            - demand-weighted energy value  w_t * k_e  per m3 turbined,
                            - spill penalty (energy-equivalent hedge) and a terminal water value.
* RollingLPPolicy       : causal Model-Predictive-Control benchmark. Every day it re-solves a 15-day LP on the
                          P50/P90 inflow FORECAST and demand-weight forecast, applies only day-1 and then the
                          actual inflow arrives. This is the fair, deployable LP comparator for DQN/hybrid.
* OmniscientLPPolicy    : whole-horizon LP with PERFECT foresight of inflow (theoretical upper bound, labelled).

Linear energy model: E = w * k_e * V_turb (k_e from rated net head). The simulator evaluates exact
non-linear physics afterwards (hydro_core.HydroParams.generation).
"""

import time
import numpy as np
import scipy.sparse as sp
import scipy.optimize as opt

from hydro_core import SECONDS_PER_DAY
import rl_common as rc
from sim_core import Policy

BIG = 10.0   # multiple of k_e charged per m3 of unmet mandatory release


def solve_lp(p, inflow, units, months, weights, S0, S_term_target, c_spill_ratio=0.25,
             terminal_value_ratio=0.5, reserve_penalty_ratio=0.3, terminal_penalty_ratio=5.0,
             storage_head_incentive=1e-7, smooth_ratio=0.0):
    T = len(inflow)
    k = p.k_e
    cap = np.array([p.turbine_cap_m3(u) for u in units])
    mand = np.array([p.mandatory_m3(m) for m in months])
    w = np.asarray(weights, float)
    smooth = smooth_ratio > 0.0 and T > 1          # optional day-to-day release smoothing (deployment plans only)
    nv = 5 * T + 1 + (T if smooth else 0)
    iv, isp, iS, iu, ir, itt = 0, T, 2 * T, 3 * T, 4 * T, 5 * T
    idd = 5 * T + 1

    c = np.zeros(nv)
    c[iv:iv + T] = -k * w
    c[isp:isp + T] = c_spill_ratio * k * w
    c[iS:iS + T] = -storage_head_incentive
    c[iS + T - 1] += -terminal_value_ratio * k * w.mean()
    c[iu:iu + T] = BIG * k
    c[ir:ir + T] = reserve_penalty_ratio * k * w
    c[itt] = terminal_penalty_ratio * k * w.mean()
    if smooth:
        c[idd:idd + T] = smooth_ratio * k * w.mean()

    rows = np.arange(T)
    A = sp.coo_matrix((np.r_[np.ones(T), np.ones(T), np.ones(T), -np.ones(T), -np.ones(T - 1)],
                       (np.r_[rows, rows, rows, rows, rows[1:]],
                        np.r_[iv + rows, isp + rows, iS + rows, iu + rows, iS + rows[:-1]])),
                      shape=(T, nv)).tocsr()
    b = np.asarray(inflow, float) - p.evap_m3 - mand
    b[0] += S0

    # reserve (soft)  -S_t - r_t <= -S_reserve ; terminal (soft) -S_T - tt <= -S_term
    Aub = sp.coo_matrix((np.r_[-np.ones(T), -np.ones(T), [-1.0, -1.0]],
                         (np.r_[rows, rows, T, T], np.r_[iS + rows, ir + rows, iS + T - 1, itt])),
                        shape=(T + 1, nv)).tocsr()
    bub = np.r_[np.full(T, -p.S_reserve), -S_term_target]
    if smooth:                                         # d_t >= |v_t - v_(t-1)|  (t = 1..T-1)
        m = np.arange(1, T)
        As = sp.coo_matrix((np.r_[np.ones(T - 1), -np.ones(T - 1), -np.ones(T - 1), -np.ones(T - 1), np.ones(T - 1), -np.ones(T - 1)],
                            (np.r_[m - 1, m - 1, m - 1, m - 1 + (T - 1), m - 1 + (T - 1), m - 1 + (T - 1)],
                             np.r_[iv + m, iv + m - 1, idd + m, iv + m, iv + m - 1, idd + m])),
                           shape=(2 * (T - 1), nv)).tocsr()
        Aub = sp.vstack([Aub, As]).tocsr()
        bub = np.r_[bub, np.zeros(2 * (T - 1))]

    lb = np.zeros(nv); ub = np.full(nv, np.inf)
    ub[iv:iv + T] = cap
    lb[iS:iS + T] = p.S_floor; ub[iS:iS + T] = p.S_max
    ub[iu:iu + T] = mand
    t0 = time.perf_counter()
    res = opt.linprog(c, A_ub=Aub, b_ub=bub, A_eq=A, b_eq=b, bounds=np.c_[lb, ub], method="highs")
    ms = (time.perf_counter() - t0) * 1000.0
    if not res.success:
        return {"success": False, "status": res.status, "message": res.message, "solve_ms": ms}
    x = res.x
    return {"success": True, "status": 0, "v": x[iv:iv + T], "spill": x[isp:isp + T], "S": x[iS:iS + T],
            "unmet": x[iu:iu + T], "reserve_short": x[ir:ir + T], "term_short": x[itt], "obj": res.fun,
            "solve_ms": ms}


class RollingLPPolicy(Policy):
    """Causal rolling-horizon (MPC) LP on forecasts."""
    name = "rolling_lp"

    def __init__(self, horizon=15, p90_blend=0.25, p90_leads=4, c_spill_ratio=0.25,
                 terminal_value_ratio=0.5, reserve_penalty_ratio=None, p90_cap_ratio=2.0, bias_correction=True,
                 bias_gain=0.7, smooth_ratio=0.0, name=None):
        self.horizon, self.p90_blend, self.p90_leads = horizon, p90_blend, p90_leads
        self.c_spill_ratio, self.terminal_value_ratio = c_spill_ratio, terminal_value_ratio
        self.reserve_penalty_ratio, self.p90_cap_ratio = reserve_penalty_ratio, p90_cap_ratio
        self.bias_correction, self.bias_gain = bias_correction, bias_gain
        self.smooth_ratio = smooth_ratio
        if name:
            self.name = name
        self.last = None
        self.n_fail = 0

    def reset(self, scenario, start, n_days, params, S0):
        super().reset(scenario, start, n_days, params, S0)
        self.end_abs = start + n_days
        self.last, self.n_fail = None, 0

    def plan(self, t, storage):
        """Solve the horizon LP at day t; returns the solution dict (also stored in self.last)."""
        sc, p = self.sc, self.p
        H = min(self.horizon, self.end_abs - t)
        idx = np.arange(t, t + H)
        q50, q90 = sc.fc50[t, :H].astype(float), sc.fc90[t, :H].astype(float)
        if self.bias_correction:                               # online correction from recent forecast errors
            corr = float(np.clip(np.exp(self.bias_gain * rc.forecast_bias_log(sc, t, self.start)), 0.5, 2.0))
            q50, q90 = q50 * corr, q90 * corr
        blend = np.where(np.arange(H) < self.p90_leads, self.p90_blend, 0.0)
        q90c = np.minimum(q90, self.p90_cap_ratio * q50)      # a very wide P90 must not inflate the plan
        inflow = q50 * (1 - blend) + q90c * blend
        w = np.r_[sc.weight[t], sc.dwf[t, 1:H]].astype(float)
        months = [sc.month(i) for i in idx]
        s_term = p.S_terminal if (t + self.horizon >= self.end_abs) else p.S_reserve
        rpr = self.reserve_penalty_ratio if self.reserve_penalty_ratio is not None else (8.0 if p.enforce_reserve else 0.3)
        sol = solve_lp(p, inflow, sc.units[idx], months, w, storage, s_term, self.c_spill_ratio,
                       self.terminal_value_ratio, rpr, smooth_ratio=self.smooth_ratio)
        self.last = sol
        return sol

    def act(self, t, storage):
        sol = self.plan(t, storage)
        if not sol["success"]:
            self.n_fail += 1
            return self.p.turbine_cap_m3(self.sc.units[t]) * 0.5
        return float(sol["v"][0])


class OmniscientLPPolicy(Policy):
    """Whole-horizon LP with perfect foresight (upper bound, NOT deployable)."""
    name = "omniscient_lp"

    def __init__(self, c_spill_ratio=0.0025, name=None):
        self.c_spill_ratio = c_spill_ratio
        if name:
            self.name = name

    def reset(self, scenario, start, n_days, params, S0):
        super().reset(scenario, start, n_days, params, S0)
        idx = np.arange(start, start + n_days)
        months = [scenario.month(i) for i in idx]
        sol = solve_lp(params, scenario.inflow_m3[idx], scenario.units[idx], months, scenario.weight[idx], S0,
                       params.S_terminal, self.c_spill_ratio, terminal_value_ratio=0.0,
                       reserve_penalty_ratio=8.0 if params.enforce_reserve else 0.3)
        if not sol["success"]:
            raise RuntimeError(f"Omniscient LP failed: {sol}")
        self.sol, self.plan_v = sol, sol["v"]

    def act(self, t, storage):
        return float(self.plan_v[t - self.start])
