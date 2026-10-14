"""
hybrid_policy.py
================
Hybrid LP-DQN (residual hybrid) for Component 3.

  * The causal rolling-horizon LP (rolling_lp.RollingLPPolicy) plans a release for today from the P50/P90 inflow
    forecast and demand-weight forecast.
  * The DQN observes the usual v2 state PLUS the LP plan (today's planned release, planned end-of-day storage,
    tomorrow's planned release) and chooses a discrete ADJUSTMENT of the LP release, +-0/10/20/30% of turbine capacity.
  * hydro_core's safety projection still enforces floor / mandatory release / storage cap, so the hybrid inherits the
    feasibility guarantee and can only deviate from the LP when it has learned that doing so pays off (e.g. when the
    forecast is biased, a flood was missed, or the drought outlasts the plan).

HybridEnv    : gymnasium env for training.      HybridPolicy : sim_core.Policy for evaluation / deployment.
"""

import torch_compat  # noqa: F401  (fixes DQN.load on newer torch)
import numpy as np
from gymnasium import spaces
from stable_baselines3 import DQN

import rl_common as rc
from kukule_env_v2 import KukuleEnvV2
from rolling_lp import RollingLPPolicy
from sim_core import Policy

DELTAS = np.array([-0.30, -0.20, -0.10, 0.0, 0.10, 0.20, 0.30])
HYB_DIM = rc.OBS_DIM + 3


def lp_features(p, sol, cap_today, cap_next):
    if sol is None or not sol.get("success"):
        return np.array([0.5, 0.5, 0.5], dtype=np.float32), 0.5 * cap_today
    v = sol["v"]
    f = np.array([v[0] / max(cap_today, 1.0), sol["S"][0] / p.S_max,
                  (v[1] / max(cap_next, 1.0)) if len(v) > 1 else v[0] / max(cap_today, 1.0)], dtype=np.float32)
    return f, float(v[0])


class HybridEnv(KukuleEnvV2):
    def __init__(self, *args, lp_kwargs=None, **kw):
        super().__init__(*args, **kw)
        self.lp = RollingLPPolicy(**(lp_kwargs or {}))
        self._lp_key, self._plan_v0 = None, 0.0
        self.action_space = spaces.Discrete(len(DELTAS))
        self.observation_space = spaces.Box(-5.0, 5.0, shape=(HYB_DIM,), dtype=np.float32)

    def _obs(self):
        base = super()._obs()
        key = (id(self.sc), self.start)
        if self._lp_key != key:
            self.lp.reset(self.sc, self.start, self.end_abs - self.start, self.p, self.S)
            self._lp_key = key
        t = min(self.t, self.sc.n_days - 1)
        if self.t >= self.end_abs:                      # terminal observation: no plan needed
            self._plan_v0 = 0.0
            return np.r_[base, np.zeros(3, dtype=np.float32)].astype(np.float32)
        sol = self.lp.plan(t, self.S)
        feats, self._plan_v0 = lp_features(self.p, sol, self.p.turbine_cap_m3(self.sc.units[t]),
                                           self.p.turbine_cap_m3(self.sc.units[min(t + 1, len(self.sc.units) - 1)]))
        return np.r_[base, feats].astype(np.float32)

    def _obs_terminal(self):
        return np.r_[super()._obs_terminal(), np.zeros(3, dtype=np.float32)].astype(np.float32)

    def _request(self, action, cap):
        return float(np.clip(self._plan_v0 + DELTAS[int(action)] * cap, 0.0, cap))


class HybridPolicy(Policy):
    name = "hybrid"

    def __init__(self, model_or_path, lp_kwargs=None, name=None, deterministic=True):
        self.model = DQN.load(model_or_path, device="cpu") if isinstance(model_or_path, str) else model_or_path
        self.lp = RollingLPPolicy(**(lp_kwargs or {}))
        self.deterministic = deterministic
        self.last_plan = 0.0
        if name:
            self.name = name

    def reset(self, scenario, start, n_days, params, S0):
        super().reset(scenario, start, n_days, params, S0)
        self.end_abs = start + n_days
        self.lp.reset(scenario, start, n_days, params, S0)

    def act(self, t, storage):
        sc, p = self.sc, self.p
        sol = self.lp.plan(t, storage)
        cap = p.turbine_cap_m3(sc.units[t])
        feats, v0 = lp_features(p, sol, cap, p.turbine_cap_m3(sc.units[min(t + 1, len(sc.units) - 1)]))
        self.last_plan = v0
        obs = np.r_[rc.build_obs(p, sc, t, storage, self.start, self.end_abs), feats].astype(np.float32)
        a, _ = self.model.predict(obs, deterministic=self.deterministic)
        return float(np.clip(v0 + DELTAS[int(a)] * cap, 0.0, cap))
