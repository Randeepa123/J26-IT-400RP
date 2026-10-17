> **Component 3 v2 (LP + rolling LP + DQN + hybrid + adaptation, evaluation, forecast-driven CLI): see [README_V2.md](README_V2.md).** The sections below describe the v1 synthetic-data pipeline.

# Kukule Ganga Hydropower Synthetic Dataset Pipeline

**Research Subsystem:** Hydropower Generation and Reservoir Release Optimization Subsystem (Component 3)  
**Target Station:** Kukule Ganga Power Station, Sabaragamuwa Province, Sri Lanka  
**Temporal Coverage:** 2021-10-19 to 2026-10-18 (Exactly 1,826 Calendar Days Inclusive)  
**Primary Application:** Training and testing Linear Programming (LP) and Deep Q-Network (DQN) optimization models  

---

## 1. Project Background and Motivation

The Kukule Ganga Power Station is a 70 MW (2 &times; 35 MW Francis turbines) run-of-river facility with daily pondage located in the wet-zone uplands of the Kalu Ganga basin, Sri Lanka. Historical daily generation and reservoir elevation data were unavailable from the public Samanala Complex web dashboard (`samanalacomplex.lk/test/test/index.php`) as the server only provided a single live telemetry record for 18 October 2026.

This pipeline synthesizes a physically grounded, mass-conserving, and scientifically defensible five-year daily dataset adhering strictly to hydrological and electrical engineering constraints. Original rainfall files in `G:\SLIIT\Research\Rainfall data` are reused without alteration.

---

## 2. Directory and Artifact Structure

```
Waterlevel_And_Demand/
├── generate_synthetic_kukule_dataset.py      # Kukule Ganga generation pipeline
├── verify_synthetic_dataset.py               # Kukule Ganga 8-point QA verification suite
├── simulation_config.json                    # Kukule Ganga simulation parameters
├── generate_ratnapura_electricity_demand.py  # Ratnapura 5-year demand scenario generator
├── forecast_ratnapura_electricity_demand.py  # Ratnapura 15-day demand forecasting pipeline
├── ratnapura_demand_config.json              # Ratnapura demand configuration parameters
├── requirements.txt                          # Python dependencies
├── README.md                                 # Master technical documentation
├── synthetic_kukule_dataset/                 # Dedicated hydropower dataset directory
│   ├── synthetic_kukule_daily_rainfall_5years.csv       (Dataset A)
│   ├── synthetic_kukule_daily_inflow_5years.csv         (Dataset B)
│   ├── synthetic_kukule_pond_water_level_5years.csv     (Dataset C)
│   ├── synthetic_kukule_generation_5years.csv           (Dataset D)
│   ├── synthetic_kukule_integrated_dataset_5years.csv   (Integrated master)
│   ├── synthetic_dataset_quality_checks.csv             (10-point audit table)
│   ├── synthetic_dataset_assumptions.json               (Machine-readable specs)
│   ├── synthetic_dataset_validation_report.txt          (Statistical validation)
│   ├── synthetic_dataset_generation_report.txt          (Execution metadata & SHA256)
│   └── plots/                                           (8 publication-quality charts)
└── ratnapura_electricity_demand/             # Dedicated electricity demand directory
    ├── ratnapura_daily_electricity_demand_5years.csv     (5-year historical scenario)
    ├── ratnapura_electricity_demand_forecast_15days.csv  (15-day out-of-sample forecast)
    ├── ratnapura_demand_historical_and_forecast.png      (2-panel publication chart)
    ├── ratnapura_demand_validation_report.txt           (Chronological backtest report)
    ├── ratnapura_demand_assumptions.json                (CEB benchmarks & model specs)
    └── ratnapura_demand_quality_checks.csv              (8-point automated QA audit)
```

---

## 3. Core Mathematical and Physical Equations

### A. Catchment Hydrology (Rainfall-Runoff Model)
- **Catchment Area:** $A = 312\text{ km}^2$.
- **Unit Conversion:** $1\text{ mm}$ over $312\text{ km}^2 = 312,000\text{ m}^3 \equiv 3.6111\text{ m}^3/\text{s}$ per day.
- **Dynamic Soil Wetness Index:**
  $$\theta_t = \frac{S_t}{S_{\max}} \in [0, 1], \quad S_{\max} = 150.0\text{ mm}$$
- **Direct Surface Runoff Fraction:**
  $$C_d(\theta_t) = 0.12 + 0.62 \cdot \theta_t^{1.8} \quad (\text{boosted to } \min(0.92, C_d + 0.10) \text{ for } P_t > 40\text{ mm})$$
- **Groundwater Percolation & Exponential Baseflow:**
  $$L_{gw, t} = K_{perc} \cdot \theta_t \cdot 45.0, \quad Q_{base, t} = K_{base} \cdot G_t \cdot \frac{A \cdot 1000}{86400}$$
- **Catchment Inflow with 2-Day Unit Hydrograph Routing:**
  $$Q_{in, t} = 0.65 \cdot Q_{quick, t} + 0.35 \cdot Q_{quick, t-1} + Q_{base, t}$$

### B. Reservoir Continuity & Water Balance
- **Continuity Equation:**
  $$S_{end, t} = S_{begin, t} + V_{in, t} - V_{turb, t} - V_{spill, t} - V_{loss, t}$$
- **Active Storage Bounds:**
  $$0.0\text{ m}^3 \le S_t \le 1,670,000\text{ m}^3 \quad (1.67\text{ MCM})$$
- **Pond Water Elevation Curve:**
  $$h(S) = \text{MOL} + (\text{FSL} - \text{MOL}) \cdot \left(\frac{S}{V_{active, \max}}\right)^{\frac{1}{\alpha}}, \quad \text{MOL} = 204.25\text{ m}, \text{ FSL} = 206.00\text{ m}, \alpha = 1.05$$
- **Spillway Overflow:**
  $$V_{spill, t} = \max(0.0, \, S_{begin, t} + V_{in, t} - V_{loss, t} - V_{turb, t} - 1,670,000)$$

### C. Hydropower Generation & Capacity Limits
- **Gross & Net Hydraulic Head:**
  $$H_{gross, t} = h_t - Z_{tail}, \quad Z_{tail} = 29.50\text{ MASL}$$
  $$H_{net, t} = H_{gross, t} - h_{loss}(Q_{turb}), \quad h_{loss} = 2.50 \cdot \left(\frac{Q_{turb}}{47.50}\right)^2$$
- **Electrical Power Output:**
  $$P_t = \rho \cdot g \cdot Q_{turb} \cdot H_{net, t} \cdot \eta \times 10^{-6}\text{ [MW]}$$
  $$\rho = 1000\text{ kg/m}^3, \quad g = 9.81\text{ m/s}^2, \quad \eta \in [0.865, 0.895]$$
- **Daily Generation Constraint:**
  $$E_t = \min\left(\frac{\rho \cdot g \cdot V_{turb} \cdot H_{net, t} \cdot \eta}{3.6 \times 10^9}, \, P_{avail, t} \times 24.0\text{ h}\right) \le 1,680.0\text{ MWh/day}$$

---

## 4. Reconciliation of the 18 October 2026 Dashboard Conflict

The test dashboard reading of **1,835.300 MWh** for Kukule PS on 18 October 2026 was thoroughly audited:
1. Continuous 24-hour operation at the full 70.0 MW rated capacity yields a maximum theoretical daily output of:
   $$70.0\text{ MW} \times 24.0\text{ h} = 1,680.0\text{ MWh/day}$$
2. The dashboard figure exceeds this ceiling by **+155.300 MWh (+9.24%)**, which is physically impossible for a 70 MW facility.
3. Analysis of the test dashboard source code revealed identical uncalibrated field mappings between daily and annual generation metrics.
4. **Resolution:** The synthetic dataset strictly enforces the 1,680.0 MWh engineering ceiling. The discrepancy is fully recorded in the provenance and validation reports.

---

## 5. Execution and Verification Commands

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Regenerate Synthetic Dataset
```bash
python generate_synthetic_kukule_dataset.py
```

### Step 3: Run Automated QA Verification Suite
```bash
python verify_synthetic_dataset.py
```
Expected output:
```
ALL QUALITY ASSURANCE CHECKS PASSED PERFECTLY (8/8)!
Dataset is 100% verified, physically consistent, and ready for LP/DQN.
```

---

## 6. Modular Extensibility

The pipeline is modular:
- **Measured Inflow:** Replace `df_inflow` in `build_integrated_dataset()` with river gauge observations.
- **Authoritative Reservoir Bathymetry:** Adjust `elevation_storage_alpha` in `simulation_config.json`.
- **Actual CEB Generation:** Replace `MODEL_ESTIMATED` generation column with audited dispatch logs.

---

## 7. Ratnapura Area Electricity Demand Forecasting Subsystem

**Geographic Scope:** Ratnapura District, Sabaragamuwa Province, Sri Lanka (CEB Distribution Division 3)  
**Historical Period:** 2021-10-19 to 2026-10-18 (1,826 days)  
**Forecast Period:** 2026-10-19 to 2026-11-02 (15 consecutive days)  
**Directory:** `ratnapura_electricity_demand/`

### Artifacts Generated:
- `ratnapura_daily_electricity_demand_5years.csv`: Historical daily retail energy consumption (MWh/day).
- `ratnapura_electricity_demand_forecast_15days.csv`: 15-day out-of-sample forecast with 90% prediction intervals.
- `ratnapura_demand_historical_and_forecast.png`: 2-panel publication chart labeled *"SYNTHETIC RATNAPURA DEMAND SCENARIO — NOT OFFICIAL METER DATA"*.
- `ratnapura_demand_validation_report.txt`: Chronological backtest evaluation (MAE, RMSE, MAPE) and CEB benchmark reconciliation.
- `ratnapura_demand_assumptions.json`: Parameter metadata, weekly multipliers, and event factors.
- `ratnapura_demand_quality_checks.csv`: Automated QA audit verifying 8 consistency constraints.

### Execution Commands:
```bash
# 1. Generate 5-year daily demand scenario
python generate_ratnapura_electricity_demand.py

# 2. Run chronological model backtest & generate 15-day forecast
python forecast_ratnapura_electricity_demand.py
```
