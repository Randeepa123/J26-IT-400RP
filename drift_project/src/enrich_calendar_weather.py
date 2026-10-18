"""
enrich_calendar_weather.py
---------------------------
Adds is_holiday (+ Poya days) and Colombo weather columns to the clean
daily PUCSL dataset produced by pucsl_scraper.py.

CONFIRMED: is_holiday logic, tested directly in this environment.
NOT YET TESTED LIVE: the weather API call (sandbox network restriction) --
the contract is well-documented but you should sanity-check the first run.
"""
import time
from pathlib import Path
import requests
import pandas as pd
import holidays

DATA_DIR = Path(__file__).parent.parent / "data"
IN_FILE = DATA_DIR / "pucsl_clean_daily.csv"
OUT_FILE = DATA_DIR / "pucsl_clean_daily_enriched.csv"

LATITUDE = 6.9271   # Colombo -- change if your demand data covers a different region
LONGITUDE = 79.8612
WEATHER_API = "https://archive-api.open-meteo.com/v1/archive"
DAILY_VARS = ["temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
              "precipitation_sum", "rain_sum"]


def add_holiday_column(df, date_col="date"):
    years = sorted(df[date_col].dt.year.unique().tolist())
    lk_holidays = holidays.country_holidays("LK", years=years)
    df["is_holiday"] = df[date_col].dt.date.isin(lk_holidays).astype(int)
    df["holiday_name"] = df[date_col].dt.date.map(lambda d: lk_holidays.get(d, ""))
    return df


def fetch_weather_chunk(start_date, end_date, retries=3):
    params = {
        "latitude": LATITUDE, "longitude": LONGITUDE,
        "start_date": start_date, "end_date": end_date,
        "daily": ",".join(DAILY_VARS), "timezone": "Asia/Colombo",
    }
    for attempt in range(retries):
        try:
            r = requests.get(WEATHER_API, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            wait = 5 * (attempt + 1)
            print(f"  ! weather fetch failed ({e}) -- retrying in {wait}s")
            time.sleep(wait)
    print("  ! giving up on weather fetch")
    return None


def add_weather_columns(df, date_col="date"):
    start_date = df[date_col].min().strftime("%Y-%m-%d")
    end_date = df[date_col].max().strftime("%Y-%m-%d")
    print(f"Fetching weather for {start_date} to {end_date} ...")
    payload = fetch_weather_chunk(start_date, end_date)

    if not payload or "daily" not in payload:
        print("  ! no weather data returned -- check date range/connection")
        for col in DAILY_VARS:
            df[col] = None
        return df

    weather_df = pd.DataFrame(payload["daily"]).rename(columns={"time": date_col})
    weather_df[date_col] = pd.to_datetime(weather_df[date_col])
    #df = df.merge(weather_df, on=date_col, how="left")
    df[date_col] = pd.to_datetime(df[date_col]).dt.tz_localize(None).dt.normalize()
    weather_df[date_col] = pd.to_datetime(weather_df[date_col]).dt.normalize()
    df = df.merge(weather_df, on=date_col, how="left")

    missing = df[DAILY_VARS[0]].isna().sum()
    if missing:
        print(f"  ! {missing} days have no matching weather data")
    return df


def run():
    df = pd.read_csv(IN_FILE)
    date_col = df.columns[0]  # ADJUST if your date column isn't first
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.rename(columns={date_col: "date"})

    df = add_holiday_column(df)
    df = add_weather_columns(df)

    df.to_csv(OUT_FILE, index=False)
    print(f"Enriched dataset saved to {OUT_FILE} ({len(df)} rows, "
          f"{df['is_holiday'].sum()} holiday days)")
    return df


if __name__ == "__main__":
    run()
