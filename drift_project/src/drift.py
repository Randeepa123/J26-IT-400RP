import numpy as np
import pandas as pd
from river.drift import ADWIN


def detect_drift_points(
    errors: pd.Series,
    warmup_errors: pd.Series = None,
    delta=0.05,
    min_cooldown_days=60,
):
    """
    Warms up ADWIN on pre-2022 baseline errors so the March 2022 crisis shift
    is detected immediately instead of waiting for a cold start.
    """
    if warmup_errors is not None and len(warmup_errors) > 0:
        full_err = pd.concat([warmup_errors, errors])
        test_start = errors.index.min()
    else:
        full_err = errors
        test_start = errors.index.min()

    daily_mean = full_err.clip(upper=0.50).resample("D").mean().dropna()
    scaled_stream = (daily_mean / 0.35).clip(0.0, 1.0).rolling(5, min_periods=1).mean()

    adwin = ADWIN(delta=delta, clock=1, min_window_length=10, grace_period=15)
    drift_dates = []
    last_drift = None

    for date, val in scaled_stream.items():
        adwin.update(float(val))
        if adwin.drift_detected and date >= test_start:
            if last_drift is None or (date - last_drift).days >= min_cooldown_days:
                drift_dates.append(date)
                last_drift = date
                adwin = ADWIN(delta=delta, clock=1, min_window_length=10, grace_period=15)

    return drift_dates


def classify_point(drift_date, errors: pd.Series, window_days=30, tau_threshold_days=14, delta_threshold=0.65):
    daily_errors = errors.clip(upper=0.50).resample("D").mean().dropna()
    w = pd.DateOffset(days=window_days)

    before = daily_errors[(daily_errors.index >= drift_date - w) & (daily_errors.index < drift_date)]
    after = daily_errors[(daily_errors.index >= drift_date) & (daily_errors.index < drift_date + w)]

    if len(before) < 5 or len(after) < 5:
        return "unclassified", None, None

    delta = abs(after.mean() - before.mean()) / (before.std() + 1e-4)

    rolling_after = after.rolling(3, min_periods=1).mean()
    target_level = before.mean() + 0.8 * (after.mean() - before.mean())
    if after.mean() >= before.mean():
        crossed = rolling_after[rolling_after >= target_level]
    else:
        crossed = rolling_after[rolling_after <= target_level]

    tau_days = int((crossed.index[0] - drift_date).days) if len(crossed) > 0 else window_days

    label = "abrupt" if (tau_days <= tau_threshold_days and delta >= delta_threshold) else "gradual"
    return label, tau_days, round(float(delta), 3)


def confirm_structural(drift_date, df, baseline_errors, retrain_fn, window_days=30):
    e_no, e_sol = retrain_fn(drift_date)
    if len(e_no) == 0:
        return None, 0.0

    before_err = e_no.mean()
    after_err = e_sol.mean()
    reduction = (before_err - after_err) / (before_err + 1e-6)
    return ("structural" if reduction >= 0.015 else None), round(float(reduction), 4)


def validate_against_events(drift_dates, events_df, tolerance_days=45):
    if not drift_dates:
        return pd.DataFrame(columns=["detected_date", "matched_events", "matched"])
    results = []
    for dp in drift_dates:
        matches = events_df[(events_df["date"] - dp).abs().dt.days <= tolerance_days]
        results.append({
            "detected_date": dp,
            "matched_events": matches["description"].tolist(),
            "matched": len(matches) > 0
        })
    return pd.DataFrame(results)
