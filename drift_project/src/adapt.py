import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
try:
    from .baseline import make_features
except ImportError:  # Existing direct-script entry point
    from baseline import make_features


def hard_reset(df, drift_date, target_col="total_generation_mw", window_days=60, **feature_flags):
    """Abrupt drift: Fits on a recent 60-day window without multi-year linear trend."""
    w_start = drift_date - pd.DateOffset(days=45)
    w_end = drift_date + pd.DateOffset(days=15)
    recent = df[(df["date"] >= w_start) & (df["date"] <= w_end)]
    if len(recent) < 96:
        recent = df[df["date"] <= drift_date].tail(window_days * 96)

    flags = {**feature_flags, "include_trend_annual": False}
    X, _ = make_features(recent, **flags)
    y = recent[target_col].values
    model = Ridge(alpha=10.0).fit(X, y)
    model._adapt_flags = flags
    return model


def decayed_reweight(df, drift_date, target_col="total_generation_mw", half_life_days=45, **feature_flags):
    """
    Gradual drift: Uses trailing 180 days with exponential decay (half-life 45 days)
    and disables the unregularized multi-year linear trend so predictions remain stable.
    """
    w_start = drift_date - pd.DateOffset(days=180)
    w_end = drift_date + pd.DateOffset(days=14)
    hist = df[(df["date"] >= w_start) & (df["date"] <= w_end)]

    flags = {**feature_flags, "include_trend_annual": False}
    X, _ = make_features(hist, **flags)
    y = hist[target_col].values
    age_days = (hist["date"].max() - hist["date"]).dt.total_seconds().values / 86400.0
    weights = 0.5 ** (age_days / half_life_days)
    model = Ridge(alpha=20.0).fit(X, y, sample_weight=weights)
    model._adapt_flags = flags
    return model


def feature_augmented(df, drift_date, target_col="total_generation_mw", **feature_flags):
    """
    Structural drift: Augments features with solar_generation_mw on the trailing 180 days.
    """
    w_start = drift_date - pd.DateOffset(days=180)
    w_end = drift_date + pd.DateOffset(days=14)
    hist = df[(df["date"] >= w_start) & (df["date"] <= w_end)]

    flags = {**feature_flags, "use_solar": True, "include_trend_annual": False}
    X, _ = make_features(hist, **flags)
    y = hist[target_col].values
    age_days = (hist["date"].max() - hist["date"]).dt.total_seconds().values / 86400.0
    weights = 0.5 ** (age_days / 60.0)
    model = Ridge(alpha=20.0).fit(X, y, sample_weight=weights)
    model._adapt_flags = flags
    return model


def route_and_adapt(drift_type, df, drift_date, **kwargs):
    if drift_type == "abrupt":
        return hard_reset(df, drift_date, **kwargs)
    elif drift_type in ("gradual", "incremental"):
        return decayed_reweight(df, drift_date, **kwargs)
    elif drift_type == "structural":
        return feature_augmented(df, drift_date, **kwargs)
    else:
        raise ValueError(f"Unknown drift type: {drift_type}")
