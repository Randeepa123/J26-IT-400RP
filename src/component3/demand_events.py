"""
demand_events.py
================
Festival / holiday demand-event calendar and demand-weight utilities for Component 3 (v2).

Purpose
-------
* Add the high-consumption periods the existing synthetic demand lacked (Vesak illuminations,
  Poson, Christmas / year-end, Deepavali). The earlier config treated Christmas as a SUPPRESSION
  (x0.92); v2 replaces that with an uplift. Avurudu (Apr 13-16) stays suppressed (commercial closure).
* Convert demand (historical or forecast) into a daily DEMAND WEIGHT  w_t = demand_t / normal level,
  clipped to the configured range, used to value energy in the LP objective, DQN reward and metrics.

Disclaimer: uplift magnitudes are ASSUMPTIONS (no meter data). Vesak / Poson / Deepavali dates are
approximate lunar-calendar dates and should be checked against the official Sri Lanka holiday calendar.
"""

import os
import numpy as np
import pandas as pd

import paths

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))

# Approximate poya / festival dates (ASSUMPTION - verify against the official calendar)
VESAK_DATES = {2021: "2021-05-26", 2022: "2022-05-15", 2023: "2023-05-05", 2024: "2024-05-23",
               2025: "2025-05-12", 2026: "2026-05-31", 2027: "2027-05-20", 2028: "2028-05-08",
               2029: "2029-05-27", 2030: "2030-05-16", 2031: "2031-05-05", 2032: "2032-05-23"}
POSON_DATES = {2021: "2021-06-24", 2022: "2022-06-14", 2023: "2023-06-03", 2024: "2024-06-21",
               2025: "2025-06-10", 2026: "2026-06-29", 2027: "2027-06-18", 2028: "2028-06-06",
               2029: "2029-06-25", 2030: "2030-06-14", 2031: "2031-06-03", 2032: "2032-06-21"}
DEEPAVALI_DATES = {2021: "2021-11-04", 2022: "2022-10-24", 2023: "2023-11-12", 2024: "2024-10-31",
                   2025: "2025-10-20", 2026: "2026-11-08", 2027: "2027-10-29", 2028: "2028-10-17",
                   2029: "2029-11-05", 2030: "2030-10-26", 2031: "2031-11-14", 2032: "2032-11-02"}

# multiplier by day offset from the festival date
VESAK_PROFILE = {-3: 1.04, -2: 1.06, -1: 1.09, 0: 1.15, 1: 1.12, 2: 1.05}
POSON_PROFILE = {-1: 1.04, 0: 1.08, 1: 1.04}
DEEPAVALI_PROFILE = {-1: 1.04, 0: 1.08}
CHRISTMAS_PROFILE = {(12, 23): 1.03, (12, 24): 1.10, (12, 25): 1.12, (12, 26): 1.06,
                     (12, 27): 1.04, (12, 28): 1.04, (12, 29): 1.04, (12, 30): 1.04,
                     (12, 31): 1.10, (1, 1): 1.06}
AVURUDU_DAYS = {13, 14, 15, 16}
AVURUDU_FACTOR = 0.82
OLD_YEAREND_SUPPRESSED = {25, 26, 31}   # days that the ORIGINAL generator multiplied by 0.92
OLD_YEAREND_FACTOR = 0.92

DOW_MULT = {"Monday": 1.025, "Tuesday": 1.030, "Wednesday": 1.035, "Thursday": 1.030,
            "Friday": 1.020, "Saturday": 0.965, "Sunday": 0.895}
MONTH_MULT = {1: 0.985, 2: 0.990, 3: 1.040, 4: 0.980, 5: 1.010, 6: 1.000,
              7: 1.000, 8: 1.010, 9: 1.000, 10: 1.010, 11: 0.990, 12: 1.005}


def _festival_offset(ts, table):
    d = table.get(ts.year)
    if d is None:
        return None
    return (ts - pd.Timestamp(d)).days


def event_multiplier(ts, vesak_override=None):
    """Return (multiplier, label) for a date. `vesak_override`: Timestamp to move Vesak (scenario bank)."""
    ts = pd.Timestamp(ts)
    mult, label = 1.0, ""
    if vesak_override is not None:
        off = (ts - pd.Timestamp(vesak_override)).days
    else:
        off = _festival_offset(ts, VESAK_DATES)
    if off is not None and off in VESAK_PROFILE:
        mult *= VESAK_PROFILE[off]; label = "vesak"
    off = _festival_offset(ts, POSON_DATES)
    if off is not None and off in POSON_PROFILE:
        mult *= POSON_PROFILE[off]; label = label or "poson"
    off = _festival_offset(ts, DEEPAVALI_DATES)
    if off is not None and off in DEEPAVALI_PROFILE:
        mult *= DEEPAVALI_PROFILE[off]; label = label or "deepavali"
    key = (ts.month, ts.day)
    if key in CHRISTMAS_PROFILE:
        mult *= CHRISTMAS_PROFILE[key]; label = label or "christmas_yearend"
    if ts.month == 4 and ts.day in AVURUDU_DAYS:
        mult *= AVURUDU_FACTOR; label = label or "avurudu"
    return mult, label


def event_series(dates, vesak_override_by_year=None):
    """Event multiplier + label for each date."""
    vesak_override_by_year = vesak_override_by_year or {}
    out_m, out_l = [], []
    for d in pd.to_datetime(dates):
        m, l = event_multiplier(d, vesak_override_by_year.get(d.year))
        out_m.append(m); out_l.append(l)
    return np.array(out_m), np.array(out_l)


def build_event_aware_demand(df_demand):
    """
    Non-destructively derive the v2 demand series from the existing synthetic series:
    remove the old Christmas/year-end suppression, then apply the event multipliers
    (Vesak, Poson, Deepavali, Christmas/year-end uplift). Avurudu is already in the base series.
    """
    df = df_demand.copy()
    df["date"] = pd.to_datetime(df["date"])
    base = df["daily_energy_consumption_mwh"].astype(float).values.copy()
    old_mask = ((df["date"].dt.month == 12) & (df["date"].dt.day.isin(OLD_YEAREND_SUPPRESSED))).values
    base[old_mask] = base[old_mask] / OLD_YEAREND_FACTOR
    mult, label = event_series(df["date"])
    # Avurudu already applied in the base series -> do not apply twice
    avu = (df["date"].dt.month == 4) & (df["date"].dt.day.isin(AVURUDU_DAYS))
    mult = np.where(avu.values, 1.0, mult)
    df["daily_energy_consumption_mwh_v1"] = df["daily_energy_consumption_mwh"]
    df["daily_energy_consumption_mwh"] = np.round(base * mult, 3)
    df["event_label"] = label
    df["data_status"] = "SYNTHETIC_SCENARIO_EVENT_AWARE_V2"
    return df


def demand_weights_from_series(demand, window=29, clip=(0.8, 1.5)):
    """w_t = demand_t / centred rolling mean (removes the long-run trend, keeps weekly/festival shape)."""
    s = pd.Series(np.asarray(demand, dtype=float))
    norm = s.rolling(window, center=True, min_periods=7).mean()
    return np.clip((s / norm).values, clip[0], clip[1])


def demand_weights_from_forecast(forecast_mwh, history_mwh, clip=(0.8, 1.5)):
    """Forecast weights relative to the mean of the most recent 28 days of history."""
    ref = float(np.mean(np.asarray(history_mwh, dtype=float)[-28:]))
    return np.clip(np.asarray(forecast_mwh, dtype=float) / ref, clip[0], clip[1])


def calendar_demand_weights(dates, rng=None, noise_sigma=0.02, clip=(0.8, 1.5), vesak_override_by_year=None):
    """
    Pure-calendar demand weights for synthetic scenario years (dow x month x events, mean ~1, AR(1) noise).
    Used by the scenario bank where no demand series exists.
    """
    dates = pd.to_datetime(dates)
    mult, _ = event_series(dates, vesak_override_by_year)
    idx = np.array([DOW_MULT[d.day_name()] * MONTH_MULT[d.month] for d in dates]) * mult
    idx = idx / np.mean(idx)
    if rng is not None and noise_sigma > 0:
        phi, e = 0.65, 0.0
        noise = np.zeros(len(idx))
        for i in range(len(idx)):
            e = phi * e + rng.normal(0.0, noise_sigma * np.sqrt(1 - phi ** 2))
            noise[i] = e
        idx = idx * (1.0 + noise)
    return np.clip(idx, clip[0], clip[1])


def main():
    """Write the event-aware v2 demand series and weights next to the original (originals untouched)."""
    src = paths.DEMAND_5Y
    df = build_event_aware_demand(pd.read_csv(src))
    df["demand_weight"] = np.round(demand_weights_from_series(df["daily_energy_consumption_mwh"]), 4)
    out = paths.DEMAND_5Y_V2
    df.to_csv(out, index=False)
    print(f"Wrote {out} ({len(df)} rows)")
    for lab in ["vesak", "poson", "deepavali", "christmas_yearend", "avurudu"]:
        sub = df[df["event_label"] == lab]
        if len(sub):
            print(f"  {lab:18s} n={len(sub):3d} mean weight={sub['demand_weight'].mean():.3f}")
    print(f"  all days           mean weight={df['demand_weight'].mean():.3f} "
          f"range=[{df['demand_weight'].min():.3f},{df['demand_weight'].max():.3f}]")


if __name__ == "__main__":
    main()
