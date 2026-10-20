"""
build_dashboards.py - generates the three Grafana dashboards (JSON) for the Kukule Ganga project.

    python grafana/build_dashboards.py          # writes grafana/dashboards/{1_live_plan,2_results,3_scenario_explorer}.json

All panels read the local API (src/component3/api_server.py) through the Infinity data source (uid kukule-api).
Colours, units and thresholds are defined once here so the dashboards look consistent.
"""
import json
import pathlib

OUT = pathlib.Path(__file__).resolve().parent / "dashboards"
DS = {"type": "yesoreyeram-infinity-datasource", "uid": "kukule-api"}
import os
# Grafana runs in a Docker container; host.docker.internal is the Windows host (where the API listens on 127.0.0.1:8765).
API = os.environ.get("KUKULE_API_BASE", "http://host.docker.internal:8765")
NOTE = "Modelled study dataset (not observed CEB telemetry) - decision support only."

COL = {"Hybrid LP-DQN": "#3fb950", "Rolling LP": "#58a6ff", "DQN": "#f85149", "Reference rule (causal)": "#8b949e",
       "Reference rule (reads gauge)": "#d29922", "Perfect-foresight LP (bound)": "#bc8cff"}
METHODS = list(COL)
GREEN, AMBER, RED, BLUE, GREY = "#3fb950", "#d29922", "#f85149", "#58a6ff", "#8b949e"

_id = [0]


def nid():
    _id[0] += 1
    return _id[0]


def pos(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h}


# ----------------------------------------------------------------------------------------------- queries
def q(path, params=None, columns=None, ref="A", fmt="table", root=""):
    t = {"refId": ref, "datasource": DS, "type": "json", "source": "url", "url": API + path, "format": fmt, "parser": "backend",
         "root_selector": root, "url_options": {"method": "GET", "data": "", "body_type": "none", "headers": [],
                                                "params": [{"key": k, "value": v} for k, v in (params or [])]}}
    if columns:
        t["columns"] = [{"selector": s, "text": txt, "type": typ} for s, txt, typ in columns]
    return t


def steps(*pairs, base=None):
    """thresholds: steps((value, color), ...) with optional base colour for -inf."""
    out = [{"color": base or pairs[0][1], "value": None}]
    for v, c in (pairs[1:] if base is None else pairs):
        out.append({"color": c, "value": v})
    return {"mode": "absolute", "steps": out}


def fixed(color):
    return {"mode": "fixed", "fixedColor": color}


def color_override(name, color):
    return {"matcher": {"id": "byName", "options": name}, "properties": [{"id": "color", "value": fixed(color)}]}


def base_panel(kind, title, gp, targets, desc="", **kw):
    p = {"id": nid(), "type": kind, "title": title, "description": desc, "datasource": DS, "gridPos": gp, "targets": targets,
         "fieldConfig": {"defaults": {}, "overrides": []}, "options": {}, "transformations": []}
    p.update(kw)
    return p


# ----------------------------------------------------------------------------------------------- panel builders
def text(content, gp, title=""):
    return {"id": nid(), "type": "text", "title": title, "gridPos": gp, "transparent": True,
            "options": {"mode": "markdown", "content": content}}


def row(title, y):
    return {"id": nid(), "type": "row", "title": title, "collapsed": False, "gridPos": pos(0, y, 24, 1), "panels": []}


def stat(title, gp, path, params, field, unit="", decimals=None, th=None, mappings=None, desc="", text_mode="value", ftype="number",
         size=44, color_mode="background", title_size=15):
    p = base_panel("stat", title, gp, [q(path, params, [(field, field, ftype)])], desc)
    p["fieldConfig"]["defaults"] = {"unit": unit, "thresholds": th or steps((0, BLUE)), "mappings": mappings or [],
                                    "color": {"mode": "thresholds"}}
    if decimals is not None:
        p["fieldConfig"]["defaults"]["decimals"] = decimals
    p["options"] = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": f"/^{field}$/", "values": False}, "colorMode": color_mode,
                    "graphMode": "none", "textMode": text_mode, "justifyMode": "center", "orientation": "auto",
                    "text": {"titleSize": title_size, "valueSize": size}, "wideLayout": True}
    return p


def gauge(title, gp, path, params, field, lo, hi, th, unit="", decimals=None, desc=""):
    p = base_panel("gauge", title, gp, [q(path, params, [(field, field, "number")])], desc)
    p["fieldConfig"]["defaults"] = {"unit": unit, "min": lo, "max": hi, "thresholds": th, "color": {"mode": "thresholds"}}
    if decimals is not None:
        p["fieldConfig"]["defaults"]["decimals"] = decimals
    p["options"] = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": f"/^{field}$/", "values": False},
                    "showThresholdMarkers": True, "showThresholdLabels": False, "text": {"valueSize": 40, "titleSize": 14}}
    return p


def timeseries(title, gp, targets, unit="", desc="", overrides=None, lo=None, hi=None, fill=12, bars=False, transformations=None,
               legend="bottom", width=2, decimals=None, stepped=False):
    p = base_panel("timeseries", title, gp, targets, desc)
    d = {"unit": unit, "color": {"mode": "palette-classic"},
         "custom": {"drawStyle": "bars" if bars else "line", "lineWidth": width, "fillOpacity": fill, "showPoints": "never",
                    "spanNulls": True, "axisPlacement": "auto", "lineInterpolation": "stepAfter" if stepped else "linear",
                    "gradientMode": "none", "barAlignment": 0, "stacking": {"mode": "none"}}}
    if lo is not None:
        d["min"] = lo
    if hi is not None:
        d["max"] = hi
    if decimals is not None:
        d["decimals"] = decimals
    p["fieldConfig"]["defaults"] = d
    p["fieldConfig"]["overrides"] = overrides or []
    p["options"] = {"legend": {"displayMode": "list", "placement": legend, "showLegend": True, "calcs": []},
                    "tooltip": {"mode": "multi", "sort": "none"}}
    p["transformations"] = transformations or []
    return p


def line_style(name, color, dash=False, width=2, axis_right=False, bars=False, fill=0, hide_legend=False):
    props = [{"id": "color", "value": fixed(color)}, {"id": "custom.lineWidth", "value": width},
             {"id": "custom.fillOpacity", "value": fill}]
    if dash:
        props.append({"id": "custom.lineStyle", "value": {"fill": "dash", "dash": [8, 6]}})
    if axis_right:
        props += [{"id": "custom.axisPlacement", "value": "right"}]
    if bars:
        props += [{"id": "custom.drawStyle", "value": "bars"}, {"id": "custom.fillOpacity", "value": 70}]
    if hide_legend:
        props.append({"id": "custom.hideFrom", "value": {"legend": True, "tooltip": False, "viz": False}})
    return {"matcher": {"id": "byName", "options": name}, "properties": props}


def bars_by_method(title, gp, path, params, unit="", decimals=1, desc="", lo=None, hi=None):
    """Bar chart, one bar per method, fixed colour per method (stacked single-value columns from the API)."""
    p = base_panel("barchart", title, gp, [q(path, params)], desc)
    d = {"unit": unit, "decimals": decimals, "color": {"mode": "palette-classic"}, "custom": {"fillOpacity": 85, "lineWidth": 0, "gradientMode": "none"}}
    if lo is not None:
        d["min"] = lo
    if hi is not None:
        d["max"] = hi
    p["fieldConfig"]["defaults"] = d
    p["fieldConfig"]["overrides"] = [color_override(m, c) for m, c in COL.items()]
    p["options"] = {"xField": "method", "orientation": "horizontal", "stacking": "normal", "showValue": "always", "barWidth": 0.8,
                    "groupWidth": 0.8, "xTickLabelRotation": 0, "xTickLabelSpacing": 0, "fullHighlight": False,
                    "legend": {"showLegend": False, "displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "single"},
                    "text": {"valueSize": 14}}
    return p


def table(title, gp, targets, desc="", overrides=None, transformations=None, cell_color=False, font=14):
    p = base_panel("table", title, gp, targets, desc)
    p["fieldConfig"]["defaults"] = {"custom": {"align": "auto", "cellOptions": {"type": "color-background", "mode": "basic"} if cell_color else {"type": "auto"},
                                               "inspect": False, "filterable": False}, "color": {"mode": "thresholds"},
                                    "thresholds": steps((0, "transparent"))}
    p["fieldConfig"]["overrides"] = overrides or []
    p["options"] = {"showHeader": True, "cellHeight": "sm", "footer": {"show": False}}
    p["transformations"] = transformations or []
    cols = targets[0].get("columns") if targets else None
    if cols and not transformations:                    # keep the declared column order
        p["transformations"] = [{"id": "organize", "options": {"excludeByName": {}, "renameByName": {},
                                                                "indexByName": {c["text"]: i for i, c in enumerate(cols)}}}]
    return p


def col_override(field, unit=None, decimals=None, width=None, th=None, mappings=None, cell=None, name=None):
    props = []
    if name:
        props.append({"id": "displayName", "value": name})
    if unit is not None:
        props.append({"id": "unit", "value": unit})
    if decimals is not None:
        props.append({"id": "decimals", "value": decimals})
    if width:
        props.append({"id": "custom.width", "value": width})
    if th:
        props.append({"id": "thresholds", "value": th})
        props.append({"id": "color", "value": {"mode": "thresholds"}})
    if mappings:
        props.append({"id": "mappings", "value": mappings})
    if cell:
        props.append({"id": "custom.cellOptions", "value": cell})
    return {"matcher": {"id": "byName", "options": field}, "properties": props}


def vmap(**kv):
    """value mappings: vmap(OK=GREEN, REJECTED=RED)"""
    return [{"type": "value", "options": {k: {"text": k, "color": c, "index": i} for i, (k, c) in enumerate(kv.items())}}]


def nmap(*items):
    """numeric value mappings: nmap((0,'OK',GREEN), (1,'WATCH',AMBER))"""
    return [{"type": "value", "options": {str(v): {"text": t, "color": c, "index": i} for i, (v, t, c) in enumerate(items)}}]


def var_custom(name, label, options, default, multi=False, include_all=False):
    """options: list of (text, value)."""
    q_ = ",".join(f"{t} : {v}" for t, v in options)
    cur_val = default if isinstance(default, list) else [default]
    texts = [t for t, v in options if v in cur_val]
    return {"type": "custom", "name": name, "label": label, "query": q_, "multi": multi, "includeAll": include_all,
            "current": {"selected": True, "text": texts if multi else texts[0], "value": cur_val if multi else cur_val[0]},
            "options": [{"selected": v in cur_val, "text": t, "value": v} for t, v in options], "hide": 0, "skipUrlSync": False}


def var_text(name, label, default):
    return {"type": "textbox", "name": name, "label": label, "query": str(default), "current": {"text": str(default), "value": str(default)},
            "options": [{"selected": True, "text": str(default), "value": str(default)}], "hide": 0}


def relayout(panels):
    """Stack panels top to bottom: panels sharing an original y form a band; the band height is the tallest panel."""
    bands = {}
    for p in panels:
        bands.setdefault(p["gridPos"]["y"], []).append(p)
    y = 0
    for oy in sorted(bands):
        h = max(p["gridPos"]["h"] for p in bands[oy])
        for p in bands[oy]:
            p["gridPos"]["y"] = y
        y += h
    return panels


def dashboard(uid, title, panels, variables=None, time=("now", "now"), refresh="", tags=None, links=None, desc=""):
    return {"uid": uid, "title": title, "description": desc, "tags": tags or ["kukule", "component3"], "timezone": "utc", "editable": True,
            "graphTooltip": 1, "schemaVersion": 39, "version": 1, "refresh": refresh, "time": {"from": time[0], "to": time[1]},
            "templating": {"list": variables or []}, "annotations": {"list": []}, "links": links or [], "panels": relayout(panels),
            "style": "dark", "liveNow": False, "fiscalYearStartMonth": 0, "weekStart": ""}


NAV = [{"title": "1 Live plan & what-if", "type": "link", "url": "/d/kg-live", "icon": "dashboard", "targetBlank": False},
       {"title": "2 Results & robustness", "type": "link", "url": "/d/kg-results", "icon": "dashboard", "targetBlank": False},
       {"title": "3 Scenario explorer", "type": "link", "url": "/d/kg-scen", "icon": "dashboard", "targetBlank": False}]


# ================================================================================================= dashboard 1
PLAN_P = [("storage_pct", "${storage_pct}"), ("inflow_scale", "${inflow_scale}"), ("p90_scale", "${p90_scale}"),
          ("demand_scale", "${demand_scale}"), ("units", "${units}"), ("method", "${method}"), ("source", "${source}")]
TIME_COL = ("time", "time", "timestamp_epoch")


def d1():
    P = []
    P.append(text(f"## Kukule Ganga - release & generation plan\n**Change any value in the bar above and every panel re-runs the model.** "
                  f"*Starting storage*, *inflow vs forecast* (wet/dry), *demand vs forecast*, *units available* and the *method* are the inputs. "
                  f"*Source = Live files* plans from the daily-runner inbox (`data/live_inputs`).  \n_{NOTE}_", pos(0, 0, 24, 4)))
    P.append(row("Today's decision", 4))
    th_store = steps((0, RED), (20, AMBER), (50, GREEN))
    P += [stat("Turbine release today", pos(0, 5, 4, 5), "/plan/summary", PLAN_P, "release_m3s", "m3/s", 1, steps((0, BLUE)),
               desc="Recommended turbine discharge for day 1 of the plan."),
          stat("Generation today", pos(4, 5, 4, 5), "/plan/summary", PLAN_P, "generation_mwh", "MWh", 0, steps((0, BLUE)),
               desc="Expected energy for day 1 (station maximum 1,680 MWh/day)."),
          stat("Storage at end of day", pos(8, 5, 4, 5), "/plan/summary", PLAN_P, "end_storage_pct", "percent", 0, th_store,
               desc="Active storage after day 1. Red < 20% reserve, amber < 50% year-end target, green otherwise."),
          stat("Pond level", pos(12, 5, 4, 5), "/plan/summary", PLAN_P, "level_masl", "lengthm", 2, steps((0, RED), (204.35, AMBER), (204.9, GREEN)),
               desc="Pond level after day 1. Hard floor 204.00 masl, full supply level 206.00 masl."),
          stat("Mandatory river release", pos(16, 5, 4, 5), "/plan/summary", PLAN_P, "mandatory_m3s", "m3/s", 1, steps((0, GREY)),
               desc="Environmental flow (2 m3/s) plus the seasonal irrigation release; served first, never counted as spill."),
          stat("Alert status", pos(20, 5, 4, 5), "/plan/summary", PLAN_P, "alert_level", "", 0, steps((0, GREEN), (1, AMBER), (2, RED)),
               nmap((0, "OK", GREEN), (1, "WATCH", AMBER), (2, "ALERT", RED)), desc="OK = no warnings; WATCH = flood risk or plan ends below target; ALERT = reserve or river-release shortfall.")]
    P.append(stat("What the model is warning about", pos(0, 10, 24, 3), "/plan/summary", PLAN_P, "alert_text", "", None, steps((0, GREY)),
                  text_mode="value", ftype="string", size=22, color_mode="none", title_size=14))
    P += [stat("Energy over the next 15 days", pos(0, 13, 6, 4), "/plan/summary", PLAN_P, "plan_energy_mwh", "MWh", 0, steps((0, BLUE)), size=36),
          stat("Lowest storage in the plan", pos(6, 13, 6, 4), "/plan/summary", PLAN_P, "min_storage_pct", "percent", 0, th_store, size=36,
               desc="Never below the 20% operating reserve unless the river release forces it."),
          stat("Days below the 20% reserve", pos(12, 13, 6, 4), "/plan/summary", PLAN_P, "reserve_breach_days", "", 0, steps((0, GREEN), (1, AMBER)), size=36),
          stat("Hard-floor breaches (204.00 masl)", pos(18, 13, 6, 4), "/plan/summary", PLAN_P, "floor_breach_days", "", 0, steps((0, GREEN), (1, RED)), size=36,
               desc="Must be 0: the safety layer never lets the pond go below the floor.")]
    P.append(row("15-day plan", 17))
    P.append(timeseries("Turbine release vs forecast inflow (m3/s)", pos(0, 18, 12, 9),
                        [q("/plan", PLAN_P, [TIME_COL, ("inflow_p50_m3s", "Forecast inflow (median)", "number"),
                                              ("release_m3s", "Turbine release", "number"),
                                              ("spill_m3s", "Spill", "number"), ("mandatory_m3s", "River release", "number")])],
                        "m3/s", "The plan releases water through the turbines and always keeps the river release. The dashed line is the median inflow forecast (the P90 flood risk is summarised by the alert status).",
                        [line_style("Forecast inflow (median)", GREY, dash=True), line_style("Turbine release", GREEN, width=3, fill=15),
                         line_style("Spill", RED, bars=True), line_style("River release", BLUE, width=1)], lo=0))
    P.append(timeseries("Storage vs reserve and year-end target (%)", pos(12, 18, 12, 9),
                        [q("/plan", PLAN_P, [TIME_COL, ("storage_pct", "Storage at end of day", "number"), ("reserve_pct", "Operating reserve (20%)", "number"),
                                              ("target_pct", "Year-end target (50%)", "number")])],
                        "percent", "Active storage after each day. It should stay above the reserve line and finish near the target.",
                        [line_style("Storage at end of day", BLUE, width=3, fill=20), line_style("Operating reserve (20%)", RED, dash=True, width=2),
                         line_style("Year-end target (50%)", GREEN, dash=True, width=2)], lo=0, hi=100))
    P.append(timeseries("Daily generation (MWh) and demand weight", pos(0, 27, 12, 9),
                        [q("/plan", PLAN_P, [TIME_COL, ("generation_mwh", "Generation", "number"), ("demand_weight", "Demand weight (right axis)", "number")])],
                        "MWh", "Energy is worth more on high-demand days (weight > 1: festivals, weekdays). The plan shifts water towards them within the pond's limits.",
                        [line_style("Generation", GREEN, bars=True), line_style("Demand weight (right axis)", AMBER, width=3, axis_right=True)], lo=0))
    P.append(timeseries("Pond level (masl) vs hard floor and full supply level", pos(12, 27, 12, 9),
                        [q("/plan", PLAN_P, [TIME_COL, ("level_masl", "Pond level", "number"), ("floor_masl", "Hard floor 204.00", "number"),
                                              ("fsl_masl", "Full supply level 206.00", "number")])],
                        "lengthm", "Pond water level after each day.",
                        [line_style("Pond level", BLUE, width=3, fill=15), line_style("Hard floor 204.00", RED, dash=True), line_style("Full supply level 206.00", GREEN, dash=True)],
                        lo=203.8, hi=206.2, decimals=2))
    P.append(row("Method comparison on these inputs", 36))
    mp = [("metric", "plan_energy_mwh")] + PLAN_P
    P.append(bars_by_method("Day-1 turbine release by method (m3/s)", pos(0, 37, 8, 8), "/plan/methods_chart", [("metric", "day1_release_m3s")] + PLAN_P, "m3/s", decimals=1,
                            desc="What each method would release today."))
    P.append(bars_by_method("Energy over the 15-day plan (MWh)", pos(8, 37, 8, 8), "/plan/methods_chart", mp, "MWh", decimals=0, lo=0,
                            desc="Energy differs by only a few percent between methods; the differences that matter are storage and safety."))
    P.append(bars_by_method("Storage at end of the plan (%)", pos(16, 37, 8, 8), "/plan/methods_chart", [("metric", "final_storage_pct")] + PLAN_P, "percent", decimals=0, lo=0, hi=100,
                            desc="Year-end target is 50%. The reference rule drains the pond to the reserve."))
    P.append(table("Safety and efficiency check by method", pos(0, 45, 24, 7),
                   [q("/plan/methods", PLAN_P, [("method", "Method", "string"), ("day1_release_m3s", "Day-1 release (m3/s)", "number"),
                                                 ("plan_energy_mwh", "Energy 15 d (MWh)", "number"), ("final_storage_pct", "End storage (%)", "number"),
                                                 ("min_storage_pct", "Lowest storage (%)", "number"), ("avoidable_spill_mcm", "Avoidable spill (MCM)", "number"),
                                                 ("reserve_breach_days", "Days below reserve", "number"), ("unmet_days", "River-release shortfall days", "number"),
                                                 ("floor_breach_days", "Floor breaches", "number")])],
                   "Every method runs through the same safety layer: floor breaches must be 0.",
                   [col_override("Floor breaches", th=steps((0, GREEN), (1, RED)), cell={"type": "color-background", "mode": "basic"}),
                    col_override("Days below reserve", th=steps((0, GREEN), (1, AMBER)), cell={"type": "color-background", "mode": "basic"}),
                    col_override("River-release shortfall days", th=steps((0, GREEN), (1, AMBER)), cell={"type": "color-background", "mode": "basic"}),
                    col_override("Energy 15 d (MWh)", decimals=0), col_override("Day-1 release (m3/s)", decimals=1)]))
    P.append(table("15-day schedule (selected method)", pos(0, 51, 24, 10),
                   [q("/plan", PLAN_P, [("date", "Date", "string"), ("day", "Day", "number"), ("release_m3s", "Release (m3/s)", "number"),
                                         ("spill_m3s", "Spill (m3/s)", "number"), ("mandatory_m3s", "River release (m3/s)", "number"),
                                         ("storage_pct", "Storage (%)", "number"), ("level_masl", "Level (masl)", "number"),
                                         ("generation_mwh", "Generation (MWh)", "number"), ("demand_weight", "Demand weight", "number"),
                                         ("inflow_p50_m3s", "Inflow median (m3/s)", "number"), ("inflow_p90_m3s", "Inflow P90 (m3/s)", "number")])],
                   "The exact numbers behind the charts.",
                   [col_override("Storage (%)", unit="percent", decimals=0, th=steps((0, RED), (20, AMBER), (50, GREEN)), cell={"type": "color-text"}),
                    col_override("Level (masl)", decimals=2), col_override("Release (m3/s)", decimals=1), col_override("Spill (m3/s)", decimals=1),
                    col_override("River release (m3/s)", decimals=1), col_override("Generation (MWh)", decimals=0), col_override("Demand weight", decimals=2),
                    col_override("Inflow median (m3/s)", decimals=1), col_override("Inflow P90 (m3/s)", decimals=1), col_override("Day", width=60)]))
    P.append(row("Live operations (daily runner)", 60))
    P += [stat("Input files", pos(0, 61, 4, 4), "/live/status", [], "inbox_status", "", None, steps((0, GREEN)),
               vmap(VALID=GREEN, REJECTED=RED), ftype="string", size=30, desc="Validation of data/live_inputs (forecasts + state.json)."),
          stat("Minutes since last plan", pos(4, 61, 4, 4), "/live/status", [], "minutes_since_last_plan", "m", 0, steps((0, GREEN), (1500, AMBER), (2880, RED)), size=36,
               desc="Time since the daily runner last produced a plan."),
          stat("Plans made", pos(8, 61, 4, 4), "/live/status", [], "plans_made", "", 0, steps((0, BLUE)), size=36),
          stat("Inputs rejected", pos(12, 61, 4, 4), "/live/status", [], "plans_rejected", "", 0, steps((0, GREEN), (1, AMBER)), size=36,
               desc="Bad or stale input files are rejected (and logged) instead of being used."),
          stat("Last recommended release", pos(16, 61, 4, 4), "/live/status", [], "last_release_m3s", "m3/s", 1, steps((0, BLUE)), size=36),
          stat("Last recommended generation", pos(20, 61, 4, 4), "/live/status", [], "last_generation_mwh", "MWh", 0, steps((0, BLUE)), size=36)]
    P.append(stat("Input check message", pos(0, 65, 24, 3), "/live/status", [], "inbox_message", "", None, steps((0, GREY)), ftype="string", size=18,
                  color_mode="none", text_mode="value", title_size=14))
    lg = base_panel("barchart", "Accepted plans: recommended release and expected storage (one group per plan)", pos(0, 68, 12, 9),
                    [q("/live/log", [("limit", "12"), ("order", "asc")],
                       [("timestamp", "Plan time", "string"), ("status", "Status", "string"), ("turbine_release_m3s", "Recommended release (m3/s)", "number"),
                        ("expected_end_storage_pct", "Expected end storage (%)", "number")])],
                    "One group of bars per daily-runner check (outputs/live/decision_log.csv); rejected inputs have no bars.")
    lg["transformations"] = [{"id": "filterByValue", "options": {"type": "exclude", "match": "any", "filters": [
        {"fieldName": "Status", "config": {"id": "equal", "options": {"value": "REJECTED"}}}]}}]
    lg["fieldConfig"] = {"defaults": {"decimals": 1, "color": {"mode": "palette-classic"}, "custom": {"fillOpacity": 85, "lineWidth": 0}},
                         "overrides": [color_override("Recommended release (m3/s)", GREEN), color_override("Expected end storage (%)", BLUE)]}
    lg["options"] = {"xField": "Plan time", "orientation": "vertical", "stacking": "none", "showValue": "auto", "barWidth": 0.9, "groupWidth": 0.8,
                     "xTickLabelRotation": -45, "legend": {"showLegend": True, "displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "single"}}
    P.append(lg)
    P.append(table("Decision log (newest first)", pos(12, 68, 12, 9),
                   [q("/live/log", [("limit", "30")], [("timestamp", "Time", "string"), ("status", "Status", "string"), ("turbine_release_m3s", "Release (m3/s)", "number"),
                                                         ("generation_mwh", "Generation (MWh)", "number"), ("storage_pct", "Start storage (%)", "number"),
                                                         ("message", "Reason / note", "string")])],
                   "PLANNED = accepted inputs and a new plan; REJECTED = bad or stale input (reason shown); previous plan stays valid.",
                   [col_override("Status", mappings=vmap(PLANNED=GREEN, REJECTED=RED), cell={"type": "color-background", "mode": "basic"}, width=105),
                    col_override("Time", width=160), col_override("Reason / note", width=420),
                    col_override("Release (m3/s)", decimals=1), col_override("Generation (MWh)", decimals=0), col_override("Start storage (%)", decimals=0)]))
    vars_ = [var_text("storage_pct", "Starting storage (%)", 60),
             var_custom("inflow_scale", "Inflow vs forecast (x)", [("0.3 (very dry)", "0.3"), ("0.5", "0.5"), ("0.7", "0.7"), ("1.0 (as forecast)", "1"), ("1.3", "1.3"),
                                                                    ("1.6", "1.6"), ("2.0", "2"), ("2.5 (very wet)", "2.5")], "1"),
             var_custom("p90_scale", "Forecast spread (x)", [("0.5", "0.5"), ("1.0", "1"), ("1.5", "1.5"), ("2.0", "2")], "1"),
             var_custom("demand_scale", "Demand vs forecast (x)", [("0.8", "0.8"), ("0.9", "0.9"), ("1.0", "1"), ("1.1", "1.1"), ("1.2", "1.2"), ("1.3", "1.3")], "1"),
             var_custom("units", "Units available", [("2 units", "2"), ("1 unit", "1"), ("0 (outage)", "0")], "2"),
             var_custom("method", "Method", [("Hybrid LP-DQN", "hybrid"), ("DQN", "dqn"), ("Rolling LP", "rolling_lp"), ("Reference rule", "reference")], "hybrid"),
             var_custom("source", "Source", [("What-if inputs", "whatif"), ("Live files (inbox)", "live")], "whatif")]
    return dashboard("kg-live", "1 - Live plan & what-if", P, vars_, time=("now/d", "now/d+15d"), refresh="30s", links=NAV,
                     desc="Today's decision and 15-day plan. Change the variables to re-run the model.")


# ================================================================================================= dashboard 2
def matrix(row_field, col_field, value_field):
    return [{"id": "groupingToMatrix", "options": {"columnField": col_field, "rowField": row_field, "valueField": value_field, "emptyValue": "null"}}]


def d2():
    P = []
    P.append(text(f"## Results & robustness\nAll methods are tested on the same 9 stress scenarios x 3 forecast-noise seeds (27 cases), through the same safety layer. "
                  f"The **hybrid LP-DQN** keeps the pond healthier and handles the drought best; raw energy differs by under 1% between the good methods "
                  f"(the pond holds only about 0.4 day of flow), so the story is *storage, drought handling and robustness*.  \n_{NOTE}_", pos(0, 0, 24, 4)))
    P.append(row("Headline", 4))
    def tile(x, title, method, field, unit, dec, th, desc=""):
        p = stat(title, pos(x, 5, 4, 5), "/table/scoreboard", [("method", method)], field, unit, dec, th, desc=desc, size=40)
        return p
    P += [tile(0, "Hybrid score", "Hybrid LP-DQN", "episode_score", "", 1, steps((0, GREEN)), "Higher is better (energy minus penalties for spill, reserve, river shortfall, year-end shortfall)."),
          tile(4, "Rolling LP score", "Rolling LP", "episode_score", "", 1, steps((0, BLUE)), "The strong forecast-driven LP benchmark."),
          tile(8, "Upper-bound score", "Perfect-foresight LP (bound)", "episode_score", "", 1, steps((0, "#bc8cff")), "Knows the future inflow: not deployable, shows the ceiling."),
          tile(12, "Hybrid year-end MCM", "Hybrid LP-DQN", "terminal_storage_mcm", "", 2, steps((0, RED), (0.5, AMBER), (0.835, GREEN)), "Target 0.835 MCM (50%)."),
          tile(16, "Hybrid constraints met", "Hybrid LP-DQN", "constraint_satisfaction_pct", "percent", 1, steps((0, RED), (95, AMBER), (98.5, GREEN))),
          stat("Safety violations", pos(20, 5, 4, 5), "/table/constraint_audit", [("method", "Hybrid LP-DQN")], "floor_breach_days", "", 0, steps((0, GREEN), (1, RED)),
               desc="Across all evaluation runs of every method: 0 floor breaches and 0 mass-balance violations.", size=40)]
    P.append(row("Method scoreboard (mean of 27 cases)", 10))
    P.append(bars_by_method("Composite score (higher is better)", pos(0, 11, 8, 8), "/chart/by_method", [("metric", "episode_score")], "", 1,
                            desc="Demand-weighted energy minus penalties for spill, reserve breaches, river-release shortfall and year-end shortfall."))
    P.append(bars_by_method("Storage left at year end (MCM, target 0.835)", pos(8, 11, 8, 8), "/chart/by_method", [("metric", "terminal_storage_mcm")], "", 2, lo=0,
                            desc="The old DQN ended the year empty; every v2 method keeps the reserve, the rolling LP and hybrid also approach the 50% target."))
    P.append(bars_by_method("Avoidable spill (MCM)", pos(16, 11, 8, 8), "/chart/by_method", [("metric", "spill_avoidable_mcm")], "", 2, lo=0,
                            desc="Water spilled while the turbines could have taken it (lower is better)."))
    P.append(bars_by_method("Days with river-release shortfall (mean per case)", pos(0, 19, 8, 8), "/chart/by_method", [("metric", "unmet_mandatory_days")], "", 1, lo=0,
                            desc="Environmental / irrigation release that could not be met (mostly in the drought scenario)."))
    P.append(bars_by_method("Days below the 20% reserve (% of days)", pos(8, 19, 8, 8), "/chart/by_method", [("metric", "reserve_breach_pct")], "", 1, lo=0))
    P.append(bars_by_method("Decision time (ms per decision)", pos(16, 19, 8, 8), "/chart/by_method", [("metric", "decision_latency_ms_mean")], "", 2, lo=0,
                            desc="All methods decide in a few milliseconds - fast enough for real-time use."))
    P.append(table("Full scoreboard", pos(0, 27, 24, 9),
                   [q("/table/scoreboard", [], [("method", "Method", "string"), ("energy_gwh", "Energy (GWh/yr)", "number"), ("storage_adjusted_energy_gwh", "Energy + stored water (GWh)", "number"),
                                                 ("episode_score", "Composite score", "number"), ("spill_mcm", "Spill (MCM)", "number"),
                                                 ("spill_avoidable_mcm", "Avoidable spill (MCM)", "number"), ("terminal_storage_mcm", "Year-end storage (MCM)", "number"),
                                                 ("terminal_target_met_pct", "Year-end target met (%)", "number"), ("constraint_satisfaction_pct", "Constraints satisfied (%)", "number"),
                                                 ("reserve_breach_pct", "Days below reserve (%)", "number"), ("unmet_mandatory_days", "River shortfall days", "number")])],
                   "Mean over 9 scenarios x 3 forecast-noise seeds, initial storage 50%.",
                   [col_override("Method", width=230)] + [col_override(f, decimals=d) for f, d in
                                                           (("Energy (GWh/yr)", 1), ("Energy + stored water (GWh)", 1), ("Composite score", 1), ("Spill (MCM)", 0),
                                                            ("Avoidable spill (MCM)", 1), ("Year-end storage (MCM)", 2), ("Year-end target met (%)", 0),
                                                            ("Constraints satisfied (%)", 1), ("Days below reserve (%)", 1), ("River shortfall days", 1))]))
    P.append(row("Where each method wins or loses (composite score by scenario)", 35))
    order = ["scenario\\method"] + ["Hybrid LP-DQN", "Rolling LP", "DQN", "Reference rule (reads gauge)", "Reference rule (causal)", "Perfect-foresight LP (bound)"]
    hm = table("Scenario x method heat-map (composite score)", pos(0, 36, 24, 12),
               [q("/table/heatmap", [], [("scenario", "scenario", "string"), ("method", "method", "string"), ("episode_score", "episode_score", "number")])],
               "Green = better. The El Nino drought separates the methods most; in normal scenarios they are close.",
               [col_override("scenario\\method", width=300, cell={"type": "auto"}, name="Scenario")],
               matrix("scenario", "method", "episode_score") +
               [{"id": "sortBy", "options": {"fields": {}, "sort": [{"field": "scenario\\method"}]}}] +
               [{"id": "organize", "options": {"excludeByName": {}, "renameByName": {}, "indexByName": {c: i for i, c in enumerate(order)}}}])
    hm["fieldConfig"]["defaults"] = {"custom": {"align": "center", "cellOptions": {"type": "color-background", "mode": "gradient"}}, "decimals": 1,
                                     "color": {"mode": "continuous-RdYlGr"}, "min": -230, "max": 60, "thresholds": steps((0, "transparent"))}
    P.append(hm)
    P.append(row("Robustness across training seeds (5 hybrid seeds, 4 DQN seeds)", 47))
    P.append(table("Mean and spread across training seeds", pos(0, 48, 12, 7),
                   [q("/table/multiseed", [], [("method", "Method", "string"), ("n_seeds", "Seeds", "number"), ("episode_score_mean", "Score (mean)", "number"),
                                               ("score_std", "Score (std)", "number"), ("storage_adjusted_energy_gwh_mean", "Energy (GWh, mean)", "number"),
                                               ("energy_std", "Energy (std)", "number"), ("unmet_mandatory_days_mean", "Shortfall days", "number")])],
                   "Standard deviation across independently trained models: the hybrid is steady, the plain DQN varies more.",
                   [col_override("Method", width=210), col_override("Seeds", width=60)] + [col_override(f, decimals=2) for f in
                                                                                         ("Score (mean)", "Score (std)", "Energy (GWh, mean)", "Energy (std)", "Shortfall days")]))
    P.append(table("Paired test against the rolling LP (positive = better)", pos(12, 48, 12, 7),
                   [q("/table/paired_tests", [], [("method", "Method", "string"), ("metric", "Metric", "string"), ("mean_diff_vs_rolling_lp", "Mean difference", "number"),
                                                  ("t_test_p(seeds)", "p-value (seeds)", "number"), ("win_rate_cases_%", "Cases won (%)", "number"),
                                                  ("seeds_better_than_LP", "Seeds better", "number"), ("significant_5pct", "Significant (5%)", "string")])],
                   "Hybrid beats the rolling LP in all 5 seeds on energy and river shortfall; plain DQN does not.",
                   [col_override("Mean difference", decimals=3), col_override("p-value (seeds)", decimals=4), col_override("Cases won (%)", decimals=0),
                    col_override("Significant (5%)", mappings=vmap(yes=GREEN, no=GREY), cell={"type": "color-background", "mode": "basic"}, width=120),
                    col_override("Method", width=130)]))
    sp = base_panel("barchart", "Composite score of every trained model (one bar per training seed)", pos(0, 55, 24, 8),
                    [q("/table/seed_points", [], [("method", "method", "string"), ("seed_label", "seed_label", "string"), ("episode_score", "episode_score", "number")])],
                    "Each bar is one independently trained model on the same 27 test cases.")
    sp["transformations"] = matrix("seed_label", "method", "episode_score")
    sp["fieldConfig"] = {"defaults": {"unit": "", "decimals": 1, "color": {"mode": "palette-classic"}, "custom": {"fillOpacity": 85, "lineWidth": 0}},
                         "overrides": [color_override(m, c) for m, c in COL.items()]}
    sp["options"] = {"xField": "seed_label\\method", "orientation": "vertical", "stacking": "none", "showValue": "auto", "barWidth": 0.9, "groupWidth": 0.8,
                     "legend": {"showLegend": True, "displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "single"}, "xTickLabelRotation": 0}
    P.append(sp)
    P.append(row("Policy adaptation (regime shift: drought + biased forecasts from day 150)", 63))
    ad = bars_by_method("Composite score after the regime shift (higher is better)", pos(0, 64, 10, 9), "/table/adaptation", [], "", 1,
                        desc="Hybrid with online fine-tuning vs frozen hybrid vs the rolling LP.")
    ad["targets"] = [q("/chart/by_method", [("metric", "episode_score"), ("source", "adaptation")])]
    ad["fieldConfig"]["overrides"] = [color_override("Hybrid (frozen)", "#2f8f46"), color_override("Hybrid (adapted)", GREEN), color_override("Rolling LP", COL["Rolling LP"]),
                                      color_override("Perfect-foresight LP (bound)", COL["Perfect-foresight LP (bound)"])]
    P.append(ad)
    P.append(table("Fine-tuning rounds (accepted only if safe)", pos(10, 64, 14, 9),
                   [q("/table/adaptation_events", [], [("day", "Day", "number"), ("recent_old", "Recent score (current)", "number"), ("recent_new", "Recent score (fine-tuned)", "number"),
                                                       ("guard_old", "Guard set (current)", "number"), ("guard_new", "Guard set (fine-tuned)", "number"), ("accepted", "Accepted", "string")])],
                   "A fine-tuned model is deployed only if it helps on the last 60 days and does not lose more than 6 points on the guard scenarios.",
                   [col_override("Accepted", mappings=vmap(**{"true": GREEN, "false": GREY, "True": GREEN, "False": GREY}), cell={"type": "color-background", "mode": "basic"}, width=100)] +
                   [col_override(f, decimals=1) for f in ("Recent score (current)", "Recent score (fine-tuned)", "Guard set (current)", "Guard set (fine-tuned)")]))
    P.append(row("Training progress and safety audit", 73))
    tr = base_panel("trend", "Validation score during training (mean of seeds, with lowest/highest seed)", pos(0, 74, 14, 9),
                    [q("/table/training_summary", [])],
                    "Validation score during training; hybrid (green) versus plain DQN (red), solid = mean over training seeds, dashed = lowest and highest seed.")
    ov_tr = []
    for kind, colr in (("Hybrid LP-DQN", GREEN), ("DQN", RED)):
        ov_tr += [line_style(f"{kind} (mean)", colr, width=3),
                  line_style(f"{kind} (lowest seed)", colr, dash=True, width=1),
                  line_style(f"{kind} (highest seed)", colr, dash=True, width=1)]
    tr["fieldConfig"] = {"defaults": {"unit": "none", "decimals": 0, "custom": {"lineWidth": 2, "fillOpacity": 0, "showPoints": "never", "spanNulls": True},
                                      "color": {"mode": "palette-classic"}}, "overrides": ov_tr}
    tr["options"] = {"xField": "steps", "legend": {"showLegend": True, "displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi", "sort": "none"}}
    P.append(tr)
    P.append(table("Hard-constraint audit over all evaluation runs", pos(14, 74, 10, 9),
                   [q("/table/constraint_audit", [], [("method", "Method", "string"), ("runs", "Runs", "number"), ("floor_breach_days", "Floor breach days", "number"),
                                                       ("mass_balance_violation_days", "Mass-balance violation days", "number")])],
                   "Every method, every scenario: the 204.00 masl floor was never breached and water balance always closed.",
                   [col_override("Floor breach days", th=steps((0, GREEN), (1, RED)), cell={"type": "color-background", "mode": "basic"}),
                    col_override("Mass-balance violation days", th=steps((0, GREEN), (1, RED)), cell={"type": "color-background", "mode": "basic"}),
                    col_override("Method", width=230)]))
    return dashboard("kg-results", "2 - Results & robustness", P, [], time=("now-6h", "now"), links=NAV, desc="Method comparison, seeds, adaptation, training.")


# ================================================================================================= dashboard 3
SCEN = [("Normal year (held-out)", "test_year_real_sim"), ("El Nino drought (270 days)", "drought_el_nino"), ("Flood year (3 extreme storms)", "flood_year"),
        ("Flood over Vesak week", "vesak_flood"), ("Dry spell over Christmas", "dry_christmas"), ("Forecasts 40% too wet", "forecast_bias_high"),
        ("Forecasts 40% too dry", "forecast_bias_low"), ("Very wide forecast spread", "wide_forecast_spread"), ("Unit outages", "double_outage")]
MID = [("Hybrid LP-DQN", "hybrid"), ("Rolling LP", "rolling_lp"), ("DQN", "dqn"), ("Reference rule (causal)", "reference"),
       ("Reference rule (reads gauge)", "reference_gauge"), ("Perfect-foresight LP (bound)", "omniscient_lp")]


def d3():
    P = []
    SP = [("scenario_id", "${scenario}"), ("methods", "${methods:csv}"), ("smooth", "${smooth}")]
    P.append(text(f"## Scenario explorer\nPick a **scenario** and the **methods** to compare at the top. Each curve is one full year (2025-10-19 to 2026-10-18) of daily operation, starting at 50% storage. "
                  f"Watch the *storage* chart: good operation stays above the 20% reserve and finishes near the 50% target.  \n_{NOTE}_", pos(0, 0, 24, 4)))
    kp = ["scenario_id", "method_id"]
    P.append(table("Year summary for the selected scenario", pos(0, 4, 24, 6),
                   [q("/table/scenario_kpis", [("scenario_id", "${scenario}"), ("method_id", "${methods:csv}")],
                      [("method", "Method", "string"), ("energy_gwh", "Energy (GWh)", "number"), ("episode_score", "Composite score", "number"),
                       ("spill_mcm", "Spill (MCM)", "number"), ("spill_avoidable_mcm", "Avoidable spill", "number"),
                       ("terminal_storage_mcm", "Year-end MCM", "number"), ("min_storage_pct", "Lowest storage %", "number"),
                       ("reserve_breach_pct", "Below reserve %", "number"), ("unmet_mandatory_days", "River short days", "number"),
                       ("constraint_satisfaction_pct", "Constraints OK %", "number")])],
                   "Same simulator and safety layer for every method.",
                   [col_override("Method", width=230), col_override("Year-end MCM", decimals=2, th=steps((0, RED), (0.5, AMBER), (0.835, GREEN)), cell={"type": "color-text"})] +
                   [col_override(f, decimals=1) for f in ("Energy (GWh)", "Composite score", "Spill (MCM)", "Avoidable spill", "Lowest storage %",
                                                          "Below reserve %", "River short days", "Constraints OK %")]))
    conv = [{"id": "convertFieldType", "options": {"conversions": [{"targetField": "time", "destinationType": "time"}], "fields": {}}}]
    ov = [line_style(m, c, width=2) for m, c in COL.items()]

    def series(title, metric, unit, gp, desc="", lo=None, hi=None, extra=None, fill=0):
        t = timeseries(title, gp, [q("/scenario/series", SP + [("metric", metric)])], unit, desc, list(ov) + (extra or []), lo=lo, hi=hi, transformations=conv, fill=fill)
        return t
    ref_inflow = timeseries("River inflow (m3/s) - what the system had to handle", pos(0, 11, 12, 8),
                            [q("/scenario/reference", [("scenario_id", "${scenario}")])], "m3/s", "True simulated inflow for the scenario (not known in advance).",
                            [line_style("inflow_m3s", BLUE, width=2, fill=20)], lo=0, transformations=conv)
    ref_inflow["targets"] = [q("/scenario/reference", [("scenario_id", "${scenario}")], [TIME_COL, ("inflow_m3s", "River inflow", "number")])]
    ref_inflow["fieldConfig"]["overrides"] = [line_style("River inflow", BLUE, width=2, fill=20)]
    ref_inflow["transformations"] = []
    ref_w = timeseries("Demand weight (festival peaks: Vesak, Christmas, year-end)", pos(12, 11, 12, 8),
                       [q("/scenario/reference", [("scenario_id", "${scenario}")], [TIME_COL, ("weight", "Demand weight", "number")])], "", "Above 1 = energy is worth more that day.",
                       [line_style("Demand weight", "#d29922", width=2, fill=15)], lo=0.8, hi=1.25, decimals=2)
    P += [ref_inflow, ref_w]
    st = series("Storage at end of day (%, moving average)", "storage_pct", "percent", pos(0, 19, 24, 10),
                "Good operation stays above the red dashed line (20% reserve) and finishes near the green dashed line (50% target).", lo=0, hi=100,
                extra=[line_style("Operating reserve (20%)", RED, dash=True, width=2), line_style("Year-end target (50%)", GREEN, dash=True, width=2)])
    st["targets"] = [q("/scenario/series", SP + [("metric", "storage_pct"), ("ref_lines", "1")])]
    P.append(st)
    P.append(series("Generation (MWh/day, moving average)", "generation_mwh", "MWh", pos(0, 29, 12, 8), lo=0))
    P.append(series("Turbine release (m3/s, moving average)", "release_m3s", "m3/s", pos(12, 29, 12, 8), lo=0))
    P.append(series("Spill over the weir (m3/s, moving average)", "spill_m3s", "m3/s", pos(0, 37, 12, 8), "Spill = water lost without generating; mostly unavoidable in floods.", lo=0))
    P.append(series("River-release shortfall (m3/s, moving average)", "unmet_release_m3s", "m3/s", pos(12, 37, 12, 8),
                    "Environmental/irrigation release that could not be met because the river itself was too low.", lo=0))
    vars_ = [var_custom("scenario", "Scenario", SCEN, "drought_el_nino"),
             var_custom("smooth", "Moving average (days)", [("none (daily)", "1"), ("3 days", "3"), ("7 days", "7"), ("14 days", "14")], "7"),
             var_custom("methods", "Methods", MID, ["hybrid", "rolling_lp", "reference_gauge"], multi=True)]
    return dashboard("kg-scen", "3 - Scenario explorer", P, vars_, time=("2025-10-19T00:00:00.000Z", "2026-10-19T00:00:00.000Z"), links=NAV,
                     desc="Year-long behaviour of each method in drought, flood, Vesak and Christmas scenarios.")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in (("1_live_plan.json", d1), ("2_results.json", d2), ("3_scenario_explorer.json", d3)):
        _id[0] = 0
        d = fn()
        (OUT / name).write_text(json.dumps(d, indent=1), encoding="utf-8")
        print(f"wrote {name}: {len(d['panels'])} panels")


if __name__ == "__main__":
    main()
