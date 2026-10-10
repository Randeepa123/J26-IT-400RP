"""
kukule_env_v2.py
================
Gymnasium environment v2 for Kukule Ganga (Component 3). Differences from kukule_waterlevel_env.py (v1, kept
for reproducibility):

  * Episodes are 365-day windows sampled from a SCENARIO BANK (droughts, floods, shifted monsoons, outages,
    festival demand, forecast error) with random start date and random initial storage - not one fixed series.
  * Observation includes P50/P90 inflow forecasts, demand weights (Vesak / Christmas ...), drought index,
    flood-risk, mandatory release, outage outlook and episode progress (see rl_common.py).
  * Action = Discrete(11) fraction of the turbine capacity; a SAFETY PROJECTION in hydro_core.step guarantees the
    hard floor and serves environmental / irrigation release first. Projected requests are counted.
  * Reward penalises spill (lost energy), operating-reserve shortfall, unmet mandatory release and the terminal
    storage shortfall; potential-based shaping values stored water. The episode ends by TRUNCATION (time limit).

Synthetic-data disclaimer: scenarios are simulated.
"""

import numpy as np
import gymnasium as gym
from gymnasium import spaces

from hydro_core import HydroParams
import rl_common as rc

N_ACTIONS = 11


class KukuleEnvV2(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, params=None, bank=None, episode_days=365, seed=0, shaping_beta=0.5, gamma=0.99,
                 regime_weights=None, extra_fn=None, terminal_penalty=True):
        super().__init__()
        self.p = params or HydroParams.from_config()
        self.bank = list(bank) if bank is not None else []
        self.episode_days = episode_days
        self.beta, self.gamma = shaping_beta, gamma
        self.terminal_penalty = terminal_penalty
        self.extra_fn = extra_fn            # optional hook: extra_fn(env) -> float for obs slot 22 (hybrid)
        self.rng = np.random.default_rng(seed)
        self.action_space = spaces.Discrete(N_ACTIONS)
        self.observation_space = spaces.Box(-5.0, 5.0, shape=(rc.OBS_DIM,), dtype=np.float32)
        self._probs = None
        if regime_weights is not None and self.bank:
            w = np.array([regime_weights.get(s.meta.get("regime", {}).get("enso", "neutral"), 1.0) for s in self.bank], float)
            self._probs = w / w.sum()
        self.sc = None

    # ---- episode control ---------------------------------------------------------
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        options = options or {}
        if "scenario" in options:
            self.sc = options["scenario"]
        else:
            self.sc = self.bank[self.rng.choice(len(self.bank), p=self._probs)]
        max_start = max(0, self.sc.n_days - self.episode_days)
        self.start = int(options.get("start", self.rng.integers(0, max_start + 1)))
        self.end_abs = self.start + min(self.episode_days, self.sc.n_days - self.start)
        if "S0" in options:
            S0 = float(options["S0"])
        else:
            u = self.rng.random()
            S0 = (self.p.S_max if u < 0.25 else
                  self.rng.uniform(self.p.S_floor, self.p.S_max) if u < 0.85 else
                  self.p.S_reserve)
        self.S, self.t = float(S0), self.start
        return self._obs(), {"scenario": self.sc.name, "start": self.start, "S0": self.S}

    def _request(self, action, cap):
        """Map a discrete action to a turbine-release request [m3] (overridden by the hybrid environment)."""
        return float(action) / (N_ACTIONS - 1.0) * cap

    def _obs(self):
        extra = self.extra_fn(self) if self.extra_fn else None
        return rc.build_obs(self.p, self.sc, self.t, self.S, self.start, self.end_abs, extra)

    def step(self, action):
        p, sc, t = self.p, self.sc, self.t
        cap = p.turbine_cap_m3(sc.units[t])
        req = self._request(action, cap)
        w = float(sc.weight[t])
        phi0 = rc.potential(p, self.S, self.beta)
        d = p.step(self.S, float(sc.inflow_m3[t]), int(sc.units[t]), sc.month(t), req, w)
        self.S, self.t = d["end_storage_m3"], t + 1
        truncated = bool(self.t >= self.end_abs)
        r, comps = rc.reward_terms(p, d, w, truncated and self.terminal_penalty)
        r += self.gamma * rc.potential(p, self.S, self.beta) - phi0
        obs = self._obs() if not truncated else self._obs_terminal()
        info = {"turbine_release_m3": d["turbine_release_m3"], "spill_volume_m3": d["spill_volume_m3"],
                "end_storage_m3": d["end_storage_m3"], "generation_mwh": d["generation_mwh"],
                "action_projected": d["action_projected"], "unmet_mandatory_m3": d["unmet_mandatory_m3"],
                "reward_components": comps, "date": str(sc.dates[t])[:10]}
        return obs, float(r), False, truncated, info

    def _obs_terminal(self):
        # next-state observation after the last day: reuse the final forecast row (episode is truncated anyway)
        t_last = min(self.t, self.sc.n_days - 1)
        return rc.build_obs(self.p, self.sc, t_last, self.S, self.start, self.end_abs,
                            self.extra_fn(self) if self.extra_fn else None)
