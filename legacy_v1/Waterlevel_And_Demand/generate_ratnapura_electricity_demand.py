"""
generate_ratnapura_electricity_demand.py
=========================================
Five-Year Daily Synthetic Electricity Demand Generator for Ratnapura District, Sri Lanka
Target Period: 2021-10-19 to 2026-10-18 (Exactly 1,826 Calendar Days Inclusive)
Research Context: Component 3 - Regional Electricity Demand Forecasting Subsystem
Integration Target: Coupled Optimization with Kukule Ganga Power Station

Methodology:
------------
1. Geographic Scope:
   Strictly Ratnapura District, Sabaragamuwa Province, Sri Lanka (CEB Distribution Division 3).
   Encompasses key consumer service centers: Ratnapura Urban, Kahawatte, Eheliyagoda,
   Pelmadulla, Balangoda, and Embilipitiya.
2. Official Baseline Calibration:
   Anchored in official retail sales statistics from the Ceylon Electricity Board (CEB)
   Statistical Digest (2018-2025) and Sales and Generation Data Books for Sabaragamuwa Province
   (530 to 616 GWh/year). Ratnapura District accounts for ~63.5% of provincial consumption
   (~340 to 410 GWh/year, or 930 to 1,123 MWh/day).
3. Temporal Structure:
   - Calibrated weekly profile: Industrial/commercial peak Wednesday (1.035) to weekend Sunday trough (0.895).
   - Monthly seasonal variations: Higher demand in hot/dry March (1.040), holiday dips in April (Avurudu).
   - Documented historical macro-events: 2022 economic crisis rotational load-shedding and fuel shortages.
   - Autoregressive continuity: AR(1) smooth stochastic residuals preserving multi-day persistence.
4. Data Authenticity:
   All records are strictly marked as SYNTHETIC_SCENARIO. No synthetic value is falsely labeled as observed.

Author: Antigravity Agentic Demand Modeling Pipeline
Date: October 2026
"""

import os
import sys
import json
import numpy as np
import pandas as pd

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(WORKSPACE_DIR, "ratnapura_demand_config.json")
OUTPUT_DIR = os.path.join(WORKSPACE_DIR, "ratnapura_electricity_demand")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Configuration file not found: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_demand_series(config):
    t_cfg = config["temporal_scope"]
    g_cfg = config["geographic_scope"]
    b_cfg = config["ceb_statistical_benchmarks"]
    p_cfg = config["temporal_profile_parameters"]

    start_dt = pd.Timestamp(t_cfg["historical_start_date"])
    end_dt = pd.Timestamp(t_cfg["historical_end_date"])
    expected_days = t_cfg["expected_historical_days"]

    dates = pd.date_range(start_dt, end_dt, freq="D")
    n_days = len(dates)
    assert n_days == expected_days, f"Expected {expected_days} days, got {n_days}"

    # Smooth yearly baseline interpolation
    # Define anchor dates at mid-year (July 1st) for each year
    years = [2021, 2022, 2023, 2024, 2025, 2026]
    anchor_dates = [pd.Timestamp(f"{y}-07-01") for y in years]
    anchor_values = [b_cfg["ratnapura_district_mean_daily_mwh"][str(y)] for y in years]

    # Convert to numeric days for smooth cubic/linear spline interpolation
    t_numeric = [(d - start_dt).days for d in dates]
    anchor_numeric = [(d - start_dt).days for d in anchor_dates]
    baseline_smooth = np.interp(t_numeric, anchor_numeric, anchor_values)

    # Multipliers
    dow_map = p_cfg["day_of_week_multipliers"]
    month_map = p_cfg["monthly_seasonality_multipliers"]
    events_cfg = p_cfg["special_events_and_disturbances"]

    demand_mwh = np.zeros(n_days)

    # Fixed random seed for complete reproducibility
    rng = np.random.default_rng(config["project_metadata"]["random_seed"])
    phi = p_cfg["autoregressive_noise"]["ar_phi"]
    sigma = p_cfg["autoregressive_noise"]["noise_sigma"]

    ar_noise = np.zeros(n_days)
    curr_noise = 0.0
    for t in range(n_days):
        innov = rng.normal(0.0, sigma * np.sqrt(1.0 - phi ** 2))
        curr_noise = phi * curr_noise + innov
        ar_noise[t] = curr_noise

    # Events lookup
    crisis_start = pd.Timestamp(events_cfg["economic_crisis_load_shedding_2022"]["start_date"])
    crisis_end = pd.Timestamp(events_cfg["economic_crisis_load_shedding_2022"]["end_date"])
    crisis_factor = events_cfg["economic_crisis_load_shedding_2022"]["mean_suppression_factor"]

    avurudu_days = set(events_cfg["sinhala_tamil_new_year"]["days"])
    avurudu_factor = events_cfg["sinhala_tamil_new_year"]["suppression_factor"]

    yearend_days = set(events_cfg["year_end_holidays"]["days"])
    yearend_factor = events_cfg["year_end_holidays"]["suppression_factor"]

    for t in range(n_days):
        dt = dates[t]
        dow = dt.day_name()
        month_str = str(dt.month)

        w_mult = dow_map[dow]
        m_mult = month_map[month_str]

        # Event multiplier
        e_mult = 1.0
        if crisis_start <= dt <= crisis_end:
            # Random variation in power cut severity
            e_mult *= (crisis_factor + rng.normal(0.0, 0.03))
        if dt.month == 4 and dt.day in avurudu_days:
            e_mult *= avurudu_factor
        if dt.month == 12 and dt.day in yearend_days:
            e_mult *= yearend_factor

        # Total energy calculation
        val = baseline_smooth[t] * w_mult * m_mult * e_mult * (1.0 + ar_noise[t])
        demand_mwh[t] = max(100.0, val) # strictly positive

    df_demand = pd.DataFrame({
        "date": dates,
        "geographic_scope": g_cfg["scope_name"],
        "daily_energy_consumption_mwh": np.round(demand_mwh, 3),
        "data_status": "SYNTHETIC_SCENARIO",
        "generation_method": "CEB_DISTRICT_ANNUAL_DISAGGREGATION_WITH_CALIBRATED_WEEKLY_PROFILE",
        "data_source": "Ceylon Electricity Board (CEB) Statistical Digest (2018-2025) Sabaragamuwa Province / Distribution Division 3 Baseline"
    })

    return df_demand


def main():
    print("=" * 80)
    print("STARTING RATNAPURA DISTRICT ELECTRICITY DEMAND DATASET GENERATION")
    print("=" * 80)

    config = load_config()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df_demand = generate_demand_series(config)
    output_csv = os.path.join(OUTPUT_DIR, "ratnapura_daily_electricity_demand_5years.csv")
    df_demand.to_csv(output_csv, index=False)

    print(f"Generated {len(df_demand)} daily records from {df_demand['date'].iloc[0].date()} to {df_demand['date'].iloc[-1].date()}")
    print(f"Exported: {output_csv}")
    print(f"Mean daily consumption: {df_demand['daily_energy_consumption_mwh'].mean():.2f} MWh/day")
    print(f"Range: [{df_demand['daily_energy_consumption_mwh'].min():.2f}, {df_demand['daily_energy_consumption_mwh'].max():.2f}] MWh/day")
    print("=" * 80)


if __name__ == "__main__":
    main()
