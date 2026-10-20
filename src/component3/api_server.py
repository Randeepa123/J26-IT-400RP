"""
api_server.py - local JSON API that feeds the Grafana dashboards (Infinity data source).

    python src/component3/api_server.py            # serves http://127.0.0.1:8765 (local machine only)

Endpoints (all GET, flat JSON records):
  /health, /meta
  /plan, /plan/summary, /plan/methods      what-if or live planning with the SAME engine as run_component3 (query inputs below)
  /live/status, /live/log                   daily-runner heartbeat and decision log (outputs/live/)
  /table/{name}                             precomputed tables (scoreboard, heatmap, multiseed, ...), optional column filters
  /scenario/series                          year-long series for one scenario / metric / several methods
Plan inputs (validated and clipped):
  storage_pct (0-100, default 60)  inflow_scale (0.2-2.5)  p90_scale (0.5-3)  demand_scale (0.5-2)  units (0-2)
  method (hybrid|dqn|rolling_lp|reference)  source (whatif|live)  align (today|forecast)
All values describe the MODELLED study dataset; outputs are decision support, not control signals.
"""
import os
import json
import time
import threading
from datetime import date, datetime
from functools import lru_cache

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

import paths
import run_component3 as rc3
import daily_runner as dr
from hydro_core import HydroParams, SECONDS_PER_DAY

P = HydroParams.from_config()
LOCK = threading.RLock()                                  # policies hold state -> one plan at a time; also lets simultaneous identical requests share one result
STATE = {}
METHOD_NAMES = {"hybrid": "Hybrid LP-DQN", "dqn": "DQN", "rolling_lp": "Rolling LP", "reference": "Reference rule (causal)",
                "reference_gauge": "Reference rule (reads gauge)", "omniscient_lp": "Perfect-foresight LP (bound)"}
TABLES = {"scoreboard", "heatmap", "multiseed", "paired_tests", "seed_points", "adaptation", "adaptation_events",
          "training_curves", "training_summary", "constraint_audit", "scenario_kpis"}

app = FastAPI(title="Kukule Ganga - Component 3 dashboard API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DASHBOARD_DIR = paths.SRC_DIR / "dashboard"

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    index_file = DASHBOARD_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>Live Dashboard not found in " + str(DASHBOARD_DIR) + "</h2>", status_code=404)

@app.get("/dashboard.css")
def serve_css():
    f = DASHBOARD_DIR / "dashboard.css"
    if f.exists():
        return FileResponse(str(f), media_type="text/css")
    raise HTTPException(404, "CSS not found")

@app.get("/dashboard.js")
def serve_js():
    f = DASHBOARD_DIR / "dashboard.js"
    if f.exists():
        return FileResponse(str(f), media_type="application/javascript")
    raise HTTPException(404, "JS not found")


# ------------------------------------------------------------------------------------------------ startup / helpers
def _engine():
    if "pols" not in STATE:
        hy, dq = paths.MODELS_DIR / "hybrid_selected.zip", paths.MODELS_DIR / "dqn_selected.zip"
        STATE["pols"] = rc3.build_policies(str(dq) if dq.exists() else None, str(hy) if hy.exists() else None)
        STATE["inp"] = rc3.load_inputs(str(paths.INFLOW_FORECAST_15D), str(paths.DEMAND_FORECAST_15D), str(paths.DEMAND_5Y_V2))
    return STATE["pols"], STATE["inp"]


def records(df):
    df = df.replace({np.nan: None})
    return json.loads(df.to_json(orient="records"))


_table_cache = {}


def table(name):
    f = paths.DASHBOARD_CACHE_DIR / f"{name}.csv"
    if not f.exists():
        raise HTTPException(404, f"table '{name}' not built - run build_dashboard_data.py")
    key = (name, f.stat().st_mtime)
    if key not in _table_cache:
        _table_cache.clear() if len(_table_cache) > 40 else None
        _table_cache[key] = pd.read_csv(f)
    return _table_cache[key]


def clip(x, lo, hi, default):
    try:
        return float(min(max(float(x), lo), hi))
    except (TypeError, ValueError):
        return default


def norm_inputs(storage_pct, inflow_scale, p90_scale, demand_scale, units, method, source, align):
    return (round(clip(storage_pct, 0, 100, 60.0), 2), round(clip(inflow_scale, 0.2, 2.5, 1.0), 3),
            round(clip(p90_scale, 0.5, 3.0, 1.0), 3), round(clip(demand_scale, 0.5, 2.0, 1.0), 3),
            int(clip(units, 0, 2, 2)), method if method in ("hybrid", "dqn", "rolling_lp", "reference") else "hybrid",
            source if source in ("whatif", "live") else "whatif", align if align in ("today", "forecast") else "today")


def _severity(alerts):
    sev = 0
    for a in alerts:
        if a == "No alerts.":
            continue
        sev = max(sev, 2 if ("SHORT" in a or "below the operating reserve" in a) else 1)
    return sev


@lru_cache(maxsize=64)
def _compute(key, live_sig):
    storage_pct, inflow_scale, p90_scale, demand_scale, units, method, source, align = key
    pols, inp0 = _engine()
    status, message = "OK", ""
    if source == "live":
        inbox = str(paths.LIVE_INPUT_DIR)
        errors, warns, first, sdate = dr.validate_inputs(inbox)
        if errors:
            return {"status": "REJECTED", "message": "; ".join(errors), "key": key}
        inp = rc3.load_inputs(os.path.join(inbox, dr.INBOX_FILES["inflow"]), os.path.join(inbox, dr.INBOX_FILES["demand"]),
                              str(paths.DEMAND_5Y_V2))
        st, units_list = rc3._read_state(P, os.path.join(inbox, dr.INBOX_FILES["state"]), str(inp["dates"][0])[:10])
        S0 = st["storage_m3"]
        message = "; ".join(warns)
    else:
        inp = dict(inp0)
        inp["p50"] = inp0["p50"] * inflow_scale
        inp["p90"] = np.maximum(inp0["p90"] * inflow_scale * p90_scale, inp["p50"])
        inp["demand"] = inp0["demand"] * demand_scale
        S0 = float(np.clip(storage_pct / 100.0 * P.S_max, P.S_floor, P.S_max))
        units_list = [units]
    with LOCK:
        res = rc3.plan_from_arrays(P, inp, S0, units_list, pols, method)
    res.update({"status": status, "message": message, "key": key, "S0": S0, "first_date": str(inp["dates"][0])[:10]})
    return res


def get_plan(storage_pct, inflow_scale, p90_scale, demand_scale, units, method, source, align):
    key = norm_inputs(storage_pct, inflow_scale, p90_scale, demand_scale, units, method, source, align)
    sig = dr._sha(str(paths.LIVE_INPUT_DIR)) if key[6] == "live" else ""
    with LOCK:                                     # concurrent panels with the same inputs wait here, then hit the cache
        return _compute(key, sig)


def _dates(res, align):
    d0 = pd.Timestamp(res["first_date"])
    shift = (pd.Timestamp(date.today()) - d0) if align == "today" else pd.Timedelta(0)
    return shift


PLAN_Q = dict(storage_pct=Query(60.0), inflow_scale=Query(1.0), p90_scale=Query(1.0), demand_scale=Query(1.0), units=Query(2),
              method=Query("hybrid"), source=Query("whatif"), align=Query("today"))


# ------------------------------------------------------------------------------------------------ endpoints
@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat(timespec="seconds"), "models": sorted(_engine()[0])}


@app.get("/meta")
def meta():
    return [{"floor_masl": P.floor_level, "fsl_masl": P.FSL, "reserve_pct": P.reserve_fraction * 100, "terminal_pct": P.terminal_fraction * 100,
             "installed_mw": P.installed_mw, "active_storage_mcm": P.S_max / 1e6, "env_flow_m3s": P.env_flow_m3s,
             "methods": ",".join(METHOD_NAMES.values()), "data_status": "MODELLED study dataset - decision support only"}]


@app.get("/plan")
def plan(storage_pct: float = 60.0, inflow_scale: float = 1.0, p90_scale: float = 1.0, demand_scale: float = 1.0, units: int = 2,
         method: str = "hybrid", source: str = "whatif", align: str = "today"):
    res = get_plan(storage_pct, inflow_scale, p90_scale, demand_scale, units, method, source, align)
    if res["status"] != "OK" and "dfs" not in res:
        return []
    key = res["key"]
    df = res["dfs"][res["primary"]]
    sc = res["scenario"]
    shift = _dates(res, key[7])
    dts = pd.to_datetime(df["date"]) + shift
    cap = np.array([P.turbine_cap_m3(u) for u in df["units"]]) / SECONDS_PER_DAY
    n = len(df)
    out = pd.DataFrame({
        "time": [int(t.timestamp() * 1000) for t in dts], "date": dts.dt.strftime("%Y-%m-%d").values, "day": np.arange(1, n + 1),
        "inflow_p50_m3s": sc.fc50[:n, 0] / SECONDS_PER_DAY, "inflow_p90_m3s": sc.fc90[:n, 0] / SECONDS_PER_DAY,
        "release_m3s": df["turbine_release_m3"].values / SECONDS_PER_DAY, "spill_m3s": df["spill_volume_m3"].values / SECONDS_PER_DAY,
        "mandatory_m3s": df["mandatory_release_m3"].values / SECONDS_PER_DAY, "turbine_cap_m3s": cap,
        "storage_pct": df["end_storage_m3"].values / P.S_max * 100.0, "level_masl": df["pond_level_masl"].values,
        "generation_mwh": df["generation_mwh"].values, "demand_weight": df["weight"].values, "net_head_m": df["net_head_m"].values,
        "reserve_pct": P.reserve_fraction * 100.0, "target_pct": P.terminal_fraction * 100.0, "floor_masl": P.floor_level, "fsl_masl": P.FSL,
        "flood_watch": [1 if sc.fc90[i, :3].sum() > 3 * P.turbine_cap_m3(2) + (P.S_max - df["beginning_storage_m3"].iloc[i]) and i < 3 else 0
                        for i in range(n)]})
    return records(out.round(4))


@app.get("/plan/summary")
def plan_summary(storage_pct: float = 60.0, inflow_scale: float = 1.0, p90_scale: float = 1.0, demand_scale: float = 1.0, units: int = 2,
                 method: str = "hybrid", source: str = "whatif", align: str = "today"):
    res = get_plan(storage_pct, inflow_scale, p90_scale, demand_scale, units, method, source, align)
    if "dfs" not in res:
        return [{"status": res["status"], "alert_level": 2, "alert_text": res["message"], "n_alerts": 1,
                 "method": METHOD_NAMES.get(res["key"][5], res["key"][5])}]
    key, rec = res["key"], res["rec"]
    df = res["dfs"][res["primary"]]
    sc = res["scenario"]
    shift = _dates(res, key[7])
    flood_days = int(sum(1 for i in range(min(3, len(df))) if sc.fc90[i, :3].sum() > 3 * P.turbine_cap_m3(2) + (P.S_max - df["beginning_storage_m3"].iloc[i])))
    unmet_days = int((df["unmet_mandatory_m3"] > 1).sum())
    res_days = int((df["end_storage_m3"] < P.S_reserve - 1).sum())
    final_pct = float(df["end_storage_m3"].iloc[-1] / P.S_max * 100)
    parts = []
    if flood_days:
        parts.append(f"Flood watch ({flood_days} of next 3 days)")
    if unmet_days:
        parts.append(f"Env/irrigation release short on {unmet_days} day(s)")
    if res_days:
        parts.append(f"Below reserve on {res_days} day(s)")
    if final_pct < P.terminal_fraction * 100 - 0.5:
        parts.append(f"Plan ends at {final_pct:.0f}% (target {P.terminal_fraction*100:.0f}%)")
    sev = 2 if (unmet_days or res_days) else (1 if parts else 0)
    al = parts
    return [{
        "status": res["status"], "date": str((pd.Timestamp(rec["date"]) + shift).date()), "method": METHOD_NAMES[res["primary"]],
        "release_m3s": round(rec["turbine_release_m3s"], 2), "generation_mwh": round(rec["generation_mwh"], 1),
        "end_storage_pct": round(rec["expected_end_storage_pct"], 1), "level_masl": round(float(df["pond_level_masl"].iloc[0]), 3),
        "mandatory_m3s": round(rec["mandatory_release_m3s"], 2), "demand_weight": round(rec["demand_weight"], 3),
        "start_storage_pct": round(res["S0"] / P.S_max * 100, 1), "n_alerts": len(al), "alert_level": sev,
        "alert_text": " · ".join(parts) if parts else "No alerts",
        "plan_energy_mwh": round(float(df["generation_mwh"].sum()), 0), "min_storage_pct": round(float(df["end_storage_m3"].min() / P.S_max * 100), 1),
        "final_storage_pct": round(float(df["end_storage_m3"].iloc[-1] / P.S_max * 100), 1),
        "spill_mcm": round(float(df["spill_volume_m3"].sum() / 1e6), 3), "unmet_days": int((df["unmet_mandatory_m3"] > 1).sum()),
        "reserve_breach_days": int((df["end_storage_m3"] < P.S_reserve - 1).sum()),
        "floor_breach_days": int((df["end_storage_m3"] < P.S_floor - 1e-6).sum()), "horizon_days": int(len(df)),
        "message": res["message"]}]


@app.get("/plan/methods")
def plan_methods(storage_pct: float = 60.0, inflow_scale: float = 1.0, p90_scale: float = 1.0, demand_scale: float = 1.0, units: int = 2,
                 method: str = "hybrid", source: str = "whatif", align: str = "today"):
    res = get_plan(storage_pct, inflow_scale, p90_scale, demand_scale, units, method, source, align)
    if "dfs" not in res:
        return []
    rows = []
    for name, df in res["dfs"].items():
        rows.append({"method": METHOD_NAMES[name], "day1_release_m3s": round(float(df["turbine_release_m3"].iloc[0] / SECONDS_PER_DAY), 2),
                     "plan_energy_mwh": round(float(df["generation_mwh"].sum()), 0),
                     "final_storage_pct": round(float(df["end_storage_m3"].iloc[-1] / P.S_max * 100), 1),
                     "min_storage_pct": round(float(df["end_storage_m3"].min() / P.S_max * 100), 1),
                     "avoidable_spill_mcm": round(float(df["spill_avoidable_m3"].sum() / 1e6), 3),
                     "reserve_breach_days": int((df["end_storage_m3"] < P.S_reserve - 1).sum()),
                     "unmet_days": int((df["unmet_mandatory_m3"] > 1).sum()),
                     "floor_breach_days": int((df["end_storage_m3"] < P.S_floor - 1e-6).sum())})
    return rows


@app.get("/plan/methods_chart")
def plan_methods_chart(metric: str = "plan_energy_mwh", storage_pct: float = 60.0, inflow_scale: float = 1.0, p90_scale: float = 1.0,
                       demand_scale: float = 1.0, units: int = 2, method: str = "hybrid", source: str = "whatif", align: str = "today"):
    """/plan/methods reshaped for per-method colouring (see /chart/by_method)."""
    rows = plan_methods(storage_pct, inflow_scale, p90_scale, demand_scale, units, method, source, align)
    if not rows:
        return []
    if metric not in rows[0]:
        raise HTTPException(400, f"metric '{metric}' not available")
    names = [r["method"] for r in rows]
    out = []
    for r in rows:
        row = {"method": r["method"], **{n: None for n in names}}
        row[r["method"]] = r[metric]
        out.append(row)
    return out


@app.get("/live/status")
def live_status():
    root = paths.LIVE_OUTPUT_DIR
    sf, lf = root / "status.json", root / "decision_log.csv"
    st = json.load(open(sf, encoding="utf-8")) if sf.exists() else {}
    log = pd.read_csv(lf) if lf.exists() else pd.DataFrame()
    errors, warns, first, sdate = dr.validate_inputs(str(paths.LIVE_INPUT_DIR))
    def age(ts):
        try:
            return round((datetime.now() - datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")).total_seconds() / 60.0, 1)
        except Exception:                                                         # noqa: BLE001
            return None
    rec = st.get("last_recommendation", {})
    return [{"inbox_status": "REJECTED" if errors else "VALID", "inbox_message": "; ".join(errors) if errors else ("; ".join(warns) or "inputs valid"),
             "last_check": st.get("last_check", ""), "last_success": st.get("last_success", ""),
             "minutes_since_last_plan": age(st.get("last_success", "")), "minutes_since_last_check": age(st.get("last_check", "")),
             "plans_made": int((log["status"] == "PLANNED").sum()) if len(log) else 0,
             "plans_rejected": int((log["status"] == "REJECTED").sum()) if len(log) else 0,
             "last_release_m3s": rec.get("turbine_release_m3s"), "last_generation_mwh": rec.get("generation_mwh"),
             "last_end_storage_pct": rec.get("expected_end_storage_pct"), "last_method": rec.get("primary_method", ""),
             "last_rejection_reason": st.get("last_rejection_reason", "")}]


@app.get("/live/log")
def live_log(limit: int = 30, order: str = "desc"):
    lf = paths.LIVE_OUTPUT_DIR / "decision_log.csv"
    if not lf.exists():
        return []
    df = pd.read_csv(lf).tail(int(clip(limit, 1, 500, 30)))
    if order != "asc":
        df = df.iloc[::-1]                              # newest first (default); order=asc for charts
    df["time"] = pd.to_datetime(df["timestamp"]).map(lambda x: int(x.timestamp() * 1000))
    cols = [c for c in ("time", "timestamp", "status", "message", "state_date", "storage_pct", "primary_method", "turbine_release_m3s",
                        "generation_mwh", "expected_end_storage_pct", "n_alerts", "alerts", "run_seconds") if c in df.columns]
    return records(df[cols])


@app.get("/table/{name}")
def get_table(name: str, scenario_id: str = "", method_id: str = "", method: str = "", scenario: str = "", metric: str = ""):
    if name not in TABLES:
        raise HTTPException(404, f"unknown table '{name}'")
    df = table(name)
    for col, val in (("scenario_id", scenario_id), ("method_id", method_id), ("method", method), ("scenario", scenario)):
        if val and col in df.columns:
            df = df[df[col].isin(val.split(","))]
    return records(df)


@app.get("/chart/by_method")
def chart_by_method(metric: str = "episode_score", source: str = "scoreboard", methods: str = ""):
    """One row per method with the value placed in a column named after the method (others null), so that a stacked bar chart
    can colour every method consistently (fixed colour per method in the dashboard)."""
    df = table(source)
    if metric not in df.columns:
        raise HTTPException(400, f"metric '{metric}' not in table '{source}'")
    names = [m for m in df["method"].tolist() if not methods or m in methods.split(",")]
    rows = []
    for _, r in df.iterrows():
        if r["method"] not in names:
            continue
        row = {"method": r["method"]}
        for n in names:
            row[n] = None
        row[r["method"]] = None if pd.isna(r[metric]) else round(float(r[metric]), 4)
        rows.append(row)
    return rows


@app.get("/scenario/series")
def scenario_series(scenario_id: str = "drought_el_nino", metric: str = "storage_pct", methods: str = "hybrid,rolling_lp,reference_gauge",
                    smooth: int = 7, ref_lines: int = 0):
    """Wide table: one row per day, `time` (epoch ms), `date`, then one column per selected method (its display name)."""
    allowed = {"inflow_m3s", "release_m3s", "spill_m3s", "storage_pct", "level_masl", "generation_mwh", "weight", "unmet_release_m3s"}
    if metric not in allowed:
        raise HTTPException(400, f"metric must be one of {sorted(allowed)}")
    df = table("trajectories")
    ms = [m for m in methods.split(",") if m]
    df = df[(df["scenario_id"] == scenario_id) & (df["method_id"].isin(ms))]
    wide = df.pivot_table(index=["time", "date"], columns="method", values=metric, aggfunc="first").reset_index()
    order = [METHOD_NAMES[m] for m in ms if METHOD_NAMES.get(m) in wide.columns]
    wide = wide[["time", "date"] + order]
    k = int(clip(smooth, 1, 31, 7))
    if k > 1:                                           # centred moving average for readability (year-long curves are very jagged)
        wide[order] = wide[order].rolling(k, center=True, min_periods=1).mean()
    if ref_lines and metric == "storage_pct":            # constant reference lines in the same frame (clean legend in Grafana)
        wide["Operating reserve (20%)"] = P.reserve_fraction * 100.0
        wide["Year-end target (50%)"] = P.terminal_fraction * 100.0
    return records(wide.round(4))


@app.get("/scenario/reference")
def scenario_reference(scenario_id: str = "drought_el_nino"):
    """Method-independent series for a scenario (true inflow, demand weight) and constant reference lines."""
    df = table("trajectories")
    d = df[(df["scenario_id"] == scenario_id) & (df["method_id"] == "omniscient_lp")]
    return records(d[["time", "date", "inflow_m3s", "weight", "reserve_pct", "target_pct"]].round(4))


if __name__ == "__main__":
    _engine()
    uvicorn.run(app, host=paths.API_HOST, port=paths.API_PORT, log_level="warning")
