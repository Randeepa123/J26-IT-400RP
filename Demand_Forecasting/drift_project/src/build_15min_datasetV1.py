"""
build_15min_dataset.py
----------------------
Builds the 15-minute resolution dataset (~350,000 rows) directly from the 
already-downloaded chunks in data/pucsl_raw_chunks/ without re-scraping PUCSL,
and merges daily holidays + Colombo weather onto each 15-min interval.
"""
from pathlib import Path
import pandas as pd
from pucsl_scraper import RAW_DIR, LOCAL_TZ, PLANT_MAPPING
from enrich_calendar_weather import add_holiday_column, add_weather_columns, DAILY_VARS

DATA_DIR = Path(__file__).parent.parent / "data"
DAILY_ENRICHED_FILE = DATA_DIR / "pucsl_clean_daily_enriched.csv"
OUT_15MIN_CSV = DATA_DIR / "pucsl_clean_15min_enriched.csv"
OUT_15MIN_PARQUET = DATA_DIR / "pucsl_clean_15min_enriched.parquet"


def build_15min():
    files = sorted(RAW_DIR.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No raw chunks found in {RAW_DIR}. Run pucsl_scraper.py first.")

    print(f"Reading {len(files)} raw chunk files from {RAW_DIR}...")
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)

    # Convert UTC timestamps to Sri Lanka local time (Asia/Colombo)
    df["reportTimestamp"] = (
        pd.to_datetime(df["reportTimestamp"], utc=True)
        .dt.tz_convert(LOCAL_TZ)
        .dt.tz_localize(None)
    )
    df["fuel_type"] = df["powerPlantId"].map(PLANT_MAPPING).fillna("Unknown")

    # Pivot to wide format at native 15-minute timestamps (NO .resample("D"))
    wide = df.pivot_table(
        index="reportTimestamp",
        columns="fuel_type",
        values="dispatchValueInMW",
        aggfunc="sum",
    )

    # Ensure a clean, regular 15-minute grid and fill missing plant dispatches with 0
    wide = wide.resample("15min").mean().fillna(0.0)

    # Compute total and solar generation properly across all solar columns
    plant_cols = list(wide.columns)
    wide["total_generation_mw"] = wide[plant_cols].sum(axis=1)
    solar_cols = [c for c in plant_cols if "solar" in c.lower()]
    wide["solar_generation_mw"] = wide[solar_cols].sum(axis=1) if solar_cols else 0.0

    wide = wide.reset_index().rename(columns={"reportTimestamp": "timestamp"})
    wide["date_key"] = wide["timestamp"].dt.normalize()

    # Merge daily holiday + weather features using the calendar date
    if DAILY_ENRICHED_FILE.exists():
        print(f"Merging existing weather & holidays from {DAILY_ENRICHED_FILE}...")
        daily_enriched = pd.read_csv(DAILY_ENRICHED_FILE)
        daily_enriched["date_key"] = pd.to_datetime(daily_enriched["date"]).dt.tz_localize(None).dt.normalize()
        keep_cols = ["date_key", "is_holiday", "holiday_name"] + [
            c for c in DAILY_VARS if c in daily_enriched.columns
        ]
        wide = wide.merge(daily_enriched[keep_cols].drop_duplicates("date_key"), on="date_key", how="left")
    else:
        print("Daily enriched file not found; fetching holidays and weather directly...")
        cal_df = pd.DataFrame({"date": wide["date_key"].drop_duplicates().sort_values()})
        cal_df = add_holiday_column(cal_df, date_col="date")
        cal_df = add_weather_columns(cal_df, date_col="date")
        cal_df = cal_df.rename(columns={"date": "date_key"})
        wide = wide.merge(cal_df, on="date_key", how="left")

    # Rename timestamp -> date so baseline.py, drift.py, adapt.py, and main.py work seamlessly
    wide = wide.drop(columns=["date_key"]).rename(columns={"timestamp": "date"})

    # Save both CSV and Parquet (Parquet is ~5x smaller for uploading to Kaggle)
    wide.to_csv(OUT_15MIN_CSV, index=False)
    try:
        wide.to_parquet(OUT_15MIN_PARQUET, index=False)
        print(f"Saved Parquet: {OUT_15MIN_PARQUET}")
    except Exception:
        pass

    print(f"Saved 15-min dataset: {OUT_15MIN_CSV} ({len(wide):,} rows, {len(wide.columns)} columns)")
    return wide


if __name__ == "__main__":
    build_15min()