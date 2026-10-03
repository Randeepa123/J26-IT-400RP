"""
scenario_generator.py
=====================
Scenario bank + stress suite for training and testing Component 3 (v2).

Why: the original DQN trained on ONE fixed 4-year series (34 identical episodes) and never saw droughts,
extreme floods, shifted monsoons, outages, festival demand peaks or poor forecasts.

What it builds (all SYNTHETIC - derived from the project's own rainfall-runoff model):
  * A stochastic daily rainfall generator (monthly 2-state Markov chain + gamma amounts) fitted to the
    project's synthetic Ratnapura rainfall, with regime controls:
      - El Nino multi-month drought, La Nina wet spell, monsoon-onset shift,
      - flash-flood / depression events (1-4 day extreme rain, biased to May-Jun and Oct-Nov).
  * The SAME two-store catchment model as generate_synthetic_kukule_dataset.simulate_hydrological_inflow
    (re-implemented here and verified to reproduce the existing dataset), so soil wetness / baseflow
    stay physically consistent under every regime.
  * Unit outages, calendar demand weights (Vesak / Poson / Christmas / Deepavali / Avurudu) and a SIMULATED
    forecast (horizon-dependent log-normal error, shrinkage toward trailing mean, occasionally-missed floods,
    optional bias) giving P50 / P90 inflow forecasts for the next 15 days.
  * Train bank / validation bank (disjoint seeds) and a fixed, named STRESS SUITE built on the real-simulation
    test year (2025-10-19 .. 2026-10-18).

Disclaimer: synthetic-from-synthetic. Results must be reported as performance on simulated scenarios.
"""

import os
import json
import pickle
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import demand_events as de
import paths

SECONDS_PER_DAY = 86400.0
H_FC = 15                        # forecast horizon (days)
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
BANK_DIR = str(paths.SCENARIO_BANK_DIR)
DATASET_PATH = str(paths.STATION_DATASET)
RAIN10_PATH = str(paths.RAIN_10Y)
DEMAND_V2_PATH = str(paths.DEMAND_5Y_V2)
TEST_START, TEST_END = pd.Timestamp("2025-10-19"), pd.Timestamp("2026-10-18")


# =============================================================================
# Scenario container
# =============================================================================
@dataclass
class Scenario:
    name: str
    dates: np.ndarray          # datetime64[D], length L = n_days + H_FC
    inflow_m3: np.ndarray      # (L,) daily inflow volume
    units: np.ndarray          # (L,) operating units 0..2
    weight: np.ndarray         # (L,) demand weight
    fc50: np.ndarray           # (L, H_FC) P50 inflow forecast (m3/day), lead 0..H_FC-1
    fc90: np.ndarray           # (L, H_FC) P90 inflow forecast
    dwf: np.ndarray            # (L, H_FC) demand-weight forecast
    meta: dict = field(default_factory=dict)

    @property
    def n_days(self):
        return len(self.dates) - H_FC

    def month(self, t):
        return int(pd.Timestamp(self.dates[t]).month)

    def with_forecast_bias(self, factor, name=None):
        s = Scenario(name or f"{self.name}_bias{factor}", self.dates, self.inflow_m3, self.units, self.weight,
                     self.fc50 * factor, self.fc90 * factor, self.dwf, dict(self.meta))
        s.meta["forecast_bias"] = factor
        return s


def slice_scenario(sc, lo, hi, name=None):
    """Scenario covering decision days [lo, hi) (plus the H_FC look-ahead arrays), e.g. a recent window of 'actual' days."""
    L = len(sc.dates)
    hi_ext = min(hi + H_FC, L)
    pad = (hi + H_FC) - hi_ext
    def cut(a):
        x = a[lo:hi_ext]
        return np.concatenate([x, np.repeat(x[-1:], pad, axis=0)]) if pad > 0 else x
    dates = cut(sc.dates)
    if pad > 0:
        dates = np.concatenate([sc.dates[lo:hi_ext], sc.dates[hi_ext - 1] + np.arange(1, pad + 1).astype("timedelta64[D]")])
    return Scenario(name or f"{sc.name}[{lo}:{hi}]", dates, cut(sc.inflow_m3), cut(sc.units), cut(sc.weight),
                    cut(sc.fc50), cut(sc.fc90), cut(sc.dwf), dict(sc.meta))


# =============================================================================
# Catchment model (verified copy of simulate_hydrological_inflow)
# =============================================================================
class CatchmentModel:
    def __init__(self, cfg):
        h, s, m = cfg["hydrological_parameters"], cfg["shared_station_specifications"], cfg["meteorological_parameters"]
        self.S_max = h["soil_moisture_capacity_mm"]
        self.S0, self.G0 = h["initial_soil_moisture_mm"], h["initial_groundwater_storage_mm"]
        self.k_base, self.k_perc = h["baseflow_recession_k"], h["percolation_rate_coeff"]
        self.uh = h["routing_unit_hydrograph_weights"]
        self.pet = {int(k): v for k, v in h["evapotranspiration_monthly_mm_day"].items()}
        self.min_env = h["minimum_environmental_flow_m3s"]
        self.oro = m.get("catchment_orographic_enhancement_factor", 1.18)
        self.mm_to_m3s = s["catchment_area_km2"] * 1000.0 / SECONDS_PER_DAY

    def inflow_m3s(self, rain_mm, months):
        n = len(rain_mm)
        crf = np.asarray(rain_mm, float) * self.oro
        S, G = self.S0, self.G0
        dro = np.zeros(n); bfl = np.zeros(n)
        for t in range(n):
            theta = min(max(S / self.S_max, 0.0), 1.0)
            aet = self.pet[int(months[t])] * (0.20 + 0.65 * theta)
            p = crf[t]
            d_frac = 0.12 + 0.62 * theta ** 1.8
            if p > 40.0:
                d_frac = min(0.92, d_frac + 0.10)
            direct = p * d_frac
            S_next = S + (p - direct) - aet
            perc = 0.0
            if S_next > self.S_max:
                ex = S_next - self.S_max
                perc += ex * 0.75; direct += ex * 0.25; S_next = self.S_max
            elif S_next > 0.35 * self.S_max:
                perc = self.k_perc * (S_next / self.S_max) * 45.0
                S_next -= perc
            else:
                S_next = max(5.0, S_next)
            S = S_next
            G_next = G + perc
            bf = self.k_base * G_next
            G = max(15.0, G_next - bf)
            dro[t] = direct; bfl[t] = bf * self.mm_to_m3s
        quick = dro * self.mm_to_m3s * self.uh[0]
        quick[1:] += dro[:-1] * self.mm_to_m3s * self.uh[1]
        quick[0] += dro[0] * self.mm_to_m3s * self.uh[1]
        return np.maximum(quick + bfl, self.min_env)


# =============================================================================
# Weather generator
# =============================================================================
class WeatherGenerator:
    """Monthly 2-state Markov chain + (1mm + gamma) wet-day amounts, fitted to the project rainfall."""

    def __init__(self, rain, dates, wet_thr=1.0):
        rain = np.asarray(rain, float); months = pd.to_datetime(dates).month.values
        self.pww, self.pwd, self.k, self.theta = np.zeros(12), np.zeros(12), np.zeros(12), np.zeros(12)
        wet = rain >= wet_thr
        for m in range(1, 13):
            idx = np.where(months == m)[0]
            idx = idx[idx > 0]
            prev, cur = wet[idx - 1], wet[idx]
            self.pww[m - 1] = (cur[prev].mean() if prev.any() else 0.6)
            self.pwd[m - 1] = (cur[~prev].mean() if (~prev).any() else 0.3)
            x = rain[(months == m) & wet] - wet_thr
            mu, var = (x.mean(), x.var()) if len(x) > 5 else (8.0, 80.0)
            var = max(var, 1e-3)
            self.k[m - 1], self.theta[m - 1] = mu * mu / var, var / mu
        self.wet_thr = wet_thr

    def _param(self, arr, doy_eff):
        # periodic linear interpolation of monthly values at mid-month points
        mid = (np.arange(12) + 0.5) * 30.4
        x = doy_eff % 365.0
        return np.interp(x, np.r_[mid - 365.0, mid, mid + 365.0], np.r_[arr, arr, arr])

    def generate(self, dates, rng, wetfac=None, ampfac=None, shift_days=0):
        n = len(dates)
        doy = pd.to_datetime(dates).dayofyear.values + shift_days
        wetfac = np.ones(n) if wetfac is None else wetfac
        ampfac = np.ones(n) if ampfac is None else ampfac
        pww, pwd = self._param(self.pww, doy), self._param(self.pwd, doy)
        kk, th = self._param(self.k, doy), self._param(self.theta, doy)
        rain = np.zeros(n); prev = rng.random() < 0.5
        u = rng.random(n)
        for t in range(n):
            p = min(0.97, (pww[t] if prev else pwd[t]) * wetfac[t])
            if u[t] < p:
                rain[t] = (self.wet_thr + rng.gamma(kk[t], th[t])) * ampfac[t]
                prev = True
            else:
                prev = False
        return rain


# =============================================================================
# Outages, demand weights, forecasts
# =============================================================================
def make_units(dates, rng, planned=True, unplanned_p=0.012, extra_blocks=()):
    n = len(dates)
    out = np.zeros((n, 2), dtype=int)               # outage flag per unit
    d = pd.to_datetime(dates)
    if planned:
        for yr in sorted(set(d.year)):
            for unit, lo, hi, dur in ((0, 35, 55, 12), (1, 222, 242, 11)):
                s = int(rng.integers(lo, hi)) + (pd.Timestamp(f"{yr}-01-01") - d[0]).days
                out[max(0, s):max(0, s + dur), unit] = 1
    t = 0
    while t < n:
        if rng.random() < unplanned_p:
            dur = int(rng.integers(1, 6)); u = int(rng.integers(0, 2))
            out[t:t + dur, u] = 1; t += dur
        t += 1
    for (s, e, n_out) in extra_blocks:               # explicit stress outages: (start, end, units_out)
        out[s:e, 0] = 1
        if n_out >= 2:
            out[s:e, 1] = 1
    return np.clip(2 - out.sum(axis=1), 0, 2)


def make_forecasts(inflow_m3, dwt, rng, bias=1.0, s0=0.20, s1=0.05, miss_prob=0.30, p90_width=1.0):
    """Simulated P50/P90 inflow forecasts and demand-weight forecasts (shape (L,H_FC))."""
    L = len(inflow_m3)
    lg = np.log(np.maximum(inflow_m3, 1.0))
    trail = pd.Series(lg).rolling(30, min_periods=1).mean().shift(1).bfill().values
    fc50 = np.zeros((L, H_FC)); fc90 = np.zeros((L, H_FC)); dwf = np.zeros((L, H_FC))
    h = np.arange(H_FC)
    s_h = np.minimum(s0 + s1 * h, 0.9)
    shrink = np.maximum(0.15, 1.0 - 0.07 * h)
    z_common = rng.normal(size=L)
    z_each = rng.normal(size=(L, H_FC))
    miss = rng.random(L) < miss_prob
    med = np.exp(trail)
    for t in range(L):
        idx = np.minimum(t + h, L - 1)
        truth = lg[idx]
        base = shrink * truth + (1 - shrink) * trail[t]
        e = s_h * (0.5 * z_common[t] + np.sqrt(0.75) * z_each[t])
        val = base + e
        if miss[t]:
            flood = (inflow_m3[idx] > 4.0 * med[t]) & (h >= 2)
            val = np.where(flood, np.log(0.35) + val + 0.0, val)
            val = np.where(flood, np.minimum(val, trail[t] + 0.5), val)
        fc50[t] = np.exp(val) * bias
        fc90[t] = np.exp(val + 1.2816 * 0.8 * s_h * p90_width) * bias
        dwf[t] = dwt[idx] * (1.0 + rng.normal(0.0, 0.02 + 0.004 * h))
    return fc50.astype(np.float32), fc90.astype(np.float32), np.clip(dwf, 0.8, 1.5).astype(np.float32)


# =============================================================================
# Regime sampling and bank construction
# =============================================================================
def sample_regime(rng, force=None):
    kind = rng.choice(["neutral", "el_nino", "la_nina"], p=[0.45, 0.30, 0.25])
    if force:
        kind = force
    reg = {"enso": kind, "events": [], "shift_days": int(rng.choice([0, 0, -20, 20, 30]))}
    if kind == "el_nino":
        reg["enso_len"] = int(rng.integers(120, 301)); reg["enso_amp"] = float(rng.uniform(0.40, 0.70))
        reg["enso_wet"] = float(rng.uniform(0.70, 0.92))
    elif kind == "la_nina":
        reg["enso_len"] = int(rng.integers(90, 241)); reg["enso_amp"] = float(rng.uniform(1.15, 1.45))
        reg["enso_wet"] = float(rng.uniform(1.05, 1.20))
    n_flood = int(rng.poisson(1.8))   # per ~3-year span (spin-up + 2 years), ~0.6/yr
    reg["n_flood"] = n_flood
    reg["flood_peak_mm"] = [float(rng.uniform(90, 250)) for _ in range(n_flood)]
    reg["flood_biased"] = [bool(rng.random() < 0.7) for _ in range(n_flood)]
    reg["flood_days"] = [int(rng.integers(1, 5)) for _ in range(n_flood)]
    return reg


def _flood_day_index(dates, biased, rng):
    d = pd.to_datetime(dates)
    if biased:
        cand = np.where(d.month.isin([5, 6, 10, 11]))[0]
        if len(cand) > 10:
            return int(rng.choice(cand[5:-6]))
    return int(rng.integers(5, len(dates) - 6))


def apply_regime(n, dates, reg, rng):
    wetfac, ampfac = np.ones(n), np.ones(n)
    if reg["enso"] in ("el_nino", "la_nina"):
        s = int(rng.integers(0, max(1, n - reg["enso_len"])))
        wetfac[s:s + reg["enso_len"]] = reg["enso_wet"]; ampfac[s:s + reg["enso_len"]] = reg["enso_amp"]
        reg["enso_start_idx"] = s
    storms = []
    for i in range(reg["n_flood"]):
        c = _flood_day_index(dates, reg["flood_biased"][i], rng)
        storms.append((c, reg["flood_days"][i], reg["flood_peak_mm"][i]))
        wetfac[max(0, c - 3):c] = 0.95; ampfac[max(0, c - 3):c] *= 1.5
    reg["storms"] = [(int(c), int(dd), float(p)) for c, dd, p in storms]
    return wetfac, ampfac, storms


def add_storms(rain, storms):
    rain = rain.copy()
    for c, dur, peak in storms:
        shape = [0.55, 1.0, 0.6, 0.3][:max(1, dur)] if dur > 1 else [1.0]
        for j, f in enumerate(shape):
            if 0 <= c + j < len(rain):
                rain[c + j] = max(rain[c + j], peak * f)
    return rain


def _assemble(name, dates_full, rain_full, catch, wgen_rng, units_rng, fc_rng, keep, weight_full=None,
              bias=1.0, units_extra=(), meta=None, vesak_override=None, p90_width=1.0):
    """Run hydrology on the full rainfall, slice [keep) window (+H_FC tail) and attach units/weights/forecasts."""
    months = pd.to_datetime(dates_full).month.values
    q = catch.inflow_m3s(rain_full, months)
    lo, hi = keep
    hi_t = min(hi + H_FC, len(dates_full))
    sl = slice(lo, hi_t)
    dates = dates_full[sl]
    inflow = q[sl] * SECONDS_PER_DAY
    pad = (hi + H_FC) - hi_t
    if pad > 0:
        dates = np.concatenate([dates, dates[-1] + np.arange(1, pad + 1).astype("timedelta64[D]")])
        inflow = np.concatenate([inflow, inflow[-pad:][::-1]])
    units = make_units(dates, units_rng, extra_blocks=units_extra)
    if weight_full is None:
        yrs = {pd.Timestamp(d).year for d in dates}
        w = de.calendar_demand_weights(dates, rng=units_rng, vesak_override_by_year=vesak_override)
    else:
        w = weight_full
    fc50, fc90, dwf = make_forecasts(inflow, w, fc_rng, bias=bias, p90_width=p90_width)
    meta = dict(meta or {}, p90_width=p90_width)
    return Scenario(name, dates.astype("datetime64[D]"), inflow, units, w, fc50, fc90, dwf, meta)


class Generators:
    """Lazy singleton holding the config, catchment model and fitted weather generator."""
    _inst = None

    def __init__(self):
        with open(paths.SCENARIOS_CONFIG, "r", encoding="utf-8") as f:
            self.cfg = json.load(f)
        self.catch = CatchmentModel(self.cfg)
        df5 = pd.read_csv(DATASET_PATH, parse_dates=["date"])
        self.df5 = df5
        if os.path.exists(RAIN10_PATH):
            r10 = pd.read_csv(RAIN10_PATH, parse_dates=["date"])
            rain, dts = r10["rainfall_mm"].values, r10["date"].values
        else:
            rain, dts = df5["rainfall_mm"].values, df5["date"].values
        self.wgen = WeatherGenerator(rain, dts)

    @classmethod
    def get(cls):
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst


def generate_bank_entry(i, seed_base, force_regime=None, n_days=730):
    g = Generators.get()
    rng = np.random.default_rng([seed_base, i])
    start = pd.Timestamp("2027-01-01") + pd.Timedelta(days=int(rng.integers(0, 365 * 3)))
    spin = 365
    dates_full = pd.date_range(start - pd.Timedelta(days=spin), periods=spin + n_days + H_FC, freq="D").values
    reg = sample_regime(rng, force_regime)
    wetfac, ampfac, storms = apply_regime(len(dates_full), dates_full, reg, rng)
    rain = g.wgen.generate(dates_full, rng, wetfac, ampfac, reg["shift_days"])
    rain = add_storms(rain, storms)
    bias = float(np.exp(rng.normal(0.0, 0.10))) if rng.random() < 0.3 else 1.0
    width = float(rng.choice([1.0, 1.0, 2.0, 3.0, 4.0]))   # Component-1 style P90 is far wider than a narrow forecast
    ves = {start.year + k: start + pd.Timedelta(days=0) for k in ()}  # default table
    sc = _assemble(f"bank_{seed_base}_{i}", dates_full, rain, g.catch, rng, rng, rng, (spin, spin + n_days),
                   bias=bias, p90_width=width, meta={"regime": {k: v for k, v in reg.items() if k != "storms"},
                                    "storms": reg["storms"], "bias": bias, "kind": "bank"})
    return sc


def build_bank(n, seed_base, path, force=None, verbose=True):
    sc = [generate_bank_entry(i, seed_base, force) for i in range(n)]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(sc, f)
    if verbose:
        q = np.array([s.inflow_m3[:s.n_days].mean() / SECONDS_PER_DAY for s in sc])
        print(f"bank {os.path.basename(path)}: {n} entries, mean inflow {q.mean():.1f} m3/s "
              f"(min {q.min():.1f}, max {q.max():.1f})")
    return sc


def load_bank(path):
    with open(path, "rb") as f:
        return pickle.load(f)


# =============================================================================
# Stress suite on the real-simulation test year
# =============================================================================
def _test_year_base():
    g = Generators.get()
    df = g.df5
    dates = df["date"].values
    rain = df["rainfall_mm"].values.astype(float)
    t0 = int(np.where(df["date"] == TEST_START)[0][0]); t1 = int(np.where(df["date"] == TEST_END)[0][0]) + 1
    return g, df, dates, rain, t0, t1


def build_stress_suite():
    g, df, dates, rain, t0, t1 = _test_year_base()
    dem = pd.read_csv(DEMAND_V2_PATH, parse_dates=["date"]).set_index("date")["demand_weight"]
    weight_full = dem.reindex(pd.to_datetime(dates)).fillna(1.0).values
    n = t1 - t0
    doy_dates = pd.to_datetime(dates[t0:t1])
    idx = lambda ts: int(np.where(pd.to_datetime(dates) == pd.Timestamp(ts))[0][0])

    def build(name, rain_mod, bias=1.0, seed=0, units_extra=(), meta=None, p90_width=1.0):
        rng = np.random.default_rng([777, seed])
        return _assemble(name, dates, rain_mod, g.catch, rng, rng, rng, (t0, t1), weight_full=weight_full,
                         bias=bias, units_extra=units_extra, meta=dict(meta or {}, kind="stress"), p90_width=p90_width)

    out = {}
    out["test_year_real_sim"] = build("test_year_real_sim", rain, seed=1, meta={"desc": "untouched held-out year"})

    r = rain.copy()                                           # El Nino drought: 270-day dry window
    ds = t0 + 30
    r[ds:ds + 270] = np.where(rain[ds:ds + 270] > 1.0, rain[ds:ds + 270] * 0.45, rain[ds:ds + 270])
    keep = np.random.default_rng(5).random(270) < 0.25        # also drop 25% of the remaining wet days
    sub = r[ds:ds + 270]; sub[keep & (sub > 1.0)] = 0.0
    out["drought_el_nino"] = build("drought_el_nino", r, seed=2, meta={"desc": "270-day El Nino drought (-55% rain, fewer wet days)"})

    r = rain.copy()                                           # flood year: 3 big storms (Nov, May, Oct)
    storms = [(idx("2025-11-20"), 3, 260.0), (idx("2026-05-22"), 4, 290.0), (idx("2026-10-08"), 3, 210.0)]
    r = add_storms(r, storms)
    out["flood_year"] = build("flood_year", r, seed=3, meta={"desc": "3 extreme storms", "storms": storms})

    r = rain.copy()                                           # flood during Vesak week (2026-05-31 +-)
    r[idx("2026-05-24"):idx("2026-06-06")] = np.minimum(r[idx("2026-05-24"):idx("2026-06-06")], 3.0)
    r = add_storms(r, [(idx("2026-05-30"), 3, 240.0)])
    out["vesak_flood"] = build("vesak_flood", r, seed=4, meta={"desc": "extreme storm over Vesak 2026-05-30..06-01"})

    r = rain.copy()                                           # dry Christmas: Nov 25 - Jan 10 almost rain-free
    a, b = idx("2025-11-25"), idx("2026-01-10")
    r[a:b] = np.where(r[a:b] > 0, r[a:b] * 0.1, 0.0)
    out["dry_christmas"] = build("dry_christmas", r, seed=5, meta={"desc": "46-day dry spell across Christmas/year-end peak"})

    out["wide_forecast_spread"] = build("wide_forecast_spread", rain, seed=9, p90_width=4.0,
                                        meta={"desc": "P90/P50 spread like the Component-1 product (3-7x)"})
    out["forecast_bias_high"] = build("forecast_bias_high", rain, bias=1.4, seed=6, meta={"desc": "forecasts 40% too wet"})
    out["forecast_bias_low"] = build("forecast_bias_low", rain, bias=0.6, seed=7, meta={"desc": "forecasts 40% too dry"})

    s1, s2 = idx("2026-02-01") - t0, idx("2026-08-10") - t0
    out["double_outage"] = build("double_outage", rain, seed=8,
                                 units_extra=[(s1, s1 + 60, 1), (s2, s2 + 3, 2)],
                                 meta={"desc": "one unit out 60 days + station fully out 3 days"})
    return out


def save_stress_suite(path=None):
    path = path or os.path.join(BANK_DIR, "stress_suite.pkl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    suite = build_stress_suite()
    with open(path, "wb") as f:
        pickle.dump(suite, f)
    return suite


def load_stress_suite(path=None):
    path = path or os.path.join(BANK_DIR, "stress_suite.pkl")
    with open(path, "rb") as f:
        return pickle.load(f)


def verify_hydrology_reproduces_dataset():
    """Max abs difference (m3/s) between this module's catchment model and the existing dataset inflow."""
    g = Generators.get()
    df = g.df5
    q = g.catch.inflow_m3s(df["rainfall_mm"].values, pd.to_datetime(df["date"]).dt.month.values)
    return float(np.abs(q - df["estimated_inflow_m3s"].values).max())


def main():
    print("hydrology reproduction max |diff| m3/s :", round(verify_hydrology_reproduces_dataset(), 6))
    build_bank(300, 1000, os.path.join(BANK_DIR, "train_bank.pkl"))
    build_bank(40, 2000, os.path.join(BANK_DIR, "val_bank.pkl"))
    suite = save_stress_suite()
    for k, s in suite.items():
        q = s.inflow_m3[:s.n_days] / SECONDS_PER_DAY
        print(f"  stress {k:20s} days={s.n_days} mean={q.mean():6.1f} max={q.max():7.1f} m3/s  "
              f"units<2 days={(s.units[:s.n_days] < 2).sum()}")


if __name__ == "__main__":
    # Re-import under the module name so pickled Scenario objects are stored as scenario_generator.Scenario
    # (running the file directly would store them as __main__.Scenario, which cannot be loaded later).
    import scenario_generator as _sg
    _sg.main()
