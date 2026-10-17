"""
reference_release_policy.py
===========================
Heuristic Benchmark Release Policy for Kukule Ganga Power Station
Target Facility : Kukule Ganga Power Station, Sabaragamuwa Province, Sri Lanka
Component       : Component 3 - Hydropower Generation & Reservoir Release Optimization Subsystem

Purpose:
--------
Implements a feasible, deterministic rule-curve baseline dispatch policy for run-of-river
hydropower with daily regulating pondage. Serves as the benchmark against which the Linear
Programming (LP) and Deep Q-Network (DQN) optimization models are evaluated.

Physical & Hydraulic Logic:
---------------------------
1. Available water calculation:
     W_avail,t = S_{t-1} + V_in,t - V_loss,t
2. Surplus flow (High Inflow):
     If W_avail,t >= V_turb_max,t + S_max:
       V_turb,t = V_turb_max,t
       S_t      = S_max
       V_spill,t = W_avail,t - V_turb,t - S_max
3. Normal flow (Moderate Inflow):
     If V_turb_max,t <= W_avail,t < V_turb_max,t + S_max:
       V_turb,t = V_turb_max,t
       S_t      = W_avail,t - V_turb,t
       V_spill,t = 0.0
4. Deficit flow (Low Inflow):
     If W_avail,t < V_turb_max,t:
       S_target,t = min(0.35 * S_max, max(0.0, W_avail,t * 0.25))
       V_turb,t   = min(V_turb_max,t, max(0.0, W_avail,t - S_target,t))
       S_t        = max(0.0, W_avail,t - V_turb,t)
       V_spill,t  = 0.0

5. Strict Mass Balance & Non-Linear Hydraulic Evaluation:
     Evaluates head variation, friction loss, turbine-generator wire-to-water efficiency,
     and enforces the 70.0 MW continuous electrical capacity ceiling (1,680.0 MWh/day).

Author: Antigravity Research Pipeline
Date  : October 2026
"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd

# Physical constants
SECONDS_PER_DAY = 86400.0
HOURS_PER_DAY = 24.0
JOULES_PER_MWH = 3.6e9
RHO = 1000.0        # Water density [kg/m³]
G = 9.81            # Gravitational acceleration [m/s²]

# Default engineering parameters (Baseline scenario)
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


class KukuleReferencePolicy:
    """Deterministic Rule-Curve Release Policy for Kukule Ganga Hydropower."""

    def __init__(self, config_dict=None, scenario="baseline"):
        """Initialize parameters from configuration or defaults."""
        self.scenario = scenario
        self.config = config_dict or {}
        self._load_parameters()

    def _load_parameters(self):
        """Extract parameters from configuration dictionary."""
        s_cfg = self.config.get("shared_station_specifications", {})
        op_cfg = self.config.get("operational_and_scenario_parameters", {})
        scenarios = self.config.get("scenarios", {})
        scen_cfg = scenarios.get(self.scenario, {})

        # Storage & Levels
        self.S_max = float(s_cfg.get("active_storage_volume_m3", DEFAULT_ACTIVE_STORAGE_M3))
        self.S_min = 0.0
        self.FSL = float(s_cfg.get("full_supply_level_masl", DEFAULT_FSL_MASL))
        self.MOL = float(scen_cfg.get("minimum_operating_level_masl",
                         s_cfg.get("minimum_operating_level_masl", DEFAULT_MOL_MASL)))
        self.delta_H = self.FSL - self.MOL
        self.alpha = float(s_cfg.get("elevation_storage_alpha", DEFAULT_ALPHA))

        # Hydraulics & Generation
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

        # Efficiency & Losses
        self.eff_nominal = float(s_cfg.get("nominal_overall_efficiency", DEFAULT_EFF_NOMINAL))
        self.eff_part = float(s_cfg.get("part_load_efficiency", DEFAULT_EFF_PART))
        self.daily_evap_m3 = float(op_cfg.get("daily_evaporation_loss_m3", DEFAULT_DAILY_EVAP_M3))
        self.rho = float(s_cfg.get("water_density_kg_m3", RHO))
        self.g = float(s_cfg.get("gravity_acceleration_m_s2", G))
        self.tolerance = float(op_cfg.get("daily_water_balance_tolerance_m3", 0.0001))

        # Linear water-to-power energy coefficient [MWh/m³]
        H_rated_net = (self.FSL + self.MOL) / 2.0 - self.Z_tail - self.system_loss_rated
        self.k_e = (self.rho * self.g * H_rated_net * self.eff_nominal) / JOULES_PER_MWH

    def run(self, df_input, initial_storage_m3=None):
        """
        Execute reference rule-curve dispatch on an input DataFrame.
        
        Parameters:
        -----------
        df_input : pd.DataFrame
            Must contain 'date', 'inflow_volume_m3', and optionally 'operating_units'.
        initial_storage_m3 : float, optional
            Starting active storage at t=0. Defaults to S_max (full pondage).
            
        Returns:
        --------
        pd.DataFrame with complete physical dispatch and generation trajectory.
        """
        n_days = len(df_input)
        if initial_storage_m3 is None:
            initial_storage = self.S_max
        else:
            initial_storage = float(initial_storage_m3)

        dates = pd.to_datetime(df_input["date"]).dt.strftime("%Y-%m-%d").values
        inflow_vol = df_input["inflow_volume_m3"].values.astype(float)
        
        if "operating_units" in df_input.columns:
            units_series = df_input["operating_units"].values.astype(int)
        else:
            units_series = np.full(n_days, 2, dtype=int)

        # Allocate arrays
        storage_begin = np.zeros(n_days, dtype=float)
        storage_end = np.zeros(n_days, dtype=float)
        turbine_release = np.zeros(n_days, dtype=float)
        spill_volume = np.zeros(n_days, dtype=float)
        pond_level_masl = np.zeros(n_days, dtype=float)
        active_storage_pct = np.zeros(n_days, dtype=float)
        net_head_m = np.zeros(n_days, dtype=float)
        efficiency = np.zeros(n_days, dtype=float)
        available_mw = np.zeros(n_days, dtype=float)
        generation_mwh = np.zeros(n_days, dtype=float)
        linear_gen_mwh = np.zeros(n_days, dtype=float)

        current_s = initial_storage

        for t in range(n_days):
            storage_begin[t] = current_s
            v_in = inflow_vol[t]
            u = units_series[t]
            cap_mw = u * self.unit_cap_mw
            available_mw[t] = cap_mw

            q_station_max = u * self.Q_unit_rated
            v_turb_max = q_station_max * SECONDS_PER_DAY

            # Net water available before new discharge
            w_avail = current_s + v_in - self.daily_evap_m3

            # Rule-Curve Dispatch Logic
            if w_avail >= v_turb_max + self.S_max:
                v_turb = v_turb_max
                s_end = self.S_max
                v_spill = w_avail - v_turb - self.S_max
            elif w_avail >= v_turb_max:
                v_turb = v_turb_max
                s_end = w_avail - v_turb
                v_spill = 0.0
            else:
                s_target = min(0.35 * self.S_max, max(0.0, w_avail * 0.25))
                v_turb = min(v_turb_max, max(0.0, w_avail - s_target))
                s_end = max(0.0, w_avail - v_turb)
                v_spill = 0.0

            # Guard against exceeding maximum active storage
            if s_end > self.S_max:
                v_spill += (s_end - self.S_max)
                s_end = self.S_max

            # Round to ensure exact float conservation
            v_turb = round(v_turb, 2)
            v_spill = round(v_spill, 2)
            s_end = round(storage_begin[t] + v_in - v_turb - v_spill - self.daily_evap_m3, 2)

            turbine_release[t] = v_turb
            spill_volume[t] = v_spill
            storage_end[t] = s_end
            current_s = s_end

            # Reservoir storage-to-elevation power-law curve
            elev = self.MOL + self.delta_H * ((s_end / self.S_max) ** (1.0 / self.alpha))
            pond_level_masl[t] = elev
            active_storage_pct[t] = (s_end / self.S_max) * 100.0

            # Hydraulic Net Head & Non-Linear Wire-to-Water Efficiency
            q_turb = v_turb / SECONDS_PER_DAY
            h_gross = elev - self.Z_tail
            h_loss = self.system_loss_rated * ((q_turb / self.Q_station_rated) ** 2) if q_turb > 0 else 0.0
            h_net = h_gross - h_loss
            net_head_m[t] = h_net

            eff = self.eff_nominal if q_turb > 0.35 * q_station_max else self.eff_part
            efficiency[t] = eff

            # Physical generation calculation with electrical ceiling
            if v_turb > 0:
                e_calc = (self.rho * self.g * v_turb * h_net * eff) / JOULES_PER_MWH
                e_mwh = min(e_calc, cap_mw * HOURS_PER_DAY)
            else:
                e_mwh = 0.0
            generation_mwh[t] = e_mwh
            linear_gen_mwh[t] = min(self.k_e * v_turb, cap_mw * HOURS_PER_DAY)

        # Verification: Daily water balance mass continuity
        wb_residuals = np.abs(storage_end - (storage_begin + inflow_vol - turbine_release - spill_volume - self.daily_evap_m3))
        max_wb_error = float(wb_residuals.max())
        assert max_wb_error < self.tolerance, f"Reference policy water balance error: {max_wb_error} m3"

        df_out = pd.DataFrame({
            "date": dates,
            "inflow_volume_m3": np.round(inflow_vol, 2),
            "beginning_storage_m3": np.round(storage_begin, 2),
            "turbine_release_m3": np.round(turbine_release, 2),
            "spill_volume_m3": np.round(spill_volume, 2),
            "end_storage_m3": np.round(storage_end, 2),
            "pond_level_masl": np.round(pond_level_masl, 4),
            "active_storage_pct": np.round(active_storage_pct, 2),
            "net_head_m": np.round(net_head_m, 2),
            "turbine_efficiency": np.round(efficiency, 4),
            "available_capacity_mw": np.round(available_mw, 1),
            "operating_units": units_series,
            "generation_mwh": np.round(generation_mwh, 3),
            "linear_generation_mwh": np.round(linear_gen_mwh, 3),
            "dispatch_policy": "REFERENCE_RULE_CURVE"
        })

        return df_out


def load_config(config_path="scenarios_config.json"):
    """Load configuration from JSON file."""
    if not os.path.exists(config_path):
        fallback = os.path.join(os.path.dirname(__file__), config_path)
        if os.path.exists(fallback):
            config_path = fallback
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Kukule Ganga Reference Rule-Curve Dispatch Policy")
    parser.add_argument("--config", default="scenarios_config.json", help="Path to scenario configuration file")
    parser.add_argument("--scenario", default="baseline", help="Scenario ID (e.g. baseline, alt_a, alt_b, alt_c)")
    parser.add_argument("--dataset", default=None, help="Path to input integrated dataset CSV")
    parser.add_argument("--split", choices=["full", "dev", "test"], default="full", help="Chronological split")
    parser.add_argument("--output", default=None, help="Path to save output CSV")
    args = parser.parse_args()

    # Load configuration
    cfg = load_config(args.config)

    # Determine input dataset path
    dataset_path = args.dataset
    if dataset_path is None:
        scen_out = cfg.get("scenarios", {}).get(args.scenario, {}).get("output_dir", f"scenarios/scenario_{args.scenario}")
        dataset_path = os.path.join(os.path.dirname(__file__), scen_out, "synthetic_kukule_integrated_dataset_5years.csv")
        if not os.path.exists(dataset_path):
            dataset_path = os.path.join(os.path.dirname(__file__), "synthetic_kukule_dataset", "synthetic_kukule_integrated_dataset_5years.csv")

    print(f"[Reference Policy] Reading dataset: {dataset_path}")
    df_raw = pd.read_csv(dataset_path)

    # Apply chronological split if specified
    df_raw["dt"] = pd.to_datetime(df_raw["date"])
    if args.split == "dev":
        df_eval = df_raw[(df_raw["dt"] >= "2021-10-19") & (df_raw["dt"] <= "2025-10-18")].copy()
    elif args.split == "test":
        df_eval = df_raw[(df_raw["dt"] >= "2025-10-19") & (df_raw["dt"] <= "2026-10-18")].copy()
    else:
        df_eval = df_raw.copy()
    df_eval.drop(columns=["dt"], inplace=True)

    print(f"[Reference Policy] Running scenario='{args.scenario}' on split='{args.split}' ({len(df_eval)} days)...")
    policy = KukuleReferencePolicy(cfg, scenario=args.scenario)
    df_res = policy.run(df_eval)

    # Print summary metrics
    total_energy_gwh = df_res["generation_mwh"].sum() / 1000.0
    total_spill_mcm = df_res["spill_volume_m3"].sum() / 1e6
    mean_cf = (df_res["generation_mwh"].sum() / (len(df_res) * 70.0 * 24.0)) * 100.0
    end_s = df_res["end_storage_m3"].iloc[-1]

    print("\n" + "=" * 60)
    print(f"REFERENCE RULE-CURVE DISPATCH RESULTS ({args.split.upper()} SPLIT)")
    print("=" * 60)
    print(f"Calendar Days Evaluated      : {len(df_res)}")
    print(f"Total Physical Generation    : {total_energy_gwh:.3f} GWh")
    print(f"Total Spill Volume           : {total_spill_mcm:.3f} MCM")
    print(f"Mean Capacity Factor (70 MW) : {mean_cf:.2f} %")
    print(f"Initial Active Storage (S_0) : {df_res['beginning_storage_m3'].iloc[0]:,.1f} m3")
    print(f"Terminal Active Storage (S_T): {end_s:,.1f} m3 ({end_s/policy.S_max*100:.1f}%)")
    print("=" * 60)

    if args.output:
        df_res.to_csv(args.output, index=False)
        print(f"[Reference Policy] Output written to: {args.output}")

    return df_res


if __name__ == "__main__":
    main()
