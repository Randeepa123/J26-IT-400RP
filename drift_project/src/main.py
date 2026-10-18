"""
main.py
-------
Runs the full pipeline end to end:
  1. (Assumes pucsl_scraper.py and enrich_calendar_weather.py already ran)
  2. Load enriched dataset + event table
  3. Train baseline, compute rolling error
  4. Detect drift (ADWIN), classify each point, confirm structural via ablation
  5. Validate against known events
  6. Route each drift point to its adaptation strategy, retrain
  7. Evaluate regime-by-regime + adaptation lag

Run: python main.py
Requires data/pucsl_clean_daily_enriched.csv and data/event_table.csv to exist.
"""
from pathlib import Path
import numpy as np
import pandas as pd

from baseline import train_baseline, predict
from drift import detect_drift_points, classify_point, confirm_structural, validate_against_events
from adapt import route_and_adapt
import evaluate as ev

DATA_DIR = Path(__file__).parent.parent / "data"
ENRICHED_FILE = DATA_DIR / "pucsl_clean_daily_enriched.csv"
EVENT_FILE = DATA_DIR / "event_table.csv"
TARGET_COL = "total_generation_mw"


def load_data():
    df = pd.read_csv(ENRICHED_FILE)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    if EVENT_FILE.exists():
        events = pd.read_csv(EVENT_FILE)
        events["date"] = pd.to_datetime(events["date"])
    else:
        print(f"! {EVENT_FILE} not found -- using an empty event table. "
              "Create one with columns: date, event_type, description.")
        events = pd.DataFrame(columns=["date", "event_type", "description"])
    return df, events


def main():
    df, events = load_data()
    print(f"Loaded {len(df)} days of data, {df['date'].min()} to {df['date'].max()}")

    # --- 1. Baseline, trained ONLY on pre-crisis data (not a generic split) ---
    # This is deliberate: training must stop before 2022-03-01 so the crisis,
    # tariff, and solar regimes all fall in the TEST set, where drift should
    # actually be detected. A generic 70/30 split would bury the crisis inside
    # training data and defeat the entire premise of this research.
    CUTOFF = pd.Timestamp("2022-01-01")  # ADJUST if your data starts later/earlier
    train_df = df[df["date"] < CUTOFF].reset_index(drop=True)
    test_df = df[df["date"] >= CUTOFF].reset_index(drop=True)
    if len(train_df) < 180:
        print(f"! only {len(train_df)} days before {CUTOFF.date()} -- baseline may be unreliable "
              f"with less than ~6 months of pre-crisis training data")

    model, feature_names = train_baseline(train_df, target_col=TARGET_COL, use_holiday=True, use_weather=True)
    print("Baseline trained on features:", feature_names)

    preds = predict(model, test_df, use_holiday=True, use_weather=True)
    errors = pd.Series(
        np.abs(test_df[TARGET_COL].values - preds) / np.maximum(test_df[TARGET_COL].values, 1e-6),
        index=test_df["date"]
    )

    # --- 2. Detect + classify drift ---
    drift_dates = detect_drift_points(errors)
    print(f"Detected {len(drift_dates)} drift points")

    classified = []
    for dp in drift_dates:
        label, tau, delta = classify_point(dp, errors)

        def retrain_with_solar(d, use_solar=True):
            m, _ = train_baseline(train_df, target_col=TARGET_COL, use_solar=use_solar, use_holiday=True, use_weather=True)
            p = predict(m, test_df, use_solar=use_solar, use_holiday=True, use_weather=True)
            e = pd.Series(np.abs(test_df[TARGET_COL].values - p) / np.maximum(test_df[TARGET_COL].values, 1e-6), index=test_df["date"])
            return m, e

        structural_label, reduction = confirm_structural(dp, test_df, errors, retrain_with_solar)
        final_label = structural_label or label
        classified.append({"date": dp, "label": final_label, "tau": tau, "delta": delta, "structural_reduction": reduction})

    classified_df = pd.DataFrame(classified)
    print(classified_df)

    # --- 3. Validate against known events ---
    validation = validate_against_events(drift_dates, events)
    print(validation)

    # --- 4. Route + adapt for each drift point ---
    for _, row in classified_df.iterrows():
        adapted_model = route_and_adapt(row["label"], train_df, row["date"], target_col=TARGET_COL, use_holiday=True, use_weather=True)
        print(f"Adapted model trained for {row['date'].date()} ({row['label']})")

    # --- 5. Evaluate (ADJUST regime boundaries to your actual event dates) ---
    regimes = {
        "pre_crisis": (df["date"].min(), pd.Timestamp("2022-03-01")),
        "crisis": (pd.Timestamp("2022-03-01"), pd.Timestamp("2022-08-01")),
        "tariff_adjustment": (pd.Timestamp("2022-08-01"), pd.Timestamp("2023-06-01")),
        "solar_growth": (pd.Timestamp("2023-06-01"), df["date"].max()),
    }
    test_df = test_df.copy()
    test_df["pred"] = preds
    results = ev.regime_mape_rmse(test_df, TARGET_COL, "pred", regimes)
    print(results)
    results.to_csv(DATA_DIR / "regime_results.csv", index=False)


if __name__ == "__main__":
    main()
