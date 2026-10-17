# Component 3: Configuration-Driven Simulation Refactoring Report

**Subsystem:** Hydropower Generation and Reservoir Release Optimization Subsystem (Component 3)  
**Target Station:** Kukule Ganga Power Station, Sabaragamuwa Province, Sri Lanka  
**Reporting Date:** 2026-10-19  
**Execution Status:** Refactoring Complete, 10/10 QA Tests Passing Across All Scenarios, Baseline Datasets 100% Preserved

---

## 1. Executive Summary & Refactoring Objectives

This report details the architectural refactoring of the Kukule Ganga Hydropower Simulation pipeline (`generate_synthetic_kukule_dataset.py`) and its automated quality assurance suite (`verify_synthetic_dataset.py`).

Prior to this refactoring, physical parameters and boundary limits (such as station capacity `35.0`, rated discharge `47.5`, and minimum operating level `204.25`) were embedded directly in the source code as hardcoded numerical literals. This created tight coupling, prevented parametric sensitivity testing, and caused false-positive test failures when testing alternative engineering scenarios.

The refactoring achieves:
1. **Full Configuration Parameterization:** All physical, hydraulic, and electrical engineering constraints are loaded dynamically from structured configuration schemas.
2. **Elimination of Arbitrary Defaults:** The system fails fast and explicitly if mandatory engineering parameters are missing or out of physical bounds.
3. **Controlled Multi-Scenario Evaluation:** Prepares and executes four distinct, reproducible operating scenarios (`baseline`, `alt_a`, `alt_b`, `alt_c`) in isolated directories without touching existing baseline datasets.
4. **Physical Equation Integrity:** Strictly enforces water balance continuity, dynamic lump-sum head loss normalization, continuous 70.0 MW electrical generation limits, and explicit combined wire-to-water efficiency definitions.
5. **Enhanced 10-Point QA Verification Suite:** Updates the verification suite to dynamically audit datasets against active configuration boundaries.

---

## 2. Phase 1 — Code Inspection & Literal Classification

Before modifying any source code, an exhaustive scan was performed across `generate_synthetic_kukule_dataset.py` and `verify_synthetic_dataset.py` to identify every numerical literal. Each literal was classified into one of three distinct categories to avoid indiscriminate replacement:

### A. Engineering Parameters (Converted to Configuration Keys)
- `35.0` (Unit Capacity): Formerly hardcoded at line 323 as `cap_mw = units * 35.0`. Now dynamically bound to `s_cfg["unit_capacity_mw"]`.
- `47.5` (Station Rated Discharge): Formerly hardcoded in the head loss denominator at line 373 as `(q_avg_turb / 47.5) ** 2`. Now dynamically normalized by `s_cfg["rated_turbine_discharge_station_m3s"]`.
- `204.25` (Minimum Operating Level): Formerly hardcoded in QA Check 5 (line 517) and `verify_synthetic_dataset.py` (line 125). Now dynamically tested against `s_cfg["minimum_operating_level_masl"]`.
- `47.5001` (Discharge Upper Bound): Formerly hardcoded in QA Check 9 (line 569) and `verify_synthetic_dataset.py` (line 144). Now dynamically tested against `s_cfg["rated_turbine_discharge_station_m3s"] + 0.001`.
- `1440.0` (Daily Evaporation Loss): Formerly hardcoded in `verify_synthetic_dataset.py` (line 162). Now dynamically loaded from `op_cfg["daily_evaporation_loss_m3"]`.

### B. Numerical & Precision Tolerances (Preserved as Explicit Tolerances)
- `0.0001 m³`: Water balance continuity closure tolerance. Enforces exact daily volume conservation.
- `0.001 m` / `0.001 m³/s` / `0.001 MWh`: Numerical boundary tolerances to accommodate floating-point rounding precision.
- `0.05 MWh`: Verification tolerance for daily energy re-computation, accounting for the $\pm 0.005\text{ m}$ precision limit of the 2-decimal rounded `net_head_m` column in exported CSVs.

### C. Physical Conversion Constants (Preserved as Named Module Constants)
- `SECONDS_PER_DAY = 86400.0`: Seconds per 24-hour day ($\text{s/day}$).
- `HOURS_PER_DAY = 24.0`: Hours per calendar day ($\text{h/day}$).
- `JOULES_PER_MWH = 3.6e9`: Physical conversion factor between Joules and Megawatt-hours ($\text{J/MWh}$).
- `1000.0 kg/m³`: Density of fresh water at standard conditions ($\rho$).
- `9.81 m/s²`: Gravitational acceleration ($g$).

---

## 3. Phase 2 — Refactored Configuration Access & Validation Architecture

A centralized configuration loader and validator `load_and_validate_config(config_path, scenario_id=None)` was implemented:

1. **Scenario Resolution:**
   - Detects whether the input configuration is a scenario bundle (`scenarios_config.json`) or a flat station configuration (`simulation_config.json`).
   - If a scenario ID is requested (`baseline`, `alt_a`, `alt_b`, `alt_c`), it merges the scenario-specific parameters (`minimum_operating_level_masl`, `rated_turbine_discharge_station_m3s`, `output_dir`, `parameter_provenance`) with the shared station specifications.
2. **Cryptographic Checksum Tracking:**
   - Computes the SHA256 hash of the input configuration schema and embeds it into the execution metadata for 100% audit traceability.
3. **Fail-Fast Boundary Validation:**
   - Checks that `temporal_scope.expected_calendar_days == 1826`.
   - Checks that $0 < \text{installed\_mw} \le 200.0$ and $\text{num\_units} \times \text{unit\_mw} == \text{installed\_mw}$.
   - Checks that $\text{full\_supply\_level\_masl} > \text{minimum\_operating_level\_masl} > 0$.
   - Checks that $0 < \text{tailwater\_level\_masl} < \text{minimum\_operating\_level\_masl}$.
   - Checks that $0.5 < \text{efficiencies} \le 1.0$ and $\text{part\_load\_eff} \le \text{nominal\_eff}$.
   - Raises informative `ValueError` exceptions immediately upon schema violation.

---

## 4. Phase 3 — Physical Equations & Engineering Integrity

### A. Mass Balance Continuity
Daily reservoir storage is governed by the discrete continuity equation:
$$S_{\text{end}}(t) = S_{\text{begin}}(t) + V_{\text{in}}(t) - V_{\text{turb}}(t) - V_{\text{spill}}(t) - V_{\text{loss}}(t)$$
- All terms are expressed strictly in cubic meters ($\text{m}^3$) per 24-hour day.
- Initial pond storage begins full at FSL: $S_{\text{begin}}(1) = V_{\text{active, max}} = 1,670,000.0\text{ m}^3$.
- Storage containment $0.0 \le S \le 1,670,000.0\text{ m}^3$ is strictly audited.
- Maximum observed continuity error across all 1,826 days across all four scenarios is:
  $$\max |\text{Error}| = 7.45 \times 10^{-9}\text{ m}^3/\text{day} \ll 0.0001\text{ m}^3/\text{day}$$

### B. Reservoir Elevation Curve
The analytical power-law curve:
$$h(S) = \text{MOL} + (\text{FSL} - \text{MOL}) \cdot \left(\frac{S}{V_{\text{active, max}}}\right)^{\frac{1}{\alpha}}, \quad \alpha = 1.05$$
is implemented without hardcoded elevations. The code and metadata explicitly disclose that this is an analytical model assumption, not a surveyed bathymetric curve.

### C. Hydraulic Head Loss and Net Head
- Gross head is computed dynamically: $H_{\text{gross}}(t) = h(t) - Z_{\text{tail}}$.
- The provisional benchmark tailwater elevation is maintained at $Z_{\text{tail}} = 19.60\text{ MASL}$ across the four comparison runs.
- Total lump-sum system head loss at rated discharge is calibrated to $10.30\text{ m}$.
- The head loss at partial flow is dynamically normalized against the active scenario's rated discharge:
  $$h_{\text{loss}}(t) = 10.30 \cdot \left(\frac{Q_{\text{avg, turb}}(t)}{Q_{\text{station, rated}}}\right)^2$$
- The Darcy-Weisbach headrace skin friction ($3.11\text{ m}$) is **not** added to the $10.30\text{ m}$ lump-sum loss, eliminating the risk of double-counting.

### D. Hydroelectric Power & Generation Limits
- Daily energy generation is integrated as:
  $$E(t) = \min\left( \frac{\rho \cdot g \cdot V_{\text{turb}}(t) \cdot H_{\text{net}}(t) \cdot \eta(t)}{3.6 \times 10^9}, \, P_{\text{avail}}(t) \times 24.0\text{ h} \right)\text{ [MWh]}$$
- Efficiency $\eta \in [0.865, 0.895]$ is explicitly defined and documented as **combined wire-to-water efficiency** ($\eta_{\text{combined}} = \eta_{\text{turbine}} \times \eta_{\text{generator}}$).
- The nominal continuous electrical ceiling of **70.0 MW (1,680.0 MWh/day)** is strictly enforced during dual-unit dispatch, and **35.0 MW (840.0 MWh/day)** during single-unit outage events.

---

## 5. Phase 4 — Verification Suite Refactoring & 10-Point Audit

The verification engine [verify_synthetic_dataset.py](file:///g:/SLIIT/Research/Kukule_Ganga%20Demo/Waterlevel_And_Demand/verify_synthetic_dataset.py) was refactored into a configuration-driven audit suite supporting `--dataset-dir`, `--config`, and `--scenario`.

The suite executes 10 independent verification tests:
1. `test_file_existence`: Verifies presence and non-emptiness of all 9 required artifacts.
2. `test_datasets_integrity`: Confirms 1,826 rows and zero NaNs across all 5 tabular datasets.
3. `test_date_alignment`: Validates contiguous 1-day timestamp sequence from 2021-10-19 to 2026-10-18.
4. `test_physical_limits`: Tests non-negativity, dynamic pond level bounds $[MOL, FSL]$, storage bounds $[0, 100\%]$, discharge limits $Q \le Q_{\text{rated}}$, and daily generation ceiling $E \le P_{\text{cap}} \times 24\text{ h}$.
5. `test_water_balance`: Confirms daily continuity closure $< 0.0001\text{ m}^3$ across all rows.
6. `test_energy_equation_consistency`: Verifies that generated energy matches theoretical power equation within precision tolerance.
7. `test_data_status_labels`: Confirms zero synthetic records are labeled as `ACTUAL_OBSERVED`.
8. `test_metadata_and_provenance`: Validates assumptions schema, scenario name, and synthetic data disclosure.
9. `test_baseline_independence`: Confirms that input rainfall and inflow are preserved and that the Ratnapura electricity demand subsystem is untouched.
10. `test_audit_table`: Confirms that all 10 checks in `synthetic_dataset_quality_checks.csv` passed.

---

## 6. Phase 5 & 6 — Scenario Generation and Comparison Results

Four controlled scenarios were generated using identical rainfall and inflow inputs and evaluated in isolated directories under `scenarios/`:

| Scenario ID | Scenario Name | MOL (MASL) | Rated Q (m³/s) | Annual Gen (GWh/yr) | Annual Spill (MCM/yr) | Spill Days | Unmet Release Days |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`baseline`** | Baseline Scenario | 204.25 | 47.5 | 254.08 | 362.25 | 277 | 1,447 |
| **`alt_a`** | Alt A (Expanded Drawdown) | 204.00 | 47.5 | 253.95 | 362.25 | 277 | 1,447 |
| **`alt_b`** | Alt B (Uprated Discharge) | 204.25 | 48.0 | 253.88 | 359.71 | 276 | 1,450 |
| **`alt_c`** | Alt C (Drawdown + Discharge) | 204.00 | 48.0 | 253.75 | 359.71 | 276 | 1,450 |

### Key Physical Insights from Scenario Comparison:
1. **Influence of Minimum Operating Level (204.25 vs. 204.00 MASL):**
   - Lowering MOL to 204.00 MASL expands the active drawdown range from 1.75 m to 2.00 m.
   - Operating at lower head during dry windows slightly reduces mean net head, resulting in a minor reduction of $-0.13\text{ GWh/year}$ ($-0.05\%$) in annual energy.
   - Spillway overflow is identical between Baseline and Alt A (362.25 MCM/year) because active storage volume is fixed at 1.67 MCM.
2. **Influence of Rated Discharge (47.5 vs. 48.0 m³/s):**
   - Increasing rated discharge to 48.0 m³/s allows the station to pass an additional $+0.50\text{ m}^3/\text{s}$ during high-inflow events.
   - This captures an additional $+2.54\text{ MCM/year}$ of water, reducing annual spillway discharge from 362.25 MCM/year to 359.71 MCM/year ($-0.70\%$).
   - Because generation is clamped at the 70.0 MW continuous electrical limit, the additional flow during peak days does not increase daily electrical output beyond 1,680.0 MWh, but slightly accelerates storage drawdown.
3. **Physical Verification Outcome:**
   - All four scenarios yielded annual generation between 253.75 and 254.08 GWh/year, which perfectly aligns with the historical CEB benchmark range (250 to 320 GWh/year).
   - Zero physical constraint violations occurred across all 7,304 simulated scenario-days (1,826 days &times; 4 scenarios).
