"""
lp_optimizer.py
===============
Genuine Linear Programming (LP) Reservoir Dispatch Optimizer
Target Facility : Kukule Ganga Power Station, Sabaragamuwa Province, Sri Lanka
Component       : Component 3 - Hydropower Generation & Reservoir Release Optimization Subsystem

Mathematical & Algorithmic Principles:
--------------------------------------
1. Genuine Linear Programming:
   Solves the multi-period reservoir dispatch problem using the HiGHS dual simplex/interior-point
   solver (scipy.optimize.linprog method='highs'). No non-linear solver heuristics.
2. Decision Variables:
   For horizon T (t = 1 ... T):
     - V_turb,t  : Volumetric turbine release [m³/day]
     - V_spill,t : Volumetric spillway discharge [m³/day]
     - S_t       : End-of-day active storage volume [m³]
   Total variable dimension = 3T.
3. Objective Function:
   Maximize total linear generation while strictly penalizing unnecessary spillway discharge:
     min sum_{t=1}^T ( -k_e * V_turb,t + c_spill * V_spill,t )
   where:
     k_e = (rho * g * H_net_rated * eff_nominal) / 3.6e9 = 4.2694e-4 MWh/m³
     c_spill = 1e-7 MWh/m³ (resolves degeneracies, prevents artificial spilling)
4. System Constraints:
   - Daily Water Balance Equality:
       S_t - S_{t-1} + V_turb,t + V_spill,t = V_in,t - V_loss,t
   - Storage Bounds:
       0.0 <= S_t <= S_max = 1,670,000.0 m³
   - Turbine Flow & Electrical Capacity Bounds:
       0.0 <= V_turb,t <= min(u_t * Q_unit_rated * 86400, (u_t * 35.0 * 24.0) / k_e)
   - Terminal Storage Stewardship Constraint:
       S_T >= S_target (default: S_0 = 1,670,000.0 m³)
5. Separation of Optimization Objective from Physical Evaluation Metrics:
   Post-processes optimal releases through the exact non-linear hydraulic equations:
     - Storage-elevation power law: elev = MOL + (FSL - MOL) * (S_t / S_max)^(1/alpha)
     - Lump-sum friction loss: h_loss = h_loss_rated * (Q_turb / Q_rated)^2
     - Net hydraulic head: H_net = elev - Z_tail - h_loss
     - Wire-to-water loading efficiency: eff = nominal if Q_turb > 0.35 * Q_max else part_load
     - Physical generation: E_phys = min(rho * g * V_turb * H_net * eff / 3.6e9, P_cap * 24.0)
     - Approximation gap: Delta_E = E_lp - E_phys

Author: Antigravity Research Pipeline
Date  : October 2026
"""

import os
import sys
import json
import argparse
import time
from datetime import datetime
import numpy as np
import pandas as pd
import scipy.optimize as opt
import scipy.sparse as sp

# Physical & Unit Conversion Constants
SECONDS_PER_DAY = 86400.0
HOURS_PER_DAY = 24.0
JOULES_PER_MWH = 3.6e9
RHO = 1000.0        # Water density [kg/m³]
G = 9.81            # Gravitational acceleration [m/s²]

# Default Baseline Engineering Parameters
DEFAULT_ACTIVE_STORAGE_M3 = 1670000.0   # 1.67 MCM
DEFAULT_MOL_MASL = 204.25               # Minimum Operating Level
DEFAULT_FSL_MASL = 206.00               # Full Supply Level
DEFAULT_TAILWATER_MASL = 19.60          # Fixed tailwater elevation
DEFAULT_RATED_STATION_Q = 47.5          # Station rated discharge [m³/s]
DEFAULT_RATED_UNIT_Q = 23.75            # Unit rated discharge [m³/s]
DEFAULT_HEADLOSS_RATED = 10.30          # System friction loss at rated Q [m]
DEFAULT_EFF_NOMINAL = 0.895             # Nominal wire-to-water efficiency
DEFAULT_EFF_PART = 0.865                # Part-load wire-to-water efficiency
DEFAULT_DAILY_EVAP_M3 = 1440.0          # Daily evaporation loss [m³/day]
DEFAULT_ALPHA = 1.05                    # Storage-elevation exponent
DEFAULT_INSTALLED_MW = 70.0             # Installed capacity [MW]
DEFAULT_UNIT_MW = 35.0                  # Unit capacity [MW]
DEFAULT_ENV_FLOW_M3S = 2.0              # Environmental flow requirement [m³/s]


class KukuleLPOptimizer:
    """Genuine Highs-based Linear Programming Reservoir Dispatch Optimizer."""

    def __init__(self, config_dict=None, scenario="baseline", terminal_storage_target=None,
                 spill_penalty=1e-6, storage_reward=1e-7, enforce_env_flow=False):
        """
        Initialize the LP Optimizer with physical configuration.

        Parameters:
        -----------
        config_dict : dict, optional
            Loaded configuration dictionary (scenarios_config.json).
        scenario : str
            Scenario ID to configure parameters for ('baseline', 'alt_a', 'alt_b', 'alt_c').
        terminal_storage_target : float, optional
            Target terminal storage S_T [m³]. Defaults to S_max (full pondage).
        spill_penalty : float
            Economic penalty coefficient c_spill [MWh/m³] applied to spillway release (default 1e-6).
        storage_reward : float
            Small incentive coefficient c_storage [MWh/m³] applied to active storage (default 1e-7).
            Resolves multi-period storage degeneracy and preserves maximum operating head.
        enforce_env_flow : bool
            Whether to enforce total release >= environmental flow as a hard LP constraint.
        """
        self.scenario = scenario
        self.config = config_dict or {}
        self.spill_penalty = float(spill_penalty)
        self.storage_reward = float(storage_reward)
        self.enforce_env_flow = bool(enforce_env_flow)
        self._load_parameters()

        if terminal_storage_target is None:
            self.terminal_storage_target = self.S_max
        else:
            self.terminal_storage_target = float(terminal_storage_target)

    def _load_parameters(self):
        """Extract station parameters from configuration dictionary."""
        s_cfg = self.config.get("shared_station_specifications", {})
        op_cfg = self.config.get("operational_and_scenario_parameters", {})
        h_cfg = self.config.get("hydrological_parameters", {})
        scenarios = self.config.get("scenarios", {})
        scen_cfg = scenarios.get(self.scenario, {})

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

        # Efficiency & Environmental
        self.eff_nominal = float(s_cfg.get("nominal_overall_efficiency", DEFAULT_EFF_NOMINAL))
        self.eff_part = float(s_cfg.get("part_load_efficiency", DEFAULT_EFF_PART))
        self.daily_evap_m3 = float(op_cfg.get("daily_evaporation_loss_m3", DEFAULT_DAILY_EVAP_M3))
        self.rho = float(s_cfg.get("water_density_kg_m3", RHO))
        self.g = float(s_cfg.get("gravity_acceleration_m_s2", G))
        self.tolerance = float(op_cfg.get("daily_water_balance_tolerance_m3", 0.0001))
        self.env_flow_m3s = float(h_cfg.get("minimum_environmental_flow_m3s", DEFAULT_ENV_FLOW_M3S))
        self.env_flow_vol_day = self.env_flow_m3s * SECONDS_PER_DAY

        # Rated Net Head and Linear Energy Coefficient (k_e) [MWh/m³]
        H_rated_net = (self.FSL + self.MOL) / 2.0 - self.Z_tail - self.system_loss_rated
        self.H_rated_net = H_rated_net
        self.k_e = (self.rho * self.g * H_rated_net * self.eff_nominal) / JOULES_PER_MWH
        self.water_rate_m3_per_mwh = 1.0 / self.k_e

    def build_model(self, df_input, initial_storage_m3=None):
        """
        Construct the canonical Linear Programming matrices (c, A_eq, b_eq, bounds).

        Parameters:
        -----------
        df_input : pd.DataFrame
            Input dataset containing 'date', 'inflow_volume_m3', and optionally 'operating_units'.
        initial_storage_m3 : float, optional
            Storage at t=0. Defaults to S_max.

        Returns:
        --------
        tuple : (c, A_eq, b_eq, bounds, A_ub, b_ub)
        """
        T = len(df_input)
        S_0 = self.S_max if initial_storage_m3 is None else float(initial_storage_m3)
        inflow_vol = df_input["inflow_volume_m3"].values.astype(float)

        if "operating_units" in df_input.columns:
            units = df_input["operating_units"].values.astype(int)
        else:
            units = np.full(T, 2, dtype=int)

        # Dimension: 3T
        # Indices:
        #   V_turb,t  : 0 ... T-1
        #   V_spill,t : T ... 2T-1
        #   S_t       : 2T ... 3T-1
        num_vars = 3 * T

        # 1. Objective Vector c (minimize c^T x)
        c = np.zeros(num_vars, dtype=float)
        c[0:T] = -self.k_e
        c[T:2*T] = self.spill_penalty
        c[2*T:3*T] = -self.storage_reward

        # 2. Water Balance Equality Constraints: A_eq x = b_eq
        # For t=0: S_0 + V_in,0 - V_loss,0 = S_0_var + V_turb,0 + V_spill,0
        # -> V_turb,0 + V_spill,0 + S_0 = S_0 + V_in,0 - V_loss,0
        # For t>0: S_t - S_{t-1} + V_turb,t + V_spill,t = V_in,t - V_loss,t
        A_eq = sp.dok_matrix((T, num_vars), dtype=float)
        b_eq = np.zeros(T, dtype=float)

        for t in range(T):
            A_eq[t, t] = 1.0        # V_turb,t
            A_eq[t, T + t] = 1.0    # V_spill,t
            A_eq[t, 2*T + t] = 1.0  # S_t
            if t == 0:
                b_eq[0] = S_0 + inflow_vol[0] - self.daily_evap_m3
            else:
                A_eq[t, 2*T + t - 1] = -1.0  # -S_{t-1}
                b_eq[t] = inflow_vol[t] - self.daily_evap_m3

        # 3. Variable Bounds
        bounds = []
        for t in range(T):
            u_t = units[t]
            # Hydraulic physical discharge limit
            v_hydraulic_max = u_t * self.Q_unit_rated * SECONDS_PER_DAY
            # Electrical power ceiling limit: P_cap * 24.0 / k_e
            v_electrical_max = (u_t * self.unit_cap_mw * HOURS_PER_DAY) / self.k_e
            v_turb_upper = min(v_hydraulic_max, v_electrical_max)
            bounds.append((0.0, v_turb_upper))

        for t in range(T):
            # Spillway release bound: [0, inf)
            bounds.append((0.0, None))

        for t in range(T):
            # Storage bounds: [0, S_max]
            if t == T - 1:
                # Terminal storage constraint: S_T >= S_target
                bounds.append((self.terminal_storage_target, self.S_max))
            else:
                bounds.append((0.0, self.S_max))

        # 4. Optional Environmental Flow Inequality: -V_turb,t - V_spill,t <= -V_env_req
        A_ub = None
        b_ub = None
        if self.enforce_env_flow:
            A_ub = sp.dok_matrix((T, num_vars), dtype=float)
            b_ub = np.full(T, -self.env_flow_vol_day, dtype=float)
            for t in range(T):
                A_ub[t, t] = -1.0
                A_ub[t, T + t] = -1.0
            A_ub = A_ub.tocsr()

        return c, A_eq.tocsr(), b_eq, bounds, A_ub, b_ub

    def optimize(self, df_input, initial_storage_m3=None):
        """
        Solve the LP problem using SciPy HiGHS.

        Returns:
        --------
        scipy.optimize.OptimizeResult object
        """
        c, A_eq, b_eq, bounds, A_ub, b_ub = self.build_model(df_input, initial_storage_m3)
        start_time = time.time()
        res = opt.linprog(
            c=c,
            A_ub=A_ub,
            b_ub=b_ub,
            A_eq=A_eq,
            b_eq=b_eq,
            bounds=bounds,
            method="highs",
            options={"disp": False, "presolve": True}
        )
        solve_duration = time.time() - start_time
        res.solve_duration_sec = solve_duration
        return res

    def evaluate(self, res, df_input, initial_storage_m3=None):
        """
        Post-process optimal decision variables through exact non-linear physical equations.

        Parameters:
        -----------
        res : OptimizeResult
            Output from SciPy linprog.
        df_input : pd.DataFrame
            Original input DataFrame.
        initial_storage_m3 : float, optional
            Starting active storage.

        Returns:
        --------
        tuple : (pd.DataFrame, dict)
            (Detailed daily DataFrame, Summary Metrics Dictionary)
        """
        T = len(df_input)
        S_0 = self.S_max if initial_storage_m3 is None else float(initial_storage_m3)

        if not res.success:
            return None, {
                "solver_status": "INFEASIBLE" if res.status == 2 else f"FAILED_STATUS_{res.status}",
                "solver_message": res.message,
                "success": False,
                "calendar_days": T
            }

        x = res.x
        v_turb = x[0:T]
        v_spill = x[T:2*T]
        s_end = x[2*T:3*T]

        # Reconstruct beginning storage
        s_begin = np.zeros(T, dtype=float)
        s_begin[0] = S_0
        s_begin[1:] = s_end[:-1]

        dates = pd.to_datetime(df_input["date"]).dt.strftime("%Y-%m-%d").values
        inflow_vol = df_input["inflow_volume_m3"].values.astype(float)
        units = df_input["operating_units"].values.astype(int) if "operating_units" in df_input.columns else np.full(T, 2, dtype=int)

        # Allocate arrays for exact non-linear hydraulic evaluation
        pond_level = np.zeros(T, dtype=float)
        active_pct = np.zeros(T, dtype=float)
        net_head = np.zeros(T, dtype=float)
        efficiency = np.zeros(T, dtype=float)
        avail_mw = np.zeros(T, dtype=float)
        gen_mwh_phys = np.zeros(T, dtype=float)
        gen_mwh_lp = np.zeros(T, dtype=float)
        unmet_env_vol = np.zeros(T, dtype=float)

        for t in range(T):
            u_t = units[t]
            cap_mw = u_t * self.unit_cap_mw
            avail_mw[t] = cap_mw
            q_station_max = u_t * self.Q_unit_rated

            # Storage & Elevation
            s_t = s_end[t]
            elev = self.MOL + self.delta_H * ((max(0.0, s_t) / self.S_max) ** (1.0 / self.alpha))
            pond_level[t] = elev
            active_pct[t] = (s_t / self.S_max) * 100.0

            # Hydraulics & Loss
            q_turb = v_turb[t] / SECONDS_PER_DAY
            h_gross = elev - self.Z_tail
            h_loss = self.system_loss_rated * ((q_turb / self.Q_station_rated) ** 2) if q_turb > 0 else 0.0
            h_net = h_gross - h_loss
            net_head[t] = h_net

            # Wire-to-water loading efficiency
            eff = self.eff_nominal if q_turb > 0.35 * q_station_max else self.eff_part
            efficiency[t] = eff

            # Physical non-linear generation with station continuous ceiling
            if v_turb[t] > 0:
                e_calc = (self.rho * self.g * v_turb[t] * h_net * eff) / JOULES_PER_MWH
                gen_mwh_phys[t] = min(e_calc, cap_mw * HOURS_PER_DAY)
            else:
                gen_mwh_phys[t] = 0.0

            # Linear model generation estimate
            gen_mwh_lp[t] = self.k_e * v_turb[t]

            # Environmental deficit tracking
            total_rel = v_turb[t] + v_spill[t]
            unmet_env_vol[t] = max(0.0, self.env_flow_vol_day - total_rel)

        # Numerical Water Balance Residual Check on raw continuous solution
        wb_residuals = np.abs(s_end - (s_begin + inflow_vol - v_turb - v_spill - self.daily_evap_m3))
        max_wb_error = float(wb_residuals.max())

        # Exact decimal rounding for DataFrame presentation preserving continuity and boundaries
        v_turb_rnd = np.round(v_turb, 2)
        v_spill_rnd = np.round(v_spill, 2)
        inflow_rnd = np.round(inflow_vol, 2)
        s_begin_rnd = np.zeros(T, dtype=float)
        s_end_rnd = np.zeros(T, dtype=float)
        curr = round(S_0, 2)
        for t in range(T):
            s_begin_rnd[t] = curr
            val = round(curr + inflow_rnd[t] - v_turb_rnd[t] - v_spill_rnd[t] - self.daily_evap_m3, 2)
            if val < 0.0 and val >= -0.05:
                # Absorb sub-cent rounding artifact into turbine release to preserve non-negative storage
                v_turb_rnd[t] = round(v_turb_rnd[t] + val, 2)
                val = 0.0
            elif val > self.S_max and val <= self.S_max + 0.05:
                # Absorb sub-cent rounding artifact into spill
                v_spill_rnd[t] = round(v_spill_rnd[t] + (val - self.S_max), 2)
                val = self.S_max
            s_end_rnd[t] = val
            curr = val

        df_out = pd.DataFrame({
            "date": dates,
            "inflow_volume_m3": inflow_rnd,
            "beginning_storage_m3": s_begin_rnd,
            "turbine_release_m3": v_turb_rnd,
            "spill_volume_m3": v_spill_rnd,
            "end_storage_m3": s_end_rnd,
            "pond_level_masl": np.round(pond_level, 4),
            "active_storage_pct": np.round(active_pct, 2),
            "net_head_m": np.round(net_head, 2),
            "turbine_efficiency": np.round(efficiency, 4),
            "available_capacity_mw": np.round(avail_mw, 1),
            "operating_units": units,
            "generation_mwh": np.round(gen_mwh_phys, 3),
            "linear_generation_mwh": np.round(gen_mwh_lp, 3),
            "linear_approximation_error_mwh": np.round(gen_mwh_lp - gen_mwh_phys, 3),
            "unmet_env_release_m3": np.round(unmet_env_vol, 2),
            "dispatch_policy": "OPTIMAL_LP"
        })

        # Summary Metrics
        tot_phys_gwh = float(gen_mwh_phys.sum() / 1000.0)
        tot_lp_gwh = float(gen_mwh_lp.sum() / 1000.0)
        gap_pct = ((tot_lp_gwh - tot_phys_gwh) / tot_phys_gwh) * 100.0 if tot_phys_gwh > 0 else 0.0
        tot_spill_mcm = float(v_spill.sum() / 1e6)
        mean_cf = float((gen_mwh_phys.sum() / (T * self.installed_cap_mw * HOURS_PER_DAY)) * 100.0)

        metrics = {
            "solver_status": "OPTIMAL",
            "solver_message": res.message,
            "success": True,
            "solve_duration_sec": getattr(res, "solve_duration_sec", 0.0),
            "calendar_days": T,
            "total_physical_generation_gwh": round(tot_phys_gwh, 4),
            "total_linear_generation_gwh": round(tot_lp_gwh, 4),
            "linear_model_gap_pct": round(gap_pct, 4),
            "total_spill_mcm": round(tot_spill_mcm, 4),
            "capacity_factor_pct": round(mean_cf, 2),
            "initial_storage_m3": float(S_0),
            "terminal_storage_m3": float(s_end[-1]),
            "terminal_storage_target_m3": float(self.terminal_storage_target),
            "terminal_storage_satisfied": bool(s_end[-1] >= self.terminal_storage_target - 1.0),
            "max_water_balance_error_m3": float(max_wb_error),
            "water_balance_valid": bool(max_wb_error < self.tolerance),
            "total_unmet_env_release_m3": float(unmet_env_vol.sum()),
            "days_unmet_env_release": int((unmet_env_vol > 0.01).sum())
        }

        return df_out, metrics

    def run(self, df_input, initial_storage_m3=None):
        """High-level execute optimization and return evaluated DataFrame and metrics."""
        res = self.optimize(df_input, initial_storage_m3)
        df_out, metrics = self.evaluate(res, df_input, initial_storage_m3)
        return df_out, metrics, res


def load_config(config_path="scenarios_config.json"):
    """Load configuration from JSON file."""
    if not os.path.exists(config_path):
        fallback = os.path.join(os.path.dirname(__file__), config_path)
        if os.path.exists(fallback):
            config_path = fallback
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_optimization_dataset(cfg, scenario="baseline", dataset_path=None, forecast_path=None,
                              split="full", start_date=None, end_date=None):
    """
    Loads and filters the appropriate hydrological dataset for optimization, supporting
    historical baseline splits, custom date ranges, and future ECMWF forecasts.

    Returns:
    --------
    tuple : (pd.DataFrame, bool is_forecast)
    """
    workspace_dir = os.path.dirname(os.path.abspath(__file__))

    # Detect if future forecast is requested or implied by date range
    is_future_request = False
    if forecast_path is not None:
        is_future_request = True
    elif start_date is not None and str(start_date) >= "2026-10-18":
        is_future_request = True

    if is_future_request:
        fc_path = forecast_path
        if fc_path is None or not os.path.exists(fc_path):
            candidates = [
                os.path.join(workspace_dir, "..", "..", "data_pipelines", "rainfall_forecast", "kukule_ganga_15day_forecast.csv"),
                os.path.join(workspace_dir, "..", "Rainfall data", "kukule_ganga_15day_forecast.csv"),
                os.path.join(workspace_dir, "Rainfall data", "kukule_ganga_15day_forecast.csv"),
                os.path.join(workspace_dir, "kukule_ganga_15day_forecast.csv")
            ]
            for c in candidates:
                if os.path.exists(c):
                    fc_path = c
                    break

        if fc_path is None or not os.path.exists(fc_path):
            raise FileNotFoundError(f"Future forecast dataset not found. Searched candidates: {candidates}")

        print(f"[LP Optimizer] Loading future forecast dataset: {fc_path}")
        df_fc_raw = pd.read_csv(fc_path)
        df_fc = pd.DataFrame()
        df_fc["date"] = pd.to_datetime(df_fc_raw["date"]).dt.strftime("%Y-%m-%d")

        if "inflow_median_m3s" in df_fc_raw.columns:
            df_fc["estimated_inflow_m3s"] = df_fc_raw["inflow_median_m3s"].astype(float)
            df_fc["inflow_volume_m3"] = df_fc_raw["inflow_median_m3s"].astype(float) * SECONDS_PER_DAY
        elif "inflow_volume_m3" in df_fc_raw.columns:
            df_fc["inflow_volume_m3"] = df_fc_raw["inflow_volume_m3"].astype(float)
            df_fc["estimated_inflow_m3s"] = df_fc["inflow_volume_m3"] / SECONDS_PER_DAY
        else:
            raise ValueError(f"Unrecognized inflow columns in forecast dataset: {fc_path}")

        df_fc["operating_units"] = 2
        df_fc["data_status"] = df_fc_raw.get("data_status", "PROVISIONAL_SYNTHETIC_ECMWF_GUIDED")

        # Support extending date range if requested past forecast end (e.g. up to 2026-11-03)
        if end_date is not None:
            target_end_dt = pd.to_datetime(end_date)
            max_fc_dt = pd.to_datetime(df_fc["date"].iloc[-1])
            if target_end_dt > max_fc_dt:
                curr_dt = max_fc_dt
                last_q = float(df_fc["estimated_inflow_m3s"].iloc[-1])
                recession_k = 0.035
                extended_rows = []
                while curr_dt < target_end_dt:
                    curr_dt += pd.Timedelta(days=1)
                    last_q = last_q * (1.0 - recession_k)
                    extended_rows.append({
                        "date": curr_dt.strftime("%Y-%m-%d"),
                        "estimated_inflow_m3s": round(last_q, 4),
                        "inflow_volume_m3": round(last_q * SECONDS_PER_DAY, 2),
                        "operating_units": 2,
                        "data_status": "PROVISIONAL_SYNTHETIC_EXTENDED_RECESSION"
                    })
                if extended_rows:
                    df_fc = pd.concat([df_fc, pd.DataFrame(extended_rows)], ignore_index=True)

        if start_date is not None:
            df_fc = df_fc[df_fc["date"] >= str(start_date)].copy()
        if end_date is not None:
            df_fc = df_fc[df_fc["date"] <= str(end_date)].copy()

        return df_fc.reset_index(drop=True), True

    # Standard historical baseline simulation dataset
    if dataset_path is None:
        scen_out = cfg.get("scenarios", {}).get(scenario, {}).get("output_dir", f"scenarios/scenario_{scenario}")
        dataset_path = os.path.join(workspace_dir, scen_out, "synthetic_kukule_integrated_dataset_5years.csv")
        if not os.path.exists(dataset_path):
            dataset_path = os.path.join(workspace_dir, "synthetic_kukule_dataset", "synthetic_kukule_integrated_dataset_5years.csv")

    print(f"[LP Optimizer] Loading dataset: {dataset_path}")
    df_raw = pd.read_csv(dataset_path)
    df_raw["dt"] = pd.to_datetime(df_raw["date"])

    if start_date is not None or end_date is not None:
        df_eval = df_raw.copy()
        if start_date is not None:
            df_eval = df_eval[df_eval["date"] >= str(start_date)]
        if end_date is not None:
            df_eval = df_eval[df_eval["date"] <= str(end_date)]
    else:
        if split == "dev":
            df_eval = df_raw[(df_raw["dt"] >= "2021-10-19") & (df_raw["dt"] <= "2025-10-18")].copy()
        elif split == "test":
            df_eval = df_raw[(df_raw["dt"] >= "2025-10-19") & (df_raw["dt"] <= "2026-10-18")].copy()
        else:
            df_eval = df_raw.copy()

    df_eval.drop(columns=["dt"], inplace=True)
    return df_eval.reset_index(drop=True), False


def main():
    parser = argparse.ArgumentParser(description="Kukule Ganga Genuine LP Reservoir Dispatch Optimizer")
    parser.add_argument("--config", default="scenarios_config.json", help="Path to scenario configuration file")
    parser.add_argument("--scenario", default="baseline", help="Scenario ID (e.g. baseline, alt_a, alt_b, alt_c)")
    parser.add_argument("--dataset", default=None, help="Path to input integrated dataset CSV")
    parser.add_argument("--forecast", default=None, help="Path to future forecast CSV (e.g. kukule_ganga_15day_forecast.csv)")
    parser.add_argument("--split", choices=["full", "dev", "test"], default="full", help="Chronological split")
    parser.add_argument("--start-date", default=None, help="Start date for optimization (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=None, help="End date for optimization (YYYY-MM-DD)")
    parser.add_argument("--initial-storage", type=float, default=None, help="Initial active storage S_0 [m3]")
    parser.add_argument("--terminal-storage", type=float, default=None, help="Target terminal storage S_T [m3]")
    parser.add_argument("--enforce-env-flow", action="store_true", help="Add hard constraint for environmental flow")
    parser.add_argument("--output", default="lp_results.csv", help="Path to save output results CSV")
    parser.add_argument("--output-dir", default=None, help="Directory to save graphs and optimization schedule")
    parser.add_argument("--no-plots", action="store_true", help="Run optimizer without generating visualization graphs")
    parser.add_argument("--show-plots", action="store_true", help="Display interactive graphical windows if supported")
    args = parser.parse_args()

    cfg = load_config(args.config)
    workspace_dir = os.path.dirname(os.path.abspath(__file__))

    df_eval, is_forecast = load_optimization_dataset(
        cfg=cfg,
        scenario=args.scenario,
        dataset_path=args.dataset,
        forecast_path=args.forecast,
        split=args.split,
        start_date=args.start_date,
        end_date=args.end_date
    )

    if len(df_eval) == 0:
        print("[ERROR] Selected optimization date range resulted in 0 records! Check --start-date and --end-date.")
        sys.exit(1)

    start_str = df_eval["date"].iloc[0]
    end_str = df_eval["date"].iloc[-1]
    split_label = f"PERIOD {start_str} to {end_str}" if (args.start_date or args.end_date or is_forecast) else f"{args.split.upper()} SPLIT"

    print(f"[LP Optimizer] Solving scenario='{args.scenario}' on {split_label} ({len(df_eval)} days)...")
    optimizer = KukuleLPOptimizer(
        config_dict=cfg,
        scenario=args.scenario,
        terminal_storage_target=args.terminal_storage,
        enforce_env_flow=args.enforce_env_flow
    )

    df_res, metrics, res = optimizer.run(df_eval, initial_storage_m3=args.initial_storage)

    print("\n" + "=" * 65)
    print(f"LP OPTIMIZER EXECUTION SUMMARY ({split_label})")
    print("=" * 65)
    print(f"Solver Status                : {metrics['solver_status']} (HiGHS)")
    print(f"Solver Message               : {metrics['solver_message']}")
    print(f"Solve Duration               : {metrics.get('solve_duration_sec', 0.0):.3f} seconds")
    print(f"Calendar Days Optimized      : {metrics['calendar_days']}")
    
    if metrics["success"]:
        print(f"Total Physical Generation    : {metrics['total_physical_generation_gwh']:.3f} GWh")
        print(f"Total Linear Generation (LP) : {metrics['total_linear_generation_gwh']:.3f} GWh")
        print(f"Linear Model Gap             : {metrics['linear_model_gap_pct']:+.2f} %")
        print(f"Total Spillway Overflow      : {metrics['total_spill_mcm']:.3f} MCM")
        print(f"Station Capacity Factor      : {metrics['capacity_factor_pct']:.2f} %")
        print(f"Initial Storage (S_0)        : {metrics['initial_storage_m3']:,.1f} m3")
        print(f"Terminal Storage (S_T)       : {metrics['terminal_storage_m3']:,.1f} m3 (Target: {metrics['terminal_storage_target_m3']:,.1f} m3)")
        print(f"Terminal Storage Satisfied   : {'YES' if metrics['terminal_storage_satisfied'] else 'NO'}")
        print(f"Max Water Balance Error      : {metrics['max_water_balance_error_m3']:.8f} m3 (Valid: {metrics['water_balance_valid']})")
        print(f"Unmet Env. Release Volume    : {metrics['total_unmet_env_release_m3']:,.1f} m3 (Days: {metrics['days_unmet_env_release']})")
    print("=" * 65)

    if args.output and df_res is not None:
        df_res.to_csv(args.output, index=False)
        print(f"[LP Optimizer] Output written to: {args.output}")

    # Generate Visualization Outputs if successful and not suppressed
    if metrics["success"] and not args.no_plots and df_res is not None and len(df_res) > 0:
        start_clean = start_str.replace("-", "")
        end_clean = end_str.replace("-", "")

        if args.output_dir:
            out_dir = args.output_dir
        elif is_forecast or (args.start_date is not None):
            out_dir = os.path.join(workspace_dir, "outputs", f"future_{start_clean}_{end_clean}")
        else:
            out_dir = os.path.join(workspace_dir, "outputs", f"{args.split}_{start_clean}_{end_clean}")

        os.makedirs(out_dir, exist_ok=True)
        schedule_path = os.path.join(out_dir, "optimization_schedule.csv")
        df_res.to_csv(schedule_path, index=False)

        from lp_plotter import generate_all_future_lp_plots
        plots = generate_all_future_lp_plots(
            df_res=df_res,
            output_dir=out_dir,
            is_forecast=is_forecast,
            show_plots=args.show_plots
        )

        print("\n" + "=" * 70)
        print("VISUALIZATION OUTPUTS")
        print("=" * 70)
        print(f"Optimization period: {start_str} to {end_str}")
        print(f"Generation graph: {plots['generation_graph']}")
        print(f"Reservoir storage graph: {plots['storage_graph']}")
        print(f"Inflow/release/spill graph: {plots['flow_graph']}")
        print(f"Water allocation graph: {plots['allocation_graph']}")
        print(f"Daily results CSV: {os.path.abspath(schedule_path)}")
        print("=" * 70)

    return df_res, metrics


if __name__ == "__main__":
    main()
