"""
adapt.py
--------
Three cause-matched adaptation strategies, plus the router that picks
between them based on the classified drift type.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from baseline import make_features


def hard_reset(df, drift_date, target_col="total_generation_mw", window_days=60, **feature_flags):
    recent = df[df["date"] >= drift_date - pd.Timedelta(days=window_days)]
    X, _ = make_features(recent, **feature_flags)
    y = recent[target_col].values
    return Ridge(alpha=1.0).fit(X, y)


def decayed_reweight(df, drift_date, target_col="total_generation_mw", half_life_days=30, **feature_flags):
    X, _ = make_features(df, **feature_flags)
    y = df[target_col].values
    age_days = (df["date"].max() - df["date"]).dt.days.values
    weights = 0.5 ** (age_days / half_life_days)
    return Ridge(alpha=1.0).fit(X, y, sample_weight=weights)


def feature_augmented(df, drift_date, target_col="total_generation_mw", **feature_flags):
    feature_flags = {**feature_flags, "use_solar": True}
    X, _ = make_features(df, **feature_flags)
    y = df[target_col].values
    return Ridge(alpha=1.0).fit(X, y)


def route_and_adapt(drift_type, df, drift_date, **kwargs):
    if drift_type == "abrupt":
        return hard_reset(df, drift_date, **kwargs)
    elif drift_type in ("gradual", "incremental"):
        return decayed_reweight(df, drift_date, **kwargs)
    elif drift_type == "structural":
        return feature_augmented(df, drift_date, **kwargs)
    else:
        raise ValueError(f"Unknown drift type: {drift_type}")
