"""
Kukule Ganga inflow forecast API.
Loads the exported LightGBM bundle and reproduces the notebook's
seasonal-analogue prediction (same feature engineering, same aggregation).

Run:  uvicorn main:app --reload --port 8000
"""
import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BUNDLE_PATH = Path(__file__).parent / "kukule_ganga_inflow_seasonal_models.json"

# ---------------------------------------------------------------- load bundle
with open(BUNDLE_PATH, "r", encoding="utf-8") as f:
    BUNDLE = json.load(f)

META = BUNDLE["metadata"]
RAW_COLS = META["raw_input_columns"]
FEATURE_COLS = META["engineered_feature_columns"]
HORIZONS = META["forecast_horizons_days"]
HISTORY_DAYS = META["history_days_required"]            # 75
Q_DESIGN = META["turbine_design_flow_m3s"]               # 47.5
Q_ENV = META["environmental_release_m3s"]                # 3.0


def _booster(entry):
    return lgb.Booster(model_str=entry["model_string"])


POINT = {int(h): _booster(m) for h, m in BUNDLE["point_forecast_models"].items()}
QUANT = {
    int(h): {q: _booster(m) for q, m in qs.items()}
    for h, qs in BUNDLE["quantile_forecast_models"].items()
}
EVENT = {
    int(h): {k: _booster(m) for k, m in ev.items()}
    for h, ev in BUNDLE["event_classification_models"].items()
}

CLEAN = pd.DataFrame(BUNDLE["historical_analogue_archive"]["records"])
CLEAN["date"] = pd.to_datetime(CLEAN["date"]).dt.normalize()
CLEAN = CLEAN.sort_values("date").reset_index(drop=True)
DATA_START, DATA_END = CLEAN["date"].min(), CLEAN["date"].max()
HISTORY_BY_DATE = CLEAN.set_index("date")[RAW_COLS]
MIN_ORIGIN_DATE = CLEAN["date"].iloc[HISTORY_DAYS - 1]


# ------------------------------------------- feature engineering (from notebook)
def usable_from_inflow(q):
    return (q - Q_ENV).clip(lower=0).clip(upper=Q_DESIGN)


def build_features(df):
    d = df.sort_values("date").reset_index(drop=True).copy()
    q, r = d["reservoir_inflow"], d["rainfall"]
    d["usable_inflow"] = usable_from_inflow(q)

    doy = d["date"].dt.dayofyear
    d["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    d["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    d["month"] = d["date"].dt.month
    d["season_wet"] = d["month"].between(5, 11).astype(int)

    d["enso_cat"] = np.select([d["enso_index"] >= 0.5, d["enso_index"] <= -0.5], [1, -1], 0)
    d["iod_cat"] = np.select([d["iod_index"] >= 0.4, d["iod_index"] <= -0.4], [1, -1], 0)

    for l in (1, 2, 3):
        d[f"rain_lag{l}"] = r.shift(l)
    d["rain_3d_avg"] = r.rolling(3).mean()
    for w in (7, 14, 30, 60):
        d[f"rain_{w}d_sum"] = r.rolling(w).sum()
    d["rain_days_14d"] = (r > 1).astype(int).rolling(14).sum()

    for l in (1, 2, 3, 5, 7, 14):
        d[f"inflow_lag{l}"] = q.shift(l)
    for w in (3, 7, 14, 30, 60):
        d[f"inflow_mean_{w}d"] = q.rolling(w).mean()
    d["inflow_max_7d"] = q.rolling(7).max()
    d["inflow_min_7d"] = q.rolling(7).min()
    d["inflow_std_7d"] = q.rolling(7).std()
    d["inflow_chg_1d"] = q.diff(1)
    d["inflow_chg_3d"] = q.diff(3)
    d["inflow_ratio_30d"] = q / d["inflow_mean_30d"]

    d["level_chg_1d"] = d["reservoir_water_level"].diff()
    d["storage_chg_1d"] = d["reservoir_storage"].diff()
    d["outflow_minus_inflow"] = d["reservoir_outflow"] - q
    d["discharge_to_inflow"] = d["river_discharge"] / q
    return d


# --------------------------------------------------------- history construction
def build_histories(origin, manual):
    """Actual history if available, otherwise one seasonal analogue per past year."""
    n_prev = HISTORY_DAYS - 1

    def with_manual(prev):
        prev = prev[["date"] + RAW_COLS].copy()
        row = pd.DataFrame([{"date": origin, **manual}])
        h = pd.concat([prev, row], ignore_index=True).sort_values("date").reset_index(drop=True)
        if len(h) != HISTORY_DAYS or not h["date"].diff().dropna().eq(pd.Timedelta(days=1)).all():
            raise ValueError("Constructed history is not a consecutive daily series.")
        return h

    if origin <= DATA_END + pd.Timedelta(days=1):
        prev = CLEAN.loc[CLEAN["date"] < origin, ["date"] + RAW_COLS].tail(n_prev)
        if len(prev) != n_prev:
            raise ValueError(f"Not enough history before {origin.date()}.")
        return [with_manual(prev)], False

    target_dates = pd.date_range(end=origin - pd.Timedelta(days=1), periods=n_prev, freq="D")
    out = []
    for year in range(DATA_START.year, DATA_END.year + 1):
        try:
            end = pd.Timestamp(year=year, month=origin.month, day=origin.day)
        except ValueError:
            continue
        if end > DATA_END:
            continue
        src_dates = pd.date_range(end=end - pd.Timedelta(days=1), periods=n_prev, freq="D")
        if src_dates[0] < DATA_START:
            continue
        win = HISTORY_BY_DATE.reindex(src_dates)
        if win.isna().any().any():
            continue
        win = win.reset_index(drop=True)
        win.insert(0, "date", target_dates)
        out.append(with_manual(win))
    if not out:
        raise ValueError("No suitable historical seasonal analogues were found for this date.")
    return out, True


# ------------------------------------------------------------------- schema/API
class PredictRequest(BaseModel):
    input_date: str
    days_ahead: int = Field(ge=1, le=7)
    reservoir_inflow: float = Field(ge=5.15, le=585.07)
    reservoir_water_level: float = Field(ge=190, le=210)
    reservoir_storage: float = Field(ge=1.0, le=2.0)
    reservoir_outflow: float = Field(ge=4.0, le=600)
    river_discharge: float = Field(ge=5.0, le=800.0)
    rainfall: float = Field(ge=0, le=500)
    temperature: float = Field(ge=10, le=40)
    humidity: float = Field(ge=50, le=98)
    evaporation: float = Field(ge=1.5, le=7.0)
    enso_index: float = Field(ge=-1.70, le=2.60)
    iod_index: float = Field(ge=-0.96, le=1.27)


app = FastAPI(title="Kukule Ganga Inflow Forecast API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # add your prod origin
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "data_range": [str(DATA_START.date()), str(DATA_END.date())]}


@app.post("/api/predict")
def predict(req: PredictRequest):
    try:
        origin = pd.Timestamp(req.input_date).normalize()
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid input_date.")
    if origin < MIN_ORIGIN_DATE:
        raise HTTPException(status_code=422, detail=f"input_date must be on or after {MIN_ORIGIN_DATE.date()}.")

    h = req.days_ahead
    manual = {c: float(getattr(req, c)) for c in RAW_COLS}

    try:
        histories, future_gap = build_histories(origin, manual)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    points, spills, lows = [], [], []
    for hist in histories:
        x = build_features(hist).iloc[[-1]][FEATURE_COLS]
        if not np.isfinite(x.to_numpy(dtype=float)).all():
            continue
        points.append(float(np.clip(POINT[h].predict(x)[0], 0, Q_DESIGN)))
        spills.append(float(EVENT[h]["spill"].predict(x)[0]))
        lows.append(float(EVENT[h]["low_flow"].predict(x)[0]))

    if not points:
        raise HTTPException(status_code=422, detail="No scenario produced a valid prediction.")

    return {
        "input_date": str(origin.date()),
        "forecast_date": str((origin + pd.Timedelta(days=h)).date()),
        "days_ahead": h,
        "history_method": (
            "Historical seasonal analogues" if future_gap else "Actual recent historical observations"
        ),
        "scenarios_used": len(points),
        "predicted_usable_inflow_m3s": round(float(np.median(points)), 3),
        "spill_probability_pct": round(float(np.mean(spills)) * 100, 2),
        "low_flow_probability_pct": round(float(np.mean(lows)) * 100, 2),
    }
