# Kukule Ganga Hydropower & Reservoir Release LP Model Formulation

**Subsystem:** Hydropower Generation and Reservoir Release Optimization Subsystem (Component 3)  
**Target Station:** Kukule Ganga Power Station, Sabaragamuwa Province, Sri Lanka  
**Document Purpose:** Rigorous Mathematical Formulation of the Linear Programming (LP) Reservoir Dispatch Optimizer  
**Author:** Antigravity Research Pipeline  
**Date:** October 2026  

---

## 1. Introduction and System Context

The Kukule Ganga Power Station is a 70.0 MW ($2 \times 35.0\text{ MW}$ vertical Francis units) run-of-river facility with daily regulating pondage ($1.67\text{ million m}^3$ active storage) located in the wet-zone uplands of the Kalu Ganga basin, Sri Lanka.

The primary operational challenge is optimizing daily reservoir release and storage trajectories:
1. In high-flow monsoon periods, the facility receives inflows far exceeding the rated turbine capacity ($47.5$ or $48.0\text{ m}^3/\text{s}$), leading to substantial spillway overflow unless discharge is scheduled at capacity.
2. In dry-flow inter-monsoon periods, inflows drop well below rated capacity, requiring daily pondage regulation to balance peaking hours against storage depletion.

This document establishes the first-principles Linear Programming (LP) formulation for Component 3.

---

## 2. Mathematical Notation

### Sets and Indices
- $t \in \mathcal{T} = \{1, 2, \dots, T\}$: Discrete daily time steps of the simulation horizon ($T = 1,826$ days for full 5-year scope, $T = 1,461$ for training, $T = 365$ for held-out evaluation).
- $\Delta t$: Time step duration ($1\text{ day} = 86,400\text{ s} = 24.0\text{ h}$).

### Deterministic State Parameters (from Simulator Configuration)
- $V_{\text{in}, t}$: Net inflow volume during day $t$ [m³/day], derived as $Q_{\text{in}, t} \times 86,400\text{ s}$.
- $V_{\text{loss}, t}$: Daily evaporation loss volume [m³/day] ($1,440.0\text{ m}^3/\text{day}$).
- $S_{\min}$: Minimum allowable active storage [m³] ($0.0\text{ m}^3$, corresponding to MOL).
- $S_{\max}$: Maximum allowable active storage [m³] ($1,670,000.0\text{ m}^3 = 1.67\text{ MCM}$, corresponding to FSL).
- $S_0$: Initial active storage at $t=0$ [m³] ($1,670,000.0\text{ m}^3$, pond initially full at FSL).
- $S_{\text{target}}$: Minimum terminal active storage constraint at $t=T$ [m³] ($S_{\text{target}} = S_0 = 1,670,000.0\text{ m}^3$).
- $u_t$: Number of available operating units on day $t$, accounting for planned maintenance overhauls and stochastic forced trips ($u_t \in \{1, 2\}$).
- $Q_{\text{unit, rated}}$: Rated turbine discharge per unit [m³/s] ($23.75\text{ m}^3/\text{s}$ baseline, $24.00\text{ m}^3/\text{s}$ provisional).
- $V_{\text{turb, max}, t} = u_t \times Q_{\text{unit, rated}} \times 86,400$: Maximum volumetric discharge capacity on day $t$ [m³/day].
- $P_{\text{cap}, t} = u_t \times 35.0\text{ MW}$: Continuous station electrical power ceiling [MW].
- $E_{\max, t} = P_{\text{cap}, t} \times 24.0\text{ h}$: Daily electrical generation ceiling [MWh/day] ($1,680.0\text{ MWh/day}$ for 2 units, $840.0\text{ MWh/day}$ for 1 unit).

### Decision Variables
- $V_{\text{turb}, t}$: Volume of water released through the turbines on day $t$ [m³/day].
- $V_{\text{spill}, t}$: Volume of water discharged over the weir spillway on day $t$ [m³/day].
- $S_t$: Active pond storage volume at the end of day $t$ [m³].

### Input Columns and Physical Units
The optimization subsystem interfaces directly with the standardized integrated dataset (`synthetic_kukule_integrated_dataset_5years.csv`):

| Column Name | Physical Meaning | Engineering Unit | Constraint / Role in LP |
| :--- | :--- | :--- | :--- |
| `date` | Calendar timestamp (YYYY-MM-DD) | String date | Time index $t \in \{1, \dots, T\}$ |
| `rainfall_mm` | Daily catchment basin rainfall | mm/day | Exogenous driver (used for inflow generation) |
| `antecedent_rainfall_mm`| Multi-day prior rainfall window | mm | Hydrological soil moisture index |
| `soil_wetness_index` | Catchment saturation fraction | Dimensionless [0, 1] | Hydrological state indicator |
| `estimated_inflow_m3s` | Mean daily river discharge | m³/s | Inflow rate: $Q_{\text{in}, t} = V_{\text{in}, t} / 86400$ |
| `inflow_volume_m3` | Total daily inflow volume | m³/day | Known parameter $V_{\text{in}, t}$ in water balance |
| `beginning_storage_m3` | Storage at start of day $t$ | m³ | State variable $S_{t-1}$ ($S_0 = 1.67\text{ MCM}$) |
| `turbine_release_m3` | Water discharged through turbines | m³/day | Primary decision variable $V_{\text{turb}, t}$ |
| `spill_volume_m3` | Water overflow over weir crest | m³/day | Slack decision variable $V_{\text{spill}, t}$ |
| `end_storage_m3` | Storage at end of day $t$ | m³ | State decision variable $S_t \in [0, S_{\max}]$ |
| `pond_level_masl` | Water surface elevation | MASL (m) | Hydraulic head lookup: $H(S_t)$ |
| `active_storage_pct` | Active capacity percentage | % | $100 \times (S_t / S_{\max})$ |
| `net_head_m` | Effective hydraulic head | m | Evaluated head: $H_{\text{gross}} - h_{\text{loss}}$ |
| `turbine_efficiency` | Combined wire-to-water efficiency| Dimensionless | Nominal 0.895 / Part-load 0.865 |
| `available_capacity_mw`| Station operational capacity | MW | $u_t \times 35.0\text{ MW}$ (70.0 or 35.0 MW) |
| `operating_units` | Units online (post-outage) | Count $\in \{1, 2\}$ | Sets $V_{\text{turb, max}, t}$ and $E_{\max, t}$ |
| `outage_flag` | Operational status code | Int (0=Norm, 1=Maint, 2=Trip) | Outage tracking |
| `generation_mwh` | Total daily electrical generation| MWh/day | Physical generation $E_{\text{phys}, t} \le E_{\max, t}$ |
| `data_status` | Scientific provenance tag | String | Label: `MODEL_ESTIMATED` |

### Definitions of Operational Metrics

1. **Spillway Discharge ($V_{\text{spill}}$):**
   Water volume passing over the overflow weir crest during period $t$ without passing through the penstock or generating electrical energy. Spilling occurs when available water ($S_{t-1} + V_{\text{in}, t} - V_{\text{loss}, t}$) exceeds the combined turbine release capacity ($V_{\text{turb, max}, t}$) and maximum reservoir retention ($S_{\max}$). It represents uncaptured hydraulic energy.

2. **Unmet Environmental / Target Release ($V_{\text{unmet}}$):**
   When an operational target or statutory environmental flow requirement ($Q_{\text{env, min}} = 2.0\text{ m}^3/\text{s}$, or $V_{\text{env, req}} = 172,800\text{ m}^3/\text{day}$) is mandated, any volume by which total downstream release ($V_{\text{turb}, t} + V_{\text{spill}, t}$) falls below this threshold constitutes an **unmet release deficit**:
   $$V_{\text{unmet}, t} = \max\left(0.0, \, V_{\text{env, req}} - (V_{\text{turb}, t} + V_{\text{spill}, t})\right)$$
   Under normal run-of-river operations at Kukule Ganga, downstream releases are discharged directly into the tailrace and weir pool. Because turbine release and spill both return to the river system, unmet flow only occurs if total available water is strictly less than the environmental requirement ($S_{t-1} + V_{\text{in}, t} - V_{\text{loss}, t} < V_{\text{env, req}}$).

---

## 3. Objective Function Formulation

The primary optimization goal of the power station is to **maximize total electrical energy generation** over the horizon $\mathcal{T}$, while avoiding unnecessary spillway discharge and preserving hydraulic head:

$$\max_{V_{\text{turb}}, V_{\text{spill}}, S} \quad J = \sum_{t=1}^T \left( k_e \cdot V_{\text{turb}, t} - c_{\text{spill}} \cdot V_{\text{spill}, t} + c_{\text{storage}} \cdot S_t \right)$$

Where:
- $k_e$: Water-to-power energy conversion coefficient [MWh/m³] ($k_e = 4.2694 \times 10^{-4}\text{ MWh/m}^3$).
- $c_{\text{spill}}$: Non-negative economic penalty coefficient ($10^{-6}\text{ MWh/m}^3$) applied to spillway overflow.
- $c_{\text{storage}}$: Small non-negative storage preservation incentive coefficient ($10^{-7}\text{ MWh/m}^3$) applied to active storage volume.

### Operational Hierarchy and Multi-Period Degeneracy Resolution:
In multi-period fixed-head reservoir optimization during high-flow flood events, total spill $\sum V_{\text{spill}, t}$ depends solely on total inflow and net terminal storage change $(S_T - S_0)$, creating mathematical degeneracy across intermediate storages $S_1, \dots, S_{T-1}$. Incorporating $c_{\text{storage}}$ establishes a strict, non-ambiguous physical priority ranking:
$$k_e \, (4.2694 \times 10^{-4}) \;\gg\; c_{\text{spill}} \, (1.0 \times 10^{-6}) \;\gg\; c_{\text{storage}} \, (1.0 \times 10^{-7}) > 0$$
1. **Primary Priority (Generation):** Releasing water through turbines for power generation delivers the highest benefit ($4,269 \times$ greater than storage reward).
2. **Secondary Priority (Storage Retention):** When turbine or generator capacity is saturated, excess water is retained in the reservoir up to $S_{\max}$ to sustain head and future reserves.
3. **Tertiary / Slack Priority (Spillway Overflow):** When both turbines and active storage are saturated, water spills over the weir with a positive penalty.

In standard canonical LP minimization form ($\min -J$):
$$\min_{V_{\text{turb}}, V_{\text{spill}}, S} \quad \sum_{t=1}^T \left( -k_e \cdot V_{\text{turb}, t} + c_{\text{spill}} \cdot V_{\text{spill}, t} - c_{\text{storage}} \cdot S_t \right)$$

---

## 4. Constraint Set

### 4.1. Reservoir Mass Continuity (Water Balance)
For each time step $t = 1, \dots, T$:
$$S_t - S_{t-1} + V_{\text{turb}, t} + V_{\text{spill}, t} = V_{\text{in}, t} - V_{\text{loss}, t}$$
With initial condition:
$$S_0 = 1,670,000.0\text{ m}^3$$

### 4.2. Active Storage Bounds
$$0.0 \le S_t \le S_{\max} = 1,670,000.0\text{ m}^3, \quad \forall t \in \mathcal{T}$$

### 4.3. Turbine Volumetric Release Bounds
$$0.0 \le V_{\text{turb}, t} \le V_{\text{turb, max}, t}, \quad \forall t \in \mathcal{T}$$
Where:
$$V_{\text{turb, max}, t} = u_t \times Q_{\text{unit, rated}} \times 86,400\text{ m}^3/\text{day}$$

### 4.4. Station Electrical Capacity Ceiling
$$k_e \cdot V_{\text{turb}, t} \le E_{\max, t} = u_t \times 35.0\text{ MW} \times 24.0\text{ h}, \quad \forall t \in \mathcal{T}$$
Which enforces:
$$V_{\text{turb}, t} \le \frac{E_{\max, t}}{k_e}$$

### 4.5. Spillway Non-Negativity
$$V_{\text{spill}, t} \ge 0.0, \quad \forall t \in \mathcal{T}$$

### 4.6. Terminal Storage Preservation Constraint
To prevent the mathematical optimizer from artificially inflating energy yield by exhausting active storage on the final day $T$:
$$S_T \ge S_{\text{target}} = S_0 = 1,670,000.0\text{ m}^3$$
This ensures sustainable cyclic stewardship and prevents artificial end-of-horizon depletion.

---

## 5. Physical Linearization Analysis & Justification

### A. Non-Linear Physical Hydropower Equation
The true physical power equation is:
$$E_{\text{phys}, t} = \frac{\rho \cdot g \cdot V_{\text{turb}, t} \cdot H_{\text{net}, t} \cdot \eta_t}{3.6 \times 10^9}\text{ [MWh]}$$
Where:
$$H_{\text{gross}, t} = \text{MOL} + (\text{FSL} - \text{MOL}) \cdot \left(\frac{S_t}{V_{\text{active, max}}}\right)^{\frac{1}{\alpha}} - Z_{\text{tw}}$$
$$h_{\text{loss}, t} = h_{\text{loss, rated}} \cdot \left(\frac{V_{\text{turb}, t} / 86400}{Q_{\text{station, rated}}}\right)^2$$
$$H_{\text{net}, t} = H_{\text{gross}, t} - h_{\text{loss}, t}$$

This contains:
1. A bilinear cross-product between discharge $V_{\text{turb}, t}$ and storage $S_t^{1/\alpha}$.
2. A cubic velocity-head friction loss term $\propto V_{\text{turb}, t}^3$.
3. A discontinuous loading efficiency function $\eta(V_{\text{turb}, t})$.

### B. Linear Water-to-Power Coefficient ($k_e$)
In high-head hydropower schemes with small daily pondage (such as Kukule Ganga), the active drawdown range is tiny relative to the total hydraulic head:
$$\frac{\Delta H_{\text{active}}}{H_{\text{net}}} = \frac{206.00\text{ MASL} - 204.25\text{ MASL}}{175.10\text{ m}} = \frac{1.75\text{ m}}{175.10\text{ m}} \approx 0.99\%$$

The representative design net head is $H_{\text{rated}} = 175.10\text{ m}$ (mean of FSL net head 176.10 m and MOL net head 174.10 m), with rated combined wire-to-water efficiency $\eta = 0.895$.

The exact linear generation coefficient is:
$$k_e = \frac{1000.0\text{ kg/m}^3 \times 9.81\text{ m/s}^2 \times 175.10\text{ m} \times 0.895}{3.6 \times 10^9\text{ J/MWh}} = 4.2694 \times 10^{-4}\text{ MWh/m}^3$$
Equivalently:
$$\text{Water Rate} = \frac{1}{k_e} = 2,342.25\text{ m}^3/\text{MWh} \quad (0.4269\text{ kWh/m}^3)$$

### C. Error Bound of the Linear Formulation
- At Full Supply Level ($H_{\text{net}} = 176.10\text{ m}$):
  $$\frac{176.10 - 175.10}{175.10} = +0.57\%$$
- At Minimum Operating Level ($H_{\text{net}} = 174.10\text{ m}$):
  $$\frac{174.10 - 175.10}{175.10} = -0.57\%$$

The maximum theoretical divergence of the linear power approximation is strictly bounded within **$\pm 0.57\%$** across the entire active reservoir volume.

### D. Separation of Optimization Model and Physical Evaluation
To maintain strict scientific honesty:
1. The **Linear Program** uses $k_e$ to make global optimal dispatch decisions.
2. The **Evaluation Suite** post-processes the LP decision variables $(V_{\text{turb}, t}, V_{\text{spill}, t}, S_t)$ through the exact non-linear hydraulic equations:
   $$H_{\text{gross}, t} = h(S_t) - 19.60\text{ MASL}$$
   $$h_{\text{loss}, t} = 10.30 \cdot \left(\frac{Q_{\text{turb}, t}}{Q_{\text{rated}}}\right)^2$$
   $$H_{\text{net}, t} = H_{\text{gross}, t} - h_{\text{loss}, t}$$
   $$E_{\text{phys}, t} = \min\left( \frac{\rho g V_{\text{turb}, t} H_{\text{net}, t} \eta_t}{3.6 \times 10^9}, \, P_{\text{avail}, t} \times 24.0 \right)$$
The gap between the linear LP estimate and physical non-linear energy is explicitly quantified in the evaluation report.

---

## 6. Reference Heuristic Dispatch Policy

To provide a fair, rigorous performance baseline, a reference rule-curve policy is implemented using the identical hydrological inflow sequence, initial storage, outage calendar, and physical boundaries:

1. **Available Water Calculation:**
   $$W_{\text{avail}, t} = S_{t-1} + V_{\text{in}, t} - V_{\text{loss}, t}$$
2. **Surplus Dispatch (High Inflow):**
   If $W_{\text{avail}, t} \ge V_{\text{turb, max}, t} + S_{\max}$:
   $$V_{\text{turb}, t} = V_{\text{turb, max}, t}, \quad S_t = S_{\max}, \quad V_{\text{spill}, t} = W_{\text{avail}, t} - V_{\text{turb}, t} - S_{\max}$$
3. **Normal Dispatch (Moderate Inflow):**
   If $V_{\text{turb, max}, t} \le W_{\text{avail}, t} < V_{\text{turb, max}, t} + S_{\max}$:
   $$V_{\text{turb}, t} = V_{\text{turb, max}, t}, \quad S_t = W_{\text{avail}, t} - V_{\text{turb}, t}, \quad V_{\text{spill}, t} = 0.0$$
4. **Peaking Buffer Dispatch (Low Inflow):**
   If $W_{\text{avail}, t} < V_{\text{turb, max}, t}$:
   $$S_{\text{target}, t} = \min(0.35 \times S_{\max}, \, \max(0.0, \, W_{\text{avail}, t} \times 0.25))$$
   $$V_{\text{turb}, t} = \min(V_{\text{turb, max}, t}, \, \max(0.0, \, W_{\text{avail}, t} - S_{\text{target}, t}))$$
   $$S_t = \max(0.0, \, W_{\text{avail}, t} - V_{\text{turb}, t}), \quad V_{\text{spill}, t} = 0.0$$

---

## 7. Chronological Time-Series Splits

To prevent data leakage and provide fair comparison for future Reinforcement Learning (DQN) models, the 5-year dataset is partitioned chronologically:

1. **Development / Training Horizon (4 Years, 1,461 Days):**
   - Period: `2021-10-19` to `2025-10-18` (Includes 2024 leap day).
   - Used for policy formulation, hyperparameter calibration, and reference tuning.
2. **Held-Out Evaluation Horizon (1 Year, 365 Days):**
   - Period: `2025-10-19` to `2026-10-18`.
   - Strictly reserved for out-of-sample backtesting.
3. **Full 5-Year Horizon (1,826 Days):**
   - Period: `2021-10-19` to `2026-10-18`.
   - Complete multi-year benchmark.
