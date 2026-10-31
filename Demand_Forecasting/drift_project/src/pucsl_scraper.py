"""
pucsl_scraper.py
----------------
Pulls 15-min system dispatch data from PUCSL's confirmed API:
  GET https://gendata.pucsl.gov.lk/api/actual-system-dispatch
      ?dateAggregation=15min&from=<ISO8601 UTC>&to=<ISO8601 UTC>

Response shape (confirmed from real traffic you captured):
  {"data": [{"reportTimestamp": "...", "powerPlantId": 1, "dispatchValueInMW": 48}, ...]}

ONE THING YOU STILL NEED TO FIND:
  The response only gives powerPlantId, not fuel type (solar/hydro/thermal/
  wind). Open the site, F12 -> Network -> Fetch/XHR, and look for a call
  that returns the plant list (e.g. /api/power-plants or /api/dispatch-
  sources), likely fired once on page load. Copy its response into
  PLANT_MAPPING below. Without this we get TOTAL generation correctly but
  cannot isolate solar generation for the structural-drift work.
"""
import time
import requests
import pandas as pd
from pathlib import Path

BASE_URL = "https://gendata.pucsl.gov.lk/api/actual-system-dispatch"
LOCAL_TZ = "Asia/Colombo"          # Sri Lanka, UTC+5:30, no DST
#YEARS_BACK = 10
YEARS_BACK = 10
CHUNK_DAYS = 7                       # matches the site's own weekly window
REQUEST_DELAY_SEC = 1.5              # be polite to a government server
RAW_DIR = Path(__file__).parent.parent / "data" / "pucsl_raw_chunks"
RAW_DIR.mkdir(parents=True, exist_ok=True)
OUT_CLEAN = Path(__file__).parent.parent / "data" / "pucsl_clean_daily.csv"

# ADJUST: fill this in once you find the plant list endpoint
PLANT_MAPPING = {
1: "Sapu. Station - A", 3: "Old Laxapana", 4: "Canyon", 5: "New Laxapana",
    6: "Wimalasurendra", 7: "Polpitiya", 8: "Broadlands", 9: "Kotmale",
    10: "Victoria", 11: "Randenigala", 12: "Rantambe", 13: "Ukuwela",
    14: "Bowathenna", 15: "Upper Kotmale", 16: "Nillambe", 17: "Samanalawewa",
    18: "Kukule", 19: "Inginiyagala", 20: "Udawalawe", 26: "Sapu. Station - B",
    28: "Uthuru Janani", 29: "Power Barge", 31: "DPP_KPS_Mathu", 32: "LVPS 1",
    33: "LVPS 2", 34: "LVPS 3", 35: "DPP_KPS_Thul", 36: "DPP_KPS_Kolon",
    37: "ACE Matara", 38: "Asia Power", 39: "Sojitz Kelanitissa", 40: "West Coast",
    41: "Nothern Power", 42: "ACE-Embilipitiya", 43: "VPOWER Hambantota",
    44: "VPOWER Valachchenei", 45: "VPOWER Galle", 47: "VPOWER Horona",
    48: "Solar Roof Top PV (export) Est.", 50: "Solar Ground Mounted",
    51: "Biomass + W2E6", 53: "Minihydro Telemetered", 54: "Minihydro Estimated",
    56: "KPS_DPP_HAMBA", 57: "KCCP", 58: "KCCPS2", 59: "KPS(GT7)", 60: "KPS(GT)",
    61: "Wind 1", 62: "Stand Alone Diesel Generation", 65: "V Power Pallekale",
    66: "30MW DG Hambanthota", 67: "Ace Power Horana", 68: "Solar - Rooftop",
    70: "Wind CEB", 71: "Wind (CEB)", 73: "Mini-Hydro", 74: "NCRE Mini Hydro",
    75: "Solar Power", 76: "NCRE Wind1", 77: "Dendro and Biomass",
    78: "Municiple Solid Waste", 79: "Rooftop Solar* (Ordinary)",
    80: "Rooftop Solar* (LT Bulk)", 81: "Rooftop Solar* (HT Bulk)", 85: "Uma Oya",
    86: "Sobadhanavi", 89: "Rooftop Solar (LECO)", 90: "IPP waste heat +Biomass",
    92: "Solar Roof Top", 93: "Solar Power NCRE", 94: "CEB Sup Power",
    95: "IPP Emergency", 96: "ALTAQQA-Pol.", 97: "ALTAQQA-Mahi.",
    99: "Rooftop Solar 1", 100: "Other Revewable", 101: "Lakdhanavi", 
    106: "Wind (IPP)", 107: "BESS",
}


def week_windows(years_back=YEARS_BACK, chunk_days=CHUNK_DAYS):
    """Yield (start_utc, end_utc) pairs aligned to Sri Lanka local midnight."""
    end_local = pd.Timestamp.now(tz=LOCAL_TZ).normalize()
    start_local = end_local - pd.DateOffset(years=years_back)
    current = start_local
    while current < end_local:
        chunk_end = min(current + pd.Timedelta(days=chunk_days), end_local)
        yield current.tz_convert("UTC"), chunk_end.tz_convert("UTC")
        current = chunk_end


def fmt(ts):
    return ts.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def fetch_chunk(start_utc, end_utc, session, retries=3):
    params = {"dateAggregation": "15min", "from": fmt(start_utc), "to": fmt(end_utc)}
    for attempt in range(retries):
        try:
            r = session.get(BASE_URL, params=params, timeout=30)
            r.raise_for_status()
            return r.json().get("data", [])
        except Exception as e:
            wait = 5 * (attempt + 1)
            print(f"  ! attempt {attempt+1} failed ({e}) -- retrying in {wait}s")
            time.sleep(wait)
    print(f"  ! giving up on {start_utc} - {end_utc} after {retries} attempts")
    return []


def download_all():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (academic research data collection)"})
    windows = list(week_windows())
    print(f"Downloading {len(windows)} weekly chunks covering {YEARS_BACK} years...")

    for i, (start_utc, end_utc) in enumerate(windows):
        chunk_file = RAW_DIR / f"chunk_{start_utc.date()}.csv"
        if chunk_file.exists():
            continue  # resume support
        records = fetch_chunk(start_utc, end_utc, session)
        if records:
            pd.DataFrame(records).to_csv(chunk_file, index=False)
        print(f"[{i+1}/{len(windows)}] {start_utc.date()} - {end_utc.date()}: {len(records)} rows")
        time.sleep(REQUEST_DELAY_SEC)
    print("Download complete. Raw chunks saved in", RAW_DIR)


def print_unique_plant_ids():
    all_ids = set()
    for f in RAW_DIR.glob("*.csv"):
        df = pd.read_csv(f)
        all_ids.update(df["powerPlantId"].unique().tolist())
    print("Unique power plant IDs found:", sorted(all_ids))


def clean_and_reshape():
    files = sorted(RAW_DIR.glob("*.csv"))
    if not files:
        print("No raw chunks found -- run download_all() first.")
        return None

    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df["reportTimestamp"] = pd.to_datetime(df["reportTimestamp"], utc=True).dt.tz_convert(LOCAL_TZ)
    df["fuel_type"] = df["powerPlantId"].map(PLANT_MAPPING).fillna("Unknown")

    wide = df.pivot_table(index="reportTimestamp", columns="fuel_type",
                           values="dispatchValueInMW", aggfunc="sum")
    daily = wide.resample("D").mean()
    daily["total_generation_mw"] = daily.sum(axis=1)
    daily["solar_generation_mw"] = daily.get("Solar", 0)

    daily.to_csv(OUT_CLEAN)
    print(f"Clean daily dataset saved to {OUT_CLEAN} ({len(daily)} days, "
          f"columns: {list(wide.columns)})")
    return daily


if __name__ == "__main__":
    import sys
    if "--clean-only" in sys.argv:
        clean_and_reshape()
    else:
        download_all()
        print_unique_plant_ids()   # check output, fill in PLANT_MAPPING, re-run clean_and_reshape()
        clean_and_reshape()
