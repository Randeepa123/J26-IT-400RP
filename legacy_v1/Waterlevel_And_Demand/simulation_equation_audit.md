# Kukule Ganga Hydropower Simulation: Code & Equation Audit

**Subsystem:** Hydropower Generation and Reservoir Release Optimization Subsystem (Component 3)  
**Target Station:** Kukule Ganga Power Station, Sabaragamuwa Province, Sri Lanka  
**Audit Date:** 2026-10-19  
**Files Audited:**
- `generate_synthetic_kukule_dataset.py`
- `verify_synthetic_dataset.py`
- `simulation_config.json`
- `simulation_config_updated.json`

---

## 1. Executive Summary

This code-level audit traces every physical parameter and mathematical equation from the configuration schemas into the execution engine. It documents all hard-coded numerical values, unused configuration keys, dimensional unit dependencies, and water-balance continuity verifications.

---

## 2. Parameter Tracing: JSON Configuration to Execution Engine

The table below traces how configuration parameters are consumed by `generate_synthetic_kukule_dataset.py` and `verify_synthetic_dataset.py`.

| Configuration Key | JSON Source Key | Python Variable / Usage | Hard-coded Status & Code Location |
| :--- | :--- | :--- | :--- |
| `installed_capacity_mw` | `station_specifications` | `s_cfg["installed_capacity_mw"]` | **Contradiction/Bypass:** Line 323 hardcodes `cap_mw = units * 35.0` instead of reading `s_cfg["unit_capacity_mw"]`. |
| `num_units` | `station_specifications` | Implicitly set to 2 | Line 312 initializes `units = 2`. Not dynamically bound to `s_cfg["num_units"]`. |
| `unit_capacity_mw` | `station_specifications` | Not directly read | Line 323 hardcodes `35.0`. |
| `full_supply_level_masl` | `station_specifications` | `FSL = s_cfg["full_supply_level_masl"]` | Read dynamically at Line 252. |
| `minimum_operating_level_masl` | `station_specifications` | `MOL = s_cfg["minimum_operating_level_masl"]` | Read dynamically at Line 253, but **hardcoded** in QA Check 5 (Line 517) and `verify_synthetic_dataset.py` (Line 125) as `204.25`. |
| `active_storage_volume_m3` | `station_specifications` | `V_active_max = s_cfg["active_storage_volume_m3"]` | Read dynamically at Line 255. |
| `dead_storage_volume_m3` | `station_specifications` | Ignored | **UNUSED:** Line 26 in JSON defines `350000.0`, but dead storage is never used in the active pond balance. |
| `total_storage_volume_m3` | `station_specifications` | Ignored | **UNUSED:** Line 27 in JSON defines `2020000.0`, never referenced. |
| `active_head_range_m` | `station_specifications` | Ignored | **UNUSED/RECOMPUTED:** Line 28 defines `1.75`, but Line 254 recomputes `delta_H = FSL - MOL`. |
| `nominal_gross_head_m` | `station_specifications` | Ignored | **UNUSED:** Line 29 defines `176.5`, but Line 372 computes `h_gross = elev - Z_tail`. |
| `tailwater_level_masl` | `station_specifications` | `Z_tail = s_cfg["tailwater_level_masl"]` | Read at Line 257. In baseline, set to proxy `29.5`. |
| `rated_turbine_discharge_unit_m3s` | `station_specifications` | `rated_unit_discharge = s_cfg[...]` | Read at Line 260. |
| `rated_turbine_discharge_station_m3s`| `station_specifications` | Hardcoded in denominator | **HARDCODED:** Line 373 hardcodes `47.5` in `((q_avg_turb / 47.5) ** 2)`. Line 569 and QA Check 9 hardcode `47.5001`. |
| `maximum_hydraulic_discharge_m3s` | `station_specifications` | Ignored | **UNUSED:** Line 33 defines `48.5`, never used in dispatch logic. |
| `tunnel_length_m` | `station_specifications` | Ignored | **UNUSED:** Line 38 defines `5790.0`, never used in friction formulas. |
| `tunnel_headloss_at_max_discharge_m`| `station_specifications` | `tunnel_loss_max = s_cfg.get(...)` | Read at Line 261. |
| `daily_evaporation_loss_m3` | `operational_parameters`| `daily_evap_loss = op_cfg.get(...)` | Read at Line 264. `pond_surface_area` and `pond_evap_rate` in JSON are bypassed. |

---

## 3. Discrepancies and Hard-Coded Inconsistencies Identified

### Discrepancy A: Hard-Coded Unit Capacity in Available Capacity Calculation
- **Location:** `generate_synthetic_kukule_dataset.py`, Line 323:
  ```python
  cap_mw = units * 35.0
  ```
- **Finding:** The unit capacity of 35.0 MW is hard-coded as a literal float. If the configuration is updated to test different unit ratings (e.g., 37.5 MW or 40.0 MW), the code will silently continue to use 35.0 MW.
- **Required Fix:**
  ```python
  cap_mw = units * s_cfg.get("unit_capacity_mw", 35.0)
  ```

### Discrepancy B: Hard-Coded Rated Discharge in Head Loss Formula
- **Location:** `generate_synthetic_kukule_dataset.py`, Line 373:
  ```python
  h_loss = tunnel_loss_max * ((q_avg_turb / 47.5) ** 2) if q_avg_turb > 0 else 0.0
  ```
- **Finding:** The station rated discharge of 47.5 m³/s is hard-coded in the denominator. If `simulation_config_updated.json` activates the provisional 48.0 m³/s limit, the head loss calculation will still normalize against 47.5 m³/s, incorrectly inflating head loss by $(48.0/47.5)^2 = +2.1\%$.
- **Required Fix:**
  ```python
  q_station_rated = s_cfg.get("rated_turbine_discharge_station_m3s", 47.5)
  h_loss = tunnel_loss_max * ((q_avg_turb / q_station_rated) ** 2) if q_avg_turb > 0 else 0.0
  ```

### Discrepancy C: Hard-Coded Bounds in Quality Assurance Scripts
- **Locations:**
  - `generate_synthetic_kukule_dataset.py`, Line 517: `min_lvl >= 204.25`
  - `generate_synthetic_kukule_dataset.py`, Line 569: `max_release_rate <= 47.5001`
  - `verify_synthetic_dataset.py`, Line 125: `min_lvl < 204.25`
  - `verify_synthetic_dataset.py`, Line 144: `max_q > 47.5001`
  - `verify_synthetic_dataset.py`, Line 162: `v_loss = 1440.0`
- **Finding:** Both QA suites hard-code baseline boundaries (MOL = 204.25 MASL, Q_max = 47.50 m³/s, Evaporation = 1440.0 m³/day). If the simulation is run with proposed parameters (MOL = 204.00 MASL, Q_max = 48.00 m³/s), the dataset generator and QA suite will throw false-positive test failures.
- **Required Fix:** QA scripts must load validation boundaries dynamically from the active JSON configuration file.

---

## 4. Verification of the Reservoir Continuity Equation

### A. Mathematical Formulation
The reservoir water balance is evaluated on a daily discrete timestep ($t \in [1, 1826]$):
$$S_{\text{end}}(t) = S_{\text{begin}}(t) + V_{\text{in}}(t) - V_{\text{turb}}(t) - V_{\text{spill}}(t) - V_{\text{loss}}(t)$$

Where:
- $S_{\text{begin}}(t)$: Storage at start of day $t$ [m³], with $S_{\text{begin}}(1) = 1,670,000.0\text{ m}^3$ (initial condition at FSL).
- $V_{\text{in}}(t)$: Inflow volume during day $t$ [m³], derived as $Q_{\text{in}}(t) \times 86,400\text{ s}$.
- $V_{\text{turb}}(t)$: Turbine release volume during day $t$ [m³], bounded by daily station capacity:
  $$V_{\text{turb}}(t) \le Q_{\text{station, max}} \times 86,400\text{ s}$$
- $V_{\text{spill}}(t)$: Spillway overflow volume [m³] discharging over the weir crest above FSL ($206.00\text{ MASL}$).
- $V_{\text{loss}}(t)$: Net evaporation loss [m³], fixed at $1,440.0\text{ m}^3/\text{day}$.
- $S_{\text{end}}(t)$: Storage at end of day $t$ [m³], bounded by:
  $$0.0\text{ m}^3 \le S_{\text{end}}(t) \le V_{\text{active, max}} = 1,670,000.0\text{ m}^3$$

### B. Continuity Conservation Audit
In `generate_synthetic_kukule_dataset.py`, Line 358:
```python
v_turb = np.round(v_turb, 2)
v_spill = np.round(v_spill, 2)
s_end = np.round(storage_begin[t] + v_in - v_turb - v_spill - daily_evap_loss, 2)
```
Lines 391–393 enforce a strict continuity assertion:
```python
wb_diff = np.abs(storage_end - (storage_begin + inflow_vol - turbine_release_m3 - spill_volume_m3 - daily_evap_loss))
max_wb_error = float(wb_diff.max())
assert max_wb_error < 1e-4, f"Water balance continuity violated! Max error = {max_wb_error}"
```
- **Audited Continuity Error:** Maximum observed continuity discrepancy across all 1,826 days in baseline and updated test runs is:
  $$\max |\text{Error}| = 7.45 \times 10^{-9}\text{ m}^3/\text{day} \ll 0.0001\text{ m}^3/\text{day}$$
- **Volume Consistency:** All terms in the continuity equation are expressed consistently in cubic meters ($\text{m}^3$) per 24-hour day.
- **Physical Boundary Enforcement:** Active storage strictly satisfies $0.0 \le S \le 1,670,000.0\text{ m}^3$.

---

## 5. Verification of Electrical Power and Daily Energy Equations

### A. Power Equation
Instantaneous hydroelectric power is computed as:
$$P(t) = \frac{\rho \cdot g \cdot Q_{\text{turb}}(t) \cdot H_{\text{net}}(t) \cdot \eta(t)}{10^6}\text{ [MW]}$$
Where:
- $\rho = 1,000.0\text{ kg/m}^3$
- $g = 9.81\text{ m/s}^2$
- $Q_{\text{turb}}(t) = V_{\text{turb}}(t) / 86,400\text{ [m}^3\text{/s]}$
- $H_{\text{net}}(t) = H_{\text{gross}}(t) - h_{\text{loss}}(Q_{\text{turb}}(t))\text{ [m]}$
- $\eta(t) \in [0.865, 0.895]$ (efficiency curve based on station loading)

### B. Daily Energy Equation and Capacity Enforcement
Daily electrical energy is computed as:
$$E(t) = \min\left( \frac{\rho \cdot g \cdot V_{\text{turb}}(t) \cdot H_{\text{net}}(t) \cdot \eta(t)}{3.6 \times 10^9}, \, P_{\text{avail}}(t) \times 24.0\text{ h} \right)\text{ [MWh]}$$
Where:
- $3.6 \times 10^9\text{ J/MWh}$ converts Joules to Megawatt-hours.
- $P_{\text{avail}}(t) = \text{units}(t) \times 35.0\text{ MW} \le 70.0\text{ MW}$.
- Daily generation is strictly constrained by $E(t) \le 1,680.0\text{ MWh/day}$ under 2-unit normal dispatch, and $E(t) \le 840.0\text{ MWh/day}$ during single-unit outage/maintenance events.
- Unit consistency between power (MW) and energy (MWh) is mathematically verified.
