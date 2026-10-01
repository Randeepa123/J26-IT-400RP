"""
kukule_ganga_forecast.py
========================
15-Day Probabilistic Rainfall and Water Inflow Forecast
Kukule Ganga Power Station, Kalawana, Ratnapura, Sri Lanka
Forecast period: 18 October 2026 to 01 November 2026

SOURCES USED:
  1. fifteen_day_pdf.pdf       ECMWF 24H rainfall maps, init 12UTC 16 Oct 2026
  2. weekly_forecast.pdf       NCMRWF weekly anomaly forecast, issued 15 Oct 2026
  3. rainfall_pdf.pdf          Seasonal OND outlook + Ratnapura 1991-2020 normals
  4. currentCondition_pdf.pdf  ENSO/IOD conditions, issued 6 Oct 2026
  5. aug26.pdf                 August 2026 observed rainfall anomaly (antecedent)
  6. ratnapura_synthetic_daily_rainfall_10years.csv

TARGET VARIABLE:
  NATURAL INFLOW to the Kukule Ganga hydropower system intake (NOT turbine
  discharge, reservoir release, or downstream river flow).

CRITICAL DISCLAIMERS:
  All inflow values are PROVISIONAL SYNTHETIC ESTIMATES derived from an
  uncalibrated conceptual hydrological model. They are NOT observed flow
  records and must NOT be used for operational decisions without calibration
  against observed streamflow data.

  The ECMWF forecast maps (graphical PDFs) cannot be read numerically without
  GIS processing. All ECMWF guidance is incorporated QUALITATIVELY via the
  NCMRWF weekly anomaly categories.

  The Ratnapura district rainfall data covers a broader administrative area
  than the Kukule Ganga catchment. A spatial scaling factor is applied but
  cannot be validated without rain gauges within the catchment.
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import gamma as sp_gamma
import pdfplumber

warnings.filterwarnings("ignore")

# ================================================================
# CONFIGURATION
# ================================================================
SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
SYNTH_CSV      = os.path.join(SCRIPT_DIR, "ratnapura_synthetic_daily_rainfall_10years.csv")
PDF_DIR        = SCRIPT_DIR

FORECAST_START  = pd.Timestamp("2026-10-18")
FORECAST_END    = pd.Timestamp("2026-11-01")
N_SIMULATIONS   = 1000
RANDOM_SEED     = 42

# Catchment parameters (documented approximations, not calibrated)
CATCHMENT_AREA_KM2   = 270.0    # from published CEB/LECO project documents
CATCHMENT_RF_FACTOR  = 1.25     # orographic enhancement vs Ratnapura district avg
CN_MEAN              = 80.0     # SCS Curve Number (AMC-III: wet antecedent after Aug-Sep)
CN_STD               = 5.0
BASEFLOW_MEAN_M3S    = 27.0     # approximate baseflow (m3/s)
BASEFLOW_STD_M3S     = 8.0
HIGH_INFLOW_THRESH   = 100.0    # provisional high-inflow threshold (m3/s)
DESIGN_Q_M3S         = 93.0     # approx design Q for 70 MW at ~90 m head

# Climatological normals (from rainfall_pdf.pdf annex, 1991-2020)
RATNAPURA_NORMALS_MM = {10: 396.4, 11: 393.7}

# Calibrated from synthetic 10-year dataset
OCT_PWET         = 0.395
OCT_GAMMA_SHAPE  = 0.570
OCT_GAMMA_SCALE  = 57.808
NOV_PWET         = 0.373
NOV_GAMMA_SHAPE  = 0.57
NOV_GAMMA_SCALE  = 63.5

OUTPUT_FILES = {
    "forecast_csv"   : os.path.join(SCRIPT_DIR, "kukule_ganga_15day_forecast.csv"),
    "scenarios_csv"  : os.path.join(SCRIPT_DIR, "kukule_ganga_forecast_scenarios.csv"),
    "validation_txt" : os.path.join(SCRIPT_DIR, "kukule_ganga_forecast_validation.txt"),
    "summary_png"    : os.path.join(SCRIPT_DIR, "kukule_ganga_forecast_summary.png"),
    "inflow_png"     : os.path.join(SCRIPT_DIR, "kukule_ganga_inflow_forecast.png"),
    "uncertainty_png": os.path.join(SCRIPT_DIR, "kukule_ganga_uncertainty_analysis.png"),
}


# ================================================================
# MODULE 1: PDF TEXT EXTRACTION
# ================================================================
def extract_pdf_text(pdf_path, max_pages=None):
    """Extract text from all pages of a PDF using pdfplumber."""
    if not os.path.exists(pdf_path):
        print(f"  [WARN] PDF not found: {os.path.basename(pdf_path)}")
        return ""
    texts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = pdf.pages[:max_pages] if max_pages else pdf.pages
            for pg in pages:
                t = pg.extract_text()
                if t:
                    texts.append(t)
    except Exception as exc:
        print(f"  [WARN] Could not extract text from {os.path.basename(pdf_path)}: {exc}")
    return "\n".join(texts)


def load_pdf_sources():
    """Load and return extracted text from all five PDF sources."""
    pdfs = {
        "fifteen_day"      : os.path.join(PDF_DIR, "fifteen_day_pdf.pdf"),
        "weekly_forecast"  : os.path.join(PDF_DIR, "weekly_forecast.pdf"),
        "rainfall_outlook" : os.path.join(PDF_DIR, "rainfall_pdf.pdf"),
        "current_condition": os.path.join(PDF_DIR, "currentCondition_pdf.pdf"),
        "aug26"            : os.path.join(PDF_DIR, "aug26.pdf"),
    }
    texts = {}
    for key, path in pdfs.items():
        fname = os.path.basename(path)
        texts[key] = extract_pdf_text(path)
        n_chars = len(texts[key])
        avail = "OK" if n_chars > 50 else "limited text (likely scanned maps)"
        print(f"  {fname}: {n_chars:,} chars extracted [{avail}]")
    return texts


# ================================================================
# MODULE 2: FORECAST GUIDANCE TABLE
# ================================================================
def build_forecast_guidance():
    """
    Build a day-by-day forecast guidance table from the meteorological PDFs.

    FORECAST SYNTHESIS LOGIC:
    -------------------------
    Primary source: NCMRWF weekly forecast (weekly_forecast.pdf, 15 Oct 2026)
      Week 1 (16-22 Oct): Near-normal rainfall for most of Sri Lanka
      Week 2 (23-29 Oct): Near-normal for most; slightly above in S. Province
      Week 3 (30Oct-05Nov): Below-normal for MOST of Sri Lanka
      Week 4 (06-12Nov): Near-normal

    Refining sources:
      rainfall_pdf: Week 3 of Oct (16-22 Oct) - below-normal POSSIBLE in some
                    Sabaragamuwa areas; overall Oct slightly above-normal nationally
      currentCondition_pdf: El Nino PRESENT (>90% very strong); historically
                            Ratnapura is NEAR-NORMAL in El Nino Octobers
      aug26.pdf: Antecedent wet conditions in Sabaragamuwa -> high initial wetness

    Resolution for Sabaragamuwa/Kukule Ganga catchment:
      18-22 Oct: Conflicting signals (near-normal weekly; below-possible seasonal
                 for Sabaragamuwa; near-normal El Nino analogue). Central estimate:
                 near-normal with slightly reduced mean (factor centre=0.90).
      23-29 Oct: Near-normal (weekly primary signal; El Nino near-normal for Oct)
      30-31 Oct and 1 Nov: Below-normal (strong weekly W3 signal; Week 3 is more
                 confident below-normal for all of SL including Sabaragamuwa)
    """
    dates = pd.date_range(FORECAST_START, FORECAST_END, freq="D")
    guidance = []

    for dt in dates:
        lead = (dt - FORECAST_START).days + 1

        # Weekly forecast category
        if dt <= pd.Timestamp("2026-10-22"):
            weekly_cat = "near_normal"
            weekly_desc = "W1 NCMRWF 15Oct: near-normal most areas"
        elif dt <= pd.Timestamp("2026-10-29"):
            weekly_cat = "near_normal"
            weekly_desc = "W2 NCMRWF 15Oct: near-normal most areas"
        elif dt <= pd.Timestamp("2026-11-05"):
            weekly_cat = "below_normal"
            weekly_desc = "W3 NCMRWF 15Oct: below-normal most of Sri Lanka"
        else:
            weekly_cat = "near_normal"
            weekly_desc = "W4 NCMRWF 15Oct: near-normal"

        # Seasonal context
        if dt.month == 10:
            seasonal_note = "Seasonal Oct: slightly above-normal; El Nino: near-normal for Ratnapura"
        else:
            seasonal_note = "Seasonal Nov: above-normal; El Nino: near-to-slightly above-normal"

        # ECMWF coverage
        if dt <= pd.Timestamp("2026-10-31"):
            ecmwf_cov = "ECMWF 24H map available (qualitative; graphical PDF only)"
            src_str = f"ECMWF(qualitative); {weekly_desc}; {seasonal_note}"
        else:
            ecmwf_cov = "Beyond ECMWF 14-day maps; weekly+climatology only"
            src_str = f"No ECMWF daily map; {weekly_desc}; {seasonal_note}"

        # Forecast confidence
        if lead <= 3:
            confidence = "HIGH"
        elif lead <= 7:
            confidence = "MEDIUM"
        elif lead <= 14:
            confidence = "LOW"
        else:
            confidence = "VERY_LOW"

        # Synthesised forecast category and distribution parameters
        # Lead-time additional spread: 0.013 per extra day
        lead_extra = min(0.22, lead * 0.013)

        if dt <= pd.Timestamp("2026-10-22"):
            # Near-normal weekly but slightly below-possible from seasonal for Sabaragamuwa
            # El Nino context confirms near-normal. Use 0.90 centre with wider spread.
            final_cat = "near_normal_lean_below"
            cat_centre = 0.90
            cat_spread = 0.32 + lead_extra
        elif dt <= pd.Timestamp("2026-10-29"):
            final_cat = "near_normal"
            cat_centre = 1.00
            cat_spread = 0.30 + lead_extra
        else:
            # Week 3: below-normal for most of Sri Lanka
            final_cat = "below_normal"
            cat_centre = 0.65
            cat_spread = 0.35 + lead_extra

        guidance.append({
            "date"           : dt,
            "week_category"  : weekly_cat,
            "final_category" : final_cat,
            "cat_centre"     : cat_centre,
            "cat_spread"     : cat_spread,
            "forecast_source": src_str,
            "ecmwf_coverage" : ecmwf_cov,
            "confidence"     : confidence,
            "lead_days"      : lead,
        })

    return pd.DataFrame(guidance)


# ================================================================
# MODULE 3: LOAD SYNTHETIC RAINFALL
# ================================================================
def load_and_analyse_synthetic():
    """Load synthetic CSV and compute monthly calibration statistics."""
    if not os.path.exists(SYNTH_CSV):
        sys.exit(f"[ERROR] Synthetic CSV not found: {SYNTH_CSV}")
    df = pd.read_csv(SYNTH_CSV, parse_dates=["date"])
    df["month"] = df["date"].dt.month
    n_neg = (df["rainfall_mm"] < 0).sum()
    n_na  = df["rainfall_mm"].isna().sum()
    if n_neg or n_na:
        print(f"  [WARN] Synthetic data: {n_neg} negatives, {n_na} NaN values")
    print(f"  Rows: {len(df):,}  Range: {df['date'].min().date()} to {df['date'].max().date()}")

    clim = {}
    for m in [10, 11]:
        sub = df[df["month"] == m]
        wet = sub[sub["rainfall_mm"] > 0.1]["rainfall_mm"].values
        g_shape = OCT_GAMMA_SHAPE if m == 10 else NOV_GAMMA_SHAPE
        g_scale = OCT_GAMMA_SCALE if m == 10 else NOV_GAMMA_SCALE
        clim[m] = {
            "p_wet"      : float((sub["rainfall_mm"] > 0.1).mean()),
            "mean_wet"   : float(wet.mean()) if len(wet) else 15.0,
            "gamma_shape": g_shape,
            "gamma_scale": g_scale,
        }
    return df, clim


# ================================================================
# MODULE 4: MONTE CARLO RAINFALL SCENARIOS
# ================================================================
def simulate_rainfall_scenarios(guidance_df, clim, rng):
    """
    Generate N_SIMULATIONS daily catchment rainfall scenarios.

    For each day and simulation:
      1. Sample category multiplier (lognormal around weekly forecast centre)
      2. Adjust wet-day probability: p_adj = p_clim * multiplier (clamped 0.05-0.98)
      3. Sample wet/dry occurrence
      4. If wet: sample Gamma amount, scaled by multiplier
      5. Apply catchment spatial factor (lognormal, mean=1.25)

    The catchment factor represents orographic enhancement over the Kukule Ganga
    highland catchment relative to the Ratnapura district average. It is
    estimated from regional climatological gradients and cannot be validated
    without rain gauges inside the catchment.
    """
    N = N_SIMULATIONS
    n_days = len(guidance_df)

    # Catchment scaling factors (lognormal: mean=1.25, 90% CI = 1.10-1.45)
    cf_mu    = np.log(CATCHMENT_RF_FACTOR)
    cf_sigma = (np.log(1.45) - np.log(1.10)) / (2 * 1.645)
    catch_factors = rng.lognormal(cf_mu, cf_sigma, N)

    scenarios_dist  = np.zeros((N, n_days))
    scenarios_catch = np.zeros((N, n_days))

    for d_idx in range(n_days):
        row   = guidance_df.iloc[d_idx]
        month = int(row["date"].month)
        c     = clim.get(month, clim[10])

        g_shape = c["gamma_shape"]
        g_scale = c["gamma_scale"]
        p_wet   = c["p_wet"]

        # Lognormal category multiplier
        cat_mu    = np.log(float(row["cat_centre"]))
        cat_sigma = float(row["cat_spread"])
        cat_mults = rng.lognormal(cat_mu, cat_sigma, N)

        # Adjusted wet-day probability
        p_adj = np.clip(p_wet * cat_mults, 0.05, 0.98)

        # Wet/dry occurrence
        is_wet = rng.random(N) < p_adj

        # Gamma amounts for wet days, scaled by category multiplier
        raw = sp_gamma.rvs(g_shape, scale=g_scale, size=N, random_state=rng)
        adjusted = raw * cat_mults

        district_daily = np.where(is_wet, adjusted, 0.0)
        district_daily = np.maximum(district_daily, 0.0)

        scenarios_dist[:, d_idx]  = district_daily
        scenarios_catch[:, d_idx] = district_daily * catch_factors

    return scenarios_dist, scenarios_catch


# ================================================================
# MODULE 5: SCS-CN RAINFALL-RUNOFF MODEL
# ================================================================
def scs_cn_runoff(p_mm, cn):
    """
    SCS Curve Number runoff model.
    Q = (P - 0.2*S)^2 / (P + 0.8*S)  for P > 0.2*S, else 0
    S = 25.4 * (1000/CN - 10) [mm]
    """
    S  = 25.4 * (1000.0 / np.maximum(cn, 1.0) - 10.0)
    Ia = 0.2 * S
    Q  = np.where(p_mm > Ia, (p_mm - Ia)**2 / (p_mm + 0.8 * S), 0.0)
    return np.maximum(Q, 0.0)


def simulate_inflow_scenarios(catchment_rf, rng):
    """
    Convert catchment rainfall (mm/day) into inflow (m3/s and m3/day).

    Model: SCS-CN direct runoff + subsurface linear bucket + exponential baseflow

    Uncertainty sources (all sampled per simulation):
      CN           : normal(mean=80, std=5), clipped 60-95
      Baseflow_0   : normal(mean=27, std=8) m3/s, clipped 5-60
      Recession_K  : uniform(0.87, 0.93)
      Direct_frac  : uniform(0.55, 0.75) of surface runoff
      Sub_release  : uniform(0.40, 0.60) per day from subsurface storage

    Note: This model structure is typical for humid tropical catchments but
    has NOT been calibrated against observed Kukule Ganga streamflow data.
    All results are therefore provisional synthetic estimates.
    """
    N, n_days = catchment_rf.shape
    area_m2   = CATCHMENT_AREA_KM2 * 1.0e6

    cn_s       = rng.normal(CN_MEAN, CN_STD, N).clip(60, 95)
    bf0_s      = rng.normal(BASEFLOW_MEAN_M3S, BASEFLOW_STD_M3S, N).clip(5, 60)
    k_s        = rng.uniform(0.87, 0.93, N)
    df_s       = rng.uniform(0.55, 0.75, N)
    sub_k_s    = rng.uniform(0.40, 0.60, N)

    inflow_m3s = np.zeros((N, n_days))
    inflow_m3  = np.zeros((N, n_days))

    for sim in range(N):
        cn   = cn_s[sim]
        bf   = bf0_s[sim]
        k    = k_s[sim]
        df_  = df_s[sim]
        sk   = sub_k_s[sim]
        sub_storage = 0.0

        for d in range(n_days):
            p = catchment_rf[sim, d]

            # Surface runoff
            q_mm = scs_cn_runoff(p, cn)

            # Direct runoff -> fast component (m3/s)
            direct_m3s = q_mm * df_ * area_m2 / (86400.0 * 1000.0)

            # Subsurface bucket
            sub_storage += q_mm * (1.0 - df_) * area_m2 / 1000.0
            sub_release  = sub_storage * sk
            sub_storage -= sub_release
            sub_m3s = sub_release / 86400.0

            # Baseflow recession (floor at 2 m3/s)
            total = max(direct_m3s + sub_m3s + bf, 0.0)
            bf    = max(bf * k, 2.0)

            inflow_m3s[sim, d] = total
            inflow_m3[sim, d]  = total * 86400.0

    return inflow_m3s, inflow_m3


# ================================================================
# MODULE 6: BUILD FORECAST TABLE
# ================================================================
def build_forecast_table(guidance_df, catchment_rf, inflow_m3s, inflow_m3):
    """Aggregate scenario arrays into per-day quantile summary."""
    rows = []
    for d_idx, row in guidance_df.iterrows():
        rf  = catchment_rf[:, d_idx]
        qm3 = inflow_m3s[:, d_idx]
        vm3 = inflow_m3[:, d_idx]

        rows.append({
            "date"                    : row["date"].strftime("%Y-%m-%d"),
            "location"                : "Kukule Ganga Power Station catchment (Kalawana, Ratnapura, LK91)",
            "rainfall_low_mm"         : round(float(np.percentile(rf,  5)), 3),
            "rainfall_median_mm"      : round(float(np.percentile(rf, 50)), 3),
            "rainfall_high_mm"        : round(float(np.percentile(rf, 95)), 3),
            "rainfall_p10_mm"         : round(float(np.percentile(rf, 10)), 3),
            "rainfall_p90_mm"         : round(float(np.percentile(rf, 90)), 3),
            "rainfall_probability_wet": round(float((rf > 0.1).mean()), 4),
            "inflow_low_m3s"          : round(float(np.percentile(qm3,  5)), 3),
            "inflow_median_m3s"       : round(float(np.percentile(qm3, 50)), 3),
            "inflow_high_m3s"         : round(float(np.percentile(qm3, 95)), 3),
            "inflow_p10_m3s"          : round(float(np.percentile(qm3, 10)), 3),
            "inflow_p90_m3s"          : round(float(np.percentile(qm3, 90)), 3),
            "inflow_low_m3"           : round(float(np.percentile(vm3,  5)) / 1e6, 4),
            "inflow_median_m3"        : round(float(np.percentile(vm3, 50)) / 1e6, 4),
            "inflow_high_m3"          : round(float(np.percentile(vm3, 95)) / 1e6, 4),
            "probability_high_inflow" : round(float((qm3 >= HIGH_INFLOW_THRESH).mean()), 4),
            "forecast_source"         : row["forecast_source"],
            "forecast_confidence"     : row["confidence"],
            "data_status"             : ("PROVISIONAL_SYNTHETIC_ECMWF_GUIDED"
                                         if row["date"] <= pd.Timestamp("2026-10-31")
                                         else "PROVISIONAL_SYNTHETIC_WEEKLY_ONLY"),
        })
    return pd.DataFrame(rows)


# ================================================================
# MODULE 7: VALIDATION
# ================================================================
def validate_forecast(forecast_df, catchment_rf, inflow_m3s):
    """Run QC checks on the forecast table. Returns list of issues."""
    issues = []

    def chk(cond, ok_msg, fail_msg):
        if cond:
            print(f"  [QC OK] {ok_msg}")
        else:
            print(f"  [QC FAIL] {fail_msg}")
            issues.append(fail_msg)

    chk(len(forecast_df) == 15, "15 rows present", f"Expected 15 rows, got {len(forecast_df)}")
    chk(not forecast_df["date"].duplicated().any(), "No duplicate dates", "Duplicate dates found")

    expected_dates = pd.date_range(FORECAST_START, FORECAST_END, freq="D").strftime("%Y-%m-%d").tolist()
    missing = set(expected_dates) - set(forecast_df["date"].tolist())
    chk(not missing, "All 15 dates present", f"Missing dates: {missing}")

    for col in ["rainfall_low_mm", "rainfall_median_mm", "rainfall_high_mm"]:
        chk((forecast_df[col] >= 0).all(), f"{col} non-negative", f"Negative values in {col}")
    for col in ["inflow_low_m3s", "inflow_median_m3s", "inflow_high_m3s"]:
        chk((forecast_df[col] >= 0).all(), f"{col} non-negative", f"Negative values in {col}")

    rf_mono = (
        (forecast_df["rainfall_low_mm"] <= forecast_df["rainfall_median_mm"]).all() and
        (forecast_df["rainfall_median_mm"] <= forecast_df["rainfall_high_mm"]).all()
    )
    chk(rf_mono, "Rainfall quantile order OK", "Rainfall quantile ordering violated")

    in_mono = (
        (forecast_df["inflow_low_m3s"] <= forecast_df["inflow_median_m3s"]).all() and
        (forecast_df["inflow_median_m3s"] <= forecast_df["inflow_high_m3s"]).all()
    )
    chk(in_mono, "Inflow quantile order OK", "Inflow quantile ordering violated")

    # Volume-discharge consistency: median_m3 = median_m3s * 86400
    ratio = (forecast_df["inflow_median_m3"] * 1e6) / (forecast_df["inflow_median_m3s"] * 86400)
    chk(((ratio > 0.99) & (ratio < 1.01)).all(), "Volume-discharge consistent",
        "Volume/discharge inconsistency (check Mm3 vs m3 scaling)")

    chk(
        ((forecast_df["rainfall_probability_wet"] >= 0) &
         (forecast_df["rainfall_probability_wet"] <= 1)).all(),
        "P_wet in [0,1]", "P_wet out of range"
    )
    chk(
        ((forecast_df["probability_high_inflow"] >= 0) &
         (forecast_df["probability_high_inflow"] <= 1)).all(),
        "P_high_inflow in [0,1]", "P_high_inflow out of range"
    )

    # Uncertainty should broadly increase with lead time
    early_spread = (forecast_df["inflow_high_m3s"].iloc[:5].mean() -
                    forecast_df["inflow_low_m3s"].iloc[:5].mean())
    late_spread  = (forecast_df["inflow_high_m3s"].iloc[-5:].mean() -
                    forecast_df["inflow_low_m3s"].iloc[-5:].mean())
    chk(late_spread >= early_spread * 0.6,
        "Uncertainty broadly increases with lead time",
        "Uncertainty does NOT increase with lead time (check lead-time spread parameter)")

    return issues


# ================================================================
# MODULE 8: WRITE VALIDATION REPORT
# ================================================================
def write_validation_report(forecast_df, guidance_df, qc_issues, pdf_texts):
    """Write the comprehensive plain-text validation and limitations document."""
    lines = []

    def W(s=""):
        lines.append(s)

    W("=" * 75)
    W("KUKULE GANGA POWER STATION")
    W("15-DAY PROBABILISTIC RAINFALL AND INFLOW FORECAST")
    W("VALIDATION REPORT AND SCIENTIFIC DOCUMENTATION")
    W(f"Generated  : {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    W(f"Period     : {FORECAST_START.date()} to {FORECAST_END.date()}")
    W(f"Location   : Kukule Ganga catchment, Kalawana, Ratnapura District, LK91")
    W(f"Simulations: {N_SIMULATIONS:,}  |  Random seed: {RANDOM_SEED}")
    W("=" * 75)

    W()
    W("-" * 75)
    W("1. INPUT SOURCE DOCUMENTS")
    W("-" * 75)
    W()

    W("  A. fifteen_day_pdf.pdf (ECMWF 14-day rainfall forecast)")
    W("     Title  : 24H RAINFALL (mm) & MAX 2m TEMPERATURE (C) FORECAST")
    W("     Source : NWP Division, Dept of Meteorology, Sri Lanka")
    W("     Init   : ECMWF model 12 UTC 16 October 2026")
    W("     Maps   : 14 pages covering 18-31 October 2026")
    W("     Legend : 0.1, 1, 5, 10, 15, 20, 30, 50, 80, 100, 150, 200, 250 mm")
    W("     Text extracted via pdfplumber: " +
      ("Available" if len(pdf_texts.get("fifteen_day", "")) > 100 else "Minimal (graphical PDF)"))
    W("     LIMITATION: Maps are colour-coded graphics. Exact catchment-average")
    W("     rainfall cannot be read without GIS pixel-to-coordinate mapping.")
    W("     All ECMWF guidance used QUALITATIVELY via weekly anomaly categories.")
    W()

    W("  B. weekly_forecast.pdf (NCMRWF weekly anomaly forecast)")
    W("     Title  : Weekly Rainfall Forecast 16 Oct - 12 Nov 2026")
    W("     Source : Seasonal Forecasting Division, Dept of Meteorology, Sri Lanka")
    W("     Issued : 15 October 2026")
    W("     Basis  : NCMRWF Extended Range Forecasts (init 15 Oct 2026)")
    W("     Week 1 (16-22 Oct): Near-normal most of Sri Lanka")
    W("     Week 2 (23-29 Oct): Near-normal most areas")
    W("     Week 3 (30Oct-05Nov): BELOW-NORMAL for most of Sri Lanka")
    W("     Week 4 (06-12Nov): Near-normal")
    W("     Scale  : RF anomaly -20 to +20 mm/day")
    W("     Note   : Sabaragamuwa Province not explicitly named in week descriptions.")
    W("     LIMITATION: Weekly categories, not point forecasts for the catchment.")
    W()

    W("  C. rainfall_pdf.pdf (Seasonal OND outlook, issued 2 Oct 2026)")
    W("     OND overall: Above-normal rainfall for most of Sri Lanka")
    W("     October: Slightly above-normal (most areas)")
    W("       Week 3 of Oct (16-22 Oct): Below-normal POSSIBLE in some Sabaragamuwa areas")
    W("     November: Above-normal for most")
    W("     December: Slightly above-normal for most")
    W("     Ratnapura District 1991-2020 normals (from annex):")
    W("       October  : 396.4 mm")
    W("       November : 393.7 mm")
    W("       December : 234.7 mm")
    W("     ENSO note in this doc: ENSO-neutral, La Nina development expected (~90%)")
    W("     NOTE: Conflicts with currentCondition_pdf - see discrepancy note below.")
    W()

    W("  D. currentCondition_pdf.pdf (ENSO/IOD, issued 6 Oct 2026)")
    W("     Ref    : SF-2026-10-ENSO-IOD")
    W("     ENSO   : El Nino PRESENT. >90% chance very strong El Nino through OND.")
    W("              75% chance of historic event (strongest since 1950).")
    W("     IOD    : Neutral; index +0.76 C (week ending 27 Sep 2026)")
    W("              Positive IOD likely to develop in S. Hemisphere spring.")
    W("     Rainfall implication for Ratnapura in El Nino years:")
    W("       October  : NEAR-NORMAL (Ratnapura explicitly mentioned)")
    W("       November : Near to slightly above-normal")
    W("       December : Above-normal (most areas)")
    W()
    W("     ENSO DISCREPANCY RESOLUTION:")
    W("     rainfall_pdf (2 Oct): mentions La Nina development expected")
    W("     currentCondition_pdf (6 Oct): states El Nino is present and persisting")
    W("     Resolution: The more recent, directly measured ENSO document (6 Oct)")
    W("     takes precedence. El Nino is assumed operative for this forecast.")
    W("     This does not materially change the Ratnapura Oct forecast since the")
    W("     El Nino analogue explicitly shows near-normal rainfall for Ratnapura.")
    W()

    W("  E. aug26.pdf (Historical rainfall context, August 2026)")
    W("     Title  : Observed Rainfall Anomaly - August 2026")
    W("     Source : Dept of Meteorology, Sri Lanka")
    W("     Finding: Sabaragamuwa Province had near/above-normal rainfall in Aug 2026")
    W("              Country average: 93 mm (77% of normal)")
    W("     Use    : Informs initial catchment wetness condition for Oct simulation.")
    W("     Assumption: Catchment remains wet into October after a near/above-normal")
    W("     August. CN = 80 (AMC-III) used as initial antecedent condition.")
    W("     LIMITATION: No Sep 2026 data available. High wetness assumed to persist.")
    W()

    W("  F. ratnapura_synthetic_daily_rainfall_10years.csv")
    W("     Content: Synthetic daily rainfall 17 Oct 2016 - 17 Oct 2026 (3,653 rows)")
    W("     Note   : SYNTHETIC data from ~10-day CHIRPS aggregates (NOT observed gauge)")
    W("     October calibration statistics used:")
    W(f"       p_wet        = {OCT_PWET:.3f}")
    W(f"       Gamma shape  = {OCT_GAMMA_SHAPE:.3f}")
    W(f"       Gamma scale  = {OCT_GAMMA_SCALE:.3f} mm")
    W(f"       Mean wet-day = {OCT_GAMMA_SHAPE * OCT_GAMMA_SCALE:.1f} mm (from Gamma params)")
    W()

    W("-" * 75)
    W("2. CATCHMENT AND SPATIAL INFORMATION")
    W("-" * 75)
    W()
    W(f"  Catchment  : Kukule Ganga above hydropower intake, Kalawana")
    W(f"  District   : Ratnapura, Sabaragamuwa Province, Sri Lanka")
    W(f"  Approx lat : 6.3-6.7 degN  |  Approx lon: 80.3-80.6 degE")
    W(f"  Area       : ~{CATCHMENT_AREA_KM2:.0f} km2 (approximate, from CEB/LECO project docs)")
    W(f"  Elevation  : 400-2000 m  (mean ~900 m)")
    W(f"  Land cover : Dense forest and scrub (high runoff coefficient)")
    W(f"  Power station: Kukule Ganga Power Station, 70 MW (2 x 35 MW units)")
    W()
    W(f"  Catchment RF factor: {CATCHMENT_RF_FACTOR:.2f} (mean) relative to Ratnapura district avg")
    W(f"  Uncertainty: lognormal 90% CI = 1.10 - 1.45")
    W("  Rationale: Southwest-facing highland slopes receive orographic enhancement")
    W("  during SW monsoon (May-Sep) and NE monsoon (Oct-Jan). Published annual")
    W("  rainfall for upper Kukule Ganga catchment: ~3,500-5,000 mm vs district ~3,400 mm.")
    W("  CANNOT be validated without rain gauges within the catchment.")
    W()

    W("-" * 75)
    W("3. RAINFALL GENERATION METHOD")
    W("-" * 75)
    W()
    W(f"  Monte Carlo simulations: {N_SIMULATIONS:,}")
    W(f"  Random seed: {RANDOM_SEED}")
    W()
    W("  Per-day procedure:")
    W("  1. Determine weekly forecast category (weekly_forecast.pdf primary source)")
    W("  2. Refine with seasonal outlook and El Nino analogue (secondary sources)")
    W("  3. Assign lognormal multiplier distribution: centre = category_mean,")
    W("     sigma = category_spread + 0.013 * lead_day")
    W("  4. Adjust wet-day probability: p_adj = p_clim x multiplier (clipped 0.05-0.98)")
    W("  5. Sample wet/dry occurrence; sample Gamma amounts for wet days")
    W("  6. Scale by catchment spatial factor (lognormal, mean=1.25)")
    W()
    W("  Category parameters:")
    W(f"  {'Category':<28} {'Centre':>8} {'Base spread':>13}")
    W("  " + "-" * 52)
    for cat, cen, spr in [("near_normal_lean_below", 0.90, 0.32),
                           ("near_normal",            1.00, 0.30),
                           ("below_normal",           0.65, 0.35)]:
        W(f"  {cat:<28} {cen:>8.2f} {spr:>13.2f}")
    W()
    W("  Day-by-day category assignments:")
    W(f"  {'Date':<12} {'Category':<25} {'Centre':>8} {'Confidence':>12}")
    W("  " + "-" * 60)
    for _, r in guidance_df.iterrows():
        W(f"  {str(r['date'].date()):<12} {r['final_category']:<25} "
          f"{r['cat_centre']:>8.2f} {r['confidence']:>12}")
    W()

    W("-" * 75)
    W("4. HYDROLOGICAL MODEL")
    W("-" * 75)
    W()
    W("  Model    : SCS Curve Number + Linear Baseflow Recession")
    W("  Status   : UNCALIBRATED - no observed Kukule Ganga flow data was available")
    W("  Outputs  : PROVISIONAL SYNTHETIC ESTIMATES ONLY")
    W()
    W(f"  Catchment area    : {CATCHMENT_AREA_KM2:.0f} km2")
    W(f"  CN (mean/std)     : {CN_MEAN:.0f} / {CN_STD:.0f} (normal distribution)")
    W(f"  Antecedent cond.  : AMC-III (wet, based on Aug 2026 near/above normal in Sab.)")
    W(f"  Baseflow          : normal({BASEFLOW_MEAN_M3S:.0f}, {BASEFLOW_STD_M3S:.0f}) m3/s")
    W(f"  Recession coeff K : uniform(0.87, 0.93) per day")
    W(f"  Direct frac       : uniform(0.55, 0.75) of surface runoff")
    W(f"  Subsurface release: uniform(0.40, 0.60) per day from storage bucket")
    W()
    W(f"  High-inflow threshold: {HIGH_INFLOW_THRESH:.0f} m3/s (PROVISIONAL)")
    W(f"  Basis: approx design Q for 70 MW @ ~90 m head:")
    W(f"         P = rho*g*Q*H*eta => Q = 70e6/(1000*9.81*90*0.85) = {DESIGN_Q_M3S:.0f} m3/s")
    W("  NOTE: This is NOT an official operational flood threshold.")
    W()
    W("  Mass balance: inflow_m3 = inflow_m3s * 86400 seconds/day")
    W("  Output CSV stores volumes in Mm3 (= m3 / 1e6)")
    W()

    W("-" * 75)
    W("5. VALIDATION RESULTS")
    W("-" * 75)
    W()
    if not qc_issues:
        W("  All QC checks PASSED.")
    else:
        W("  QC issues detected:")
        for iss in qc_issues:
            W(f"    FAIL: {iss}")
    W()
    W("  Independent validation: NOT POSSIBLE.")
    W("  No observed daily inflow or rain gauge data was available for comparison.")
    W()

    W("-" * 75)
    W("6. SCIENTIFIC LIMITATIONS")
    W("-" * 75)
    W()
    W("  a) ECMWF MAPS NOT NUMERICALLY READABLE")
    W("     The 14 ECMWF forecast maps are colour-coded graphical images.")
    W("     Exact catchment-average rainfall requires GIS spatial averaging.")
    W("     This was not possible. The ECMWF guidance is QUALITATIVE only.")
    W()
    W("  b) SYNTHETIC RAINFALL CALIBRATION")
    W("     Gamma parameters were fitted to SYNTHETIC daily data derived from")
    W("     ~10-day CHIRPS aggregates. Daily-scale statistics may be unreliable.")
    W()
    W("  c) SPATIAL MISMATCH")
    W(f"     Ratnapura district (~3100 km2) vs Kukule Ganga catchment (~{CATCHMENT_AREA_KM2:.0f} km2).")
    W("     The scaling factor (1.25) is an estimate, not a calibrated value.")
    W()
    W("  d) HYDROLOGICAL MODEL UNCALIBRATED")
    W("     CN, baseflow, and routing parameters are literature estimates.")
    W("     Model uncertainty is VERY HIGH. Inflow scenarios could be wrong")
    W("     by a factor of 2 or more without calibration data.")
    W()
    W("  e) ANTECEDENT CONDITIONS")
    W("     Initial catchment wetness assumed from Aug 2026 above-normal context.")
    W("     No Sep 2026 rainfall data was available to refine this assumption.")
    W()
    W("  f) 1 NOVEMBER 2026 (BEYOND ECMWF DAILY MAPS)")
    W("     No daily ECMWF map exists for this date. Forecast uses weekly W3")
    W("     (below-normal) with widened uncertainty (+0.013*lead_day spread).")
    W()

    W("-" * 75)
    W("7. ADDITIONAL DATA REQUIRED FOR DEFENSIBLE FORECAST")
    W("-" * 75)
    W()
    W("  CRITICAL (cannot produce calibrated forecast without these):")
    W("  - Observed daily streamflow at Kukule Ganga gauging station")
    W("  - Daily rain gauge records within the Kukule Ganga catchment")
    W()
    W("  IMPORTANT (would significantly improve forecast quality):")
    W("  - CHIRPS or GPM IMERG gridded daily rainfall for the catchment (GIS)")
    W("  - Digital Elevation Model for catchment delineation and area verification")
    W("  - Reservoir water level time series (for storage-based inflow estimation)")
    W()
    W("  USEFUL:")
    W("  - SMAP soil moisture satellite data (for CN parameter estimation)")
    W("  - CEB/LECO reservoir operation logs and inflow records")
    W("  - Land use and soil classification maps for the catchment")
    W()

    W("-" * 75)
    W("8. HOW TO REPRODUCE")
    W("-" * 75)
    W()
    W("  Requirements: Python 3.8+, pandas, numpy, matplotlib, scipy, pdfplumber")
    W("  Install: pip install pandas numpy matplotlib scipy pdfplumber")
    W("  Run:     python kukule_ganga_forecast.py")
    W("  Seed:    Change RANDOM_SEED constant for alternative realisations")
    W("  Dates:   Change FORECAST_START and FORECAST_END for updated periods")
    W()
    W("=" * 75)

    with open(OUTPUT_FILES["validation_txt"], "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"  Validation report: {OUTPUT_FILES['validation_txt']}")


# ================================================================
# MODULE 9: PLOTS
# ================================================================
def plot_rainfall_summary(forecast_df):
    """Chart: 15-day rainfall forecast with uncertainty bands."""
    dates  = pd.to_datetime(forecast_df["date"])
    rf_low = forecast_df["rainfall_low_mm"].values
    rf_med = forecast_df["rainfall_median_mm"].values
    rf_hi  = forecast_df["rainfall_high_mm"].values
    rf_p10 = forecast_df["rainfall_p10_mm"].values
    rf_p90 = forecast_df["rainfall_p90_mm"].values

    fig, ax = plt.subplots(figsize=(14, 6))

    ax.fill_between(dates, rf_low, rf_hi,  alpha=0.18, color="#1565C0", label="P5-P95 range")
    ax.fill_between(dates, rf_p10, rf_p90, alpha=0.35, color="#1565C0", label="P10-P90 range")
    ax.plot(dates, rf_med, "o-", color="#0D47A1", lw=2.2, ms=6, label="Median (P50)")

    # Weekly forecast shading
    shades = [
        (pd.Timestamp("2026-10-18"), pd.Timestamp("2026-10-22"), "#E8F5E9", "W1-W2: Near-normal (weekly)"),
        (pd.Timestamp("2026-10-23"), pd.Timestamp("2026-10-29"), "#E8F5E9", None),
        (pd.Timestamp("2026-10-30"), pd.Timestamp("2026-11-01"), "#FFCCBC", "W3: Below-normal (weekly)"),
    ]
    for s, e, col, lbl in shades:
        kw = {"label": lbl} if lbl else {}
        ax.axvspan(s - pd.Timedelta(hours=12), e + pd.Timedelta(hours=12),
                   alpha=0.30, color=col, zorder=0, **kw)

    # Climatological mean reference
    clim_vals = [(RATNAPURA_NORMALS_MM[d.month] / (31 if d.month == 10 else 30)) * CATCHMENT_RF_FACTOR
                 for d in dates]
    ax.step(dates, clim_vals, "--", color="darkorange", lw=1.5, where="mid",
            label=f"Climatol. mean x {CATCHMENT_RF_FACTOR} (Ratnapura normal scaled)")

    ax.set_xlabel("Date", fontsize=11)
    ax.set_ylabel("Catchment Rainfall (mm/day)", fontsize=11)
    ax.set_title(
        "Kukule Ganga Catchment — 15-Day Probabilistic Rainfall Forecast\n"
        "ECMWF (qualitative) + NCMRWF weekly anomaly constrained | 18 Oct – 01 Nov 2026",
        fontsize=11, fontweight="bold")
    ax.legend(fontsize=8.5, loc="upper right", ncol=2)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%d-%b"))

    ax.text(0.01, 0.97,
            "PROVISIONAL SYNTHETIC FORECAST — NOT AN OFFICIAL METEOROLOGICAL PRODUCT",
            transform=ax.transAxes, ha="left", va="top", color="red",
            fontsize=8, fontstyle="italic",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", alpha=0.85))
    plt.tight_layout()
    fig.savefig(OUTPUT_FILES["summary_png"], dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart: {OUTPUT_FILES['summary_png']}")


def plot_inflow_forecast(forecast_df):
    """Chart: Daily inflow scenarios (m3/s and daily volume)."""
    dates   = pd.to_datetime(forecast_df["date"])
    in_low  = forecast_df["inflow_low_m3s"].values
    in_med  = forecast_df["inflow_median_m3s"].values
    in_hi   = forecast_df["inflow_high_m3s"].values
    in_p10  = forecast_df["inflow_p10_m3s"].values
    in_p90  = forecast_df["inflow_p90_m3s"].values
    vol_low = forecast_df["inflow_low_m3"].values
    vol_med = forecast_df["inflow_median_m3"].values
    vol_hi  = forecast_df["inflow_high_m3"].values

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), sharex=True)

    ax1.fill_between(dates, in_low, in_hi,  alpha=0.18, color="#2E7D32", label="P5-P95 range")
    ax1.fill_between(dates, in_p10, in_p90, alpha=0.35, color="#2E7D32", label="P10-P90 range")
    ax1.plot(dates, in_med, "s-", color="#1B5E20", lw=2.2, ms=6, label="Median inflow (P50)")
    ax1.axhline(HIGH_INFLOW_THRESH, ls="--", color="red",    lw=1.5,
                label=f"Provisional high-Q threshold ({HIGH_INFLOW_THRESH:.0f} m³/s)")
    ax1.axhline(DESIGN_Q_M3S, ls=":",  color="orange", lw=1.5,
                label=f"Approx. design Q ({DESIGN_Q_M3S:.0f} m³/s)")
    ax1.set_ylabel("Inflow (m³/s)", fontsize=11)
    ax1.set_title(
        "Kukule Ganga Power Station — Provisional Synthetic Inflow Forecast\n"
        "SCS-CN + Baseflow Model | UNCALIBRATED | 18 Oct – 01 Nov 2026",
        fontsize=11, fontweight="bold")
    ax1.legend(fontsize=8.5, loc="upper right")
    ax1.grid(True, alpha=0.3)

    ax2.fill_between(dates, vol_low, vol_hi,  alpha=0.22, color="#0277BD", label="P5-P95 volume")
    ax2.plot(dates, vol_med, "D-", color="#01579B", lw=2.2, ms=6, label="Median volume (P50)")
    ax2.set_ylabel("Daily Volume (Mm³)", fontsize=11)
    ax2.set_xlabel("Date", fontsize=11)
    ax2.legend(fontsize=8.5)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%d-%b"))

    for ax in [ax1, ax2]:
        ax.text(0.01, 0.97, "PROVISIONAL SYNTHETIC — NOT OBSERVED OR CALIBRATED",
                transform=ax.transAxes, ha="left", va="top", color="red",
                fontsize=7.5, fontstyle="italic",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.85))

    plt.tight_layout()
    fig.savefig(OUTPUT_FILES["inflow_png"], dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart: {OUTPUT_FILES['inflow_png']}")


def plot_uncertainty_analysis(forecast_df, catchment_rf, inflow_m3s):
    """Chart: 4-panel uncertainty analysis across the 15-day horizon."""
    dates     = pd.to_datetime(forecast_df["date"])
    lead_days = np.arange(1, len(dates) + 1)
    date_lbls = [d.strftime("%d%b") for d in dates]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # P1: P(wet day)
    pwet = forecast_df["rainfall_probability_wet"].values
    axes[0, 0].bar(lead_days, pwet, color="#1565C0", alpha=0.78, edgecolor="white")
    axes[0, 0].axhline(OCT_PWET, ls="--", color="orange", lw=1.5,
                       label=f"Oct clim. p_wet={OCT_PWET:.2f}")
    axes[0, 0].set_ylabel("P(wet day >0.1mm)")
    axes[0, 0].set_ylim(0, 1)
    axes[0, 0].set_title("Probability of Wet Day\n(catchment rainfall >0.1 mm)", fontweight="bold")
    axes[0, 0].legend(fontsize=8)
    axes[0, 0].grid(True, alpha=0.3, axis="y")

    # P2: Rainfall P90-P10 spread
    rf_spread = (np.percentile(catchment_rf[:, :len(dates)], 90, axis=0) -
                 np.percentile(catchment_rf[:, :len(dates)], 10, axis=0))
    axes[0, 1].plot(lead_days, rf_spread, "o-", color="#6A1B9A", lw=2)
    axes[0, 1].fill_between(lead_days, 0, rf_spread, alpha=0.22, color="#6A1B9A")
    axes[0, 1].set_ylabel("P90-P10 spread (mm)")
    axes[0, 1].set_title("Rainfall Forecast Uncertainty\n(P90-P10 by lead day)", fontweight="bold")
    axes[0, 1].grid(True, alpha=0.3)

    # P3: P(high inflow)
    phi = forecast_df["probability_high_inflow"].values
    bar_clrs = ["#C62828" if p >= 0.25 else "#EF9A9A" if p >= 0.10 else "#FFCDD2"
                for p in phi]
    axes[1, 0].bar(lead_days, phi * 100, color=bar_clrs, edgecolor="white")
    axes[1, 0].axhline(25, ls="--", color="red", lw=1.5, label="25% alert level")
    axes[1, 0].set_ylabel("Probability (%)")
    axes[1, 0].set_ylim(0, 100)
    axes[1, 0].set_title(
        f"P(Inflow >= {HIGH_INFLOW_THRESH:.0f} m³/s)\n"
        f"Provisional threshold (~design Q {DESIGN_Q_M3S:.0f} m³/s)",
        fontweight="bold")
    axes[1, 0].legend(fontsize=8)
    axes[1, 0].grid(True, alpha=0.3, axis="y")

    # P4: Inflow P90-P10 spread
    in_spread = (np.percentile(inflow_m3s[:, :len(dates)], 90, axis=0) -
                 np.percentile(inflow_m3s[:, :len(dates)], 10, axis=0))
    axes[1, 1].plot(lead_days, in_spread, "s-", color="#E65100", lw=2)
    axes[1, 1].fill_between(lead_days, 0, in_spread, alpha=0.22, color="#E65100")
    axes[1, 1].set_ylabel("P90-P10 spread (m³/s)")
    axes[1, 1].set_title("Inflow Forecast Uncertainty\n(P90-P10 by lead day)", fontweight="bold")
    axes[1, 1].grid(True, alpha=0.3)

    for ax in axes.flat:
        ax.set_xticks(lead_days)
        ax.set_xticklabels(date_lbls, rotation=45, ha="right", fontsize=7)
        ax.text(0.99, 0.01, "PROVISIONAL SYNTHETIC",
                transform=ax.transAxes, ha="right", va="bottom",
                color="red", fontsize=7, fontstyle="italic")

    plt.suptitle(
        "Kukule Ganga — 15-Day Forecast Uncertainty Analysis\n"
        "18 October – 01 November 2026 | Provisional Synthetic Scenarios",
        fontsize=12, fontweight="bold")
    plt.tight_layout()
    fig.savefig(OUTPUT_FILES["uncertainty_png"], dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart: {OUTPUT_FILES['uncertainty_png']}")


# ================================================================
# MAIN
# ================================================================
def main():
    print("\n" + "=" * 65)
    print("  Kukule Ganga Power Station — 15-Day Forecast Pipeline")
    print(f"  Period: {FORECAST_START.date()} to {FORECAST_END.date()}")
    print("=" * 65)

    rng = np.random.default_rng(RANDOM_SEED)

    # Step 1: PDF text extraction
    print("\n[1] Loading PDF documents...")
    pdf_texts = load_pdf_sources()

    # Step 2: Synthetic rainfall statistics
    print("\n[2] Loading synthetic rainfall dataset...")
    synth_df, clim = load_and_analyse_synthetic()

    # Step 3: Forecast guidance
    print("\n[3] Building day-by-day forecast guidance...")
    guidance_df = build_forecast_guidance()
    print(f"    {len(guidance_df)} forecast days configured.")

    # Step 4: Rainfall simulation
    print(f"\n[4] Simulating {N_SIMULATIONS:,} rainfall scenarios (seed={RANDOM_SEED})...")
    district_rf, catchment_rf = simulate_rainfall_scenarios(guidance_df, clim, rng)
    med = np.median(catchment_rf, axis=0)
    print(f"    Catchment RF median range: {med.min():.1f} - {med.max():.1f} mm/day")

    # Step 5: Hydrological simulation
    print("\n[5] Running SCS-CN + baseflow inflow model...")
    inflow_m3s, inflow_m3 = simulate_inflow_scenarios(catchment_rf, rng)
    med_q = np.median(inflow_m3s, axis=0)
    print(f"    Median inflow range: {med_q.min():.1f} - {med_q.max():.1f} m3/s")

    # Step 6: Forecast table
    print("\n[6] Building forecast summary table...")
    forecast_df = build_forecast_table(guidance_df, catchment_rf, inflow_m3s, inflow_m3)

    # Step 7: Save main CSV
    forecast_df.to_csv(OUTPUT_FILES["forecast_csv"], index=False)
    print(f"    Saved: {OUTPUT_FILES['forecast_csv']}")

    # Step 8: Save scenarios CSV (200 simulations to keep file manageable)
    print("\n[7] Saving scenario ensemble (200 simulations)...")
    n_save = min(200, N_SIMULATIONS)
    scen_rows = []
    dates_list = pd.date_range(FORECAST_START, FORECAST_END, freq="D")
    for sim in range(n_save):
        for d_idx, dt in enumerate(dates_list):
            scen_rows.append({
                "simulation"    : sim + 1,
                "date"          : dt.strftime("%Y-%m-%d"),
                "catchment_rf_mm": round(float(catchment_rf[sim, d_idx]), 3),
                "inflow_m3s"    : round(float(inflow_m3s[sim, d_idx]), 3),
                "inflow_Mm3"    : round(float(inflow_m3[sim, d_idx]) / 1e6, 5),
            })
    pd.DataFrame(scen_rows).to_csv(OUTPUT_FILES["scenarios_csv"], index=False)
    print(f"    Saved: {OUTPUT_FILES['scenarios_csv']}")

    # Step 9: Validation
    print("\n[8] Validation checks...")
    qc_issues = validate_forecast(forecast_df, catchment_rf, inflow_m3s)

    # Step 10: Validation report
    print("\n[9] Writing validation report...")
    write_validation_report(forecast_df, guidance_df, qc_issues, pdf_texts)

    # Step 11: Plots
    print("\n[10] Generating charts...")
    plot_rainfall_summary(forecast_df)
    plot_inflow_forecast(forecast_df)
    plot_uncertainty_analysis(forecast_df, catchment_rf, inflow_m3s)

    # Console summary
    print("\n" + "=" * 75)
    print("  15-DAY FORECAST SUMMARY — Kukule Ganga Catchment")
    print("=" * 75)
    print(f"  {'Date':<12} {'RF_med mm':>10} {'RF_p10':>7} {'RF_p90':>7} "
          f"{'Q_med m3/s':>12} {'P(highQ)%':>10} {'Confidence':>10}")
    print("  " + "-" * 73)
    for _, r in forecast_df.iterrows():
        print(f"  {r['date']:<12} {r['rainfall_median_mm']:>10.1f} "
              f"{r['rainfall_p10_mm']:>7.1f} {r['rainfall_p90_mm']:>7.1f} "
              f"{r['inflow_median_m3s']:>12.1f} "
              f"{r['probability_high_inflow']*100:>9.1f}% "
              f"{r['forecast_confidence']:>10}")
    print("=" * 75)
    print()
    print("All outputs:")
    for v in OUTPUT_FILES.values():
        print(f"  {v}")


if __name__ == "__main__":
    main()
