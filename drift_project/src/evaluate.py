import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_percentage_error, root_mean_squared_error


def regime_mape_rmse(df, y_true_col, y_pred_col, regimes: dict):
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
            "n_intervals_15m": int(mask.sum()),
            "n_days_approx": round(mask.sum() / 96.0, 1),
        })
    return pd.DataFrame(rows)


def adaptation_lag(df, event_date, error_col, baseline_error_level, rolling_days=7, max_days=60):
    """
    Days after event_date until the 7-day rolling mean error drops back to
    baseline_error_level (prevents a single lucky low-error day from counting as recovery).
    """
    daily_err = (
        df.set_index("date")[error_col]
        .resample("D")
        .mean()
        .dropna()
        .rolling(rolling_days, min_periods=3)
        .mean()
        .reset_index()
    )
    after = daily_err[daily_err["date"] >= event_date].sort_values("date")
    for _, row in after.iterrows():
        days_elapsed = (row["date"] - event_date).days
        if days_elapsed >= 1 and row[error_col] <= baseline_error_level:
            return int(days_elapsed)
        if days_elapsed > max_days:
            break
    return None  # Did not recover within max_days