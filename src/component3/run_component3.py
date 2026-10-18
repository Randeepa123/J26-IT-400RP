"""
run_component3.py
=================
Single entry point for Component 3 (Hydropower Generation & Reservoir Release Optimisation).

INPUT CONTRACT (CSV / JSON)
  --inflow-forecast  CSV  (Component 1)  columns: date, inflow_median_m3s, inflow_p90_m3s     [m3/s, daily, >= 1 day]
                          (alt: inflow_median_m3 [m3/day] + inflow_p90_m3 [m3/day])
  --demand-forecast  CSV  (Component 2)  columns: date, forecast_energy_consumption [MWh/day]
  --demand-history   CSV  (optional)     columns: date, daily_energy_consumption_mwh  (default: event-aware 5-year series)
  --solar-surplus    CSV  (Component 4, optional) columns: date, solar_surplus_mwh. Logged; only affects the plan
                          if --solar-discount > 0 (heuristic, default OFF, not validated).
  --state            JSON current reservoir state: {"date": "YYYY-MM-DD", "pond_level_masl": 205.4}
                          or {"storage_m3": ...}; optional "units_available": [2, 2, ...] per forecast day.
OUTPUT (in --out-dir): schedule_<method>.csv, recommendation.json, status_report.html
METHODS: rolling_lp (always), reference, and dqn / hybrid when trained model zips are supplied.

All inputs in this repository are SYNTHETIC / assumed; outputs must be treated as decision SUPPORT, not control signals.
"""
import os
import io
import sys
import json
import base64
import argparse
from datetime import datetime

import numpy as np
import pandas as pd

import demand_events as de
import paths
import scenario_generator as sg
import sim_core as sm
import rolling_lp as rl
from hydro_core import HydroParams, SECONDS_PER_DAY

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
H = sg.H_FC


def level_to_storage(p, level):
    r = np.clip((level - p.MOL) / p.delta_H, 0.0, 1.0)
    return float(p.S_max * r ** p.alpha)


def load_inflow_forecast(path):
    df = pd.read_csv(path, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    if {"inflow_median_m3s", "inflow_p90_m3s"} <= set(df.columns):
        p50, p90 = df["inflow_median_m3s"].values * SECONDS_PER_DAY, df["inflow_p90_m3s"].values * SECONDS_PER_DAY
    elif {"inflow_median_m3", "inflow_p90_m3"} <= set(df.columns):
        p50, p90 = df["inflow_median_m3"].values, df["inflow_p90_m3"].values
    else:
        raise ValueError("inflow forecast needs inflow_median_m3s+inflow_p90_m3s (or the *_m3 volume columns)")
    return df["date"].values.astype("datetime64[D]"), p50.astype(float), np.maximum(p90, p50).astype(float)


def build_planning_scenario(p, dates, p50, p90, demand_fc, hist, units, solar=None, solar_discount=0.0):
    n = min(len(dates), H)
    dates, p50, p90 = dates[:n], p50[:n], p90[:n]
    ev_mult, _ = de.event_series(dates)
    w = de.demand_weights_from_forecast(np.asarray(demand_fc[:n], float) * ev_mult, hist, p.weight_clip)
    if solar is not None and solar_discount > 0:
        share = np.clip(np.asarray(solar[:n], float) / np.maximum(np.asarray(demand_fc[:n], float), 1.0), 0, 0.3)
        w = np.clip(w * (1 - solar_discount * share), *p.weight_clip)
    L = n + H
    padn = L - n
    def pad(a): return np.concatenate([a, np.repeat(a[-1:], padn, axis=0)])
    dts = np.concatenate([dates, dates[-1] + np.arange(1, padn + 1).astype("timedelta64[D]")])
    q50, q90, wl = pad(p50), pad(p90), pad(w)
    q_nom = q50          # dry run: the P50 forecast stands in for the actual inflow
    units = list(units) + [units[-1]] * max(0, n - len(units))      # pad short availability lists with the last value
    u = np.concatenate([np.asarray(units[:n], int), np.repeat(int(units[n - 1]), padn)])
    fc50 = np.zeros((L, H)); fc90 = np.zeros((L, H)); dwf = np.zeros((L, H))
    for t in range(L):
        idx = np.minimum(t + np.arange(H), L - 1)
        fc50[t], fc90[t], dwf[t] = q50[idx], q90[idx], wl[idx]
    return sg.Scenario("planning_15d", dts.astype("datetime64[D]"), q_nom, u, wl, fc50, fc90, dwf,
                       {"kind": "deployment", "note": "dry-run uses the P50 forecast as nominal inflow"}), n


def plot_png(df_by_method, p):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    for m, df in df_by_method.items():
        d = pd.to_datetime(df["date"])
        ax[0].plot(d, df["end_storage_m3"] / 1e6, label=m, marker="o", ms=3)
        ax[1].plot(d, df["generation_mwh"], label=m, marker="o", ms=3)
        ax[2].bar(d + pd.Timedelta(hours=6 * (list(df_by_method).index(m))), df["spill_volume_m3"] / 1e6, width=0.25, label=m)
    ax[0].axhline(p.S_reserve / 1e6, color="k", ls="--", lw=0.8, label="reserve")
    ax[0].axhline(p.S_terminal / 1e6, color="g", ls=":", lw=0.8, label="terminal target")
    ax[0].set_ylabel("end storage (MCM)"); ax[0].legend(fontsize=7, ncol=4)
    ax[1].set_ylabel("generation (MWh/day)"); ax[2].set_ylabel("spill (MCM/day)")
    fig.tight_layout()
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=100); plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def alerts_for(p, sc, df):
    out = []
    cap_full = p.turbine_cap_m3(2)
    for i, r in df.iterrows():
        S = r["beginning_storage_m3"]
        unabs = float(sc.fc90[i, 0:3].sum()) - 3 * cap_full - (p.S_max - S)
        if unabs > 0 and i < 3:
            out.append(f"{r['date']}: FLOOD WATCH - P90 inflow over next 3 days exceeds turbine capacity + free storage by "
                       f"{unabs/1e6:.2f} MCM; pre-drawdown is built into the plan.")
        if r["unmet_mandatory_m3"] > 1:
            out.append(f"{r['date']}: environmental/irrigation release SHORT by {r['unmet_mandatory_m3']/SECONDS_PER_DAY:.2f} m3/s-day (low inflow).")
        if r["end_storage_m3"] < p.S_reserve:
            out.append(f"{r['date']}: storage {r['end_storage_m3']/p.S_max*100:.0f}% is below the operating reserve ({p.reserve_fraction*100:.0f}%).")
    if df["end_storage_m3"].iloc[-1] < p.S_terminal:
        out.append(f"Plan ends at {df['end_storage_m3'].iloc[-1]/p.S_max*100:.0f}% storage, below the {p.terminal_fraction*100:.0f}% target.")
    return out or ["No alerts."]


def html_report(p, state, table, rec, alerts, png_b64, files):
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Kukule Ganga - Release Plan</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;max-width:1000px}}table{{border-collapse:collapse;font-size:13px}}
td,th{{border:1px solid #ccc;padding:3px 7px;text-align:right}}th{{background:#f0f0f0}}.warn{{color:#b00}}.note{{color:#555;font-size:12px}}</style></head><body>
<h2>Kukule Ganga - 15-day release & generation plan</h2>
<p class="note">Decision SUPPORT output. Inputs in this repository are synthetic / assumed. Generated {datetime.now():%Y-%m-%d %H:%M}.</p>
<h3>Current state</h3><p>Date {state['date']} &nbsp; storage {state['storage_m3']/1e6:.3f} MCM ({state['storage_m3']/p.S_max*100:.0f}%) &nbsp;
level {p.elevation(state['storage_m3']):.2f} masl &nbsp; hard floor {p.floor_level:.2f} masl &nbsp; reserve {p.reserve_fraction*100:.0f}% &nbsp; terminal target {p.terminal_fraction*100:.0f}%</p>
<h3>Recommendation for today ({rec['date']})</h3>
<p><b>{rec['primary_method']}</b>: turbine release <b>{rec['turbine_release_m3s']:.1f} m3/s</b> ({rec['turbine_release_m3']/1e6:.3f} MCM),
expected generation <b>{rec['generation_mwh']:.0f} MWh</b>, mandatory weir release {rec['mandatory_release_m3s']:.1f} m3/s.</p>
<h3>Alerts</h3><ul>{''.join(f'<li class="warn">{a}</li>' if a!='No alerts.' else f'<li>{a}</li>' for a in alerts)}</ul>
<img src="data:image/png;base64,{png_b64}" style="max-width:100%">
<h3>Schedule ({rec['primary_method']})</h3>{table}
<p class="note">Files: {', '.join(files)}</p></body></html>"""


def _read_state(p, state, first_date):
    """Normalise a state dict/JSON path -> ({'date','storage_m3'}, units list)."""
    if state is None:
        st = {"date": first_date, "storage_m3": 0.6 * p.S_max}
    elif isinstance(state, (str, os.PathLike)):
        with open(state, "r", encoding="utf-8") as f:
            st = json.load(f)
    else:
        st = dict(state)
    S0 = float(st["storage_m3"]) if "storage_m3" in st else level_to_storage(p, float(st["pond_level_masl"]))
    S0 = float(np.clip(S0, p.S_floor, p.S_max))
    units = st.get("units_available") or [2]
    return {"date": st.get("date", first_date), "storage_m3": S0}, [int(u) for u in units]


def load_inputs(inflow_forecast, demand_forecast, demand_history, solar_surplus=None):
    """Read forecast CSVs -> dict of arrays (no state, no model)."""
    dates, p50, p90 = load_inflow_forecast(inflow_forecast)
    dfd = pd.read_csv(demand_forecast, parse_dates=["date"]).set_index("date")["forecast_energy_consumption"]
    dem = dfd.reindex(pd.to_datetime(dates)).ffill().bfill().values
    hist = pd.read_csv(demand_history)["daily_energy_consumption_mwh"].values
    solar = None
    if solar_surplus:
        solar = (pd.read_csv(solar_surplus, parse_dates=["date"]).set_index("date")["solar_surplus_mwh"]
                 .reindex(pd.to_datetime(dates)).fillna(0).values)
    return {"dates": dates, "p50": p50, "p90": p90, "demand": dem, "history": hist, "solar": solar}


def build_policies(dqn=None, hybrid=None, deterministic=True):
    """
    Policy objects for every available method (rolling LP and the reference rule are always present).
    deterministic=True (deployment / dashboard): the LP plans on the median (P50) forecast without the P90 hedge or the
    online bias feedback, and a small day-to-day release-smoothing preference, so the displayed 15-day plan is self-consistent
    (expected inflow = planned inflow) and operationally smooth. The hedged
    variants are only used in the evaluations (evaluate_all, multiseed_eval), where inflow is a random draw.
    """
    lpk = dict(p90_blend=0.0, bias_correction=False, smooth_ratio=0.05) if deterministic else {}
    pols = {"rolling_lp": rl.RollingLPPolicy(**lpk), "reference": sm.ReferenceRulePolicy()}
    if dqn:
        from dqn_policy import DQNPolicy
        pols["dqn"] = DQNPolicy(dqn)
    if hybrid:
        from hybrid_policy import HybridPolicy
        pols["hybrid"] = HybridPolicy(hybrid, lp_kwargs=lpk)
    return pols


def plan_from_arrays(p, inp, S0, units, policies, primary=None, solar_discount=0.0):
    """
    In-memory planning engine (no file I/O). inp = dict from load_inputs() (possibly scaled by the caller);
    S0 = starting storage [m3]; units = per-day available units; policies = dict name -> Policy.
    Returns dict(dfs, scenario, n, primary, rec, alerts).
    """
    sc, n = build_planning_scenario(p, inp["dates"], inp["p50"], inp["p90"], inp["demand"], inp["history"], units,
                                    inp.get("solar"), solar_discount)
    primary = primary or ("hybrid" if "hybrid" in policies else "dqn" if "dqn" in policies else "rolling_lp")
    if primary not in policies:
        raise ValueError(f"primary method '{primary}' not available; have {list(policies)}")
    dfs = {name: sm.simulate(p, sc, pol, 0, n, S0=S0)[0] for name, pol in policies.items()}
    d0 = dfs[primary].iloc[0]
    rec = {"date": str(d0["date"]), "primary_method": primary, "turbine_release_m3": float(d0["turbine_release_m3"]),
           "turbine_release_m3s": float(d0["turbine_release_m3"] / SECONDS_PER_DAY), "generation_mwh": float(d0["generation_mwh"]),
           "mandatory_release_m3s": float(d0["mandatory_release_m3"] / SECONDS_PER_DAY),
           "expected_end_storage_pct": float(d0["end_storage_m3"] / p.S_max * 100),
           "expected_end_storage_m3": float(d0["end_storage_m3"]), "demand_weight": float(d0["weight"]),
           "methods_day0_turbine_release_m3s": {k: float(v.iloc[0]["turbine_release_m3"] / SECONDS_PER_DAY) for k, v in dfs.items()},
           "data_status": "MODELLED / ASSUMED INPUTS - decision support only"}
    return {"dfs": dfs, "scenario": sc, "n": n, "primary": primary, "rec": rec, "alerts": alerts_for(p, sc, dfs[primary])}


def run_plan(inflow_forecast, demand_forecast, demand_history, state=None, out_dir=None, solar_surplus=None,
             solar_discount=0.0, dqn=None, hybrid=None, primary=None, verbose=False):
    """
    One planning run: forecasts + state -> 15-day schedules (one CSV per method), recommendation.json and status_report.html.
    `state` may be a dict, a JSON path or None (60% storage assumed). Returns a dict with rec, alerts, files, state, primary.
    """
    out_dir = str(out_dir or paths.RUN_COMPONENT3_DIR)
    p = HydroParams.from_config()
    inp = load_inputs(inflow_forecast, demand_forecast, demand_history, solar_surplus)
    st, units = _read_state(p, state, str(inp["dates"][0])[:10])
    res = plan_from_arrays(p, inp, st["storage_m3"], units, build_policies(dqn, hybrid), primary, solar_discount)
    dfs, rec, al, primary, n = res["dfs"], res["rec"], res["alerts"], res["primary"], res["n"]

    os.makedirs(out_dir, exist_ok=True)
    files = []
    for name, df in dfs.items():
        out = df[["date", "turbine_release_m3", "spill_volume_m3", "mandatory_release_m3", "end_storage_m3",
                  "pond_level_masl", "generation_mwh", "net_head_m", "weight", "units", "action_projected"]].copy()
        out["turbine_release_m3s"] = out["turbine_release_m3"] / SECONDS_PER_DAY
        out["storage_pct"] = out["end_storage_m3"] / p.S_max * 100
        f = os.path.join(out_dir, f"schedule_{name}.csv")
        out.round(4).to_csv(f, index=False)
        files.append(os.path.basename(f))
    with open(os.path.join(out_dir, "recommendation.json"), "w") as f:
        json.dump(rec, f, indent=2)
    tbl = dfs[primary][["date", "turbine_release_m3", "spill_volume_m3", "mandatory_release_m3", "end_storage_m3",
                        "pond_level_masl", "generation_mwh", "weight"]].round(2).to_html(index=False)
    html = html_report(p, st, tbl, rec, al, plot_png(dfs, p), files + ["recommendation.json"])
    with open(os.path.join(out_dir, "status_report.html"), "w", encoding="utf-8") as f:
        f.write(html)
    try:
        from build_dashboard_html import build_standalone_dashboard
        build_standalone_dashboard(os.path.join(out_dir, "dashboard.html"))
        files.append("dashboard.html")
    except Exception as e:
        if verbose:
            print(f"Warning: could not bundle dashboard.html: {e}")
    if verbose:
        print(json.dumps(rec, indent=1)); print("alerts:", *al, sep="\n  "); print("out:", out_dir)
    return {"rec": rec, "alerts": al, "files": files + ["recommendation.json", "status_report.html", "dashboard.html"], "state": st,
            "primary": primary, "first_forecast_date": str(inp["dates"][0])[:10], "n_days": n}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inflow-forecast", default=str(paths.INFLOW_FORECAST_15D))
    ap.add_argument("--demand-forecast", default=str(paths.DEMAND_FORECAST_15D))
    ap.add_argument("--demand-history", default=str(paths.DEMAND_5Y_V2))
    ap.add_argument("--solar-surplus"); ap.add_argument("--solar-discount", type=float, default=0.0)
    ap.add_argument("--state", help="JSON file; default: 60%% storage on the first forecast date")
    ap.add_argument("--dqn"); ap.add_argument("--hybrid")
    ap.add_argument("--primary", default=None, help="method for the recommendation (default: hybrid > dqn > rolling_lp)")
    ap.add_argument("--out-dir", default=str(paths.RUN_COMPONENT3_DIR))
    a = ap.parse_args()
    run_plan(a.inflow_forecast, a.demand_forecast, a.demand_history, a.state, a.out_dir, a.solar_surplus,
             a.solar_discount, a.dqn, a.hybrid, a.primary, verbose=True)


if __name__ == "__main__":
    main()
