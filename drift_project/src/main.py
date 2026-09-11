"""
main.py
-------
Runs the full 15-minute drift-detection and cause-matched adaptation pipeline.
Works both locally/Contabo (via relative paths) and in Google Colab (/content).
"""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from pathlib import Path
import numpy as np
import pandas as pd

from baseline import train_baseline, predict
from drift import detect_drift_points, classify_point, confirm_structural, validate_against_events
from adapt import route_and_adapt
import evaluate as ev

# Automatically use local project folder if running as a script, or /content in Colab
if Path("/content").exists() and "__file__" not in locals():
    BASE_DIR = Path("/content")
    OUTPUT_DIR = Path("/content")
else:
    BASE_DIR = Path(__file__).resolve().parent
    OUTPUT_DIR = BASE_DIR / "data" if (BASE_DIR / "data").exists() else BASE_DIR

TARGET_COL = "total_generation_mw"


def find_csv_file():
    search_roots = [BASE_DIR, BASE_DIR.parent]
    for root in search_roots:
        for pattern in ["*15min*enriched.csv*", "*enriched.csv*"]:
            matches = list(root.rglob(pattern))
            if matches:
                return matches[0]
    raise FileNotFoundError(f"CSV not found inside {BASE_DIR}!")


def load_data():
    csv_file = find_csv_file()
    print(f"1. Loading dataset from: {csv_file}")
    df = pd.read_csv(csv_file, low_memory=False)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    bad_rows = (df[TARGET_COL] < 200).sum()
    if bad_rows > 0:
        print(f"   Filtering out {bad_rows:,} anomalous/empty intervals (total_generation_mw < 200 MW)...")
        df = df[df[TARGET_COL] >= 200].reset_index(drop=True)

    if "solar_generation_mw" in df.columns:
        df["solar_generation_mw"] = df["solar_generation_mw"].clip(lower=0.0, upper=1000.0)

    event_matches = list(BASE_DIR.rglob("event_table.csv"))
    if event_matches:
        events = pd.read_csv(event_matches[0])
        events["date"] = pd.to_datetime(events["date"])
    else:
        events = pd.DataFrame([
            {"date": "2022-03-01", "event_type": "abrupt", "description": "2022 Economic Crisis & Scheduled Load Shedding"},
            {"date": "2022-08-10", "event_type": "abrupt", "description": "August 2022 Electricity Tariff Hike (~75%)"},
            {"date": "2022-12-01", "event_type": "gradual", "description": "Late-2022 Industrial Contraction & Monsoon Shift"},
            {"date": "2023-02-15", "event_type": "abrupt", "description": "February 2023 Electricity Tariff Hike (~66%)"},
            {"date": "2023-06-01", "event_type": "structural", "description": "Accelerated Rooftop Solar PV Expansion"},
            {"date": "2023-10-20", "event_type": "abrupt", "description": "October 2023 Electricity Tariff Hike (~18%)"},
            {"date": "2024-03-05", "event_type": "gradual", "description": "March 2024 PUCSL Tariff Reduction (~22%) & Demand Recovery"},
            {"date": "2025-04-01", "event_type": "structural", "description": "2025 Dry-Season Peak Rooftop Solar Integration"},
            {"date": "2026-07-15", "event_type": "structural", "description": "2026 Grid-Scale & Rooftop Solar Expansion"},
        ])
        events["date"] = pd.to_datetime(events["date"])

    return df, events


def main():
    df, events = load_data()
    print(f"   Loaded {len(df):,} 15-min rows ({df['date'].min()} to {df['date'].max()})")

    # Step A: Train Static Baseline on Pre-2022 Data
    CUTOFF = pd.Timestamp("2022-01-01")
    train_df = df[df["date"] < CUTOFF].reset_index(drop=True)
    test_df = df[df["date"] >= CUTOFF].reset_index(drop=True)

    model, feature_names = train_baseline(train_df, target_col=TARGET_COL, use_holiday=True, use_weather=True)
    print(f"\n2. Baseline trained on {len(train_df):,} pre-2022 rows with features: {feature_names}")

    warmup_df = train_df[train_df["date"] >= pd.Timestamp("2021-07-01")]
    warmup_preds = predict(model, warmup_df, use_holiday=True, use_weather=True)
    warmup_errors = pd.Series(
        np.abs(warmup_df[TARGET_COL].values - warmup_preds) / np.maximum(warmup_df[TARGET_COL].values, 1e-6),
        index=warmup_df["date"]
    )

    preds = predict(model, test_df, use_holiday=True, use_weather=True)
    errors = pd.Series(
        np.abs(test_df[TARGET_COL].values - preds) / np.maximum(test_df[TARGET_COL].values, 1e-6),
        index=test_df["date"]
    )
    all_errors = pd.concat([warmup_errors, errors])

    # Step B: Detect & Classify Drift Points
    drift_dates = detect_drift_points(errors, warmup_errors=warmup_errors)
    print(f"\n3. Detected {len(drift_dates)} drift points via ADWIN")

    classified = []
    for dp in drift_dates:
        label, tau, delta = classify_point(dp, all_errors)

        def ablation_at_drift(drift_dt):
            train_win = df[(df["date"] >= drift_dt - pd.DateOffset(days=180)) & (df["date"] < drift_dt)]
            eval_win = df[(df["date"] >= drift_dt) & (df["date"] < drift_dt + pd.DateOffset(days=30))]
            if len(train_win) < 96 or len(eval_win) < 96:
                return pd.Series(dtype=float), pd.Series(dtype=float)

            m_no, _ = train_baseline(train_win, target_col=TARGET_COL, use_solar=False, use_holiday=True, use_weather=True, include_trend_annual=False)
            m_sol, _ = train_baseline(train_win, target_col=TARGET_COL, use_solar=True, use_holiday=True, use_weather=True, include_trend_annual=False)
            p_no = predict(m_no, eval_win, use_solar=False, use_holiday=True, use_weather=True, include_trend_annual=False)
            p_sol = predict(m_sol, eval_win, use_solar=True, use_holiday=True, use_weather=True, include_trend_annual=False)
            e_no = pd.Series(np.abs(eval_win[TARGET_COL].values - p_no) / eval_win[TARGET_COL].values, index=eval_win["date"])
            e_sol = pd.Series(np.abs(eval_win[TARGET_COL].values - p_sol) / eval_win[TARGET_COL].values, index=eval_win["date"])
            return e_no, e_sol

        structural_label, reduction = confirm_structural(dp, test_df, all_errors, ablation_at_drift)
        final_label = structural_label or label
        classified.append({
            "date": dp,
            "label": final_label,
            "tau": tau,
            "delta": delta,
            "structural_reduction": reduction
        })

    classified_df = pd.DataFrame(classified)
    print("\n--- Classified Drift Points ---")
    print(classified_df)
    classified_df.to_csv(OUTPUT_DIR / "classified_drift_points.csv", index=False)

    # Step C: Validate Against Known Events
    validation = validate_against_events(drift_dates, events)
    print("\n--- Event Validation ---")
    print(validation)
    validation.to_csv(OUTPUT_DIR / "drift_event_validation.csv", index=False)

    # Step D: Route & Adapt Sequentially
    test_df = test_df.copy()
    test_df["baseline_pred"] = preds
    test_df["adapted_pred"] = preds.copy()

    print("\n4. Applying Cause-Matched Adaptation Strategies:")
    valid_drifts = classified_df[classified_df["label"] != "unclassified"].reset_index(drop=True)

    for idx in range(len(valid_drifts)):
        dp = valid_drifts.loc[idx, "date"]
        d_label = valid_drifts.loc[idx, "label"]
        next_dp = (
            valid_drifts.loc[idx + 1, "date"]
            if (idx + 1) < len(valid_drifts)
            else test_df["date"].max() + pd.DateOffset(days=1)
        )

        adapted_model = route_and_adapt(
            d_label, df, dp, target_col=TARGET_COL, use_holiday=True, use_weather=True
        )
        seg_mask = (test_df["date"] >= dp) & (test_df["date"] < next_dp)
        if seg_mask.sum() > 0:
            flags = getattr(adapted_model, "_adapt_flags", {"use_holiday": True, "use_weather": True})
            test_df.loc[seg_mask, "adapted_pred"] = predict(adapted_model, test_df.loc[seg_mask], **flags)
        print(f"   -> Adapted at {dp.date()} [{d_label}] applied to {dp.date()} .. {next_dp.date()}")

    # Step E: Evaluate Baseline vs Adapted Model by Regime
    regimes = {
        "pre_crisis": (df["date"].min(), pd.Timestamp("2022-03-01")),
        "crisis": (pd.Timestamp("2022-03-01"), pd.Timestamp("2022-08-01")),
        "tariff_adjustment": (pd.Timestamp("2022-08-01"), pd.Timestamp("2023-06-01")),
        "solar_growth": (pd.Timestamp("2023-06-01"), df["date"].max()),
    }

    base_res = ev.regime_mape_rmse(test_df, TARGET_COL, "baseline_pred", regimes)
    base_res["model"] = "Static Baseline"

    adapt_res = ev.regime_mape_rmse(test_df, TARGET_COL, "adapted_pred", regimes)
    adapt_res["model"] = "Cause-Matched Adapted"

    comparison = pd.concat([base_res, adapt_res], ignore_index=True)
    print("\n5. --- Regime Accuracy Comparison ---")
    print(comparison)
    comparison.to_csv(OUTPUT_DIR / "regime_results_comparison.csv", index=False)

    return df, test_df, classified_df, comparison


if __name__ == "__main__":
    main()