"""
paths.py - single source of truth for every file/folder location used by Component 3 (v2).

Project layout (ROOT = folder containing README.md):
    configs/            scenarios_config.json (station + operating rules + reward weights)
    data/               station_dataset/, demand/, scenario_bank/   (inputs, generated scenario banks)
    data_pipelines/     rainfall_forecast/  (rainfall + inflow-forecast data pipelines and their outputs)
    src/component3/     all Python modules (run scripts from anywhere: python src/component3/<script>.py)
    tests/              automated tests
    models/             deployable checkpoints (selected DQN and hybrid)
    outputs/            training_runs/, evaluation_v2/, adaptation/, multiseed/, run_component3/, logs/, tuning/
    docs/               reports and notes
    legacy_v1/          frozen v1 snapshot (single-year LP/DQN work) + archive of removed duplicates
"""
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
ROOT = SRC_DIR.parents[1]

CONFIGS_DIR = ROOT / "configs"
DATA_DIR = ROOT / "data"
MODELS_DIR = ROOT / "models"
OUTPUTS_DIR = ROOT / "outputs"
DOCS_DIR = ROOT / "docs"

SCENARIOS_CONFIG = CONFIGS_DIR / "scenarios_config.json"

STATION_DATASET = DATA_DIR / "station_dataset" / "synthetic_kukule_integrated_dataset_5years.csv"
DEMAND_DIR = DATA_DIR / "demand"
DEMAND_5Y = DEMAND_DIR / "ratnapura_daily_electricity_demand_5years.csv"
DEMAND_5Y_V2 = DEMAND_DIR / "ratnapura_daily_electricity_demand_5years_v2_events.csv"
DEMAND_FORECAST_15D = DEMAND_DIR / "ratnapura_electricity_demand_forecast_15days.csv"
SCENARIO_BANK_DIR = DATA_DIR / "scenario_bank"

RAINFALL_DIR = ROOT / "data_pipelines" / "rainfall_forecast"
RAIN_10Y = RAINFALL_DIR / "ratnapura_synthetic_daily_rainfall_10years.csv"
INFLOW_FORECAST_15D = RAINFALL_DIR / "kukule_ganga_15day_forecast.csv"

TRAINING_RUNS_DIR = OUTPUTS_DIR / "training_runs"
EVALUATION_DIR = OUTPUTS_DIR / "evaluation_v2"
ADAPTATION_DIR = OUTPUTS_DIR / "adaptation"
MULTISEED_DIR = OUTPUTS_DIR / "multiseed"
RUN_COMPONENT3_DIR = OUTPUTS_DIR / "run_component3"
LOGS_DIR = OUTPUTS_DIR / "logs"
SELECTED_MODELS_JSON = OUTPUTS_DIR / "selected_models.json"
DASHBOARD_CACHE_DIR = OUTPUTS_DIR / "dashboard_cache"   # tables precomputed for the Grafana dashboards
GRAFANA_DIR = ROOT / "grafana"
TOOLS_DIR = ROOT / "tools"
API_HOST, API_PORT = "127.0.0.1", 8765               # port 8000 is commonly used by other tools

# daily / continuous mode (daily_runner.py)
LIVE_INPUT_DIR = DATA_DIR / "live_inputs"        # drop inflow_forecast.csv, demand_forecast.csv, state.json (+ optional solar_surplus.csv) here
LIVE_OUTPUT_DIR = OUTPUTS_DIR / "live"           # latest/, history/<stamp>/, decision_log.csv, status.json


def rel(path):
    """Path relative to ROOT with forward slashes (for storing in JSON / reports)."""
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def resolve(path):
    """Inverse of rel(): a ROOT-relative path (or absolute) -> absolute Path."""
    p = Path(str(path).replace("\\", "/"))
    return p if p.is_absolute() else ROOT / p
