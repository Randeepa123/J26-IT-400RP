# Kukule Ganga Research Data Pipelines

**Research Project:** Electricity Demand Forecasting and Hydropower Generation Optimisation  
**Location:** Kukule Ganga Power Station, Kalawana, Sri Lanka  
**Python version:** 3.11+

---

## Overview

Three **independent** Python data pipelines for the Kukule Ganga research project:

| Script | Purpose | Primary Source |
|--------|---------|----------------|
| `forecast_national_electricity_demand.py` | Forecast Sri Lanka national electricity demand (15 days) | edlcare.edl.lk |
| `extract_kukule_generation_history.py` | Retrieve Kukule PS daily generation history (5 years) | samanalacomplex.lk |
| `extract_kukule_pond_water_levels.py` | Retrieve Kukule Pond daily water levels (5 years) | samanalacomplex.lk |

These datasets are **separate and independent**:
- National electricity consumption ≠ Kukule generation
- Kukule daily generation ≠ water level or inflow
- Kukule Pond water level is a hydrological state, not a demand or generation metric

---

## Installation

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install Playwright browser (required for Script 1)
playwright install chromium
```

---

## Running Each Script

### Script 1 – National Electricity Demand Forecast

```bash
python forecast_national_electricity_demand.py
```

**Options:**
```
--start-date YYYY-MM-DD     Historical data start date  (default: 2021-10-19)
--end-date   YYYY-MM-DD     Historical data end date    (default: 2026-10-18)
--forecast-origin YYYY-MM-DD  Override forecast origin (default: last observed date)
--horizon    INT             Forecast horizon in days    (default: 15)
--output-dir PATH            Directory for output files  (default: script directory)
--headless / --no-headless   Run Playwright headless     (default: headless=True)
```

**Example:**
```bash
python forecast_national_electricity_demand.py \
    --start-date 2021-10-19 \
    --end-date 2026-10-18 \
    --horizon 15 \
    --output-dir "g:\SLIIT\Research\Rainfall data"
```

**Outputs:**
- `national_daily_electricity_consumption.csv` – cleaned history (or template if data unavailable)
- `national_daily_electricity_consumption_raw.csv` – raw scrape
- `national_demand_forecast_15days.csv` – 15-day forecast
- `national_demand_forecast.png` – forecast chart
- `national_demand_validation_report.txt` – validation and limitations report

---

### Script 2 – Kukule PS Generation History

```bash
python extract_kukule_generation_history.py
```

**Options:**
```
--start-date YYYY-MM-DD     Historical period start  (default: 2021-10-19)
--end-date   YYYY-MM-DD     Historical period end    (default: 2026-10-18)
--output-dir PATH            Directory for output files
--accumulate                 Append today's reading to existing daily CSV
```

**Example (accumulate daily):**
```bash
python extract_kukule_generation_history.py --accumulate
```

**Outputs:**
- `kukule_generation_raw.csv` – raw extracted records (today's value)
- `kukule_generation_daily_5years.csv` – 5-year template with observed values where available
- `kukule_generation_missing_dates.csv` – list of missing dates
- `kukule_generation_history.png` – generation chart
- `kukule_generation_extraction_report.txt` – extraction report

---

### Script 3 – Kukule Pond Water Level History

```bash
python extract_kukule_pond_water_levels.py
```

**Options:**
```
--start-date YYYY-MM-DD     Historical period start  (default: 2021-10-19)
--end-date   YYYY-MM-DD     Historical period end    (default: 2026-10-18)
--output-dir PATH            Directory for output files
--accumulate                 Append today's reading to existing daily CSV
```

**Example (accumulate daily):**
```bash
python extract_kukule_pond_water_levels.py --accumulate
```

**Outputs:**
- `kukule_pond_level_raw.csv` – raw extracted records
- `kukule_pond_water_level_daily_5years.csv` – 5-year template with observed values
- `kukule_pond_missing_dates.csv` – list of missing dates
- `kukule_pond_water_level_history.png` – water level chart (MASL + storage %)
- `kukule_pond_extraction_report.txt` – extraction report

---

## Known Data Limitations

### EDL Care (edlcare.edl.lk)
- The `/gensum/details` page is a **React Single-Page Application** (Vite build).
- Static HTTP scraping retrieves only the HTML shell — no data.
- Playwright is used to render JavaScript, but **authenticated login is required** for historical data.
- **No public historical JSON/CSV API** was found at this domain.
- The forecast CSV will contain `NaN` until real historical data is imported.

**To obtain historical national consumption data:**
1. Contact Electricity Distribution Lanka (EDL): https://edlcare.edl.lk/
2. Request the CEB Statistical Digest: https://www.ceb.lk/
3. Check PUCSL (Public Utilities Commission Sri Lanka): https://www.pucsl.gov.lk/
4. ADB / World Bank Sri Lanka energy databases

### Samanala Complex (samanalacomplex.lk)
- The public dashboard (`index.php`) shows **only the latest day's values** embedded in PHP-rendered HTML.
- **No historical API** endpoints were found (all candidate endpoints returned 404).
- `data.php` exists but returns the same current-day structure.
- Scripts 2 and 3 **extract the current day's value** and structure a 5-year template.
- Use `--accumulate` to build up a record day by day.

**To obtain historical records:**
1. Contact Samanala Complex / CEB directly: https://samanalacomplex.lk/
2. Contact the Irrigation Department of Sri Lanka (hydrological records): https://www.irrigation.gov.lk/
3. Request PUCSL licensed utility data

---

## Data Authenticity

All three scripts follow these rules:
- **No fabrication**: Synthetic or imputed data is never labelled as observed.
- **Raw data preserved**: Raw scraped files are saved separately from cleaned files.
- **Provenance recorded**: Every record includes `source_url`, `retrieved_at`, and `data_status`.
- **Template CSVs**: When historical data is unavailable, correctly-structured templates are provided.
- **No credentials hardcoded**: Scripts stop at authentication boundaries and report the limitation.
- **Validation flagging**: Values outside operational bounds are flagged for investigation, not silently removed.

---

## Data Fields

### Script 1 – National Forecast CSV
| Field | Description | Unit |
|-------|-------------|------|
| `date` | Forecast date | YYYY-MM-DD |
| `forecast_national_energy_mwh` | Forecast national daily energy | MWh |
| `lower_prediction_bound_mwh` | 80% interval lower bound | MWh |
| `upper_prediction_bound_mwh` | 80% interval upper bound | MWh |
| `forecast_model` | Model name used | — |
| `forecast_origin` | Date from which forecast was made | YYYY-MM-DD |
| `data_status` | `forecast` or `template_no_historical_data_retrieved` | — |

### Script 2 – Kukule Generation CSV
| Field | Description | Unit |
|-------|-------------|------|
| `date` | Generation date | YYYY-MM-DD |
| `kukule_generation_mwh` | Daily energy generated by Kukule PS | MWh |
| `unit` | Always `MWh` | — |
| `source_url` | Source URL | — |
| `retrieved_at` | UTC extraction timestamp | ISO 8601 |
| `data_status` | `observed` or `missing_not_available` | — |

### Script 3 – Kukule Pond Water Level CSV
| Field | Description | Unit |
|-------|-------------|------|
| `date` | Observation date | YYYY-MM-DD |
| `kukule_pond_level_masl` | Water surface elevation | MASL |
| `active_storage_percentage` | Active storage as % of capacity | % |
| `unit` | Always `MASL` | — |
| `source_url` | Source URL | — |
| `retrieved_at` | UTC extraction timestamp | ISO 8601 |
| `data_status` | `observed` or `missing_not_available` | — |

---

## Important Distinctions

| Variable | What it measures | What it does NOT measure |
|----------|-----------------|-------------------------|
| National electricity consumption | Sri Lanka national system demand | Kukule-specific consumption |
| Kukule daily generation | Energy generated by Kukule PS | National demand or water inflow |
| Kukule Pond water level | Hydrological state (elevation MASL) | Generation, demand, or inflow |

Correlation between national demand and Kukule generation **does not prove** that national demand caused Kukule generation. Any future estimate of Kukule's contribution to meeting national demand must be described as a system-level comparison, not a direct measure of consumers supplied by the station.

---

## Reproducibility

- Random seeds and model parameters are fixed inside each script.
- Forecast model selection is based on time-ordered validation MAE (no random train-test split).
- Run the same script on the same input data to reproduce the same outputs.

---

*Last updated: October 2026*
