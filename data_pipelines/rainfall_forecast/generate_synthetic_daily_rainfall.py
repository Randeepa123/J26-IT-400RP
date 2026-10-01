"""
generate_synthetic_daily_rainfall.py
=====================================
Synthetic Daily Rainfall Generator for Ratnapura, Sri Lanka
Target period: 17 October 2016 - 17 October 2026 (inclusive)

Input : ratnapura_rainfall_renamed.csv
Output: ratnapura_synthetic_daily_rainfall_10years.csv
        rainfall_synthetic_data_validation.txt
        PNG charts (chart1..chart4)

Scientific Method Summary
--------------------------
Source data structure:
  - Dates report every 1st, 11th, and 21st of each month (CHIRPS dekadal).
  - Each row rainfall_10day_mm covers the period starting at that date
    and ending the day before the next reported date.
  - rainfall_10day_historical_avg_mm is the long-run historical mean -- NOT
    an additional observed total.
  - Percentage columns (_pct_of_avg) are dimensionless ratios, not mm.

Generation approach (two-stage stochastic disaggregation):
  1. Calibrate, for each of the 36 calendar period slots (3/month x 12 months),
     a two-state Markov chain (wet/dry) and a Gamma intensity distribution
     using all historical years in the source file.
  2. For each source period within the target window, run the Markov chain
     to assign wet/dry status to each day, draw Gamma amounts for wet days,
     then rescale wet-day amounts proportionally so they sum EXACTLY to the
     observed period total.
  3. Partial boundary periods are apportioned by the day-fraction within window.

Reproducibility: fixed random seed (42).

Author  : Research Project -- Hydropower Optimisation Study
Dataset : Ratnapura Rainfall, CHIRPS Admin-2 LK91
"""

import sys, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import warnings
warnings.filterwarnings("ignore")

# ----------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------
SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE     = os.path.join(SCRIPT_DIR, "ratnapura_rainfall_renamed.csv")
OUTPUT_CSV     = os.path.join(SCRIPT_DIR, "ratnapura_synthetic_daily_rainfall_10years.csv")
VALIDATION_TXT = os.path.join(SCRIPT_DIR, "rainfall_synthetic_data_validation.txt")
CHART_DIR      = SCRIPT_DIR

TARGET_START   = pd.Timestamp("2016-10-17")
TARGET_END     = pd.Timestamp("2026-10-17")
RANDOM_SEED    = 42
REQUIRED_COLS  = ["date", "rainfall_10day_mm", "rainfall_10day_historical_avg_mm"]

MONTHS_ABBR = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]

# ================================================================
# 1. LOAD AND VALIDATE
# ================================================================
def load_and_validate(filepath):
    if not os.path.exists(filepath):
        sys.exit(f"[ERROR] Input file not found:\n  {filepath}")

    print(f"[INFO] Loading: {filepath}")
    df = pd.read_csv(filepath, parse_dates=["date"], dayfirst=False)
    missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing_cols:
        sys.exit(f"[ERROR] Missing columns: {missing_cols}\nAvailable: {list(df.columns)}")

    print(f"[INFO] Raw rows: {len(df):,}")
    print(f"[INFO] Columns : {list(df.columns)}")

    df.dropna(subset=["date"], inplace=True)
    dupes = df.duplicated(subset=["date"])
    if dupes.any():
        print(f"[WARN] {dupes.sum()} duplicate date(s) removed (kept first).")
        df = df[~dupes].copy()

    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)

    df["rainfall_10day_mm"] = pd.to_numeric(df["rainfall_10day_mm"], errors="coerce")
    df["rainfall_10day_historical_avg_mm"] = pd.to_numeric(
        df["rainfall_10day_historical_avg_mm"], errors="coerce")

    n_miss = df["rainfall_10day_mm"].isna().sum()
    if n_miss:
        print(f"[WARN] {n_miss} rows missing rainfall_10day_mm -- hist avg used as fallback.")
    print(f"[INFO] Source range: {df['date'].min().date()} to {df['date'].max().date()}")
    return df


# ================================================================
# 2. BUILD PERIOD TABLE
# ================================================================
def build_period_table(df):
    """
    Each source row starts a period that ends the day before the next row.
    Compute period_end, n_days, and effective rainfall total.
    """
    records = []
    dates  = df["date"].tolist()
    obs    = df["rainfall_10day_mm"].tolist()
    hist   = df["rainfall_10day_historical_avg_mm"].tolist()

    for i, row_date in enumerate(dates):
        if i + 1 < len(dates):
            period_end = dates[i+1] - pd.Timedelta(days=1)
        else:
            # Last row: end at last day of that month
            period_end = (row_date + pd.offsets.MonthEnd(0)).normalize()

        n_days = (period_end - row_date).days + 1
        d = row_date.day
        day_group = 1 if d <= 10 else (2 if d <= 20 else 3)

        total = obs[i]
        h_avg = hist[i]
        fallback = False
        if (total is None) or (not np.isfinite(total)) or (total < 0):
            total = h_avg if (h_avg is not None and np.isfinite(h_avg) and h_avg >= 0) else 0.0
            fallback = True

        records.append({
            "period_start": row_date,
            "period_end"  : period_end,
            "n_days"      : int(n_days),
            "total_mm"    : float(total),
            "hist_avg_mm" : float(h_avg) if (h_avg is not None and np.isfinite(h_avg)) else 0.0,
            "month"       : row_date.month,
            "day_group"   : day_group,
            "period_key"  : (row_date.month, day_group),
            "fallback"    : fallback,
        })
    return pd.DataFrame(records)


# ================================================================
# 3. CALIBRATE MARKOV + GAMMA PARAMETERS
# ================================================================
def calibrate_parameters(period_df):
    """
    For each of the 36 calendar period slots estimate:
      p_wet  -- wet-day fraction proxy
      p11    -- P(wet|wet)  Markov persistence
      p01    -- P(wet|dry)
      shape, scale -- Gamma distribution for daily intensities on wet days

    Limitations documented: no daily observations available; parameters
    are statistically approximated from period aggregates.
    """
    PERSISTENCE = 0.65
    params = {}

    for key, grp in period_df.groupby("period_key"):
        totals = grp["total_mm"].values
        n_days = grp["n_days"].values.mean()

        avg_total = float(np.mean(totals))
        p_wet = float(np.clip(avg_total / (n_days * 35.0), 0.05, 0.97))

        # Markov transitions
        p11 = float(np.clip(p_wet + PERSISTENCE * (1.0 - p_wet), p_wet + 0.01, 0.98))
        if p_wet < 0.98:
            p01 = float(np.clip(p_wet * (1.0 - p11) / max(1.0 - p_wet, 1e-9),
                                0.01, p_wet))
        else:
            p01 = 0.88

        # Gamma from period daily averages
        daily_avgs = totals / np.maximum(n_days, 1)
        pos_avgs = daily_avgs[daily_avgs > 0.1]

        if len(pos_avgs) >= 3:
            mu  = float(np.mean(pos_avgs))
            var = float(np.var(pos_avgs, ddof=1)) if len(pos_avgs) > 1 else mu
            if var > 1e-6 and mu > 1e-6:
                shape = (mu**2) / var
                scale = var / mu
            else:
                shape = 1.5
                scale = max(mu / 1.5, 0.5)
        else:
            shape = 1.5
            scale = 2.0

        shape = float(np.clip(shape, 0.5, 10.0))
        scale = float(np.clip(scale, 0.5, 50.0))

        params[key] = {"p_wet": p_wet, "p11": p11, "p01": p01,
                       "shape": shape, "scale": scale}
    return params


# ================================================================
# 4. DISAGGREGATE ONE PERIOD
# ================================================================
def disaggregate_period(period_total, n_days, p11, p01, shape, scale, rng):
    """
    Two-stage stochastic disaggregation:
    1. Markov wet/dry sequence of length n_days.
    2. Gamma-distributed amounts for wet days.
    3. Proportional rescaling to match period_total exactly.
    """
    n = int(n_days)
    if n <= 0:
        return np.array([])
    if period_total <= 0.0:
        return np.zeros(n)

    # Markov sequence
    wet = np.zeros(n, dtype=bool)
    p_wet_stat = p01 / (p01 + 1.0 - p11) if (p01 + 1.0 - p11) > 1e-9 else 0.5
    wet[0] = rng.random() < p_wet_stat
    for t in range(1, n):
        prob = p11 if wet[t-1] else p01
        wet[t] = rng.random() < prob

    if not wet.any():
        wet[rng.integers(0, n)] = True

    n_wet = int(wet.sum())
    raw   = rng.standard_gamma(shape, size=n_wet) * scale
    raw   = np.maximum(raw, 1e-9)

    scale_f = period_total / raw.sum()
    daily   = np.zeros(n)
    daily[wet] = raw * scale_f
    return daily


# ================================================================
# 5. MAIN GENERATION LOOP
# ================================================================
def generate_daily_rainfall(period_df, params, rng):
    records = []
    for _, row in period_df.iterrows():
        eff_start = max(row["period_start"], TARGET_START)
        eff_end   = min(row["period_end"],   TARGET_END)
        if eff_start > eff_end:
            continue
        day_range = pd.date_range(eff_start, eff_end, freq="D")
        n_eff     = len(day_range)

        # Apportion total if this is a partial boundary period
        n_full = row["n_days"]
        if n_full > 0 and n_eff < n_full:
            period_total = row["total_mm"] * (n_eff / n_full)
        else:
            period_total = row["total_mm"]

        key = row["period_key"]
        p   = params.get(key, {"p11": 0.6, "p01": 0.3, "shape": 1.5, "scale": 3.0})

        vals = disaggregate_period(period_total, n_eff,
                                   p["p11"], p["p01"],
                                   p["shape"], p["scale"], rng)
        for dt, v in zip(day_range, vals):
            records.append({"date": dt, "rainfall_mm": max(0.0, float(v))})

    df_daily = pd.DataFrame(records)
    df_daily.sort_values("date", inplace=True)
    df_daily.reset_index(drop=True, inplace=True)
    return df_daily


# ================================================================
# 6. FILL DATE GAPS
# ================================================================
def fill_date_gaps(df_daily, params, rng):
    full_range  = pd.date_range(TARGET_START, TARGET_END, freq="D")
    existing    = set(df_daily["date"].dt.normalize())
    missing_dts = [d for d in full_range if d.normalize() not in existing]
    if not missing_dts:
        return df_daily
    print(f"[INFO] Filling {len(missing_dts)} gap date(s) from calibrated parameters.")
    extra = []
    for dt in missing_dts:
        d = dt.day
        dg = 1 if d <= 10 else (2 if d <= 20 else 3)
        key = (dt.month, dg)
        if key in params:
            p = params[key]
            val = (rng.standard_gamma(p["shape"]) * p["scale"]
                   if rng.random() < p["p_wet"] else 0.0)
        else:
            val = 0.0
        extra.append({"date": dt, "rainfall_mm": max(0.0, val)})
    df_out = pd.concat([df_daily, pd.DataFrame(extra)], ignore_index=True)
    df_out.sort_values("date", inplace=True)
    df_out.reset_index(drop=True, inplace=True)
    return df_out


# ================================================================
# 7. QUALITY CHECKS
# ================================================================
def quality_check(df):
    n_exp = len(pd.date_range(TARGET_START, TARGET_END, freq="D"))
    assert len(df) == n_exp, f"[ERROR] Row count mismatch: got {len(df)}, expected {n_exp}"
    assert not df["date"].duplicated().any(), "[ERROR] Duplicate dates found"
    assert (df["rainfall_mm"] >= 0).all(), "[ERROR] Negative rainfall values"
    assert df["rainfall_mm"].notna().all(), "[ERROR] NaN rainfall values"
    print(f"[QC] All checks passed -- {len(df):,} rows, no negatives, no NaNs, no duplicates.")


# ================================================================
# 8. SUMMARY
# ================================================================
def print_summary(df):
    total  = df["rainfall_mm"].sum()
    rainy  = (df["rainfall_mm"] > 0.1).sum()
    n      = len(df)
    mx     = df["rainfall_mm"].max()
    mx_dt  = df.loc[df["rainfall_mm"].idxmax(), "date"].date()
    print("\n" + "="*60)
    print("  SYNTHETIC DAILY RAINFALL -- SUMMARY")
    print("="*60)
    print(f"  Records          : {n:,}")
    print(f"  Date range       : {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"  Rainy days>0.1mm : {rainy:,}  ({100*rainy/n:.1f}%)")
    print(f"  Dry days         : {n-rainy:,}  ({100*(n-rainy)/n:.1f}%)")
    print(f"  Total rainfall   : {total:,.1f} mm")
    print(f"  Mean annual      : {total/10:.1f} mm/yr (10-yr avg)")
    print(f"  Max single day   : {mx:.1f} mm  on {mx_dt}")
    print()
    print(f"  {'Month':<10} {'Avg mm/yr':>10}  {'Wet-day %':>10}")
    df2 = df.copy()
    df2["month"] = df2["date"].dt.month
    mg = df2.groupby("month")
    for m_idx in range(1, 13):
        grp = mg.get_group(m_idx)
        avg_total = grp["rainfall_mm"].sum() / 10.0
        pct_wet   = 100 * (grp["rainfall_mm"] > 0.1).sum() / len(grp)
        print(f"  {MONTHS_ABBR[m_idx-1]:<10} {avg_total:>10.1f}  {pct_wet:>9.1f}%")
    print("="*60 + "\n")


# ================================================================
# 9. PERIOD-TOTAL VERIFICATION
# ================================================================
def verify_period_totals(df_daily, period_df):
    rows = []
    for _, row in period_df.iterrows():
        ps, pe = row["period_start"], row["period_end"]
        if ps < TARGET_START or pe > TARGET_END:
            continue
        mask = (df_daily["date"] >= ps) & (df_daily["date"] <= pe)
        synth_sum = df_daily.loc[mask, "rainfall_mm"].sum()
        rows.append({
            "period_start": ps.date(),
            "period_end"  : pe.date(),
            "observed_mm" : round(row["total_mm"], 4),
            "synthetic_mm": round(synth_sum, 4),
            "diff_mm"     : round(synth_sum - row["total_mm"], 4),
        })
    return pd.DataFrame(rows)


# ================================================================
# 10. VALIDATION REPORT
# ================================================================
def write_validation_report(df_daily, period_df, params, comparison_df):
    total  = df_daily["rainfall_mm"].sum()
    rainy  = (df_daily["rainfall_mm"] > 0.1).sum()
    n      = len(df_daily)

    df2 = df_daily.copy()
    df2["month"] = df2["date"].dt.month
    synth_monthly = df2.groupby("month")["rainfall_mm"].sum() / 10.0

    period_df2 = period_df.copy()
    period_df2["month"] = period_df2["period_start"].dt.month
    hist_monthly = period_df2.groupby("month")["hist_avg_mm"].sum() / 3.0

    lines = []
    def W(s=""): lines.append(s)

    W("="*70)
    W("SYNTHETIC DAILY RAINFALL -- VALIDATION REPORT")
    W("Ratnapura, Sri Lanka | CHIRPS Admin-2 LK91")
    W(f"Generated  : {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    W(f"Target range: {TARGET_START.date()} to {TARGET_END.date()}")
    W("="*70)
    W()
    W("-"*70)
    W("1. SOURCE DATASET OVERVIEW")
    W("-"*70)
    W(f"  File         : ratnapura_rainfall_renamed.csv")
    W(f"  Source range : {period_df['period_start'].min().date()} to "
      f"{period_df['period_start'].max().date()}")
    W(f"  Periods      : {len(period_df):,}  (approx. 10-day dekadal intervals)")
    W(f"  Report dates : 1st, 11th, 21st of each month")
    W()
    W("  Column usage:")
    W("  rainfall_10day_mm             -> observed period total (USED as generation target)")
    W("  rainfall_10day_historical_avg -> long-run historical mean (USED as calibration aid)")
    W("  rainfall_1month_mm            -> NOT used directly (derived sum)")
    W("  rainfall_Xmonth_pct_of_avg    -> NOT used (dimensionless ratio, not mm)")
    W()
    W("-"*70)
    W("2. GENERATION METHOD")
    W("-"*70)
    W("  Model: Two-state Markov chain (wet/dry) + Gamma intensity distribution")
    W()
    W("  A. Calibration (per calendar slot: 3 per month x 12 months = 36 slots)")
    W("     p_wet   : proxy wet-day fraction = period_total / (n_days x 35 mm)")
    W("               35 mm/day is a soft upper bound for Ratnapura. CANNOT be")
    W("               directly validated -- no daily observations available.")
    W()
    W("     Markov  : P(wet|wet)=p11, P(wet|dry)=p01 from p_wet + persistence=0.65")
    W("               Persistence is a climatological prior for tropical humid zones.")
    W("               CANNOT be calibrated from aggregated source data.")
    W()
    W("     Gamma   : shape/scale by method-of-moments on period daily-average totals.")
    W("               Fitted to inter-period variability, NOT true daily variability.")
    W()
    W("  B. Disaggregation (per source period within target window)")
    W("     1. Run Markov chain for n_days of the period.")
    W("     2. Draw Gamma amounts for wet days.")
    W("     3. Rescale amounts so they sum EXACTLY to the observed period total.")
    W("     4. Boundary periods apportioned proportionally by day fraction.")
    W()
    W("  C. Random seed: 42 (fully reproducible)")
    W()
    W("-"*70)
    W("3. PERIOD-TOTAL PRESERVATION")
    W("-"*70)
    if len(comparison_df) > 0:
        max_diff  = comparison_df["diff_mm"].abs().max()
        mean_diff = comparison_df["diff_mm"].abs().mean()
        W(f"  Fully-contained periods checked : {len(comparison_df):,}")
        W(f"  Max absolute difference         : {max_diff:.6f} mm (floating-point only)")
        W(f"  Mean absolute difference        : {mean_diff:.6f} mm")
        W()
        W(f"  {'Period Start':<14} {'Period End':<12} {'Observed':>10} {'Synthetic':>10} {'Diff':>9}")
        W("  " + "-"*60)
        for _, cr in comparison_df.head(30).iterrows():
            W(f"  {str(cr['period_start']):<14} {str(cr['period_end']):<12} "
              f"{cr['observed_mm']:>10.3f} {cr['synthetic_mm']:>10.3f} "
              f"{cr['diff_mm']:>9.5f}")
    else:
        W("  No fully contained periods found.")
    W()
    W("-"*70)
    W("4. MONTHLY COMPARISON (Synthetic avg vs Historical avg)")
    W("-"*70)
    W("  NOTE: 'Synthetic avg mm' is mean annual monthly total from synthetic data.")
    W("  'Historical avg mm' is sum of source hist_avg columns / 3 (approximate).")
    W("  These use different sample bases -- comparison is a rough sanity check only.")
    W()
    W(f"  {'Month':<8} {'Synth avg':>12} {'Hist avg':>12} {'Ratio':>8}")
    W("  " + "-"*45)
    for m in range(1, 13):
        sv = float(synth_monthly.get(m, 0.0))
        hv = float(hist_monthly.get(m, 0.0))
        r  = sv / hv if hv > 0 else float("nan")
        W(f"  {MONTHS_ABBR[m-1]:<8} {sv:>12.1f} {hv:>12.1f} {r:>8.3f}")
    W()
    W("-"*70)
    W("5. STATISTICAL SUMMARY")
    W("-"*70)
    W(f"  Total records        : {n:,}")
    W(f"  Rainy days (>0.1mm)  : {rainy:,}  ({100*rainy/n:.1f}%)")
    W(f"  Total rainfall       : {total:,.1f} mm over 10 years")
    W(f"  Mean annual rainfall : {total/10:.1f} mm/yr")
    W(f"  Max daily value      : {df_daily['rainfall_mm'].max():.2f} mm")
    W(f"  Median wet-day amt   : {df_daily.loc[df_daily['rainfall_mm']>0.1,'rainfall_mm'].median():.2f} mm")
    W(f"  95th percentile daily: {df_daily['rainfall_mm'].quantile(0.95):.2f} mm")
    W(f"  99th percentile daily: {df_daily['rainfall_mm'].quantile(0.99):.2f} mm")
    W()
    W("-"*70)
    W("6. CALIBRATED PARAMETERS (36 calendar slots)")
    W("-"*70)
    W(f"  {'Month':<6}{'Grp':>4}  {'p_wet':>7}  {'p11':>7}  {'p01':>7}  {'shape':>7}  {'scale':>7}")
    W("  " + "-"*55)
    for m in range(1, 13):
        for g in range(1, 4):
            p = params.get((m, g))
            if p:
                W(f"  {MONTHS_ABBR[m-1]:<6}{g:>4}  "
                  f"{p['p_wet']:>7.3f}  {p['p11']:>7.3f}  {p['p01']:>7.3f}  "
                  f"{p['shape']:>7.3f}  {p['scale']:>7.3f}")
    W()
    W("-"*70)
    W("7. LIMITATIONS AND SCIENTIFIC CAVEATS")
    W("-"*70)
    W("  The following cannot be validated from the available source (aggregates only):")
    W()
    W("  a) Daily wet-day frequency -- estimated via heuristic, not observation.")
    W("  b) Markov persistence -- set as a climatological prior (0.65).")
    W("  c) Extreme daily rainfall -- Gamma fitted to period means, not daily extremes;")
    W("     true daily maxima at Ratnapura can exceed 200 mm; these may be under-")
    W("     represented in this simulation.")
    W("  d) Within-period temporal structure -- rescaling removes true day-to-day")
    W("     autocorrelation; inter-day dependence is from the Markov chain only.")
    W("  e) Monsoon onset/retreat timing -- not explicitly modeled.")
    W()
    W("  RECOMMENDATION: Use as preliminary stochastic forcing for hydropower")
    W("  simulations. Do NOT substitute for observed daily records in formal")
    W("  hydrological calibration, flood frequency analysis, or operations.")
    W()
    W("-"*70)
    W("8. HOW TO REPRODUCE")
    W("-"*70)
    W("  Requirements: Python 3.8+, pandas, numpy, matplotlib, scipy")
    W("  Install:  pip install pandas numpy matplotlib scipy")
    W("  Run:      python generate_synthetic_daily_rainfall.py")
    W("  Seed:     42  (change RANDOM_SEED constant for different realisations)")
    W("="*70)

    with open(VALIDATION_TXT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"[INFO] Validation report: {VALIDATION_TXT}")


# ================================================================
# 11. PLOTS
# ================================================================
def make_plots(df, period_df):
    df = df.copy()
    df["year"]  = df["date"].dt.year
    df["month"] = df["date"].dt.month
    BLUE = "#1565C0"

    # Chart 1 -- Monthly totals bar chart
    fig, ax = plt.subplots(figsize=(14, 5))
    df["ym"] = df["date"].dt.to_period("M")
    mtot = df.groupby("ym")["rainfall_mm"].sum()
    xs   = range(len(mtot))
    ax.bar(xs, mtot.values, color=BLUE, alpha=0.8, width=0.9)
    ax.set_xticks(list(xs)[::6])
    ax.set_xticklabels([str(p) for p in mtot.index[::6]], rotation=45, ha="right", fontsize=8)
    ax.set_xlabel("Month")
    ax.set_ylabel("Rainfall (mm)")
    ax.set_title("Monthly Rainfall Totals (Synthetic) -- Ratnapura, Sri Lanka\n"
                 "17 Oct 2016 to 17 Oct 2026", fontweight="bold")
    ax.text(0.99, 0.98, "SYNTHETIC DATA -- NOT OBSERVED",
            transform=ax.transAxes, ha="right", va="top",
            color="red", fontsize=8, fontstyle="italic")
    plt.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "chart1_monthly_totals.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[INFO] Chart 1 saved.")

    # Chart 2 -- Average monthly climatology
    fig, ax = plt.subplots(figsize=(10, 5))
    avg_mo = df.groupby("month")["rainfall_mm"].sum() / 10.0
    clrs = [plt.cm.Blues(0.35 + 0.55 * v / max(avg_mo.max(), 1)) for v in avg_mo]
    ax.bar(range(1, 13), avg_mo.values, color=clrs, edgecolor="white")
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(MONTHS_ABBR)
    ax.set_xlabel("Month")
    ax.set_ylabel("Average Rainfall (mm)")
    ax.set_title("Average Monthly Rainfall -- 10-Year Mean (Synthetic)\n"
                 "Ratnapura, Sri Lanka", fontweight="bold")
    # Overlay source historical average
    pd2 = period_df.copy()
    pd2["month"] = pd2["period_start"].dt.month
    hist_mo = pd2.groupby("month")["hist_avg_mm"].sum() / 3.0
    ax.plot(range(1, 13), [hist_mo.get(m, 0) for m in range(1, 13)],
            "o--", color="darkorange", lw=1.8, ms=5, label="Historical avg (source)")
    ax.legend(fontsize=9)
    ax.text(0.99, 0.98, "SYNTHETIC DATA -- NOT OBSERVED",
            transform=ax.transAxes, ha="right", va="top",
            color="red", fontsize=8, fontstyle="italic")
    plt.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "chart2_avg_monthly_climatology.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[INFO] Chart 2 saved.")

    # Chart 3 -- Daily time series
    fig, ax = plt.subplots(figsize=(16, 4))
    ax.fill_between(df["date"], df["rainfall_mm"], alpha=0.55, color=BLUE)
    ax.plot(df["date"], df["rainfall_mm"], lw=0.3, color=BLUE)
    ax.set_xlabel("Date")
    ax.set_ylabel("Rainfall (mm/day)")
    ax.set_title("Daily Rainfall Time Series (Synthetic) -- Ratnapura, Sri Lanka\n"
                 "17 Oct 2016 to 17 Oct 2026", fontweight="bold")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.text(0.99, 0.98, "SYNTHETIC DATA -- NOT OBSERVED",
            transform=ax.transAxes, ha="right", va="top",
            color="red", fontsize=8, fontstyle="italic")
    plt.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "chart3_daily_timeseries.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[INFO] Chart 3 saved.")

    # Chart 4 -- Distribution
    wet = df.loc[df["rainfall_mm"] > 0.1, "rainfall_mm"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].hist(wet, bins=60, color=BLUE, alpha=0.8, edgecolor="white")
    axes[0].set_xlabel("Daily Rainfall (mm)")
    axes[0].set_ylabel("Frequency")
    axes[0].set_title("Wet-Day Rainfall Distribution (linear)", fontweight="bold")
    axes[0].text(0.97, 0.97, "SYNTHETIC", transform=axes[0].transAxes,
                 ha="right", va="top", color="red", fontsize=8, fontstyle="italic")
    axes[1].hist(wet, bins=60, color="#C62828", alpha=0.8, edgecolor="white")
    axes[1].set_yscale("log")
    axes[1].set_xlabel("Daily Rainfall (mm)")
    axes[1].set_ylabel("Frequency (log scale)")
    axes[1].set_title("Wet-Day Rainfall Distribution (log-scale tail)", fontweight="bold")
    axes[1].text(0.97, 0.97, "SYNTHETIC", transform=axes[1].transAxes,
                 ha="right", va="top", color="red", fontsize=8, fontstyle="italic")
    plt.suptitle("Ratnapura -- Synthetic Daily Rainfall Distribution", fontweight="bold", y=1.01)
    plt.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "chart4_daily_distribution.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[INFO] Chart 4 saved.")


# ================================================================
# MAIN
# ================================================================
def main():
    print("\n" + "="*60)
    print("  Synthetic Daily Rainfall Generator -- Ratnapura, Sri Lanka")
    print("="*60)

    source_df = load_and_validate(INPUT_FILE)
    print("[INFO] Building period table...")
    period_df = build_period_table(source_df)
    print(f"[INFO] {len(period_df):,} periods built.")

    print("[INFO] Calibrating parameters...")
    params = calibrate_parameters(period_df)
    print(f"[INFO] {len(params)} calendar slots calibrated.")

    rng = np.random.default_rng(RANDOM_SEED)
    print("[INFO] Generating daily rainfall...")
    df_daily = generate_daily_rainfall(period_df, params, rng)
    df_daily = fill_date_gaps(df_daily, params, rng)

    quality_check(df_daily)
    print_summary(df_daily)

    print("[INFO] Verifying period totals...")
    comparison_df = verify_period_totals(df_daily, period_df)
    if len(comparison_df) > 0:
        print(f"[QC] Max period-total diff: "
              f"{comparison_df['diff_mm'].abs().max():.6f} mm  "
              f"({len(comparison_df)} periods)")

    out = df_daily[["date", "rainfall_mm"]].copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out.to_csv(OUTPUT_CSV, index=False, float_format="%.4f")
    print(f"[INFO] CSV saved: {OUTPUT_CSV}")

    write_validation_report(df_daily, period_df, params, comparison_df)

    print("[INFO] Generating plots...")
    make_plots(df_daily, period_df)

    print("\n[DONE] All outputs in:", SCRIPT_DIR)


if __name__ == "__main__":
    main()
