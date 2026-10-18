"""
drift.py
--------
Detects drift using ADWIN, then classifies each detected point as
abrupt / gradual using transition duration (tau) and magnitude (delta),
and confirms/reclassifies structural drift via covariate ablation.
"""
import numpy as np
import pandas as pd
from river.drift import ADWIN


def detect_drift_points(errors: pd.Series):
    """errors: a pandas Series of absolute-percentage-error, indexed by date."""
    adwin = ADWIN()
    drift_dates = []
    for date, err in errors.items():
        adwin.update(float(err))
        if adwin.drift_detected:
            drift_dates.append(date)
    return drift_dates


def classify_point(drift_date, errors: pd.Series, window_days=30, tau_threshold_days=14, delta_threshold=3.0):
    """Classify a single detected drift point as 'abrupt' or 'gradual'
    using error magnitude before/after. tau (transition duration) is a
    placeholder here -- refine using DDM's warning/drift gap for a more
    precise measurement; this version uses a fixed window as a first pass."""
    before = errors[errors.index < drift_date].tail(window_days)
    after = errors[errors.index >= drift_date].head(window_days)

    if len(before) < 5 or len(after) < 5:
        return "unclassified", None, None

    delta = (after.mean() - before.mean()) / (before.std() + 1e-6)
    tau_days = tau_threshold_days  # TODO: replace with real DDM warning-to-drift gap

    label = "abrupt" if (tau_days <= tau_threshold_days and delta >= delta_threshold) else "gradual"
    return label, tau_days, delta


def confirm_structural(drift_date, df, baseline_errors, retrain_fn, window_days=30):
    """Retrain with the solar covariate included; if local error shrinks
    substantially, reclassify as structural."""
    before_err = baseline_errors[
        (baseline_errors.index >= drift_date - pd.Timedelta(days=window_days)) &
        (baseline_errors.index < drift_date + pd.Timedelta(days=window_days))
    ].mean()

    augmented_model, augmented_errors = retrain_fn(df, use_solar=True)
    after_err = augmented_errors[
        (augmented_errors.index >= drift_date - pd.Timedelta(days=window_days)) &
        (augmented_errors.index < drift_date + pd.Timedelta(days=window_days))
    ].mean()

    reduction = (before_err - after_err) / (before_err + 1e-6)
    return ("structural" if reduction >= 0.2 else None), reduction


def validate_against_events(drift_dates, events_df, tolerance_days=14):
    """events_df needs columns: date, event_type, description."""
    results = []
    for dp in drift_dates:
        window = pd.Timedelta(days=tolerance_days)
        matches = events_df[(events_df["date"] - dp).abs() <= window]
        results.append({
            "detected_date": dp,
            "matched_events": matches["description"].tolist(),
            "matched": len(matches) > 0
        })
    return pd.DataFrame(results)
