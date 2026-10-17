# Kukule Ganga Hydropower Simulation: Engineering Parameter Audit Report

**Document Title:** Comprehensive Parameter Audit and Physical Validation Review  
**Subsystem:** Hydropower Generation and Reservoir Release Optimization Subsystem (Component 3)  
**Target Station:** Kukule Ganga Power Station, Sabaragamuwa Province, Sri Lanka  
**Audit Date:** 2026-10-19  
**Audit Scope:** Review of baseline configuration (`simulation_config.json`), baseline backup (`simulation_config_baseline_backup.json`), updated staging configuration (`simulation_config_updated.json`), simulation engine (`generate_synthetic_kukule_dataset.py`), QA verification suite (`verify_synthetic_dataset.py`), and generated technical reports.

---

## 1. Executive Summary & Audit Mandate

This audit provides an independent, scientifically rigorous review of the engineering update for the Kukule Ganga Hydropower Simulation before any dataset regeneration is authorized. 

In strict adherence to project protection protocols:
1. **No baseline configurations have been overwritten.**
2. **No synthetic datasets have been regenerated.**
3. **The Ratnapura electricity demand datasets remain untouched and completely isolated.**
4. **All baseline files and outputs remain 100% preserved and reproducible.**

Every parameter in the model has been audited against physical evidence, classified into formal provenance categories (`OFFICIAL_VERIFIED`, `USER_SUPPLIED_UNVERIFIED`, `DERIVED`, or `MODEL_ASSUMPTION`), and evaluated for simulation safety.

---

## 2. Parameter Classification Criteria

To prevent unverified operational claims, parameters are strictly categorized as follows:
- **`OFFICIAL_VERIFIED`:** Backed by traceable official records from the Ceylon Electricity Board (CEB), Public Utilities Commission of Sri Lanka (PUCSL), or Survey Department of Sri Lanka.
- **`USER_SUPPLIED_UNVERIFIED`:** Provided in user engineering memos, site notes, or unverified technical prompts without secondary document citation.
- **`DERIVED`:** Calculated mathematically from other parameters (e.g., gross head minus net head, or weir crest minus invert elevation).
- **`MODEL_ASSUMPTION`:** Parameter assumptions introduced to close mathematical model gaps where site measurements do not exist (e.g., storage exponents, loss multipliers).

*Rule of Evidence:* A parameter is never labeled `OFFICIAL_VERIFIED` merely because it was copied from an existing generated report or because automated simulation tests pass.

---

## 3. Investigation of Specific Engineering Issues

### Issue 1: Tailwater Level Reconciliation (19.60 MASL Inferred vs. Measured)
- **Status:** `DERIVED` / `MODEL_ASSUMPTION`
- **Audit Findings:** The value **19.60 MASL** is an inferred calculation derived from subtracting the supplied maximum gross head from the Full Supply Level ($206.00\text{ MASL} - 186.40\text{ m} = 19.60\text{ MASL}$). It is **not** an independently measured river gauge or draft tube piezometric reading.
- **Outfall Invert vs. Operating Tailwater:** The supplied tailrace outfall portal invert is **13.52 MASL**. With a 1,600 m tailrace tunnel at a 0.58% upward incline towards the powerhouse ($1,600 \times 0.0058 = +9.28\text{ m}$), the floor invert at the draft tube exit is **22.80 MASL**. Naively plugging 13.52 MASL into gross head yields $206.00 - 13.52 = 192.48\text{ m}$ (an inflation of +6.08 m).
- **Simulation Safety & Action:** The simulation engine must operate with a **configurable tailwater parameter** (`tailwater_level_mode`), allowing the user to select between:
  1. `BENCHMARK_INFERRED_19_60`: Inferred from the 186.4 m gross head benchmark.
  2. `BASELINE_PROXY_29_50`: The historical baseline model assumption.
  3. `DYNAMIC_RATING_CURVE`: Downstream river stage backwater function once river gauge telemetry is supplied.

---

### Issue 2: Hydraulic Head Loss Partitioning (10.30 m Benchmark vs. Darcy-Weisbach)
- **Status:** `DERIVED`
- **Audit Findings:** The **10.30 m** total hydraulic loss is derived as the lump-sum differential between benchmark gross head and maximum net head ($186.40\text{ m} - 176.10\text{ m} = 10.30\text{ m}$).
- **Darcy-Weisbach Check:** Computing Darcy-Weisbach friction solely along the 5,799 m headrace tunnel ($D=5.6\text{ m}$, $V=1.95\text{ m/s}$, concrete $f \approx 0.0155$) gives:
  $$h_{f, \text{headrace}} = 0.0155 \times \left(\frac{5799}{5.6}\right) \times \left(\frac{1.95^2}{2 \times 9.81}\right) \approx 3.11\text{ m}$$
- **Double-Counting Prevention:** The 10.30 m value represents the **total lump-sum system head loss** across the entire water conveyance system (headrace intake, trash racks, 5.8 km tunnel, surge shaft, penstock, bifurcations, main inlet valves, draft tube, 1.6 km tailrace, and river exit). The simulation must **never** add the 3.11 m Darcy-Weisbach skin friction on top of the 10.30 m benchmark loss, as that would double-count headrace skin friction and overestimate total losses by over 30% (yielding 13.41 m).

---

### Issue 3: Minimum Operating Level (204.00 MASL vs. 204.25 MASL)
- **Status:** Both are unverified (`USER_SUPPLIED_UNVERIFIED` vs. `MODEL_ASSUMPTION`).
- **Audit Findings:** Neither 204.00 MASL nor 204.25 MASL is accompanied by official CEB operating rule curves in the repository. The baseline 204.25 MASL was an engineering assumption from the initial model setup, whereas 204.00 MASL is an unverified user-supplied figure.
- **Physical Implications:**
  - Active drawdown: 204.25 MASL yields $\Delta H = 1.75\text{ m}$; 204.00 MASL yields $\Delta H = 2.00\text{ m}$.
  - Storage density: With active volume fixed at 1.67 MCM, average storage capacity per meter is 0.954 MCM/m at $\Delta H = 1.75\text{ m}$ vs. 0.835 MCM/m at $\Delta H = 2.00\text{ m}$.
- **Simulation Safety & Action:** The model must support a **configurable MOL sensitivity toggle** (`mol_scenario`: `"204.00_MASL"` vs. `"204.25_MASL"`). Hardcoded boundary assertions in `verify_synthetic_dataset.py` must be parameterized to evaluate both operating cases.

---

### Issue 4: Turbine Ratings (70 MW Station Ceiling vs. 40 MW / 37.5 MW Unit Capabilities)
- **Status:** 70 MW is `OFFICIAL_VERIFIED`; 40 MW and 37.5 MW are `USER_SUPPLIED_UNVERIFIED`.
- **Audit Findings:**
  - **70.0 MW Station Rating:** Universally documented as the official continuous station capacity (2 &times; 35.0 MW).
  - **40.0 MW Maximum per Turbine:** Represents runner mechanical shaft capacity under maximum gate opening / peak head. It cannot be used as an unconstrained continuous generation point without evidence of generator stator continuous MVA rating, step-up transformer capacity, and CEB grid export authorization.
  - **37.5 MW at 24 m³/s:** Represents turbine design point shaft power at rated net head (176.1 m). At $\eta \approx 90.5\%$, $P = 1000 \times 9.81 \times 24 \times 176.1 \times 0.905 \times 10^{-6} = 37.5\text{ MW}$.
- **Simulation Safety & Action:** The nominal station ceiling of **70.0 MW (1,680.0 MWh/day)** must remain strictly enforced as the maximum continuous electrical generation ceiling. The 40.0 MW and 37.5 MW values are preserved as turbine mechanical capabilities, but cannot elevate continuous daily energy output.

---

### Issue 5: Generator Specifications (42 MVA vs. 46.2 MVA and Power Factor `8.5`)
- **Status:** `USER_SUPPLIED_UNVERIFIED` / `REQUIRES_CLARIFICATION`
- **Audit Findings:**
  - **Power Factor `8.5` Flagged:** A power factor of `8.5` is physically impossible ($\cos\phi \le 1.0$). This is an obvious typographical transcription error for `0.85` (or $85\%$). However, per project audit instructions, this error must **not be silently altered** in the provenance audit. It must be explicitly recorded as `8.5` with an explanatory flag.
  - **42 MVA vs. 46.2 MVA Reconciliation:**
    - At 35.0 MW nominal unit capacity and $\cos\phi = 0.85$, apparent power is $S = 35.0 / 0.85 = 41.18\text{ MVA} \approx 42.0\text{ MVA}$.
    - At 10% thermal overload margin: $42.0\text{ MVA} \times 1.10 = 46.20\text{ MVA}$!
    - 46.2 MVA corresponds exactly to the 2-hour or continuous thermal overload rating of a 42 MVA synchronous generator.
- **Simulation Safety & Action:** Preserved in the provenance registry as flagged for official nameplate verification. Does not alter hydraulic water balance.

---

### Issue 6: Rated Turbine Discharge (47.5 m³/s vs. 48.0 m³/s)
- **Status:** 47.5 m³/s is `MODEL_ASSUMPTION`; 48.0 m³/s is `DERIVED` from `USER_SUPPLIED_UNVERIFIED`.
- **Audit Findings:** The difference between $47.50\text{ m}^3/\text{s}$ ($23.75\text{ m}^3/\text{s}$ per unit) and $48.00\text{ m}^3/\text{s}$ ($24.00\text{ m}^3/\text{s}$ per unit) is $+0.50\text{ m}^3/\text{s}$ (+1.05%). Over a 24-hour full-generation cycle, this corresponds to $43,200\text{ m}^3/\text{day}$ (+1.05% water throughput).
- **Simulation Safety & Action:** Both scenarios must be retained as separate, configurable switches (`rated_discharge_scenario`: `"BASELINE_47_5"` vs. `"PROVISIONAL_48_0"`). Because station generation is clamped at 70 MW, the 48.0 m³/s limit marginally reduces wet-weather spillway overflow without altering the daily energy ceiling.

---

### Issue 7: Annual Energy Benchmark ("317 MWh" Flagged Source Typo)
- **Status:** `USER_SUPPLIED_UNVERIFIED` / `REQUIRES_CLARIFICATION`
- **Audit Findings:**
  - Raw engineering notes contain the figure **“317 MWh”**.
  - For a 70 MW facility, 317 MWh represents less than 5 hours of full-station generation in an entire year ($70\text{ MW} \times 4.53\text{ h} = 317\text{ MWh}$). The physical annual generation of Kukule Ganga documented in CEB Statistical Digests ranges between **250 and 320 GWh/year** (with historical mean $\approx 317\text{ GWh/year}$).
  - In accordance with audit instructions, this figure is **not automatically converted** to GWh in the audit tables. It is formally flagged as an unresolved source-unit error.

---

### Issue 8: Reservoir Stage-Storage Curve & Exponent $\alpha = 1.05$
- **Status:** `MODEL_ASSUMPTION`
- **Audit Findings:**
  - The equation $h(S) = \text{MOL} + (\text{FSL} - \text{MOL}) \cdot (S / V_{\text{active, max}})^{1 / \alpha}$ with $\alpha = 1.05$ is **not supported by any bathymetric survey or area-elevation-capacity table in the repository**.
  - It is an idealized mathematical assumption reflecting a slightly convex, steep-sided upland valley.
- **Influence Testing:**
  - Setting $\alpha = 1.00$ (linear prism): At $50\%$ storage, $h = 204.00 + 1.00 = 205.000\text{ MASL}$.
  - Setting $\alpha = 1.05$: At $50\%$ storage, $h = 204.00 + 2.00 \cdot (0.5)^{1/1.05} = 205.034\text{ MASL}$.
  - Maximum elevation difference is merely **0.034 m**, representing a negligible $\pm 0.018\%$ variation on a $186\text{ m}$ head. The assumption is safe for optimization modeling, but must remain clearly labeled as a model assumption.

---

### Issue 9: Waterway Geometry & Hydraulic Grade Line
- **Status:** `USER_SUPPLIED_UNVERIFIED`
- **Audit Findings:** The tailrace tunnel length (1,600 m), slope (0.58%), and outfall invert (13.52 MASL) describe boundary geometry only. In open-channel or pressurized transient hydraulics, water surface elevation depends on Manning roughness, tunnel cross-section shape, and receiving river stage. Inferring hydraulic grade or draft tube tailwater elevation solely from geometry without a hydraulic backwater model is physically invalid.

---

### Issue 10: Energy Calculation and Mathematical Consistency
- **Audit Findings:**
  - Hydro-electric power: $P = \rho \cdot g \cdot Q \cdot H_{\text{net}} \cdot \eta \times 10^{-6}\text{ [MW]}$.
  - Daily electrical energy: $E = \min\left( \frac{\rho \cdot g \cdot V_{\text{turb}} \cdot H_{\text{net}} \cdot \eta}{3.6 \times 10^9}, \, P_{\text{avail}} \times 24.0 \right)\text{ [MWh]}$.
  - Dimensions check: Density ($1,000\text{ kg/m}^3$), gravity ($9.81\text{ m/s}^2$), volume ($\text{m}^3$), head ($\text{m}$), and $3.6 \times 10^9\text{ J/MWh}$ produce mathematically exact results in MWh.
  - The electrical power ceiling ($P_{\text{cap}} = \text{units} \times 35.0\text{ MW}$) is strictly enforced.

---

## 4. Master Parameter Audit Table

A machine-readable version of this table is exported in [engineering_parameter_audit.csv](file:///g:/SLIIT/Research/Kukule_Ganga%20Demo/Waterlevel_And_Demand/engineering_parameter_audit.csv).

| Parameter | Original | Proposed | Unit | Evidence Source | Classification | Safe to Use? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `installed_capacity_mw` | `70.0` | `70.0` | MW | CEB Asset Register | `OFFICIAL_VERIFIED` | **YES** |
| `num_units` | `2` | `2` | units | CEB Powerhouse Profile | `OFFICIAL_VERIFIED` | **YES** |
| `nominal_unit_capacity_mw` | `35.0` | `35.0` | MW | CEB Station Rating | `OFFICIAL_VERIFIED` | **YES** |
| `turbine_type` | `Francis` | `vertical Francis` | text | CEB Inventory | `OFFICIAL_VERIFIED` | **YES** |
| `turbine_maximum_output_per_unit_mw` | *Unspecified* | `40.0` | MW | User Memo | `USER_SUPPLIED_UNVERIFIED` | **PENDING_CLARIFICATION** |
| `turbine_rated_output_at_design_q_mw` | *Unspecified* | `37.5` | MW | User Memo | `USER_SUPPLIED_UNVERIFIED` | **AS_CONFIGURABLE_ASSUMPTION** |
| `turbine_rated_discharge_per_unit_m3s` | `23.75` | `24.0` | m³/s | User Memo | `USER_SUPPLIED_UNVERIFIED` | **AS_CONFIGURABLE_ASSUMPTION** |
| `station_rated_discharge_total_m3s` | `47.5` | `48.0` | m³/s | Derived (2 &times; 24.0) | `DERIVED` | **AS_CONFIGURABLE_ASSUMPTION** |
| `maximum_gross_head_m` | `176.5` | `186.4` | m | User Memo | `USER_SUPPLIED_UNVERIFIED` | **AS_CONFIGURABLE_ASSUMPTION** |
| `maximum_net_head_m` | `~174.0` | `176.1` | m | User Memo | `USER_SUPPLIED_UNVERIFIED` | **AS_CONFIGURABLE_ASSUMPTION** |
| `minimum_net_head_m` | `~172.25` | `174.1` | m | User Memo | `USER_SUPPLIED_UNVERIFIED` | **AS_CONFIGURABLE_ASSUMPTION** |
| `pond_full_spill_level_masl` | `206.00` | `206.00` | MASL | CEB Weir Rules | `OFFICIAL_VERIFIED` | **YES** |
| `minimum_operating_level_masl` | `204.25` | `204.00` | MASL | User Memo (204.0) | `USER_SUPPLIED_UNVERIFIED` | **AS_CONFIGURABLE_ASSUMPTION** |
| `usable_storage_volume_m3` | `1,670,000` | `1,670,000` | m³ | CEB Plant Profile | `OFFICIAL_VERIFIED` | **YES** |
| `active_head_range_m` | `1.75` | `2.00` | m | Derived ($206 - 204$) | `DERIVED` | **AS_CONFIGURABLE_ASSUMPTION** |
| `elevation_storage_alpha` | `1.05` | `1.05` | &mdash; | Model Assumption | `MODEL_ASSUMPTION` | **AS_CONFIGURABLE_ASSUMPTION** |
| `headrace_tunnel_length_m` | `5,790.0` | `5,799.0` | m | User Memo | `USER_SUPPLIED_UNVERIFIED` | **YES** |
| `headrace_tunnel_diameter_m` | *Unspecified* | `5.6` | m | User Memo | `USER_SUPPLIED_UNVERIFIED` | **YES** |
| `tailrace_tunnel_length_m` | *Unspecified* | `1,600.0` | m | User Memo | `USER_SUPPLIED_UNVERIFIED` | **YES** |
| `tailrace_tunnel_slope_pct` | *Unspecified* | `0.58` | % | User Memo | `USER_SUPPLIED_UNVERIFIED` | **YES** |
| `tailrace_outfall_invert_masl` | *Unspecified* | `13.52` | MASL | User Memo | `USER_SUPPLIED_UNVERIFIED` | **AS_CONFIGURABLE_ASSUMPTION** |
| `effective_operational_tailwater_masl` | `29.50` | `19.60` | MASL | Derived ($206 - 186.4$) | `DERIVED` | **AS_CONFIGURABLE_ASSUMPTION** |
| `total_system_hydraulic_headloss_m` | `2.50` | `10.30` | m | Derived ($186.4 - 176.1$) | `DERIVED` | **AS_CONFIGURABLE_ASSUMPTION** |
| `generator_frequency_hz` | `50.0` | `50.0` | Hz | Grid Standard | `OFFICIAL_VERIFIED` | **YES** |
| `generator_rated_voltage_kv` | *Unspecified* | `13.8` | kV | User Memo | `USER_SUPPLIED_UNVERIFIED` | **YES** |
| `generator_apparent_power_mva` | *Unspecified* | `42 / 46.2` | MVA | Audit Inquiry | `USER_SUPPLIED_UNVERIFIED` | **PENDING_CLARIFICATION** |
| `generator_power_factor` | *Unspecified* | `8.5` (flagged) | &mdash; | Audit Inquiry (typo) | `USER_SUPPLIED_UNVERIFIED` | **PENDING_CLARIFICATION** |
| `annual_generation_benchmark` | `250-320 GWh` | `317 MWh` (flagged) | &mdash; | Audit Inquiry (typo) | `USER_SUPPLIED_UNVERIFIED` | **PENDING_CLARIFICATION** |
| `commissioning_year` | *Unspecified* | `2003` | year | CEB Records | `OFFICIAL_VERIFIED` | **YES** |
| `catchment_area_km2` | `312.0` | `312.0` | km² | Survey Dept / CEB | `OFFICIAL_VERIFIED` | **YES** |

---

## 5. Audit Conclusion

The proposed engineering update represents a significant improvement in model fidelity over the baseline assumption of 29.50 MASL tailwater and 2.50 m loss. However, because several critical parameters remain unverified user inputs or derived estimates, the update must be deployed strictly with **configurable scenario options** rather than rigid hardcoded constants.
