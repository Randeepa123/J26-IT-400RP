"""
kukule_waterlevel_env.py
========================
Gymnasium Reinforcement Learning Environment for Kukule Ganga Hydropower Station.
Component: Component 3 - Hydropower Generation & Reservoir Release Optimization Subsystem
Target Station: Kukule Ganga Power Station (70.0 MW, 1.67 MCM active pondage), Sabaragamuwa, Sri Lanka.

Key Design Principles:
-----------------------
1. Standard Gymnasium API: Inherits from gymnasium.Env with reset() and step().
2. Discrete Action Space: Discrete(11) representing 0%, 10%, ..., 100% of maximum turbine discharge.
3. Causal Observation Space: Only historical and current-state information (storage, prior-day inflow,
   unit availability, seasonal cycle). Strictly zero lookahead into future inflows.
4. Exact Mass Continuity: Ending storage = Starting storage + Inflow - Turbine release - Spill - Evaporation.
5. Physical Non-Linear Hydraulics: Storage-elevation curve, quadratic penstock friction headloss,
   part-load efficiency switching, and continuous electrical capacity ceiling (70 MW / 1,680 MWh/day).
6. Normalized Generation Reward: Physical generation divided by 1,680.0 MWh (reward in [0.0, 1.0]).
7. Chronological Partitioning:
   - Development Split (Training): 2021-10-19 to 2025-10-18 (1,461 calendar days)
   - Held-Out Test Split (Evaluation): 2025-10-19 to 2026-10-18 (365 calendar days)

Author: Antigravity Research Pipeline
Date  : October 2026
"""

import os
import json
import math
import numpy as np
import pandas as pd
import gymnasium as gym
from gymnasium import spaces

# Physical and Unit Conversion Constants
SECONDS_PER_DAY = 86400.0
HOURS_PER_DAY = 24.0
JOULES_PER_MWH = 3.6e9
RHO = 1000.0          # Water density [kg/m³]
G = 9.81              # Gravitational acceleration [m/s²]

# Default Baseline Engineering Parameters (from scenarios_config.json)
DEFAULT_ACTIVE_STORAGE_M3 = 1670000.0     # 1.67 MCM active pondage
DEFAULT_MOL_MASL = 204.25                 # Minimum Operating Level
DEFAULT_FSL_MASL = 206.00                 # Full Supply Level
DEFAULT_TAILWATER_MASL = 19.60            # Fixed effective operational tailwater elevation
DEFAULT_RATED_STATION_Q = 47.5            # Total station rated discharge [m³/s]
DEFAULT_RATED_UNIT_Q = 23.75              # Unit rated discharge [m³/s]
DEFAULT_HEADLOSS_RATED = 10.30            # Total system friction loss at rated discharge [m]
DEFAULT_EFF_NOMINAL = 0.895               # Nominal wire-to-water efficiency
DEFAULT_EFF_PART = 0.865                  # Part-load wire-to-water efficiency
DEFAULT_DAILY_EVAP_M3 = 1440.0            # Daily evaporation loss volume [m³/day]
DEFAULT_ALPHA = 1.05                      # Storage-elevation power law exponent
DEFAULT_INSTALLED_MW = 70.0               # Total station capacity [MW]
DEFAULT_UNIT_MW = 35.0                    # Single unit capacity [MW]
DEFAULT_ENV_FLOW_M3S = 2.0                # Statutory environmental flow [m³/s]


class KukuleWaterLevelEnv(gym.Env):
    """
    Gymnasium Environment for Kukule Ganga Hydropower Daily Reservoir Dispatch.
    """
    metadata = {"render_modes": ["human"], "render_fps": 30}

    def __init__(self, config_dict=None, dataset_path=None, split="dev",
                 scenario="baseline", initial_storage_m3=None):
        """
        Initialize the environment.

        Parameters:
        -----------
        config_dict : dict, optional
            Loaded configuration dictionary (from scenarios_config.json).
        dataset_path : str, optional
            Path to integrated 5-year CSV dataset.
        split : str
            Chronological split: 'dev' (training, 1461 days), 'test' (evaluation, 365 days),
            or 'full' (1826 days). Default is 'dev'.
        scenario : str
            Scenario identifier ('baseline', 'alt_a', 'alt_b', 'alt_c').
        initial_storage_m3 : float, optional
            Starting active storage. Defaults to full pondage (S_max = 1.67 MCM).
        """
        super().__init__()

        self.scenario = scenario
        self.split = split.lower()
        self.initial_storage_arg = initial_storage_m3

        # Load configuration parameters
        self._load_configuration(config_dict)

        # Load and filter chronological dataset
        self._load_dataset(dataset_path)

        # Action Space: 11 Discrete release fractions [0%, 10%, ..., 100%]
        # Action a in {0, ..., 10} maps to fraction a / 10.0 of V_turb_max
        self.num_actions = 11
        self.action_space = spaces.Discrete(self.num_actions)

        # Observation Space: 5 Continuous normalized features in [-1.0, 1.0] or [0.0, 1.0]
        # Feature 0: Current active storage fraction S_{t-1} / S_max in [0.0, 1.0]
        # Feature 1: Prior-day inflow volume normalized by station rated flow [0.0, 1.0]
        # Feature 2: Operational unit availability u_t / 2.0 in [0.5, 1.0]
        # Feature 3: Day of year seasonality sine component in [-1.0, 1.0]
        # Feature 4: Day of year seasonality cosine component in [-1.0, 1.0]
        obs_low = np.array([0.0, 0.0, 0.0, -1.0, -1.0], dtype=np.float32)
        obs_high = np.array([1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float32)
        self.observation_space = spaces.Box(low=obs_low, high=obs_high, dtype=np.float32)

        # Internal state variables
        self.current_step = 0
        self.current_storage = self.S_max
        self.prev_inflow_vol = 0.0

    def _load_configuration(self, config_dict):
        """Extract physical parameters from configuration or defaults."""
        cfg = config_dict or {}
        s_cfg = cfg.get("shared_station_specifications", {})
        op_cfg = cfg.get("operational_and_scenario_parameters", {})
        scen_cfg = cfg.get("scenarios", {}).get(self.scenario, {})

        # Storage & Elevation Geometry
        self.S_max = float(s_cfg.get("active_storage_volume_m3", DEFAULT_ACTIVE_STORAGE_M3))
        self.S_min = 0.0
        self.FSL = float(s_cfg.get("full_supply_level_masl", DEFAULT_FSL_MASL))
        self.MOL = float(scen_cfg.get("minimum_operating_level_masl",
                         s_cfg.get("minimum_operating_level_masl", DEFAULT_MOL_MASL)))
        self.delta_H = self.FSL - self.MOL
        self.alpha = float(s_cfg.get("elevation_storage_alpha", DEFAULT_ALPHA))

        # Hydraulic & Tailwater Geometry
        self.Z_tail = float(scen_cfg.get("tailwater_level_masl",
                            s_cfg.get("tailwater_level_masl", DEFAULT_TAILWATER_MASL)))
        self.system_loss_rated = float(scen_cfg.get("tunnel_headloss_at_max_discharge_m",
                                       s_cfg.get("tunnel_headloss_at_max_discharge_m", DEFAULT_HEADLOSS_RATED)))
        self.Q_station_rated = float(scen_cfg.get("rated_turbine_discharge_station_m3s",
                                     s_cfg.get("rated_turbine_discharge_station_m3s", DEFAULT_RATED_STATION_Q)))
        self.Q_unit_rated = float(scen_cfg.get("rated_turbine_discharge_unit_m3s",
                                  s_cfg.get("rated_turbine_discharge_unit_m3s", DEFAULT_RATED_UNIT_Q)))
        self.installed_cap_mw = float(s_cfg.get("installed_capacity_mw", DEFAULT_INSTALLED_MW))
        self.unit_cap_mw = float(s_cfg.get("unit_capacity_mw", DEFAULT_UNIT_MW))
        self.num_units = int(s_cfg.get("num_units", 2))

        # Efficiency & Daily Losses
        self.eff_nominal = float(s_cfg.get("nominal_overall_efficiency", DEFAULT_EFF_NOMINAL))
        self.eff_part = float(s_cfg.get("part_load_efficiency", DEFAULT_EFF_PART))
        self.daily_evap_m3 = float(op_cfg.get("daily_evaporation_loss_m3", DEFAULT_DAILY_EVAP_M3))
        self.rho = float(s_cfg.get("water_density_kg_m3", RHO))
        self.g = float(s_cfg.get("gravity_acceleration_m_s2", G))

        # Maximum possible daily energy (70 MW * 24 h = 1680.0 MWh)
        self.max_daily_energy_mwh = self.installed_cap_mw * HOURS_PER_DAY
        # Maximum station daily volumetric discharge at 2 units (47.5 m³/s * 86400 s)
        self.v_station_rated_day = self.Q_station_rated * SECONDS_PER_DAY

    def _load_dataset(self, dataset_path):
        """Load and chronologically split the input historical/synthetic dataset."""
        workspace_dir = os.path.dirname(os.path.abspath(__file__))

        if dataset_path is None or not os.path.exists(dataset_path):
            candidates = [
                os.path.join(workspace_dir, "scenarios", f"scenario_{self.scenario}", "synthetic_kukule_integrated_dataset_5years.csv"),
                os.path.join(workspace_dir, "synthetic_kukule_dataset", "synthetic_kukule_integrated_dataset_5years.csv"),
                os.path.join(workspace_dir, "synthetic_kukule_integrated_dataset_5years.csv")
            ]
            for c in candidates:
                if os.path.exists(c):
                    dataset_path = c
                    break

        if dataset_path is None or not os.path.exists(dataset_path):
            raise FileNotFoundError(f"Kukule dataset not found. Searched candidates: {candidates}")

        df_raw = pd.read_csv(dataset_path)
        df_raw["dt"] = pd.to_datetime(df_raw["date"])

        # Apply chronological splits strictly:
        # Dev (Training)   : 2021-10-19 to 2025-10-18 (1,461 calendar days)
        # Test (Evaluation): 2025-10-19 to 2026-10-18 (365 calendar days)
        # Full             : 2021-10-19 to 2026-10-18 (1,826 calendar days)
        if self.split == "dev":
            self.df_data = df_raw[(df_raw["dt"] >= "2021-10-19") & (df_raw["dt"] <= "2025-10-18")].copy()
        elif self.split == "test":
            self.df_data = df_raw[(df_raw["dt"] >= "2025-10-19") & (df_raw["dt"] <= "2026-10-18")].copy()
        elif self.split == "full":
            self.df_data = df_raw.copy()
        else:
            raise ValueError(f"Unknown split '{self.split}'. Must be 'dev', 'test', or 'full'.")

        self.df_data.reset_index(drop=True, inplace=True)
        self.num_steps = len(self.df_data)
        if self.num_steps == 0:
            raise ValueError(f"Selected split '{self.split}' resulted in 0 records!")

        # Pre-extract numpy arrays for fast stepping
        self.inflow_series = self.df_data["inflow_volume_m3"].values.astype(float)
        self.date_series = self.df_data["date"].values
        self.dt_series = self.df_data["dt"].values

        if "operating_units" in self.df_data.columns:
            self.units_series = self.df_data["operating_units"].values.astype(int)
        else:
            self.units_series = np.full(self.num_steps, 2, dtype=int)

    def _get_observation(self):
        """
        Construct the causal observation vector at current decision step.
        Does NOT expose future or unobserved information.
        """
        # Feature 0: Current normalized storage S_{t-1} / S_max
        storage_norm = float(np.clip(self.current_storage / self.S_max, 0.0, 1.0))

        # Feature 1: Prior day inflow normalized by station capacity (saturated at 1.0)
        # Normalizing scale: 2 units * 23.75 m³/s * 86400 = 4.104 MCM/day
        inflow_norm = float(np.clip(self.prev_inflow_vol / self.v_station_rated_day, 0.0, 1.0))

        # Feature 2: Operational unit status u_t / 2.0 (0.5 for 1 unit, 1.0 for 2 units)
        u_t = self.units_series[self.current_step] if self.current_step < self.num_steps else 2
        units_norm = float(u_t / 2.0)

        # Features 3 & 4: Day-of-year cyclical encoding (sin and cos)
        if self.current_step < self.num_steps:
            d_obj = pd.Timestamp(self.dt_series[self.current_step])
            day_of_year = d_obj.dayofyear
        else:
            day_of_year = 1
        sin_season = float(math.sin(2.0 * math.pi * day_of_year / 365.25))
        cos_season = float(math.cos(2.0 * math.pi * day_of_year / 365.25))

        obs = np.array([storage_norm, inflow_norm, units_norm, sin_season, cos_season], dtype=np.float32)
        return obs

    def reset(self, seed=None, options=None):
        """
        Reset the environment to the beginning of the selected chronological split.

        Returns:
        --------
        tuple : (observation, info_dict)
        """
        super().reset(seed=seed)

        self.current_step = 0
        if self.initial_storage_arg is None:
            self.current_storage = self.S_max
        else:
            self.current_storage = float(np.clip(self.initial_storage_arg, self.S_min, self.S_max))

        # Initialize prior day inflow to first day's inflow (causal initialization)
        self.prev_inflow_vol = self.inflow_series[0]

        obs = self._get_observation()
        info = {
            "step": 0,
            "date": str(self.date_series[0]),
            "split": self.split,
            "total_days": self.num_steps,
            "initial_storage_m3": self.current_storage
        }
        return obs, info

    def step(self, action):
        """
        Execute one daily dispatch decision.

        Parameters:
        -----------
        action : int
            Discrete action index in {0, ..., 10}, representing 0%, 10%, ..., 100%
            of available turbine release capacity.

        Returns:
        --------
        tuple : (observation, reward, terminated, truncated, info)
        """
        # Validate action
        if not self.action_space.contains(action):
            raise ValueError(f"Invalid action {action}. Must be in {list(range(self.num_actions))}.")

        action_int = int(action)
        action_fraction = action_int / (self.num_actions - 1.0)  # e.g. 0.0, 0.1, ..., 1.0

        # Retrieve exogenous conditions for the current calendar day t
        t = self.current_step
        v_in = float(self.inflow_series[t])
        u_t = int(self.units_series[t])
        current_date_str = str(self.date_series[t])
        storage_begin = float(self.current_storage)

        # Available capacity
        cap_mw = u_t * self.unit_cap_mw
        v_turb_max = u_t * self.Q_unit_rated * SECONDS_PER_DAY

        # 1. Total available water before new releases:
        # W_avail = S_{t-1} + V_in - V_loss
        w_avail = storage_begin + v_in - self.daily_evap_m3
        if w_avail < 0.0:
            w_avail = 0.0  # Guard against negative available water

        # 2. Desired turbine release from discrete action
        v_turb_desired = action_fraction * v_turb_max

        # Physical limit: cannot release more water than available
        v_turb = min(v_turb_desired, w_avail)
        v_turb = max(0.0, v_turb)

        # 3. Water remaining in pond after turbine release
        s_potential = w_avail - v_turb

        # 4. Storage boundaries & Spillway discharge:
        # If remaining water exceeds active capacity S_max, excess spills over weir
        if s_potential > self.S_max:
            v_spill = s_potential - self.S_max
            s_end = self.S_max
        else:
            v_spill = 0.0
            s_end = s_potential

        # Rounding for exact float conservation (sub-millimeter precision)
        v_turb = round(v_turb, 2)
        v_spill = round(v_spill, 2)
        s_end = round(storage_begin + v_in - v_turb - v_spill - self.daily_evap_m3, 2)
        if s_end < 0.0:
            # Re-absorb tiny float precision residue
            v_turb = round(v_turb + s_end, 2)
            s_end = 0.0
        elif s_end > self.S_max:
            v_spill = round(v_spill + (s_end - self.S_max), 2)
            s_end = self.S_max

        # Update environment state
        self.current_storage = s_end
        self.prev_inflow_vol = v_in

        # 5. Non-linear Hydraulic & Physical Generation Calculation
        # Elevation-storage power law: elev = MOL + delta_H * (S / S_max)^(1/alpha)
        s_ratio = max(0.0, s_end) / self.S_max
        elev = self.MOL + self.delta_H * (s_ratio ** (1.0 / self.alpha))
        active_pct = s_ratio * 100.0

        q_turb = v_turb / SECONDS_PER_DAY
        h_gross = elev - self.Z_tail
        # Quadratic headloss: h_loss = h_loss_rated * (Q_turb / Q_rated)^2
        h_loss = self.system_loss_rated * ((q_turb / self.Q_station_rated) ** 2) if q_turb > 0.0 else 0.0
        h_net = h_gross - h_loss

        # Wire-to-water efficiency step function
        eff = self.eff_nominal if q_turb > 0.35 * (u_t * self.Q_unit_rated) else self.eff_part

        # Physical electrical energy generation [MWh] clamped by electrical ceiling
        if v_turb > 0.0:
            e_calc = (self.rho * self.g * v_turb * h_net * eff) / JOULES_PER_MWH
            e_phys = min(e_calc, cap_mw * HOURS_PER_DAY)
        else:
            e_phys = 0.0

        e_phys = round(e_phys, 3)

        # 6. Reward Calculation (Normalized Daily Generation in [0.0, 1.0])
        # Reward = physical daily generation / 1,680.0 MWh
        # (1,680 MWh corresponds to 70 MW continuous output over 24 hours)
        reward = float(np.clip(e_phys / self.max_daily_energy_mwh, 0.0, 1.0))

        # Check water balance residual for diagnostic tracking
        wb_residual = abs(s_end - (storage_begin + v_in - v_turb - v_spill - self.daily_evap_m3))

        # Step forward
        self.current_step += 1
        terminated = bool(self.current_step >= self.num_steps)
        truncated = False

        # Next observation
        obs = self._get_observation()

        # Detailed step metadata dictionary
        info = {
            "step": self.current_step,
            "date": current_date_str,
            "inflow_volume_m3": v_in,
            "beginning_storage_m3": storage_begin,
            "turbine_release_m3": v_turb,
            "spill_volume_m3": v_spill,
            "end_storage_m3": s_end,
            "pond_level_masl": round(elev, 4),
            "active_storage_pct": round(active_pct, 2),
            "net_head_m": round(h_net, 2),
            "turbine_efficiency": round(eff, 4),
            "generation_mwh": e_phys,
            "operating_units": u_t,
            "available_capacity_mw": cap_mw,
            "water_balance_residual_m3": round(wb_residual, 8),
            "action": action_int,
            "action_fraction": round(action_fraction, 2)
        }

        return obs, reward, terminated, truncated, info

    def render(self):
        """Render basic textual status to console."""
        t = max(0, self.current_step - 1)
        d_str = str(self.date_series[t]) if t < self.num_steps else "END"
        print(f"Step {self.current_step}/{self.num_steps} [{d_str}] | Storage: {self.current_storage:,.1f} m³ ({self.current_storage/self.S_max*100:.1f}%)")
