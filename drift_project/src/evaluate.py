"""
evaluate.py
-----------
Regime-by-regime accuracy and adaptation-lag measurement.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_percentage_error, root_mean_squared_error


def regime_mape_rmse(df, y_true_col, y_pred_col, regimes: dict):
    """regimes: {"pre_crisis": (start_date, end_date), ...}"""
    rows = []
    for name, (start, end) in regimes.items():
        mask = (df["date"] >= start) & (df["date"] < end)
        if mask.sum() == 0:
            continue
        y_true = df.loc[mask, y_true_col]
        y_pred = df.loc[mask, y_pred_col]
        rows.append({
            "regime": name,
            "mape": mean_absolute_percentage_error(y_true, y_pred),
            "rmse": root_mean_squared_error(y_true, y_pred),
            "n_days": mask.sum(),
        })
    return pd.DataFrame(rows)


def adaptation_lag(df, event_date, error_col, baseline_error_level, max_days=60):
    """Days after event_date until error first drops back to baseline_error_level."""
    after = df[df["date"] >= event_date].sort_values("date")
    for i, row in after.iterrows():
        if row[error_col] <= baseline_error_level:
            return (row["date"] - event_date).days
        if (row["date"] - event_date).days > max_days:
            break
    return None  # did not recover within max_days
