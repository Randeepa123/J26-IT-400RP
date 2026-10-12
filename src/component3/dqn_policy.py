"""
dqn_policy.py - wrap a trained SB3 DQN model as a sim_core.Policy using the SAME observation builder and
action mapping as KukuleEnvV2 (so training, validation and test see identical state/actions).
"""
import torch_compat  # noqa: F401  (fixes DQN.load on newer torch)
import numpy as np
from stable_baselines3 import DQN

import rl_common as rc
from sim_core import Policy
from kukule_env_v2 import N_ACTIONS


class DQNPolicy(Policy):
    name = "dqn"

    def __init__(self, model_or_path, name=None, deterministic=True):
        self.model = DQN.load(model_or_path, device="cpu") if isinstance(model_or_path, str) else model_or_path
        self.deterministic = deterministic
        if name:
            self.name = name

    def reset(self, scenario, start, n_days, params, S0):
        super().reset(scenario, start, n_days, params, S0)
        self.end_abs = start + n_days

    def act(self, t, storage):
        obs = rc.build_obs(self.p, self.sc, t, storage, self.start, self.end_abs)
        a, _ = self.model.predict(obs, deterministic=self.deterministic)
        return float(a) / (N_ACTIONS - 1.0) * self.p.turbine_cap_m3(self.sc.units[t])
