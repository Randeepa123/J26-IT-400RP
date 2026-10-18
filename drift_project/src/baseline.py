"""
baseline.py
-----------
Static baseline forecasting model, trained once on pre-2022 data.
Ridge regression on trend + seasonality + holiday + weather + solar features --
fast to iterate on; swap for LSTM later without touching any other module.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

FEATURE_COLS_BASE = ["trend", "sin_annual", "cos_annual", "sin_weekly", "cos_weekly"]


def make_features(df, date_col="date", use_solar=False, use_holiday=False, use_weather=False):
    dates = pd.to_datetime(df[date_col])
    t = (dates - dates.min()).dt.days.values.astype(float)

    feats = {
        "trend": t,
        "sin_annual": np.sin(2 * np.pi * t / 365.25),
        "cos_annual": np.cos(2 * np.pi * t / 365.25),
        "sin_weekly": np.sin(2 * np.pi * t / 7),
        "cos_weekly": np.cos(2 * np.pi * t / 7),
    }
    if use_solar and "solar_generation_mw" in df.columns:
        feats["solar"] = df["solar_generation_mw"].fillna(0).values
    if use_holiday and "is_holiday" in df.columns:
        feats["is_holiday"] = df["is_holiday"].fillna(0).values
    if use_weather:
        for col in ["temperature_2m_mean", "precipitation_sum"]:
            if col in df.columns:
                feats[col] = df[col].fillna(df[col].mean()).values

    X = np.column_stack(list(feats.values()))
    return X, list(feats.keys())


def train_baseline(df, target_col="total_generation_mw", **feature_flags):
    X, feature_names = make_features(df, **feature_flags)
    y = df[target_col].values
    model = Ridge(alpha=1.0).fit(X, y)
    return model, feature_names


def predict(model, df, **feature_flags):
    X, _ = make_features(df, **feature_flags)
    return model.predict(X)
