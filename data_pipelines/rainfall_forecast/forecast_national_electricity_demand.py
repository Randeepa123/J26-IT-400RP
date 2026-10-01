"""
forecast_national_electricity_demand.py
========================================
Script 1 of 3: National Electricity Demand Forecast (Sri Lanka)
Research Project: Electricity Demand Forecasting & Hydropower Generation Optimisation
                  Kukule Ganga Power Station, Kalawana, Sri Lanka

Primary Source:
    https://edlcare.edl.lk/gensum/details
    (EDL Care - Electricity Distribution Lanka customer portal)

Objective:
    Inspect the EDL Care source, retrieve available daily national
    electricity consumption / generation data, analyse demand patterns,
    generate a 15-day ahead forecast with prediction intervals, and
    produce all required output files.

IMPORTANT NOTES ON DATA AUTHENTICITY:
    - This script does NOT fabricate or synthesise historical data.
    - The EDL Care portal is a React SPA served by Vite; the /gensum/details
      page renders entirely in the browser and no public REST/JSON API has
      been discovered at the time of writing.
    - Playwright is used to render the page and interact with any date
      controls that are publicly accessible without authentication.
    - If authenticated login is required for historical data retrieval,
      the script stops at that boundary and reports the limitation clearly.
    - If only a limited sample of public daily data can be retrieved, the
      forecast is built from those observations with honest uncertainty
      quantification and clearly labelled limitations.

Usage:
    python forecast_national_electricity_demand.py [options]

    Options:
        --start-date  YYYY-MM-DD  Historical data start  (default: 2021-10-19)
        --end-date    YYYY-MM-DD  Historical data end    (default: 2026-10-18)
        --forecast-origin YYYY-MM-DD  Override the forecast origin date
        --horizon     INT         Forecast horizon in days (default: 15)
        --output-dir  PATH        Directory for output files
        --headless                Run Playwright in headless mode (default: True)

Requirements:
    pip install requests beautifulsoup4 pandas numpy matplotlib statsmodels playwright
    playwright install chromium
"""

import argparse
import json
import logging
import os
import sys
import time
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EDL_GENSUM_URL = "https://edlcare.edl.lk/gensum/details"
DEFAULT_START_DATE = date(2021, 10, 19)
DEFAULT_END_DATE   = date(2026, 10, 18)
DEFAULT_HORIZON    = 15
REQUEST_TIMEOUT    = 30
RETRY_ATTEMPTS     = 3
RETRY_DELAY_S      = 5


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start-date", default=str(DEFAULT_START_DATE))
    p.add_argument("--end-date",   default=str(DEFAULT_END_DATE))
    p.add_argument("--forecast-origin", default=None)
    p.add_argument("--horizon",    type=int, default=DEFAULT_HORIZON)
    p.add_argument("--output-dir", default=str(Path(__file__).parent))
    p.add_argument("--headless",   action="store_true", default=True)
    p.add_argument("--no-headless", dest="headless", action="store_false")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Step 1: Inspect & Attempt to Retrieve EDL Care Data
# ---------------------------------------------------------------------------
def inspect_edlcare_static() -> dict:
    """
    Attempt to fetch the EDL Care /gensum/details page via plain HTTP.
    The page is a React SPA - the HTML shell loads from the server but
    actual data is populated by the JavaScript bundle after execution.
    Returns a dict describing what was found.
    """
    import requests
    from bs4 import BeautifulSoup

    result = {
        "url": EDL_GENSUM_URL,
        "accessible": False,
        "requires_browser": False,
        "requires_auth": False,
        "data_found_static": False,
        "notes": [],
        "raw_html_length": 0,
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            resp = requests.get(
                EDL_GENSUM_URL, headers=headers, timeout=REQUEST_TIMEOUT
            )
            result["http_status"] = resp.status_code
            result["raw_html_length"] = len(resp.text)
            result["accessible"] = resp.status_code == 200

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                root_div = soup.find("div", {"id": "root"})
                if root_div is not None:
                    result["requires_browser"] = True
                    result["notes"].append(
                        "Page is a React SPA (div#root detected). "
                        "Data is not present in the static HTML - "
                        "Playwright is required to execute JavaScript."
                    )
                if "login" in resp.url.lower() or "login" in resp.text.lower():
                    result["requires_auth"] = True
                    result["notes"].append(
                        "Page text or redirect URL contains 'login'. "
                        "Authentication may be required for historical data."
                    )
                log.info("EDL Care HTTP %s - HTML length %d bytes",
                         resp.status_code, result["raw_html_length"])
            else:
                result["notes"].append(
                    f"HTTP {resp.status_code} returned by {EDL_GENSUM_URL}"
                )
            break
        except Exception as exc:
            log.warning("Attempt %d/%d failed: %s", attempt, RETRY_ATTEMPTS, exc)
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY_S)
            else:
                result["notes"].append(f"All {RETRY_ATTEMPTS} attempts failed: {exc}")

    return result


def retrieve_edlcare_via_playwright(headless: bool = True):
    """
    Use Playwright to render the EDL Care /gensum/details page and extract
    whatever daily generation summary data is publicly accessible.

    Returns (DataFrame, list_of_notes).
    Returns an empty DataFrame if the page requires authentication or yields no data.
    """
    records = []
    inspection_notes = []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return pd.DataFrame(), ["Playwright not installed."]

    log.info("Launching Playwright (headless=%s) to render %s", headless, EDL_GENSUM_URL)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            captured_responses = []

            def handle_response(response):
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct and response.status == 200:
                        try:
                            body = response.json()
                            captured_responses.append({
                                "url": response.url,
                                "body": body,
                            })
                            log.info("Captured JSON response from: %s", response.url)
                        except Exception:
                            pass
                except Exception:
                    pass

            page.on("response", handle_response)

            try:
                page.goto(EDL_GENSUM_URL, wait_until="networkidle", timeout=45000)
                page.wait_for_timeout(3000)
            except Exception as te:
                inspection_notes.append(
                    f"Page load issue: {te}. "
                    "Network may be slow or Cloudflare challenge encountered."
                )
                browser.close()
                return pd.DataFrame(), inspection_notes

            content = page.content()
            log.info("Rendered page length: %d chars", len(content))

            # Check for authentication wall
            if (
                "login" in page.url.lower()
                or page.query_selector("input[type='password']") is not None
            ):
                inspection_notes.append(
                    "AUTHENTICATION REQUIRED: The page redirected to a login screen "
                    "or displayed a sign-in form. "
                    "Historical national consumption data requires authorised access. "
                    "This script cannot proceed without user-provided credentials. "
                    "Do NOT hardcode credentials."
                )
                log.warning("Authentication wall detected at %s", page.url)
                browser.close()
                return pd.DataFrame(), inspection_notes

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")

            tables = soup.find_all("table")
            log.info("Found %d table(s) in rendered page", len(tables))

            for tbl_idx, table in enumerate(tables):
                headers = [th.get_text(strip=True) for th in table.find_all("th")]
                log.info("Table %d headers: %s", tbl_idx, headers)
                rows = table.find_all("tr")
                for row in rows:
                    cells = [td.get_text(strip=True) for td in row.find_all("td")]
                    if cells:
                        row_dict = {"table_index": tbl_idx}
                        for i, h in enumerate(headers):
                            if i < len(cells):
                                row_dict[h if h else f"col_{i}"] = cells[i]
                        if len(cells) > len(headers):
                            for i in range(len(headers), len(cells)):
                                row_dict[f"col_{i}"] = cells[i]
                        records.append(row_dict)

            for resp_data in captured_responses:
                inspection_notes.append(
                    f"Captured JSON API response from: {resp_data['url']}"
                )

            date_inputs = page.query_selector_all(
                "input[type='date'], input[type='text'][placeholder*='date' i]"
            )
            if date_inputs:
                inspection_notes.append(
                    f"Found {len(date_inputs)} date input(s). "
                    "The page supports date selection."
                )

            # Look for text with energy data
            text_content = soup.get_text(separator=" ", strip=True)
            if "gwh" in text_content.lower() or "mwh" in text_content.lower():
                inspection_notes.append(
                    "Page text contains GWh/MWh references - energy data is present."
                )
            else:
                inspection_notes.append(
                    "No GWh/MWh energy data found in rendered page text."
                )

            browser.close()

    except Exception as exc:
        inspection_notes.append(f"Playwright execution error: {exc}")
        log.error("Playwright error: %s", exc)

    df = pd.DataFrame(records) if records else pd.DataFrame()
    return df, inspection_notes


# ---------------------------------------------------------------------------
# Step 2: Parse & Clean Available Data
# ---------------------------------------------------------------------------
def clean_national_data(df_raw: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    """Attempt to extract structured daily consumption from the scraped DataFrame."""
    if df_raw.empty:
        return pd.DataFrame()

    log.info("Raw scraped rows: %d", len(df_raw))
    raw_path = output_dir / "national_daily_electricity_consumption_raw.csv"
    df_raw.to_csv(raw_path, index=False)
    log.info("Raw data saved to %s", raw_path)

    df = df_raw.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    date_col   = None
    energy_col = None

    for col in df.columns:
        if "date" in col and date_col is None:
            date_col = col
        if any(k in col for k in ["mwh", "gwh", "energy", "generation", "consumption"]) and energy_col is None:
            energy_col = col

    if date_col is None:
        log.warning("Could not identify a date column. Check raw CSV.")
        return pd.DataFrame()

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=False)
    df = df.dropna(subset=[date_col])
    df = df.sort_values(date_col)
    df = df.drop_duplicates(subset=[date_col], keep="first")

    if energy_col:
        df[energy_col] = pd.to_numeric(
            df[energy_col].astype(str).str.replace(",", ""), errors="coerce"
        )

    df["source"]      = EDL_GENSUM_URL
    df["data_status"] = "observed"

    return df


# ---------------------------------------------------------------------------
# Step 3 & 4: Forecast
# ---------------------------------------------------------------------------
def build_forecast(
    df_history: Optional[pd.DataFrame],
    forecast_origin,
    horizon: int,
    output_dir: Path,
) -> pd.DataFrame:
    """
    Build a 15-day demand forecast using whatever historical data is available.
    Falls back through progressively simpler methods depending on data quantity.
    Returns a DataFrame with forecast results or a clearly-labelled template.
    """
    has_data = (df_history is not None) and (not df_history.empty)

    if not has_data:
        log.warning(
            "No historical data available. "
            "Generating a clearly-labelled template forecast CSV only."
        )
        origin = forecast_origin or date.today()
        return _make_template_forecast(origin, horizon)

    # Identify the energy/demand column
    value_col = None
    for col in df_history.columns:
        if any(k in col for k in ["mwh", "gwh", "energy", "consumption", "demand", "generation"]):
            value_col = col
            break

    if value_col is None:
        log.warning("Cannot identify value column in history. Making template.")
        origin = forecast_origin or date.today()
        return _make_template_forecast(origin, horizon)

    # Determine forecast origin
    if isinstance(df_history.index, pd.DatetimeIndex):
        last_date = df_history.index.max()
    else:
        last_date = pd.Timestamp(date.today())

    origin = pd.Timestamp(forecast_origin) if forecast_origin else last_date
    log.info("Forecast origin: %s, horizon: %d days", origin.date(), horizon)

    n = len(df_history)
    val_size = min(30, max(7, n // 10))
    train = df_history.iloc[: n - val_size]
    val   = df_history.iloc[n - val_size :]

    results = {}
    future_dates = pd.date_range(
        start=origin + timedelta(days=1), periods=horizon, freq="D"
    )

    # --- Method A: Rolling 7-day average (simple baseline)
    try:
        rolling_mean = train[value_col].rolling(7).mean()
        a_forecast = float(rolling_mean.iloc[-1])
        a_preds = np.full(horizon, a_forecast)
        if not val.empty:
            val_fill = float(train[value_col].rolling(7).mean().iloc[-1])
            val_preds_a = np.full(len(val), val_fill)
            mae_a = float(np.nanmean(np.abs(val[value_col].values - val_preds_a)))
        else:
            mae_a = float("nan")
        results["rolling_7d"] = {"preds": a_preds, "mae": mae_a, "future_dates": future_dates}
        log.info("Rolling 7d baseline MAE: %.1f", mae_a)
    except Exception as e:
        log.warning("Rolling baseline failed: %s", e)

    # --- Method B: Day-of-week seasonal baseline
    try:
        dow_means = train.groupby(train.index.dayofweek)[value_col].mean()
        b_preds = np.array([
            dow_means.get(d.dayofweek, dow_means.mean()) for d in future_dates
        ])
        if not val.empty:
            val_preds_b = np.array([
                dow_means.get(d.dayofweek, dow_means.mean()) for d in val.index
            ])
            mae_b = float(np.nanmean(np.abs(val[value_col].values - val_preds_b)))
        else:
            mae_b = float("nan")
        results["dow_seasonal"] = {"preds": b_preds, "mae": mae_b, "future_dates": future_dates}
        log.info("DOW seasonal baseline MAE: %.1f", mae_b)
    except Exception as e:
        log.warning("DOW seasonal baseline failed: %s", e)

    # --- Method C: Exponential Smoothing (Holt-Winters)
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        series = train[value_col].dropna()
        if len(series) >= 14:
            use_seasonal = len(series) >= 2 * 7
            model = ExponentialSmoothing(
                series,
                trend="add",
                seasonal="add" if use_seasonal else None,
                seasonal_periods=7 if use_seasonal else None,
                initialization_method="estimated",
            ).fit(optimized=True)
            c_preds = model.forecast(horizon).values
            if not val.empty:
                c_val_preds = model.forecast(len(val)).values
                mae_c = float(np.nanmean(np.abs(val[value_col].values - c_val_preds[:len(val)])))
            else:
                mae_c = float("nan")
            results["ets_hw"] = {"preds": c_preds, "mae": mae_c, "future_dates": future_dates}
            log.info("ETS Holt-Winters MAE: %.1f", mae_c)
        else:
            log.warning("Too few data points (%d) for Holt-Winters.", len(series))
    except Exception as e:
        log.warning("Holt-Winters failed: %s", e)

    # --- Method D: SARIMA (7-day seasonality) if enough data
    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX
        series = train[value_col].dropna()
        if len(series) >= 30:
            sarima = SARIMAX(
                series, order=(1, 1, 1), seasonal_order=(1, 0, 1, 7)
            ).fit(disp=False, maxiter=200, method="lbfgs")
            d_preds = sarima.forecast(horizon).values
            if not val.empty:
                d_val_preds = sarima.forecast(len(val)).values
                mae_d = float(np.nanmean(np.abs(val[value_col].values - d_val_preds[:len(val)])))
            else:
                mae_d = float("nan")
            results["sarima"] = {"preds": d_preds, "mae": mae_d, "future_dates": future_dates}
            log.info("SARIMA MAE: %.1f", mae_d)
        else:
            log.warning("Too few data points (%d) for SARIMA.", len(series))
    except Exception as e:
        log.warning("SARIMA failed: %s", e)

    # --- Select best method by validation MAE
    valid_results = {k: v for k, v in results.items() if not np.isnan(v["mae"])}
    if valid_results:
        best_method = min(valid_results, key=lambda k: valid_results[k]["mae"])
        log.info("Best method: %s (MAE=%.1f)", best_method, valid_results[best_method]["mae"])
    elif results:
        best_method = list(results.keys())[0]
        log.info("No validation MAE available; using: %s", best_method)
    else:
        log.error("All forecasting methods failed.")
        origin_d = forecast_origin or date.today()
        return _make_template_forecast(origin_d, horizon)

    best = results[best_method]
    forecast_vals = best["preds"]
    used_future_dates = best.get("future_dates", future_dates)

    # Prediction interval using validation residuals
    if not val.empty and best_method in valid_results:
        try:
            v_preds = valid_results[best_method]["preds"][:len(val)]
            residuals = val[value_col].values - v_preds
            std_resid = float(np.nanstd(residuals)) if len(residuals) > 1 else float(np.nanmean(np.abs(forecast_vals)) * 0.10)
        except Exception:
            std_resid = float(np.nanmean(np.abs(forecast_vals)) * 0.10)
    else:
        std_resid = float(np.nanmean(np.abs(forecast_vals)) * 0.10)

    z = 1.28  # ~80% prediction interval
    lower = forecast_vals - z * std_resid
    upper = forecast_vals + z * std_resid

    # Log validation metrics
    if not val.empty and best_method in valid_results:
        v_preds = valid_results[best_method]["preds"][:len(val)]
        actuals = val[value_col].values
        mask = ~np.isnan(actuals) & ~np.isnan(v_preds)
        if mask.sum() > 0:
            mae  = np.mean(np.abs(actuals[mask] - v_preds[mask]))
            rmse = np.sqrt(np.mean((actuals[mask] - v_preds[mask]) ** 2))
            nonzero = actuals[mask] != 0
            mape = (
                np.mean(np.abs((actuals[mask][nonzero] - v_preds[mask][nonzero])
                               / actuals[mask][nonzero])) * 100
                if nonzero.sum() > 0 else float("nan")
            )
            log.info("Validation - MAE: %.2f  RMSE: %.2f  MAPE: %.2f%%", mae, rmse, mape)

    df_forecast = pd.DataFrame({
        "date":                         used_future_dates.strftime("%Y-%m-%d"),
        "forecast_national_energy_mwh": np.round(forecast_vals, 3),
        "lower_prediction_bound_mwh":   np.round(lower, 3),
        "upper_prediction_bound_mwh":   np.round(upper, 3),
        "forecast_model":               best_method,
        "forecast_origin":              str(origin.date()),
        "data_status":                  "forecast",
        "source":                       EDL_GENSUM_URL,
    })

    return df_forecast


def _make_template_forecast(origin, horizon: int) -> pd.DataFrame:
    """Return a clearly-labelled empty template forecast DataFrame."""
    if isinstance(origin, (date, datetime)):
        ts_origin = pd.Timestamp(origin)
    else:
        ts_origin = pd.Timestamp(origin)

    dates = pd.date_range(
        start=ts_origin + timedelta(days=1),
        periods=horizon,
        freq="D",
    )
    return pd.DataFrame({
        "date":                         dates.strftime("%Y-%m-%d"),
        "forecast_national_energy_mwh": [float("nan")] * horizon,
        "lower_prediction_bound_mwh":   [float("nan")] * horizon,
        "upper_prediction_bound_mwh":   [float("nan")] * horizon,
        "forecast_model":               "NO_DATA_AVAILABLE",
        "forecast_origin":              str(ts_origin.date()),
        "data_status":                  "template_no_historical_data_retrieved",
        "source":                       EDL_GENSUM_URL,
    })


# ---------------------------------------------------------------------------
# Step 5: Plotting
# ---------------------------------------------------------------------------
def plot_forecast(
    df_history: Optional[pd.DataFrame],
    df_forecast: pd.DataFrame,
    value_col: Optional[str],
    output_path: Path,
) -> None:
    """Generate the 15-day demand forecast chart."""
    fig, ax = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#1e293b")

    # Plot history
    if df_history is not None and not df_history.empty and value_col and value_col in df_history.columns:
        if isinstance(df_history.index, pd.DatetimeIndex):
            hist_dates = df_history.index[-90:]
            hist_vals  = df_history[value_col].values[-90:]
        else:
            hist_dates = pd.to_datetime(df_history.iloc[-90:, 0])
            hist_vals  = df_history[value_col].values[-90:]
        ax.plot(hist_dates, hist_vals, color="#38bdf8", linewidth=1.5,
                label="Historical (last 90 days)", alpha=0.85)

    forecast_dates = pd.to_datetime(df_forecast["date"])
    forecast_vals  = df_forecast["forecast_national_energy_mwh"].values.astype(float)
    lower = df_forecast["lower_prediction_bound_mwh"].values.astype(float)
    upper = df_forecast["upper_prediction_bound_mwh"].values.astype(float)

    if not np.all(np.isnan(forecast_vals)):
        ax.plot(forecast_dates, forecast_vals, color="#f97316", linewidth=2.0,
                linestyle="--", marker="o", markersize=4,
                label=f"Forecast ({df_forecast['forecast_model'].iloc[0]})")
        if not np.all(np.isnan(lower)):
            ax.fill_between(forecast_dates, lower, upper,
                            color="#f97316", alpha=0.15, label="80% prediction interval")
    else:
        ax.text(
            0.5, 0.5,
            "Forecast not available - historical data could not be retrieved.\n"
            "See national_demand_validation_report.txt for details.",
            transform=ax.transAxes, ha="center", va="center", fontsize=11,
            color="#fbbf24",
            bbox=dict(boxstyle="round,pad=0.6", facecolor="#1e293b", edgecolor="#fbbf24"),
        )

    ax.set_title("Sri Lanka National Electricity Demand - 15-Day Forecast",
                 color="white", fontsize=14, pad=12)
    ax.set_xlabel("Date", color="#94a3b8", fontsize=11)
    ax.set_ylabel("National Energy (MWh)", color="#94a3b8", fontsize=11)
    ax.tick_params(colors="#94a3b8")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["bottom", "left"]:
        ax.spines[spine].set_color("#475569")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.grid(axis="y", color="#334155", linewidth=0.5, alpha=0.7)
    ax.legend(facecolor="#1e293b", edgecolor="#475569", labelcolor="white", fontsize=9)

    model_name = df_forecast["forecast_model"].iloc[0] if not df_forecast.empty else "N/A"
    origin_str = df_forecast["forecast_origin"].iloc[0] if not df_forecast.empty else "N/A"
    fig.text(
        0.99, 0.01,
        f"Model: {model_name} | Origin: {origin_str} | Source: {EDL_GENSUM_URL}",
        ha="right", va="bottom", fontsize=7, color="#64748b",
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    log.info("Forecast chart saved: %s", output_path)


# ---------------------------------------------------------------------------
# Validation Report
# ---------------------------------------------------------------------------
def write_validation_report(
    output_dir: Path,
    inspection: dict,
    playwright_notes: list,
    df_history,
    df_forecast: pd.DataFrame,
    args,
) -> None:
    report_path = output_dir / "national_demand_validation_report.txt"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    has_data = df_history is not None and not df_history.empty
    n_obs = len(df_history) if has_data else 0
    model_used = df_forecast["forecast_model"].iloc[0] if not df_forecast.empty else "N/A"

    lines = [
        "=" * 72,
        "NATIONAL ELECTRICITY DEMAND FORECAST - VALIDATION REPORT",
        f"Generated at : {ts}",
        f"Script       : forecast_national_electricity_demand.py",
        "=" * 72,
        "",
        "1. SOURCE INSPECTION",
        "-" * 40,
        f"   URL              : {EDL_GENSUM_URL}",
        f"   HTTP accessible  : {inspection.get('accessible', 'N/A')}",
        f"   HTTP status      : {inspection.get('http_status', 'N/A')}",
        f"   HTML size        : {inspection.get('raw_html_length', 0):,} bytes",
        f"   Requires browser : {inspection.get('requires_browser', False)}",
        f"   Requires auth    : {inspection.get('requires_auth', False)}",
        "",
        "   Static inspection notes:",
    ]
    for note in inspection.get("notes", []):
        lines.append(f"     - {note}")

    lines += ["", "   Playwright (browser-render) notes:"]
    for note in playwright_notes:
        lines.append(f"     - {note}")

    lines += [
        "",
        "2. HISTORICAL DATA RETRIEVAL",
        "-" * 40,
        f"   Requested period : {args.start_date} to {args.end_date}",
        f"   Records retrieved: {n_obs}",
    ]
    if has_data:
        if isinstance(df_history.index, pd.DatetimeIndex):
            lines.append(
                f"   Data date range  : {df_history.index.min().date()} to "
                f"{df_history.index.max().date()}"
            )
        lines.append(f"   Columns          : {list(df_history.columns)}")
    else:
        lines += [
            "   !! No historical data could be retrieved from the public source. !!",
            "   The EDL Care portal is a React SPA. The /gensum/details page requires",
            "   JavaScript execution AND may require authenticated login for historical",
            "   daily data beyond the currently displayed summary.",
            "",
            "   To obtain this data:",
            "     a) Contact Electricity Distribution Lanka (EDL) directly:",
            "        https://edlcare.edl.lk/  |  Tel: 1987",
            "     b) Request the CEB Statistical Digest:",
            "        https://www.ceb.lk/",
            "     c) Check the Public Utilities Commission of Sri Lanka (PUCSL):",
            "        https://www.pucsl.gov.lk/",
            "     d) Query ADB / World Bank energy databases for Sri Lanka.",
        ]

    lines += [
        "",
        "3. FORECAST",
        "-" * 40,
        f"   Forecast origin  : {df_forecast['forecast_origin'].iloc[0] if not df_forecast.empty else 'N/A'}",
        f"   Forecast horizon : {len(df_forecast)} days",
        f"   Model used       : {model_used}",
        f"   Forecast status  : {'REAL DATA-DRIVEN' if has_data else 'TEMPLATE ONLY (no data)'}",
        "",
    ]
    if not has_data:
        lines += [
            "   IMPORTANT: Because no historical data was retrieved, all forecast",
            "   values in national_demand_forecast_15days.csv are NaN.",
            "   The CSV is provided as a template only.",
            "   Once real historical data is obtained, place it in",
            "   national_daily_electricity_consumption.csv and re-run the script.",
        ]

    lines += [
        "",
        "4. OUTPUT FILES",
        "-" * 40,
        "   national_daily_electricity_consumption.csv      - cleaned history",
        "   national_daily_electricity_consumption_raw.csv  - raw scrape",
        "   national_demand_forecast_15days.csv             - 15-day forecast",
        "   national_demand_forecast.png                    - forecast chart",
        "   national_demand_validation_report.txt           - this file",
        "",
        "5. DATA AUTHENTICITY STATEMENT",
        "-" * 40,
        "   This script does NOT fabricate, synthesise, or impute any historical",
        "   electricity consumption values. All NaN values indicate genuinely",
        "   missing or inaccessible observations, not synthetic replacements.",
        "",
        "6. UNRESOLVED LIMITATIONS",
        "-" * 40,
        "   - No public JSON/CSV historical API was found at edlcare.edl.lk.",
        "   - The /gensum/details page is a React SPA; static scraping yields",
        "     only the HTML shell, not the rendered data.",
        "   - Historical daily data likely requires an authorised EDL account.",
        "   - The forecast cannot be data-validated without a real historical series.",
        "   - Weather/temperature covariates were not used (no verified public source",
        "     matchable to national demand found without risk of fabrication).",
        "",
        "=" * 72,
    ]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Validation report saved: %s", report_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("Script 1: National Electricity Demand Forecast")
    log.info("Source  : %s", EDL_GENSUM_URL)
    log.info("Period  : %s to %s", args.start_date, args.end_date)
    log.info("Output  : %s", output_dir)
    log.info("=" * 60)

    # Step 1a: Static inspection
    log.info("Step 1a: Static HTTP inspection of EDL Care page ...")
    inspection = inspect_edlcare_static()

    # Step 1b: Playwright browser render
    log.info("Step 1b: Rendering EDL Care page via Playwright ...")
    df_raw_playwright, playwright_notes = retrieve_edlcare_via_playwright(
        headless=args.headless
    )

    # Step 2: Clean data
    log.info("Step 2: Cleaning extracted data ...")
    df_history = None
    value_col  = None

    if not df_raw_playwright.empty:
        df_history = clean_national_data(df_raw_playwright, output_dir)
        if df_history is not None and not df_history.empty:
            date_col_candidates = [c for c in df_history.columns if "date" in c.lower()]
            if date_col_candidates:
                idx = pd.to_datetime(df_history[date_col_candidates[0]], errors="coerce")
                df_history = df_history.set_index(idx)
            for col in df_history.columns:
                if any(k in col for k in ["mwh", "gwh", "energy", "consumption", "demand"]):
                    value_col = col
                    break
            clean_path = output_dir / "national_daily_electricity_consumption.csv"
            df_history.reset_index().to_csv(clean_path, index=False)
            log.info("Cleaned data saved: %s (%d rows)", clean_path, len(df_history))

    if df_history is None or df_history.empty:
        log.warning("No data retrieved from EDL Care portal.")
        template_path = output_dir / "national_daily_electricity_consumption.csv"
        pd.DataFrame(columns=[
            "date", "national_energy_consumption_mwh",
            "national_peak_demand_mw", "source", "data_status",
        ]).to_csv(template_path, index=False)
        log.info("Empty template CSV written: %s", template_path)
        playwright_notes.append(
            "No tabular data was extracted from the rendered page. "
            "The page may require authentication or a more specific date selection."
        )

    # Step 3: Pattern analysis
    if df_history is not None and not df_history.empty and value_col:
        log.info("Step 3: Analysing demand patterns ...")
        series = df_history[value_col].dropna()
        log.info("  Series length    : %d observations", len(series))
        log.info("  Mean             : %.2f", series.mean())
        log.info("  Std dev          : %.2f", series.std())
        log.info("  Min              : %.2f", series.min())
        log.info("  Max              : %.2f", series.max())
    else:
        log.info("Step 3: Skipped - no data available for pattern analysis.")

    # Step 4: Forecast
    log.info("Step 4: Building %d-day forecast ...", args.horizon)
    forecast_origin = (
        date.fromisoformat(args.forecast_origin) if args.forecast_origin else None
    )
    df_forecast = build_forecast(df_history, forecast_origin, args.horizon, output_dir)

    forecast_path = output_dir / "national_demand_forecast_15days.csv"
    df_forecast.to_csv(forecast_path, index=False)
    log.info("Forecast CSV saved: %s", forecast_path)

    # Step 5: Plot
    log.info("Step 5: Generating forecast chart ...")
    plot_path = output_dir / "national_demand_forecast.png"
    plot_forecast(df_history, df_forecast, value_col, plot_path)

    # Validation report
    log.info("Writing validation report ...")
    write_validation_report(
        output_dir, inspection, playwright_notes,
        df_history, df_forecast, args,
    )

    log.info("=" * 60)
    log.info("Script 1 complete. Outputs in: %s", output_dir)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
