"""
incremental_collector.py
-------------------------
Meant to be run on a schedule (cron/systemd timer), not by hand repeatedly.
Unlike pucsl_scraper.py (full 10-year backfill), this only fetches what's
new since the last successful run, and appends to the existing dataset.

Run pucsl_scraper.py ONCE to backfill history, then use this script for
every run after that.
"""
import sys
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from pucsl_scraper import fetch_chunk, fmt, LOCAL_TZ, PLANT_MAPPING
import requests

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_FILE = DATA_DIR / "pucsl_clean_daily.csv"
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
STATE_FILE = DATA_DIR / "last_collected.txt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "incremental_collector.log"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)


def get_last_collected_date():
    """Where did we leave off? Checks the state file first, falls back to
    the max date already in the dataset, falls back to 30 days ago if
    this is somehow the first-ever incremental run."""
    if STATE_FILE.exists():
        return pd.Timestamp(STATE_FILE.read_text().strip(), tz=LOCAL_TZ)

    if RAW_FILE.exists():
        existing = pd.read_csv(RAW_FILE)
        date_col = existing.columns[0]
        last_date = pd.to_datetime(existing[date_col]).max()
        return pd.Timestamp(last_date, tz=LOCAL_TZ)

    log.warning("No existing data or state file found -- defaulting to 30 days back. "
                "Run pucsl_scraper.py first for a proper historical backfill.")
    return pd.Timestamp.now(tz=LOCAL_TZ) - pd.Timedelta(days=30)


def collect_new_data():
    last_date = get_last_collected_date()
    now = pd.Timestamp.now(tz=LOCAL_TZ)

    if last_date >= now - pd.Timedelta(hours=1):
        log.info("Already up to date (last collected: %s). Nothing to do.", last_date)
        return

    log.info("Collecting new data from %s to %s", last_date, now)

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (academic research data collection)"})

    start_utc = last_date.tz_convert("UTC")
    end_utc = now.tz_convert("UTC")
    records = fetch_chunk(start_utc, end_utc, session)

    if not records:
        log.warning("No records returned for this window -- API may be down, or genuinely no new data yet.")
        return

    new_df = pd.DataFrame(records)
    new_df["reportTimestamp"] = pd.to_datetime(new_df["reportTimestamp"], utc=True).dt.tz_convert(LOCAL_TZ)
    new_df["fuel_type"] = new_df["powerPlantId"].map(PLANT_MAPPING).fillna("Unknown")

    wide = new_df.pivot_table(index="reportTimestamp", columns="fuel_type",
                               values="dispatchValueInMW", aggfunc="sum")
    daily = wide.resample("D").mean()
    daily["total_generation_mw"] = daily.sum(axis=1)
    daily["solar_generation_mw"] = daily.get("Solar", 0)
    daily = daily.reset_index().rename(columns={"reportTimestamp": "date"})

    if RAW_FILE.exists():
        existing = pd.read_csv(RAW_FILE)
        existing["date"] = pd.to_datetime(existing[existing.columns[0]])
        combined = pd.concat([existing, daily], ignore_index=True)
        combined = combined.drop_duplicates(subset="date", keep="last").sort_values("date")
    else:
        combined = daily

    combined.to_csv(RAW_FILE, index=False)
    STATE_FILE.write_text(now.isoformat())

    log.info("Appended %d new days. Dataset now covers %s to %s (%d total rows).",
              len(daily), combined["date"].min(), combined["date"].max(), len(combined))


if __name__ == "__main__":
    try:
        collect_new_data()
    except Exception:
        log.exception("Incremental collection failed")
        raise
