"""
build_15min_dataset.py
----------------------
Builds the 15-minute resolution dataset (~350,000 rows) from data/pucsl_raw_chunks/
and fetches HOURLY historical weather from Open-Meteo (interpolated to 15-min)
to avoid daily-average flattening and look-ahead leakage.
"""
import time
import requests
from pathlib import Path
import pandas as pd
from pucsl_scraper import RAW_DIR, LOCAL_TZ, PLANT_MAPPING
from enrich_calendar_weather import add_holiday_column, LATITUDE, LONGITUDE, WEATHER_API

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_15MIN_CSV = DATA_DIR / "pucsl_clean_15min_enriched.csv"
OUT_15MIN_PARQUET = DATA_DIR / "pucsl_clean_15min_enriched.parquet"

HOURLY_VARS = ["temperature_2m", "precipitation", "rain", "shortwave_radiation"]


def fetch_hourly_weather(start_date: pd.Timestamp, end_date: pd.Timestamp):
    """Fetches hourly weather in yearly chunks so Open-Meteo doesn't time out on 10 years of data."""
    all_chunks = []
    cur_start = start_date. floor("D")
    final_end = end_date.floor("D")

    while cur_start <= final_end:
        cur_end = min(cur_start + pd.DateOffset(years=1) - pd.Timedelta(days=1), final_end)
        s_str, e_str = cur_start.strftime("%Y-%m-%d"), cur_end.strftime("%Y-%m-%d")
        print(f"Fetching hourly weather: {s_str} to {e_str} ...")

        params = {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "start_date": s_str,
            "end_date": e_str,
            "hourly": ",".join(HOURLY_VARS),
            "timezone": "Asia/Colombo",
        }
        for attempt in range(3):
            try:
                r = requests.get(WEATHER_API, params=params, timeout=60)
                r.raise_for_status()
                payload = r.json()
                if "hourly" in payload:
                    all_chunks.append(pd.DataFrame(payload["hourly"]))
                break
            except Exception as e:
                wait = 5 * (attempt + 1)
                print(f"  ! retry {attempt+1} in {wait}s ({e})")
                time.sleep(wait)

        cur_start = cur_end + pd.Timedelta(days=1)
        time.sleep(1.0)

    if not all_chunks:
        raise RuntimeError("Failed to fetch hourly weather from Open-Meteo.")

    wdf = pd.concat(all_chunks, ignore_index=True)
    wdf["date"] = pd.to_datetime(wdf["time"])
    wdf = wdf.drop(columns=["time"]).drop_duplicates("date").set_index("date").sort_index()

    # Upsample 1-hour weather to 15-minute intervals:
    # - Temperature & solar radiation change smoothly -> linear interpolation
    # - Precipitation/rain are hourly totals -> divide by 4 across the four 15-min intervals
    wdf_15m = wdf.resample("15min").asfreq()
    wdf_15m["temperature_2m"] = wdf_15m["temperature_2m"].interpolate(method="time")
    wdf_15m["shortwave_radiation"] = wdf_15m["shortwave_radiation"].interpolate(method="time").fillna(0.0)
    wdf_15m["precipitation"] = wdf_15m["precipitation"].ffill() / 4.0
    wdf_15m["rain"] = wdf_15m["rain"].ffill() / 4.0

    # Keep backwards-compatible alias names so baseline.py works without breaking
    wdf_15m["temperature_2m_mean"] = wdf_15m["temperature_2m"]
    wdf_15m["precipitation_sum"] = wdf_15m["precipitation"]

    return wdf_15m.reset_index()


def build_15min():
    files = sorted(RAW_DIR.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No raw chunks found in {RAW_DIR}.")

    print(f"Reading {len(files)} raw chunk files from {RAW_DIR}...")
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)

    df["reportTimestamp"] = (
        pd.to_datetime(df["reportTimestamp"], utc=True)
        .dt.tz_convert(LOCAL_TZ)
        .dt.tz_localize(None)
    )
    df["fuel_type"] = df["powerPlantId"].map(PLANT_MAPPING).fillna("Unknown")

    # Sum MW across identical plant names at the exact same 15-min timestamp
    wide = df.pivot_table(
        index="reportTimestamp",
        columns="fuel_type",
        values="dispatchValueInMW",
        aggfunc="sum",
    )
    # Ensure regular 15-minute grid without altering existing 15-min values
    wide = wide.resample("15min").asfreq().fillna(0.0)

    plant_cols = list(wide.columns)
    wide["total_generation_mw"] = wide[plant_cols].sum(axis=1)
    solar_cols = [c for c in plant_cols if "solar" in c.lower()]
    wide["solar_generation_mw"] = wide[solar_cols].sum(axis=1) if solar_cols else 0.0

    wide = wide.reset_index().rename(columns={"reportTimestamp": "date"})

    # Add Sri Lanka holidays
    wide = add_holiday_column(wide, date_col="date")

    # Fetch and merge real intraday weather
    weather_15m = fetch_hourly_weather(wide["date"].min(), wide["date"].max())
    wide = wide.merge(weather_15m, on="date", how="left")

    wide.to_csv(OUT_15MIN_CSV, index=False)
    try:
        wide.to_parquet(OUT_15MIN_PARQUET, index=False)
    except Exception:
        pass

    print(f"Done! Saved {len(wide):,} rows to {OUT_15MIN_CSV}")


if __name__ == "__main__":
    build_15min()