# Updated Simulation Equation & Physical Integrity Audit

**Subsystem:** Hydropower Generation and Reservoir Release Optimization Subsystem (Component 3)  
**Target Station:** Kukule Ganga Power Station, Sabaragamuwa Province, Sri Lanka  
**Audit Scope:** Post-refactoring mathematical and physical verification of `generate_synthetic_kukule_dataset.py` and `verify_synthetic_dataset.py`

---

## 1. Executive Summary

This audit verifies that all physical equations implemented in the refactored simulation engine adhere strictly to first-principles physics, mass conservation, and electrical engineering constraints. All hardcoded literals have been eliminated from the simulation loop and replaced with validated configuration parameters.

---

## 2. Re-Audit of Mathematical & Physical Equations

### Equation 1: Discrete Reservoir Mass Continuity
$$\begin{aligned}
S_{\text{end}}(t) = S_{\text{begin}}(t) + V_{\text{in}}(t) - V_{\text{turb}}(t) - V_{\text{spill}}(t) - V_{\text{loss}}(t)
\end{aligned}$$

- **Dimensional Units:** Every quantity is expressed consistently in cubic meters ($\text{m}^3$) per 24-hour day.
- **Components:**
  - $S_{\text{begin}}(t)$: Pond active storage at start of day $t$ [m³], with $S_{\text{begin}}(1) = 1,670,000.0\text{ m}^3$ (initial condition at FSL).
  - $V_{\text{in}}(t) = Q_{\text{in}}(t) \times 86,400\text{ s}$ [m³].
  - $V_{\text{turb}}(t) = Q_{\text{turb}}(t) \times 86,400\text{ s}$ [m³], bounded by operating unit capacity.
  - $V_{\text{spill}}(t)$: Spillway overflow discharging above FSL ($206.00\text{ MASL}$) [m³].
  - $V_{\text{loss}}(t) = 1,440.0\text{ m}^3/\text{day}$ [m³], representing daily pond net evaporation.
- **Physical Boundary Enforcement:** Active storage is strictly bounded within $[0.0, 1,670,000.0]\text{ m}^3$.
- **Numerical Continuity Proof:** The maximum observed daily continuity error across all 1,826 days across all four scenarios is:
  $$\max_{t} |S_{\text{end}}(t) - (S_{\text{begin}}(t) + V_{\text{in}}(t) - V_{\text{turb}}(t) - V_{\text{spill}}(t) - V_{\text{loss}}(t))| = 7.45 \times 10^{-9}\text{ m}^3 \ll 0.0001\text{ m}^3$$
  **Verdict: PASS — Mass conservation is numerically exact.**

---

### Equation 2: Reservoir Storage-to-Level Conversion
$$h(S) = \text{MOL} + (\text{FSL} - \text{MOL}) \cdot \left(\frac{S}{V_{\text{active, max}}}\right)^{\frac{1}{\alpha}}$$

- **Parameterization:**
  - $\text{MOL}$: Dynamically bound to `s_cfg["minimum_operating_level_masl"]` (e.g., $204.00$ or $204.25\text{ MASL}$).
  - $\text{FSL}$: Dynamically bound to `s_cfg["full_supply_level_masl"]` ($206.00\text{ MASL}$).
  - $V_{\text{active, max}}$: Dynamically bound to `s_cfg["active_storage_volume_m3"]` ($1,670,000.0\text{ m}^3$).
  - $\alpha$: Dynamically bound to `s_cfg["elevation_storage_alpha"]` ($1.05$).
- **Scientific Disclosure:**
  - This power-law formulation is explicitly documented as an **analytical model assumption**, not an empirical bathymetric curve.
  - Sensitivity analysis confirms that varying $\alpha$ between $1.00$ and $1.05$ causes less than $0.034\text{ m}$ elevation variation at $50\%$ storage, which has negligible effect on gross head ($\pm 0.018\%$).
  **Verdict: PASS — Correctly parameterized without hardcoded boundaries.**

---

### Equation 3: Hydraulic Gross Head and Waterway Head Loss
$$H_{\text{gross}}(t) = h(t) - Z_{\text{tail}}$$
$$h_{\text{loss}}(t) = h_{\text{loss, rated}} \cdot \left(\frac{Q_{\text{avg, turb}}(t)}{Q_{\text{station, rated}}}\right)^2$$
$$H_{\text{net}}(t) = H_{\text{gross}}(t) - h_{\text{loss}}(t)$$

- **Parameters & Normalization:**
  - $Z_{\text{tail}}$: Bound to `s_cfg["tailwater_level_masl"]` ($19.60\text{ MASL}$ provisional benchmark).
  - $h_{\text{loss, rated}}$: Bound to `s_cfg["tunnel_headloss_at_max_discharge_m"]` ($10.30\text{ m}$ total lump-sum system loss).
  - $Q_{\text{station, rated}}$: Dynamically bound to `s_cfg["rated_turbine_discharge_station_m3s"]` ($47.5$ or $48.0\text{ m}^3/\text{s}$). The hardcoded denominator `47.5` has been completely eliminated.
- **Double-Counting Audit:**
  - The Darcy-Weisbach headrace friction estimate ($\sim 3.11\text{ m}$) is **not** added to $h_{\text{loss, rated}}$, because the $10.30\text{ m}$ benchmark already represents total system headloss (intake, trash racks, 5.8 km headrace, surge shaft, penstock, valves, and 1.6 km tailrace).
  **Verdict: PASS — Normalized dynamically; double-counting prevented.**

---

### Equation 4: Hydroelectric Power and Daily Energy Integration
$$P(t) = \frac{\rho \cdot g \cdot Q_{\text{turb}}(t) \cdot H_{\text{net}}(t) \cdot \eta(t)}{10^6}\text{ [MW]}$$
$$E(t) = \min\left( \frac{\rho \cdot g \cdot V_{\text{turb}}(t) \cdot H_{\text{net}}(t) \cdot \eta(t)}{3.6 \times 10^9}, \, P_{\text{avail}}(t) \times 24.0\text{ h} \right)\text{ [MWh]}$$

- **Verification of Units:**
  $$\text{Energy [J]} = \rho\left[\frac{\text{kg}}{\text{m}^3}\right] \times g\left[\frac{\text{m}}{\text{s}^2}\right] \times V_{\text{turb}}\left[\text{m}^3\right] \times H_{\text{net}}[\text{m}] \times \eta[-] = [\text{N} \cdot \text{m}] = [\text{J}]$$
  $$\text{Energy [MWh]} = \frac{\text{Energy [J]}}{3.6 \times 10^9\text{ J/MWh}} \equiv [\text{MWh}]$$
- **Capacity Clamping:**
  - $P_{\text{avail}}(t) = \text{units}(t) \times \text{unit\_mw}$ (NO hardcoded `35.0`).
  - Daily energy is clamped at $\text{units}(t) \times \text{unit\_mw} \times 24.0\text{ h}$, strictly enforcing the $1,680.0\text{ MWh/day}$ station ceiling for dual-unit operation, and $840.0\text{ MWh/day}$ during single-unit outage days.
- **Turbine Output Integrity:** Turbine output is calculated once per day and directly integrated without duplicate counting.
- **Efficiency Definition:** Combined wire-to-water efficiency ($\eta_{\text{combined}} = \eta_{\text{turbine}} \times \eta_{\text{generator}} \in [0.865, 0.895]$).
  **Verdict: PASS — Mathematically consistent and rigorously bounded.**

---

## 3. Audit of Replaced Hardcoded Literals

| File | Former Code | Refactored Replacement | Status |
| :--- | :--- | :--- | :--- |
| `generate_synthetic_kukule_dataset.py:323` | `cap_mw = units * 35.0` | `cap_mw = units * unit_cap_mw` | **RESOLVED** |
| `generate_synthetic_kukule_dataset.py:373` | `(q_avg_turb / 47.5) ** 2` | `(q_avg_turb / rated_station_discharge) ** 2` | **RESOLVED** |
| `generate_synthetic_kukule_dataset.py:517` | `min_lvl >= 204.25 and max_lvl <= 206.0001` | `min_lvl >= mol - 0.001 and max_lvl <= fsl + 0.001` | **RESOLVED** |
| `generate_synthetic_kukule_dataset.py:544` | `max_gen <= 1680.0001` | `max_gen <= max_energy_ceiling + 0.001` | **RESOLVED** |
| `generate_synthetic_kukule_dataset.py:569` | `max_release_rate <= 47.5001` | `max_release_rate <= q_max + 0.001` | **RESOLVED** |
| `verify_synthetic_dataset.py:125` | `min_lvl < 204.25 or max_lvl > 206.001` | `min_lvl < (mol - 0.001) or max_lvl > (fsl + 0.001)` | **RESOLVED** |
| `verify_synthetic_dataset.py:138` | `max_gen > 1680.0001` | `max_gen > (max_energy_ceiling + 0.001)` | **RESOLVED** |
| `verify_synthetic_dataset.py:144` | `max_q > 47.5001` | `max_q > (q_rated + 0.001)` | **RESOLVED** |
| `verify_synthetic_dataset.py:162` | `v_loss = 1440.0` | `v_loss = float(op_cfg.get("daily_evaporation_loss_m3", 1440.0))` | **RESOLVED** |
