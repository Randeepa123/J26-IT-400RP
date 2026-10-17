"""
policy_adaptation.py
====================
DQN policy adaptation (proposal 4.3.3 / Phase 5): "Actual operation -> new data -> DQN adaptation".

Online loop over a stream of ACTUAL days (a scenario):
  * the deployed policy (DQN or residual hybrid) operates day by day;
  * every `adapt_every` days a COPY of the model is fine-tuned (low learning rate, small epsilon) on a mixture of
        - REPLAYED RECENT REAL DAYS (the last `window` realised days, with the forecasts that were actually issued),
        - the original training bank (rehearsal; limits catastrophic forgetting);
  * the candidate is DEPLOYED ONLY IF it (a) beats the current model on the recent window and (b) does not regress on a
    guard set of validation scenarios. Otherwise it is rejected. Every decision is logged.

Experiment: `shift_year` = normal first half then a persistent regime shift (drought + over-wet forecast bias), compared for
frozen vs adapted vs rolling-LP. Synthetic scenarios only.

Usage:
  python policy_adaptation.py --model <zip> --kind hybrid|dqn --scenario shift_year [--out-dir DIR]
"""
import os
import io
import json
import argparse
from datetime import datetime

import numpy as np
import pandas as pd
import torch_compat  # noqa: F401  (fixes DQN.load on newer torch)
import torch
torch.set_num_threads(1)
import gymnasium as gym
from stable_baselines3 import DQN

import paths
import scenario_generator as sg
import sim_core as sm
import rolling_lp as rl
import rl_common as rc
from hydro_core import HydroParams
from kukule_env_v2 import KukuleEnvV2
from hybrid_policy import HybridEnv, HybridPolicy
from dqn_policy import DQNPolicy

WORKSPACE = os.path.dirname(os.path.abspath(__file__))


class MixedEnv(gym.Env):
    """Samples recent-real-window episodes with probability `p_recent`, otherwise full-year bank episodes."""

    def __init__(self, env_cls, params, bank, recent_scen, p_recent=0.5, seed=0):
        super().__init__()
        self.bank_env = env_cls(params, bank, seed=seed)
        self.recent_env = env_cls(params, [recent_scen], episode_days=recent_scen.n_days, seed=seed + 1,
                                  terminal_penalty=False)
        self.observation_space, self.action_space = self.bank_env.observation_space, self.bank_env.action_space
        self.rng, self.q, self.cur = np.random.default_rng(seed), p_recent, self.bank_env

    def reset(self, seed=None, options=None):
        self.cur = self.recent_env if self.rng.random() < self.q else self.bank_env
        return self.cur.reset(seed=seed, options=options)

    def step(self, a):
        return self.cur.step(a)


def clone_model(model):
    buf = io.BytesIO()
    model.save(buf)
    buf.seek(0)
    return buf


def fine_tune(model, env, steps, lr):
    buf = clone_model(model)
    new = DQN.load(buf, env=env, device="cpu",
                   custom_objects={"learning_rate": lr, "exploration_initial_eps": 0.05, "exploration_final_eps": 0.05,
                                   "exploration_fraction": 0.01, "learning_starts": 2000, "buffer_size": 100000,
                                   "lr_schedule": lambda _: lr})
    new.exploration_rate = 0.05
    new.learn(total_timesteps=steps, reset_num_timesteps=True)
    return new


def score_policy(params, policy, scen, S0, start=0, days=None):
    df, m = sm.simulate(params, scen, policy, start, days or scen.n_days, S0=S0)
    return rc.episode_score(params, df), m


def run_online(params, base_model_path, kind, scen, bank, guard_bank, adapt=True, adapt_every=30, window=60,
               steps=15000, lr=5e-5, s0_frac=0.5, seed=0, accept_margin=0.05, guard_tol=1.5, log=print):
    """Operate `scen` day by day; return (daily DataFrame, metrics, event log)."""
    env_cls = HybridEnv if kind == "hybrid" else KukuleEnvV2
    pol_cls = HybridPolicy if kind == "hybrid" else DQNPolicy
    policy = pol_cls(base_model_path)
    S = s0_frac * params.S_max
    policy.reset(scen, 0, scen.n_days, params, S)
    rows, events, S_hist = [], [], [S]
    for t in range(scen.n_days):
        req = policy.act(t, S)
        d = params.step(S, float(scen.inflow_m3[t]), int(scen.units[t]), scen.month(t), req, float(scen.weight[t]))
        d.update({"date": str(scen.dates[t])[:10], "weight": float(scen.weight[t]), "inflow_volume_m3": float(scen.inflow_m3[t]),
                  "beginning_storage_m3": S, "request_m3": req, "units": int(scen.units[t])})
        rows.append(d); S = d["end_storage_m3"]; S_hist.append(S)
        day = t + 1
        if adapt and day % adapt_every == 0 and day >= window and day < scen.n_days - 5:
            lo = day - window
            recent = sg.slice_scenario(scen, lo, day, name=f"recent_{lo}_{day}")
            S_lo = S_hist[lo]
            cur_pol = pol_cls(policy.model)                      # separate object: scoring must not reset the live policy
            cur_score, _ = score_policy(params, cur_pol, recent, S_lo)
            mixed = MixedEnv(env_cls, params, bank, recent, p_recent=0.5, seed=seed + day)
            cand_model = fine_tune(policy.model, mixed, steps, lr)
            cand = pol_cls(cand_model)
            new_score, _ = score_policy(params, cand, recent, S_lo)
            g_old = np.mean([score_policy(params, cur_pol, g, 0.5 * params.S_max)[0] for g in guard_bank])
            g_new = np.mean([score_policy(params, cand, g, 0.5 * params.S_max)[0] for g in guard_bank])
            ok = (new_score >= cur_score + accept_margin) and (g_new >= g_old - guard_tol)
            events.append({"day": day, "recent_old": cur_score, "recent_new": new_score, "guard_old": float(g_old),
                           "guard_new": float(g_new), "accepted": bool(ok)})
            log(f"  adapt@day {day}: recent {cur_score:6.2f}->{new_score:6.2f} guard {g_old:6.2f}->{g_new:6.2f} "
                f"{'ACCEPT' if ok else 'reject'}")
            if ok:
                policy.model = cand_model
    df = pd.DataFrame(rows)
    m = sm.compute_metrics(params, df, np.zeros(len(df)), "adapted" if adapt else "frozen", scen.name)
    m["episode_score"] = rc.episode_score(params, df)
    return df, m, events


def build_shift_year(seed=11):
    """Held-out year; at day 150 a persistent regime shift: 200-day drought AND over-wet (x1.8) forecasts."""
    suite = sg.load_stress_suite()
    base = suite["test_year_real_sim"]
    drought = suite["drought_el_nino"]
    shift = 150
    inflow = base.inflow_m3.copy()
    inflow[shift:] = np.minimum(inflow[shift:], drought.inflow_m3[shift:]) * 0.9
    rng = np.random.default_rng([555, seed])
    f50, f90, dwf = sg.make_forecasts(inflow, base.weight, rng)
    f50[shift:] *= 1.8; f90[shift:] *= 1.8
    return sg.Scenario("shift_year", base.dates, inflow, base.units, base.weight, f50, f90, dwf,
                       {"desc": "regime shift at day 150: drought + forecasts biased 1.8x wet", "kind": "stress"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--kind", choices=["hybrid", "dqn"], default="hybrid")
    ap.add_argument("--scenario", default="shift_year")
    ap.add_argument("--steps", type=int, default=15000)
    ap.add_argument("--adapt-every", type=int, default=30)
    ap.add_argument("--guard-tol", type=float, default=1.5, help="max allowed drop of the guard-set score for an update to be accepted")
    ap.add_argument("--out-dir")
    a = ap.parse_args()

    p = HydroParams.from_config()
    bank = sg.load_bank(os.path.join(sg.BANK_DIR, "train_bank.pkl"))
    guard = sg.load_bank(os.path.join(sg.BANK_DIR, "val_bank.pkl"))[:6]
    scen = build_shift_year() if a.scenario == "shift_year" else sg.load_stress_suite()[a.scenario]
    out = a.out_dir or os.path.join(str(paths.ADAPTATION_DIR), f"{a.kind}_{a.scenario}_{datetime.now():%Y%m%d_%H%M%S}")
    os.makedirs(out, exist_ok=True)

    print(f"scenario {scen.name}: {scen.meta.get('desc','')}")
    res = {}
    df_f, m_f, _ = run_online(p, a.model, a.kind, scen, bank, guard, adapt=False)
    res["frozen"] = m_f
    df_a, m_a, ev = run_online(p, a.model, a.kind, scen, bank, guard, adapt=True, adapt_every=a.adapt_every, steps=a.steps, guard_tol=a.guard_tol)
    res["adapted"] = m_a
    df_r, m_r = sm.simulate(p, scen, rl.RollingLPPolicy(), 0, scen.n_days, S0=0.5 * p.S_max)
    m_r["episode_score"] = rc.episode_score(p, df_r); res["rolling_lp"] = m_r
    df_o, m_o = sm.simulate(p, scen, rl.OmniscientLPPolicy(), 0, scen.n_days, S0=0.5 * p.S_max)
    m_o["episode_score"] = rc.episode_score(p, df_o); res["omniscient_lp"] = m_o

    cols = ["energy_gwh", "storage_adjusted_energy_gwh", "spill_mcm", "unmet_mandatory_days", "reserve_breach_pct",
            "terminal_storage_mcm", "constraint_satisfaction_pct", "episode_score"]
    tab = pd.DataFrame({k: {c: v[c] for c in cols} for k, v in res.items()}).T
    tab.to_csv(os.path.join(out, "adaptation_comparison.csv"))
    pd.DataFrame(ev).to_csv(os.path.join(out, "adaptation_events.csv"), index=False)
    df_a.to_csv(os.path.join(out, "adapted_schedule.csv"), index=False); df_f.to_csv(os.path.join(out, "frozen_schedule.csv"), index=False)
    print(tab.round(2).to_string())
    print(f"updates accepted: {sum(e['accepted'] for e in ev)}/{len(ev)}   out: {out}")


if __name__ == "__main__":
    main()
