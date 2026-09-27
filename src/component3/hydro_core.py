"""
hydro_core.py
=============
Shared hydropower physics for Component 3 (v2): parameters, storage-elevation curve, generation,
and the single authoritative daily reservoir step used by the v2 environment, the rolling-horizon
LP, the reference policy and the unified evaluator.

Key v2 rules (see operations_v2 in scenarios_config.json):
  * Hard floor  : storage can never go below the floor level (default 204.00 MASL).
  * Reserve     : turbines may not draw storage below the operating reserve (default 20% of active storage) when
                  enforce_reserve is on; only the mandatory weir release may dip below it (down to the floor).
  * Mandatory   : environmental + irrigation release passes the weir (non-generating) and is served
                  BEFORE turbines. It is NOT spill. Shortfall is reported as unmet.
  * Spill       : only water leaving over the weir because the pond is full. Split into
                  unavoidable (turbines at capacity) and avoidable (turbines below capacity).
  * Demand      : energy is valued with a daily demand weight w_t.

Synthetic-data disclaimer: all inputs are synthetic / assumed unless stated otherwise.
"""

import os
import json
from dataclasses import dataclass, field

import numpy as np

import paths

SECONDS_PER_DAY = 86400.0
HOURS_PER_DAY = 24.0
JOULES_PER_MWH = 3.6e9

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_config(path=None):
    path = path or paths.SCENARIOS_CONFIG
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class HydroParams:
    S_max: float = 1670000.0
    FSL: float = 206.0
    MOL: float = 204.0
    alpha: float = 1.05
    Z_tail: float = 19.6
    loss_rated: float = 10.3
    Q_station: float = 47.5
    Q_unit: float = 23.75
    unit_mw: float = 35.0
    num_units: int = 2
    eff_nom: float = 0.895
    eff_part: float = 0.865
    evap_m3: float = 1440.0
    rho: float = 1000.0
    g: float = 9.81
    # v2 operating rules
    floor_level: float = 204.0
    reserve_fraction: float = 0.20
    terminal_fraction: float = 0.50
    enforce_reserve: bool = True
    env_flow_m3s: float = 2.0
    irrigation_m3s: dict = field(default_factory=dict)  # month(int) -> extra m3/s
    weight_clip: tuple = (0.8, 1.5)
    reward_weights: dict = field(default_factory=dict)
    lp_horizon_days: int = 15

    # ---- derived -------------------------------------------------------
    def __post_init__(self):
        self.delta_H = self.FSL - self.MOL
        h_rated_net = (self.FSL + self.MOL) / 2.0 - self.Z_tail - self.loss_rated
        self.H_rated_net = h_rated_net
        self.k_e = self.rho * self.g * h_rated_net * self.eff_nom / JOULES_PER_MWH  # MWh/m3
        self.installed_mw = self.unit_mw * self.num_units
        self.max_daily_mwh = self.installed_mw * HOURS_PER_DAY
        ratio = max(0.0, (self.floor_level - self.MOL) / self.delta_H)
        self.S_floor = float(self.S_max * ratio ** self.alpha)
        self.S_reserve = max(self.S_floor, self.reserve_fraction * self.S_max)
        self.S_terminal = max(self.S_reserve, self.terminal_fraction * self.S_max)
        self.S_hold = self.S_reserve if self.enforce_reserve else self.S_floor   # lowest storage turbines may draw to

    @classmethod
    def from_config(cls, cfg=None, scenario="operational_v2"):
        cfg = cfg or load_config()
        s = cfg.get("shared_station_specifications", {})
        op = cfg.get("operational_and_scenario_parameters", {})
        sc = cfg.get("scenarios", {}).get(scenario, {})
        v2 = cfg.get("operations_v2", {})
        irr = {int(k): float(v) for k, v in v2.get("irrigation_extra_release_m3s_by_month", {}).items()}
        return cls(
            S_max=float(s.get("active_storage_volume_m3", 1670000.0)),
            FSL=float(s.get("full_supply_level_masl", 206.0)),
            MOL=float(sc.get("minimum_operating_level_masl", 204.0)),
            alpha=float(s.get("elevation_storage_alpha", 1.05)),
            Z_tail=float(sc.get("tailwater_level_masl", s.get("tailwater_level_masl", 19.6))),
            loss_rated=float(sc.get("tunnel_headloss_at_max_discharge_m",
                                    s.get("tunnel_headloss_at_max_discharge_m", 10.3))),
            Q_station=float(sc.get("rated_turbine_discharge_station_m3s", 47.5)),
            Q_unit=float(sc.get("rated_turbine_discharge_unit_m3s", 23.75)),
            unit_mw=float(s.get("unit_capacity_mw", 35.0)),
            num_units=int(s.get("num_units", 2)),
            eff_nom=float(s.get("nominal_overall_efficiency", 0.895)),
            eff_part=float(s.get("part_load_efficiency", 0.865)),
            evap_m3=float(op.get("daily_evaporation_loss_m3", 1440.0)),
            rho=float(s.get("water_density_kg_m3", 1000.0)),
            g=float(s.get("gravity_acceleration_m_s2", 9.81)),
            floor_level=float(v2.get("hard_floor_level_masl", sc.get("minimum_operating_level_masl", 204.0))),
            reserve_fraction=float(v2.get("reserve_fraction_of_active_storage", 0.20)),
            terminal_fraction=float(v2.get("terminal_target_fraction_of_active_storage", 0.50)),
            enforce_reserve=bool(v2.get("enforce_reserve_as_hard_limit", True)),
            env_flow_m3s=float(v2.get("environmental_flow_m3s", 2.0)),
            irrigation_m3s=irr,
            weight_clip=tuple(v2.get("demand_weight_clip", [0.8, 1.5])),
            reward_weights=dict(v2.get("reward_weights", {})),
            lp_horizon_days=int(v2.get("lp_horizon_days", 15)),
        )

    # ---- geometry ------------------------------------------------------
    def elevation(self, storage):
        r = min(max(storage, 0.0) / self.S_max, 1.0)
        return self.MOL + self.delta_H * r ** (1.0 / self.alpha)

    # ---- release limits --------------------------------------------------
    def turbine_cap_m3(self, units):
        """Max daily turbine volume: min(hydraulic limit, electrical ceiling / k_e) (LP convention)."""
        u = int(units)
        hyd = u * self.Q_unit * SECONDS_PER_DAY
        ele = u * self.unit_mw * HOURS_PER_DAY / self.k_e
        return min(hyd, ele)

    def mandatory_m3(self, month):
        """Daily environmental + irrigation weir release [m3]."""
        return (self.env_flow_m3s + self.irrigation_m3s.get(int(month), 0.0)) * SECONDS_PER_DAY

    def clip_weight(self, w):
        return float(np.clip(w, self.weight_clip[0], self.weight_clip[1]))

    # ---- generation --------------------------------------------------------
    def generation(self, v_turb, s_end, units):
        """Exact non-linear physical daily energy [MWh]. Returns (e_mwh, h_net, eff)."""
        u = int(units)
        cap_mw = u * self.unit_mw
        elev = self.elevation(s_end)
        q = v_turb / SECONDS_PER_DAY
        h_loss = self.loss_rated * (q / self.Q_station) ** 2 if q > 0 else 0.0
        h_net = elev - self.Z_tail - h_loss
        eff = self.eff_nom if q > 0.35 * (u * self.Q_unit) else self.eff_part
        if v_turb <= 0.0 or u <= 0:
            return 0.0, h_net, eff
        e = self.rho * self.g * v_turb * h_net * eff / JOULES_PER_MWH
        return min(e, cap_mw * HOURS_PER_DAY), h_net, eff

    # ---- authoritative daily step -------------------------------------------
    def step(self, s_begin, v_in, units, month, v_turb_request, weight=1.0):
        """
        Advance one day. Enforces: mandatory weir release first, hard floor (safety projection),
        storage cap with spill. Returns a dict (all volumes in m3, energy in MWh).
        """
        w_avail = max(0.0, s_begin + v_in - self.evap_m3)
        mand_req = self.mandatory_m3(month)
        mand = min(mand_req, max(0.0, w_avail - self.S_floor))
        unmet = mand_req - mand
        w1 = w_avail - mand

        cap = self.turbine_cap_m3(units)
        feasible_max = min(cap, max(0.0, w1 - self.S_hold))
        v_turb = float(min(max(v_turb_request, 0.0), feasible_max))
        projected = bool(v_turb_request > feasible_max + 1e-6)

        s_pot = w1 - v_turb
        spill = max(0.0, s_pot - self.S_max)
        s_end = s_pot - spill

        e, h_net, eff = self.generation(v_turb, s_end, units)
        spill_avoidable = min(spill, max(0.0, cap - v_turb))
        return {
            "turbine_release_m3": v_turb, "spill_volume_m3": spill, "end_storage_m3": s_end,
            "mandatory_release_m3": mand, "mandatory_required_m3": mand_req, "unmet_mandatory_m3": unmet,
            "turbine_cap_m3": cap, "feasible_turbine_max_m3": feasible_max,
            "spill_avoidable_m3": spill_avoidable, "spill_unavoidable_m3": spill - spill_avoidable,
            "spill_energy_equiv_mwh": spill * self.k_e, "weighted_spill_energy_equiv_mwh": spill * self.k_e * weight,
            "generation_mwh": e, "weighted_generation_mwh": e * weight,
            "pond_level_masl": self.elevation(s_end), "net_head_m": h_net, "efficiency": eff,
            "action_projected": projected,
            "water_balance_residual_m3": abs(s_end - (s_begin + v_in - self.evap_m3 - mand - v_turb - spill))
            if w_avail > 0 and s_begin + v_in - self.evap_m3 >= 0 else 0.0,
        }
