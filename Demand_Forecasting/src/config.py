"""Environment configuration, resolved relative to the repository root."""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def path_env(name: str, default: str) -> Path:
    value = Path(os.getenv(name, default))
    return value if value.is_absolute() else ROOT / value

@dataclass
class Settings:
    dataset: Path = field(default_factory=lambda: path_env('DATA_PATH', 'drift_project/data/pucsl_clean_15min_enriched.csv'))
    drifts: Path = field(default_factory=lambda: path_env('DRIFT_PATH', 'models/classified_drift_points.csv'))
    artifacts: Path = field(default_factory=lambda: path_env('MODEL_DIR', 'models'))
    columns: dict = field(default_factory=lambda: json.loads(os.getenv('COLUMN_MAP', '{}')))
    rolling_days: int = field(default_factory=lambda: int(os.getenv('RECOVERY_WINDOW_DAYS', '7')))
    sustained_days: int = field(default_factory=lambda: int(os.getenv('RECOVERY_SUSTAINED_DAYS', '3')))
    recovery_min: int = field(default_factory=lambda: int(os.getenv('RECOVERY_MIN_OBSERVATIONS', '24')))
    threshold: float = field(default_factory=lambda: float(os.getenv('RECOVERY_THRESHOLD_PERCENT', '9.5')))
    def __post_init__(self):
        if min(self.rolling_days, self.sustained_days, self.recovery_min) < 1 or self.threshold <= 0:
            raise ValueError('Recovery settings must be positive')

CUTOFF = '2022-01-01'
REGIMES = [('pre_crisis', None, '2022-03-01'), ('crisis', '2022-03-01', '2022-08-01'),
           ('tariff_adjustment', '2022-08-01', '2023-06-01'), ('solar_growth', '2023-06-01', None)]
STRATEGIES = {'abrupt': 'Hard Reset', 'gradual': 'Decayed Reweighting', 'incremental': 'Decayed Reweighting', 'structural': 'Feature-Augmented Ridge Regression'}
