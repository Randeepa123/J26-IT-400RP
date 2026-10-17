# Scenario Comparison Report: Controlled Hydropower Sensitivity Evaluation

**Subsystem:** Hydropower Generation and Reservoir Release Optimization Subsystem (Component 3)  
**Target Station:** Kukule Ganga Power Station, Sabaragamuwa Province, Sri Lanka  
**Reporting Date:** 2026-10-19  
**Evaluation Scope:** 5-Year Continuous Simulation (2021-10-19 to 2026-10-18, Exactly 1,826 Calendar Days)  
**Input Preservation:** Identical Daily Catchment Inflow & Rainfall Series Across All 4 Scenarios

---

## 1. Executive Summary

To evaluate the operational and hydrological impact of the newly supplied engineering details without biasing the research baseline or prematurely adopting unverified figures, a four-way controlled scenario experiment was executed:

1. **`baseline`**: Minimum Operating Level (MOL) **204.25 MASL**, Rated Station Discharge **47.5 m³/s**.
2. **`alt_a`**: Minimum Operating Level (MOL) **204.00 MASL**, Rated Station Discharge **47.5 m³/s**.
3. **`alt_b`**: Minimum Operating Level (MOL) **204.25 MASL**, Rated Station Discharge **48.0 m³/s**.
4. **`alt_c`**: Minimum Operating Level (MOL) **204.00 MASL**, Rated Station Discharge **48.0 m³/s**.

All four scenarios were simulated using identical hydrological inflows, rainfall disaggregation, maintenance outage schedules, and provisional tailwater ($19.60\text{ MASL}$) and head loss ($10.30\text{ m}$) assumptions.

Each scenario was exported into its own isolated directory under `scenarios/` and passed all 10 independent verification tests in the automated QA audit suite.

---

## 2. Multi-Scenario Quantitative Comparison Table

The table below compiles the operational, hydraulic, and energy metrics exported in [scenario_comparison.csv](file:///g:/SLIIT/Research/Kukule_Ganga%20Demo/Waterlevel_And_Demand/scenario_comparison.csv).

| Metric | `baseline` | `alt_a` | `alt_b` | `alt_c` | Impact / Notes |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Minimum Operating Level (MASL)** | `204.25` | `204.00` | `204.25` | `204.00` | Parameter under evaluation |
| **Rated Station Discharge (m³/s)** | `47.5` | `47.5` | `48.0` | `48.0` | Parameter under evaluation |
| **Active Head Range (m)** | `1.75` | `2.00` | `1.75` | `2.00` | FSL ($206.00$) &minus; MOL |
| **Mean Daily Generation (MWh/day)**| `695.65` | `695.28` | `695.09` | `694.72` | Range: $[694.72, 695.65]$ MWh |
| **Annual Generation Total (GWh/year)**| **`254.08`** | **`253.95`** | **`253.88`** | **`253.75`** | Matches CEB benchmark (250-320 GWh) |
| **Capacity Factor (%)** | `41.41%` | `41.39%` | `41.37%` | `41.35%` | Standard run-of-river factor |
| **5-Year Total Generation (GWh)** | `1,270.25` | `1,269.58` | `1,269.24` | `1,268.56` | Maximum difference: $-1.69\text{ GWh}$ ($-0.13\%$) |
| **Annual Spillway Discharge (MCM/yr)**| **`362.25`** | **`362.25`** | **`359.71`** | **`359.71`** | $48.0\text{ m}^3/\text{s}$ captures $+2.54\text{ MCM/yr}$ |
| **5-Year Total Spill Volume (MCM)** | `1,811.08` | `1,810.99` | `1,798.39` | `1,798.30` | $-12.78\text{ MCM}$ spill over 5 years |
| **Spill Frequency (days / % of period)**| `277 / 15.2%` | `277 / 15.2%` | `276 / 15.1%` | `276 / 15.1%` | Wet monsoon overflow events |
| **Minimum Observed Water Level (MASL)**| `204.2577` | `204.0088` | `204.2577` | `204.0323` | Strictly bounded by active MOL |
| **Maximum Observed Water Level (MASL)**| `206.0000` | `206.0000` | `206.0000` | `206.0000` | Exact weir crest containment |
| **Minimum Net Head Observed (m)** | `174.13` | `174.13` | `174.13` | `174.13` | Corresponds to benchmark minimum |
| **Maximum Net Head Observed (m)** | `184.48` | `184.48` | `184.49` | `184.49` | Low-discharge static conditions |
| **Mean Net Head Observed (m)** | `178.69` | `178.60` | `178.69` | `178.60` | Lower MOL slightly reduces mean head |
| **Unmet Release Days (Peaking Mode)**| `1,447` | `1,447` | `1,450` | `1,450` | Days where storage limits full 24h run |
| **Physical Constraint Violations** | **`0`** | **`0`** | **`0`** | **`0`** | Zero violations across all scenarios |
| **Max Water Balance Error (m³/day)**| `< 1e-7` | `< 1e-7` | `< 1e-7` | `< 1e-7` | Exact volume conservation |

---

## 3. Physical Interpretation of Scenario Dynamics

### A. Impact of Minimum Operating Level (204.25 MASL vs. 204.00 MASL)
- **Drawdown Depth & Usable Storage:**
  In both cases, the usable active pond storage volume is $1.67\text{ million m}^3$ ($1.67\text{ MCM}$). Lowering the MOL from $204.25$ to $204.00\text{ MASL}$ expands the physical operating stage range from $\Delta H = 1.75\text{ m}$ to $\Delta H = 2.00\text{ m}$.
- **Net Head and Generation:**
  Because the pond operates at a lower elevation during drawdown cycles in `alt_a` and `alt_c`, the average hydraulic gross and net head are slightly reduced (mean net head decreases by $0.09\text{ m}$ from $178.69\text{ m}$ to $178.60\text{ m}$). This causes a tiny, physically logical reduction in annual generation of approximately **$-0.13\text{ GWh/year}$ ($-0.05\%$)**.
- **Spillway Overtopping:**
  Spillway overflow remains virtually unchanged between `baseline` and `alt_a` ($362.25\text{ MCM/year}$) because the total active retention volume ($1.67\text{ MCM}$) and rated turbine throughput are identical.

### B. Impact of Rated Station Discharge (47.5 m³/s vs. 48.0 m³/s)
- **Flood Peak Water Capture:**
  Increasing rated turbine discharge from $47.5\text{ m}^3/\text{s}$ to $48.0\text{ m}^3/\text{s}$ enables the power station to divert an additional $+0.50\text{ m}^3/\text{s}$ through the Francis turbines during wet monsoon high-inflow events.
- **Spillway Volume Reduction:**
  Over a 5-year simulation, the $48.0\text{ m}^3/\text{s}$ capacity captures **$12.69\text{ MCM}$ of water** that would have otherwise spilled over the weir crest, reducing average annual spillway loss by **$2.54\text{ MCM/year}$** (from $362.25\text{ MCM/yr}$ down to $359.71\text{ MCM/yr}$).
- **Daily Electrical Generation Constraint:**
  Crucially, this additional water throughput does **not** translate into higher annual electrical generation ($253.88\text{ GWh}$ vs. $254.08\text{ GWh}$). Under dual-unit full-load operation, daily generation is capped by the nominal continuous station ceiling of **$70.0\text{ MW} \times 24.0\text{ h} = 1,680.0\text{ MWh/day}$**. Higher discharge slightly accelerates storage depletion during peaking transitions, producing slightly more unmet release days (1,450 vs. 1,447 days).

---

## 4. Scientific Policy & Recommendation

1. **Equifinality of Current Options:**
   All four scenarios produce annual generation results between **253.75 GWh/year** and **254.08 GWh/year** (a maximum delta of just $0.13\%$), all of which align with CEB historical generation records ($250 - 320\text{ GWh/year}$).
2. **Neutrality of Selection:**
   The research pipeline does **not** declare any scenario as "officially correct." `baseline` represents the established research assumption, while `alt_c` represents full adoption of the supplied unverified memo values. Both configurations are fully supported by the parameter-driven architecture.
3. **Recommended Research Path:**
   - For optimization model benchmarking (LP/DQN Component 3), `baseline` should be retained as the historical control benchmark.
   - `alt_c` should be used for stress-testing optimization policies under uprated discharge and deeper drawdown.
   - Official calibration should await CEB operational dispatch logs confirming whether the physical plant operates down to 204.00 MASL and whether governor limits are set to 47.5 or 48.0 m³/s.

> [!NOTE]
> **Data Authenticity Statement:** All figures presented in this report reflect synthetic mathematical simulation runs. They do not constitute measured historical telemetry.
