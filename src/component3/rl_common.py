"""
rl_common.py
============
Shared observation builder and reward definition for the v2 DQN, the hybrid LP-DQN and the validation scorer,
so the environment, the evaluator and every learned policy use IDENTICAL state and reward definitions.

Observation (OBS_DIM = 23, all roughly in [-1.5, 1.5]):
   0 storage fraction                      1 margin over operating reserve (clipped)
   2 yesterday inflow (log scale)          3 7-day mean inflow     4 30-day mean inflow (drought index)
   5-8 P50 forecast: lead0, lead1-2, lead3-6, lead7-14 (log scale)
   9-10 P90 forecast: lead0-2 max, lead3-6 max
  11 flood risk (forecast P90 volume that cannot be absorbed by turbines + free storage over next 3 days)
  12 demand weight today   13 mean forecast weight lead1-3   14 mean forecast weight lead4-14
  15 max demand weight next 7 days (festival flag)
  16 mandatory release today / turbine cap   17 units today   18 min units next 7 days
  19-20 season sin/cos     21 fraction of episode remaining   22 online forecast bias (mean log observed/forecast over 14 days)

Reward (per day), all in "normalised energy" units (1.0 = 70 MW for 24 h):
   + w_t * E_t / E_max
   - lam_spill  * min(3, spill_energy_equiv_weighted / E_max)         spill = lost energy
   - lam_res    * max(0, S_reserve - S_end) / S_max                    operating reserve (soft)
   - lam_unmet  * unmet_mandatory / mandatory_required                 environmental / irrigation
   - lam_term   * max(0, S_terminal - S_end) / S_max      (final day only)  terminal storage target
Training adds potential-based shaping  gamma*Phi(S') - Phi(S),  Phi = beta * k_e * S * w_bar / E_max
(policy-invariant; it only helps credit assignment for storage value).
"""

import numpy as np

OBS_DIM = 23
QREF = 30.0 * 86400.0          # 30 m3/s reference inflow


def lq(x):
    return float(np.clip(np.log(max(float(x), 1.0) / QREF) / 2.5, -1.5, 1.5))


def forecast_bias_log(sc, t, start, window=14):
    """Mean log(observed inflow / lead-1 P50 forecast) over the last `window` realised days: an online forecast-bias
    estimate usable by both the DQN state and the rolling LP (0 when fewer than 3 days of evidence)."""
    lo = max(start + 1, t - window)
    if t - lo < 3:
        return 0.0
    d = np.arange(lo, t)
    r = np.log(np.maximum(sc.inflow_m3[d], 1.0) / np.maximum(sc.fc50[d - 1, 1], 1.0))
    return float(np.clip(r.mean(), -1.5, 1.5))


def build_obs(p, sc, t, S, start, end_abs, extra=None):
    cap_full = p.turbine_cap_m3(2)
    cap_today = p.turbine_cap_m3(sc.units[t])
    obs = np.zeros(OBS_DIM, dtype=np.float32)
    obs[0] = S / p.S_max
    obs[1] = np.clip((S - p.S_reserve) / p.S_max, -1.0, 1.0)
    if t > start:
        lo7, lo30 = max(start, t - 7), max(start, t - 30)
        obs[2] = lq(sc.inflow_m3[t - 1])
        obs[3] = lq(sc.inflow_m3[lo7:t].mean())
        obs[4] = lq(sc.inflow_m3[lo30:t].mean())
    else:                                            # first day: fall back on today's forecast
        q = sc.fc50[t, 0]
        obs[2] = obs[3] = obs[4] = lq(q)
    f50, f90 = sc.fc50[t], sc.fc90[t]
    obs[5] = lq(f50[0]); obs[6] = lq(f50[1:3].mean()); obs[7] = lq(f50[3:7].mean()); obs[8] = lq(f50[7:15].mean())
    obs[9] = lq(f90[0:3].max()); obs[10] = lq(f90[3:7].max())
    free = p.S_max - S
    unabsorbed = max(0.0, float(f90[0:3].sum()) - 3.0 * cap_full - free)
    obs[11] = min(unabsorbed / p.S_max, 3.0) / 3.0
    w, dwf = float(sc.weight[t]), sc.dwf[t]
    obs[12] = (w - 1.0) / 0.5
    obs[13] = (float(dwf[1:4].mean()) - 1.0) / 0.5
    obs[14] = (float(dwf[4:15].mean()) - 1.0) / 0.5
    obs[15] = (max(w, float(dwf[1:8].max())) - 1.0) / 0.5
    obs[16] = p.mandatory_m3(sc.month(t)) / cap_full
    obs[17] = sc.units[t] / 2.0
    obs[18] = sc.units[t:t + 8].min() / 2.0
    doy = (sc.dates[t].astype("datetime64[D]") - sc.dates[t].astype("datetime64[Y]")).astype(int) + 1
    obs[19] = np.sin(2 * np.pi * doy / 365.25); obs[20] = np.cos(2 * np.pi * doy / 365.25)
    obs[21] = (end_abs - t) / 365.0
    obs[22] = forecast_bias_log(sc, t, start)           # online forecast-bias estimate (log ratio)
    return obs


def reward_terms(p, d, weight, is_last, rw=None):
    """Unshaped reward and its components from a hydro_core step dict `d`."""
    rw = rw or p.reward_weights
    e_max = p.max_daily_mwh
    gen = weight * d["generation_mwh"] / e_max
    spill_pen = rw.get("spill_energy_loss", 1.0) * min(3.0, d["weighted_spill_energy_equiv_mwh"] / e_max)
    res_pen = rw.get("reserve_shortfall", 0.5) * max(0.0, p.S_reserve - d["end_storage_m3"]) / p.S_max
    unmet_pen = rw.get("unmet_mandatory", 10.0) * d["unmet_mandatory_m3"] / max(d["mandatory_required_m3"], 1.0)
    term_pen = 0.0
    if is_last:
        term_pen = rw.get("terminal_shortfall", 5.0) * max(0.0, p.S_terminal - d["end_storage_m3"]) / p.S_max
    r = gen - spill_pen - res_pen - unmet_pen - term_pen
    return r, {"gen": gen, "spill": spill_pen, "reserve": res_pen, "unmet": unmet_pen, "terminal": term_pen}


def potential(p, S, beta=0.5):
    return beta * p.k_e * S / p.max_daily_mwh


def episode_score(p, df):
    """Sum of unshaped daily rewards over a simulate() DataFrame (used for validation / model selection)."""
    n = len(df)
    tot = 0.0
    for i, row in enumerate(df.to_dict("records")):
        r, _ = reward_terms(p, row, row["weight"], i == n - 1)
        tot += r
    return tot
