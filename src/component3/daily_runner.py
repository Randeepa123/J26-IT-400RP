"""
daily_runner.py - daily / continuous operation mode for Component 3.

Watches an INBOX folder; whenever the inflow forecast (Component 1), demand forecast (Component 2), optional solar
surplus (Component 4) or the reservoir state changes, it validates the files, re-plans (run_component3.run_plan),
publishes the newest plan to a fixed place and appends the decision to a log.

INBOX (default data/live_inputs/)                OUTPUT ROOT (default outputs/live/)
    inflow_forecast.csv   date,inflow_median_m3s,inflow_p90_m3s        latest/            newest plan (always the same file names)
    demand_forecast.csv   date,forecast_energy_consumption             history/<stamp>/   copy of every accepted plan
    state.json            {"date":..,"pond_level_masl":..}             decision_log.csv   one row per check/decision
    solar_surplus.csv     (optional) date,solar_surplus_mwh            status.json        heartbeat (last check / last success)

Safety behaviour: invalid or inconsistent inputs are REJECTED (reason logged, previous plan kept, process keeps running);
unchanged inputs are not re-planned; a lock file prevents two runs at once. Outputs are decision support, not control signals.

Usage:
    python src/component3/daily_runner.py --init-demo           # create example inputs in the inbox
    python src/component3/daily_runner.py --once                # check once (re-plans only if inputs changed)
    python src/component3/daily_runner.py --once --force        # re-plan now
    python src/component3/daily_runner.py --watch --interval 60 # keep running, check every 60 s (Ctrl+C to stop)
    python src/component3/daily_runner.py --demo-days 5         # show continuous operation: 5 consecutive days, storage carried forward
"""
import os
import csv
import json
import time
import shutil
import hashlib
import argparse
from datetime import datetime

import numpy as np
import pandas as pd

import paths
import run_component3 as rc3
from hydro_core import HydroParams

INBOX_FILES = {"inflow": "inflow_forecast.csv", "demand": "demand_forecast.csv", "state": "state.json",
               "solar": "solar_surplus.csv"}
LOG_FIELDS = ["timestamp", "status", "message", "forecast_first_date", "state_date", "storage_m3", "storage_pct",
              "primary_method", "turbine_release_m3s", "generation_mwh", "expected_end_storage_pct", "n_alerts",
              "alerts", "input_sha", "run_seconds"]


# ----------------------------------------------------------------------------------------------- helpers
def _sha(inbox):
    h = hashlib.sha256()
    for key in ("inflow", "demand", "state", "solar"):
        f = os.path.join(inbox, INBOX_FILES[key])
        if os.path.exists(f):
            with open(f, "rb") as fh:
                h.update(key.encode()); h.update(fh.read())
    return h.hexdigest()[:12]


def _settled(inbox, seconds=2.0):
    """True when no inbox file was modified in the last `seconds` (avoid reading half-written files)."""
    if seconds <= 0:
        return True
    now = time.time()
    return all(now - os.path.getmtime(os.path.join(inbox, f)) >= seconds
               for f in INBOX_FILES.values() if os.path.exists(os.path.join(inbox, f)))


def validate_inputs(inbox):
    """Return (errors, warnings, first_forecast_date, state_date). Any error => the run is rejected."""
    p = HydroParams.from_config()
    errors, warns, first, sdate = [], [], None, None
    for key in ("inflow", "demand", "state"):
        if not os.path.exists(os.path.join(inbox, INBOX_FILES[key])):
            errors.append(f"missing required file {INBOX_FILES[key]}")
    if errors:
        return errors, warns, first, sdate
    try:
        df = pd.read_csv(os.path.join(inbox, INBOX_FILES["inflow"]), parse_dates=["date"])
        cols = ({"inflow_median_m3s", "inflow_p90_m3s"} if {"inflow_median_m3s", "inflow_p90_m3s"} <= set(df.columns)
                else {"inflow_median_m3", "inflow_p90_m3"})
        if not cols <= set(df.columns):
            errors.append("inflow_forecast.csv needs inflow_median_m3s + inflow_p90_m3s (or the *_m3 columns)")
        else:
            if len(df) < 1:
                errors.append("inflow_forecast.csv has no rows")
            if df[list(cols)].isna().any().any() or (df[list(cols)] < 0).any().any():
                errors.append("inflow_forecast.csv has missing or negative values")
            if not df["date"].is_monotonic_increasing or (df["date"].diff().dropna() != pd.Timedelta(days=1)).any():
                errors.append("inflow_forecast.csv dates must be consecutive days in increasing order")
            if (df[sorted(cols)[1]] < df[sorted(cols)[0]]).any() if len(cols) == 2 and len(df) else False:
                warns.append("P90 below median on some days (P90 is raised to the median)")
            if len(df) < 5:
                warns.append(f"only {len(df)} forecast day(s); the plan horizon is short")
            first = str(df["date"].iloc[0].date()) if len(df) else None
    except Exception as e:                                            # noqa: BLE001
        errors.append(f"cannot read inflow_forecast.csv: {e}")
    try:
        dd = pd.read_csv(os.path.join(inbox, INBOX_FILES["demand"]), parse_dates=["date"])
        if "forecast_energy_consumption" not in dd.columns:
            errors.append("demand_forecast.csv needs column forecast_energy_consumption")
        elif dd["forecast_energy_consumption"].isna().any() or (dd["forecast_energy_consumption"] <= 0).any():
            errors.append("demand_forecast.csv has missing or non-positive values")
        elif first and pd.Timestamp(first) not in set(dd["date"]):
            warns.append("demand forecast does not cover the first forecast day (nearest values are reused)")
    except Exception as e:                                            # noqa: BLE001
        errors.append(f"cannot read demand_forecast.csv: {e}")
    try:
        with open(os.path.join(inbox, INBOX_FILES["state"]), "r", encoding="utf-8") as f:
            st = json.load(f)
        if "storage_m3" in st:
            S = float(st["storage_m3"])
            if not (0.0 <= S <= 1.01 * p.S_max):
                errors.append(f"storage_m3={S:.0f} is outside 0..{p.S_max:.0f}")
        elif "pond_level_masl" in st:
            L = float(st["pond_level_masl"])
            if not (p.floor_level - 0.3 <= L <= p.FSL + 0.3):
                errors.append(f"pond_level_masl={L:.2f} is outside {p.floor_level-0.3:.2f}..{p.FSL+0.3:.2f}")
        else:
            errors.append("state.json needs storage_m3 or pond_level_masl")
        if "date" not in st:
            warns.append("state.json has no date; the first forecast date is assumed")
        else:
            sdate = str(pd.Timestamp(st["date"]).date())
            if first:
                gap = abs((pd.Timestamp(sdate) - pd.Timestamp(first)).days)
                if gap > 3:
                    errors.append(f"state date {sdate} and first forecast date {first} differ by {gap} days (stale file?)")
                elif gap > 1:
                    warns.append(f"state date {sdate} and first forecast date {first} differ by {gap} days")
        ua = st.get("units_available")
        if ua is not None and (not isinstance(ua, list) or any(int(u) not in (0, 1, 2) for u in ua)):
            errors.append("units_available must be a list of 0/1/2")
    except Exception as e:                                            # noqa: BLE001
        errors.append(f"cannot read state.json: {e}")
    return errors, warns, first, sdate


def _append_log(root, row):
    f = os.path.join(root, "decision_log.csv")
    new = not os.path.exists(f)
    with open(f, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LOG_FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in LOG_FIELDS})


def _write_status(root, **kw):
    f = os.path.join(root, "status.json")
    cur = {}
    if os.path.exists(f):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                cur = json.load(fh)
        except Exception:                                             # noqa: BLE001
            cur = {}
    cur.update(kw)
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(cur, fh, indent=2)


def _lock(root):
    lf = os.path.join(root, ".lock")
    if os.path.exists(lf) and time.time() - os.path.getmtime(lf) < 600:
        return None
    with open(lf, "w") as fh:
        fh.write(str(os.getpid()))
    return lf


# ----------------------------------------------------------------------------------------------- one check
def run_once(inbox, root, hybrid=None, dqn=None, primary=None, force=False, settle=2.0, quiet=False):
    """One check of the inbox. Returns a status string: PLANNED | UNCHANGED | REJECTED | BUSY | WAITING."""
    os.makedirs(inbox, exist_ok=True); os.makedirs(root, exist_ok=True)
    stamp_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lock = _lock(root)
    if lock is None:
        return "BUSY"
    try:
        if not _settled(inbox, settle):
            return "WAITING"
        sha = _sha(inbox)
        sig_file = os.path.join(root, ".last_signature")
        last = ""
        if os.path.exists(sig_file):
            with open(sig_file) as fh:
                last = fh.read().strip()
        _write_status(root, last_check=stamp_now)
        if sha == last and not force:
            return "UNCHANGED"
        t0 = time.time()
        errors, warns, first, sdate = validate_inputs(inbox)
        if errors:
            msg = "; ".join(errors)
            _append_log(root, {"timestamp": stamp_now, "status": "REJECTED", "message": msg, "forecast_first_date": first or "",
                               "state_date": sdate or "", "input_sha": sha})
            _write_status(root, last_rejected=stamp_now, last_rejection_reason=msg)
            with open(sig_file, "w") as fh:
                fh.write(sha)                      # do not re-report the same bad files every cycle
            if not quiet:
                print(f"[{stamp_now}] REJECTED: {msg}")
            return "REJECTED"
        work = os.path.join(root, "_work")
        shutil.rmtree(work, ignore_errors=True)
        solar = os.path.join(inbox, INBOX_FILES["solar"])
        res = rc3.run_plan(os.path.join(inbox, INBOX_FILES["inflow"]), os.path.join(inbox, INBOX_FILES["demand"]),
                           str(paths.DEMAND_5Y_V2), os.path.join(inbox, INBOX_FILES["state"]), work,
                           solar if os.path.exists(solar) else None, 0.0, dqn, hybrid, primary)
        latest = os.path.join(root, "latest")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]          # millisecond stamp: unique even for rapid runs
        hist = os.path.join(root, "history", stamp)
        while os.path.exists(hist):
            hist += "x"
        os.makedirs(os.path.dirname(hist), exist_ok=True)
        shutil.copytree(work, hist)
        shutil.rmtree(latest, ignore_errors=True)
        shutil.move(work, latest)
        rec, st = res["rec"], res["state"]
        # keep a copy of the exact inputs that produced this plan (audit + later model adaptation)
        os.makedirs(os.path.join(hist, "inputs"), exist_ok=True)
        for f in INBOX_FILES.values():
            if os.path.exists(os.path.join(inbox, f)):
                shutil.copy2(os.path.join(inbox, f), os.path.join(hist, "inputs", f))
        al = [a for a in res["alerts"] if a != "No alerts."]
        _append_log(root, {"timestamp": stamp_now, "status": "PLANNED", "message": ("warnings: " + "; ".join(warns)) if warns else "",
                           "forecast_first_date": res["first_forecast_date"], "state_date": st["date"],
                           "storage_m3": round(st["storage_m3"], 1), "storage_pct": round(100 * st["storage_m3"] / HydroParams.from_config().S_max, 1),
                           "primary_method": rec["primary_method"], "turbine_release_m3s": round(rec["turbine_release_m3s"], 2),
                           "generation_mwh": round(rec["generation_mwh"], 1), "expected_end_storage_pct": round(rec["expected_end_storage_pct"], 1),
                           "n_alerts": len(al), "alerts": " | ".join(al[:3]), "input_sha": sha, "run_seconds": round(time.time() - t0, 2)})
        _write_status(root, last_success=stamp_now, last_plan_dir=os.path.relpath(hist, root), last_recommendation=rec,
                      last_rejection_reason="")
        with open(sig_file, "w") as fh:
            fh.write(sha)
        if not quiet:
            print(f"[{stamp_now}] PLANNED  {rec['primary_method']}: release {rec['turbine_release_m3s']:.1f} m3/s, "
                  f"gen {rec['generation_mwh']:.0f} MWh, end storage {rec['expected_end_storage_pct']:.0f}%, alerts {len(al)}"
                  + (f", warnings: {'; '.join(warns)}" if warns else ""))
        return "PLANNED"
    finally:
        try:
            os.remove(lock)
        except OSError:
            pass


# ----------------------------------------------------------------------------------------------- demo helpers
def init_demo(inbox, storage_frac=0.6, shift_days=0, storage_m3=None):
    """Write example inputs into the inbox from the repository's example 15-day forecasts (optionally rolled forward)."""
    os.makedirs(inbox, exist_ok=True)
    p = HydroParams.from_config()
    inflow = pd.read_csv(paths.INFLOW_FORECAST_15D, parse_dates=["date"]).iloc[shift_days:]
    keep = [c for c in ("date", "inflow_median_m3s", "inflow_p90_m3s") if c in inflow.columns]
    inflow[keep].to_csv(os.path.join(inbox, INBOX_FILES["inflow"]), index=False)
    dem = pd.read_csv(paths.DEMAND_FORECAST_15D, parse_dates=["date"])
    dem = dem[dem["date"] >= inflow["date"].iloc[0]]
    dem[["date", "forecast_energy_consumption"]].to_csv(os.path.join(inbox, INBOX_FILES["demand"]), index=False)
    S = storage_m3 if storage_m3 is not None else storage_frac * p.S_max
    with open(os.path.join(inbox, INBOX_FILES["state"]), "w", encoding="utf-8") as f:
        json.dump({"date": str(inflow["date"].iloc[0].date()), "storage_m3": round(float(S), 1), "units_available": [2]}, f, indent=1)
    return str(inflow["date"].iloc[0].date())


def demo_days(inbox, root, n, **kw):
    """Simulate n consecutive daily runs: forecasts roll forward one day, storage carries over from the previous plan."""
    shutil.rmtree(root, ignore_errors=True)
    S = None
    for k in range(n):
        init_demo(inbox, shift_days=k, storage_m3=S)
        time.sleep(0.05)
        run_once(inbox, root, force=True, settle=0.0, **kw)
        S = json.load(open(os.path.join(root, "latest", "recommendation.json")))["expected_end_storage_m3"]


# ----------------------------------------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inbox", default=str(paths.LIVE_INPUT_DIR))
    ap.add_argument("--out-root", default=str(paths.LIVE_OUTPUT_DIR))
    ap.add_argument("--hybrid", default=str(paths.MODELS_DIR / "hybrid_selected.zip"))
    ap.add_argument("--dqn", default=None)
    ap.add_argument("--no-models", action="store_true", help="use the rolling LP only (no DQN / hybrid)")
    ap.add_argument("--primary", default=None)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true", help="check the inbox once (default)")
    g.add_argument("--watch", action="store_true", help="keep checking until stopped")
    g.add_argument("--init-demo", action="store_true", help="write example inputs into the inbox and exit")
    g.add_argument("--demo-days", type=int, metavar="N", help="demo of N consecutive daily runs (uses separate demo folders)")
    ap.add_argument("--interval", type=float, default=60.0, help="seconds between checks in --watch mode")
    ap.add_argument("--force", action="store_true", help="re-plan even if the inputs did not change")
    ap.add_argument("--max-runs", type=int, default=None, help="stop --watch after this many checks (testing)")
    a = ap.parse_args()

    hybrid = None if a.no_models or not a.hybrid or not os.path.exists(a.hybrid) else a.hybrid
    dqn = a.dqn if (a.dqn and os.path.exists(a.dqn) and not a.no_models) else None
    kw = dict(hybrid=hybrid, dqn=dqn, primary=a.primary)

    if a.init_demo:
        d = init_demo(a.inbox)
        print(f"example inputs written to {a.inbox} (first forecast day {d}); now run with --once or --watch")
        return
    if a.demo_days:
        inbox, root = str(paths.DATA_DIR / "live_inputs_demo"), str(paths.OUTPUTS_DIR / "live_demo")
        demo_days(inbox, root, a.demo_days, **kw)
        print(f"\ndecision log: {os.path.join(root, 'decision_log.csv')}")
        print(pd.read_csv(os.path.join(root, "decision_log.csv"))[
            ["forecast_first_date", "status", "storage_pct", "turbine_release_m3s", "generation_mwh",
             "expected_end_storage_pct", "n_alerts"]].to_string(index=False))
        return
    if a.watch:
        print(f"watching {a.inbox} every {a.interval:.0f}s (Ctrl+C to stop); plans -> {a.out_root}")
        n = 0
        try:
            while True:
                s = run_once(a.inbox, a.out_root, force=a.force and n == 0, **kw)
                if s in ("UNCHANGED", "BUSY", "WAITING"):
                    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {s.lower()} - waiting for new inputs", flush=True)
                n += 1
                if a.max_runs and n >= a.max_runs:
                    break
                time.sleep(a.interval)
        except KeyboardInterrupt:
            print("stopped")
        return
    s = run_once(a.inbox, a.out_root, force=a.force, **kw)
    if s in ("UNCHANGED", "BUSY", "WAITING"):
        print(f"{s}: nothing to do" + (" (inputs unchanged since the last plan; use --force to re-plan)" if s == "UNCHANGED" else ""))


if __name__ == "__main__":
    main()
