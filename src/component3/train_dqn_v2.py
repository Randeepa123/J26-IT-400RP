"""
train_dqn_v2.py - train the v2 DQN on the TRAIN scenario bank; select the best checkpoint on the VALIDATION bank
only (the stress suite / real-sim test year are never used for training or selection).

Usage:  python train_dqn_v2.py --timesteps 300000 --seed 1 --tag a
"""
import os
import json
import time
import argparse
from datetime import datetime

import numpy as np
import torch
torch.set_num_threads(1)
from stable_baselines3 import DQN
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.callbacks import BaseCallback

import paths
import scenario_generator as sg
import sim_core as sm
import rl_common as rc
from hydro_core import HydroParams
from kukule_env_v2 import KukuleEnvV2
from dqn_policy import DQNPolicy
from hybrid_policy import HybridEnv, HybridPolicy

WORKSPACE = os.path.dirname(os.path.abspath(__file__))


def validation_score(params, policy, val_bank, n_scen=12, s0_fracs=(0.5,)):
    scores, mets = [], []
    for sc in val_bank[:n_scen]:
        for f in s0_fracs:
            df, m = sm.simulate(params, sc, policy, 0, 365, S0=f * params.S_max)
            scores.append(rc.episode_score(params, df)); mets.append(m)
    keys = ["energy_gwh", "spill_mcm", "reserve_breach_pct", "terminal_storage_mcm", "unmet_mandatory_days",
            "projected_actions"]
    return float(np.mean(scores)), {k: float(np.mean([m[k] for m in mets])) for k in keys}


class ValidationCallback(BaseCallback):
    def __init__(self, params, val_bank, out_dir, eval_freq, policy_cls=DQNPolicy, n_val=12):
        super().__init__()
        self.p, self.val, self.out, self.freq, self.policy_cls, self.n_val = params, val_bank, out_dir, eval_freq, policy_cls, n_val
        self.best, self.hist = -1e18, []

    def _on_step(self):
        if self.num_timesteps % self.freq == 0:
            self._eval()
        return True

    def _eval(self):
        score, m = validation_score(self.p, self.policy_cls(self.model, deterministic=True), self.val, n_scen=self.n_val)
        self.hist.append({"timesteps": self.num_timesteps, "val_score": score, **m})
        flag = ""
        if score > self.best:
            self.best = score
            self.model.save(os.path.join(self.out, "dqn_best_val.zip")); flag = "  <- best"
        print(f"[val] step {self.num_timesteps:>8,} score {score:7.2f} E={m['energy_gwh']:6.1f}GWh spill={m['spill_mcm']:6.1f} "
              f"resBreach={m['reserve_breach_pct']:4.1f}% S_T={m['terminal_storage_mcm']:.2f} unmetD={m['unmet_mandatory_days']:.1f}{flag}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timesteps", type=int, default=300000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--tag", default="run")
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--gamma", type=float, default=0.99)
    ap.add_argument("--net", type=int, default=256)
    ap.add_argument("--buffer", type=int, default=200000)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--expl-frac", type=float, default=0.3)
    ap.add_argument("--target-update", type=int, default=2000)
    ap.add_argument("--train-freq", type=int, default=4)
    ap.add_argument("--shaping-beta", type=float, default=0.5)
    ap.add_argument("--eval-freq", type=int, default=20000)
    ap.add_argument("--val-n", type=int, default=20)
    ap.add_argument("--hybrid", action="store_true", help="train the residual LP-DQN hybrid instead of the plain DQN")
    ap.add_argument("--out-dir", default=None)
    a = ap.parse_args()

    p = HydroParams.from_config()
    train = sg.load_bank(os.path.join(sg.BANK_DIR, "train_bank.pkl"))
    val = sg.load_bank(os.path.join(sg.BANK_DIR, "val_bank.pkl"))
    out = a.out_dir or os.path.join(str(paths.TRAINING_RUNS_DIR),
                                    f"{a.tag}{'_hyb' if a.hybrid else ''}_{a.timesteps//1000}k_s{a.seed}_{datetime.now():%Y%m%d_%H%M%S}")
    os.makedirs(out, exist_ok=True)

    env_cls = HybridEnv if a.hybrid else KukuleEnvV2
    env = Monitor(env_cls(p, train, seed=a.seed, shaping_beta=a.shaping_beta, gamma=a.gamma,
                          regime_weights={"neutral": 1.0, "el_nino": 1.3, "la_nina": 1.0}),
                  filename=os.path.join(out, "monitor.csv"))
    model = DQN("MlpPolicy", env, learning_rate=a.lr, buffer_size=a.buffer, learning_starts=5000,
                batch_size=a.batch, tau=1.0, gamma=a.gamma, train_freq=(a.train_freq, "step"), gradient_steps=1,
                target_update_interval=a.target_update, exploration_fraction=a.expl_frac,
                exploration_initial_eps=1.0, exploration_final_eps=0.05,
                policy_kwargs=dict(net_arch=[a.net, a.net]), seed=a.seed, verbose=0, device="cpu")
    cb = ValidationCallback(p, val, out, a.eval_freq, HybridPolicy if a.hybrid else DQNPolicy, a.val_n)
    t0 = time.time()
    model.learn(total_timesteps=a.timesteps, callback=cb)
    el = time.time() - t0
    cb._eval()
    model.save(os.path.join(out, "dqn_final.zip"))
    cfg = {"args": vars(a), "elapsed_s": round(el, 1), "fps": round(a.timesteps / el, 1),
           "train_bank": len(train), "val_bank": len(val), "best_val_score": cb.best, "val_history": cb.hist,
           "data_note": "SYNTHETIC scenario bank; model selected on validation bank only"}
    with open(os.path.join(out, "train_config.json"), "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"done in {el/60:.1f} min ({a.timesteps/el:.0f} fps); best val score {cb.best:.2f}; out: {out}")


if __name__ == "__main__":
    main()
