import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

REF_DATE = pd.Timestamp("2016-01-01")


def make_features(
    df,
    date_col="date",
    use_solar=False,
    use_holiday=False,
    use_weather=False,
    include_trend_annual=True,
    ref_date=REF_DATE,
):
    dates = pd.to_datetime(df[date_col])
    t = (dates - ref_date).dt.total_seconds().values / 86400.0

    feats = {}
    if include_trend_annual:
        feats["trend"] = t / 365.25  # Scaled in years so Ridge alpha=1.0 regularizes it properly
        feats["sin_annual"] = np.sin(2 * np.pi * t / 365.25)
        feats["cos_annual"] = np.cos(2 * np.pi * t / 365.25)

    feats["sin_weekly"] = np.sin(2 * np.pi * t / 7.0)
    feats["cos_weekly"] = np.cos(2 * np.pi * t / 7.0)
    feats["sin_daily"] = np.sin(2 * np.pi * t)
    feats["cos_daily"] = np.cos(2 * np.pi * t)
    feats["sin_half_daily"] = np.sin(4 * np.pi * t)
    feats["cos_half_daily"] = np.cos(4 * np.pi * t)

    if use_solar and "solar_generation_mw" in df.columns:
        feats["solar"] = df["solar_generation_mw"].fillna(0.0).values
    if use_holiday and "is_holiday" in df.columns:
        feats["is_holiday"] = df["is_holiday"].fillna(0).values
    if use_weather:
        temp_col = "temperature_2m" if "temperature_2m" in df.columns else "temperature_2m_mean"
        precip_col = "precipitation" if "precipitation" in df.columns else "precipitation_sum"

        for col in [temp_col, precip_col, "shortwave_radiation"]:
            if col in df.columns:
                col_mean = df[col].mean()
                feats[col] = df[col].fillna(0.0 if pd.isna(col_mean) else col_mean).values

    X = np.column_stack(list(feats.values()))
    return X, list(feats.keys())


def train_baseline(df, target_col="total_generation_mw", **feature_flags):
    X, feature_names = make_features(df, **feature_flags)
    y = df[target_col].values
    model = Ridge(alpha=10.0).fit(X, y)
    return model, feature_names


def predict(model, df, **feature_flags):
    X, _ = make_features(df, **feature_flags)
    return model.predict(X)