# Drift-Type-Aware Adaptive Electricity Demand Forecasting

Tested, runnable pipeline (verified end-to-end with synthetic data standing
in for real PUCSL data — see "What's actually confirmed" below).

## Setup

```bash
pip install pandas numpy scikit-learn river requests holidays
```

## Run order

```bash
cd src
python pucsl_scraper.py            # 1. ONE-TIME: backfill 10 years of history
python enrich_calendar_weather.py  # 2. add holiday + weather columns
python main.py                     # 3. run baseline -> drift -> adapt -> evaluate
```

## Continuous collection (server deployment)

After the one-time backfill above, use `incremental_collector.py` instead
of re-running `pucsl_scraper.py` — it only fetches what's new since the
last run (tracked in `data/last_collected.txt`) and appends to the
existing dataset, rather than redoing the full 10-year pull every time.

```bash
python src/incremental_collector.py
```

Schedule it with cron (e.g. daily at 1 AM):
```
0 1 * * * cd /path/to/drift_project && venv/bin/python src/incremental_collector.py >> logs/collector.log 2>&1
```

Logs go to `logs/incremental_collector.log` automatically (via Python's
`logging` module) regardless of whether you also redirect stdout in cron.

`main.py` expects `data/pucsl_clean_daily_enriched.csv` and
`data/event_table.csv` (date, event_type, description columns) to exist.

## What's actually confirmed vs. not yet tested

| Part | Status |
|---|---|
| `holidays` library (Sri Lanka + Poya days) | **Confirmed** — tested directly, returns real dates |
| Full pipeline wiring (baseline → drift → classify → adapt → evaluate) | **Confirmed** — ran end-to-end on synthetic data, two real bugs found and fixed |
| PUCSL `actual-system-dispatch` API contract | **Confirmed by you** — real traffic you captured |
| Open-Meteo weather API contract | Documented across multiple sources, **not executed live** (sandbox network restriction) |
| ADWIN drift-detection sensitivity | **Not yet tuned** — only caught 1 point on synthetic test data; expect to need threshold tuning on real data |
| `PLANT_MAPPING` (which plant ID = which fuel type) | **Still needs you** to find via browser DevTools |

## Known TODOs marked in code (`ADJUST` comments)

- `pucsl_scraper.py`: `PLANT_MAPPING` dict — fill in plant ID → fuel type
- `main.py`: `CUTOFF` date — confirm 2022-01-01 matches your actual crisis onset
- `drift.py`: `classify_point()` — tau is a placeholder; wire in DDM's real warning→drift gap for a precise transition-duration measurement
- `evaluate.py` regime boundaries in `main.py` — adjust to your confirmed event dates once the real event table is finalized

## File map

```
src/
  pucsl_scraper.py           # real API -> data/pucsl_clean_daily.csv
  enrich_calendar_weather.py # -> data/pucsl_clean_daily_enriched.csv
  baseline.py                # Ridge regression baseline (swap for LSTM later)
  drift.py                   # ADWIN detection + abrupt/gradual/structural classification
  adapt.py                   # hard_reset / decayed_reweight / feature_augmented + router
  evaluate.py                # regime-by-regime MAPE/RMSE + adaptation lag
  main.py                    # orchestrates all of the above
data/
  event_table.csv            # you create this: date, event_type, description
```
