"""Load only locally prepared, provenance-checked research predictions."""
import json
import importlib.metadata
import joblib
import numpy as np
import pandas as pd
from drift_project.src.baseline import predict
from .config import CUTOFF
from .data_loader import digest, model_frame

def source_signature():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    return {name: digest(root / name) for name in ['drift_project/src/baseline.py', 'drift_project/src/adapt.py',
            'drift_project/src/drift.py', 'src/prepare.py', 'src/data_loader.py', 'src/config.py']}

class PredictionService:
    def __init__(self, settings, data):
        self.settings, self.data = settings, data
        folder = settings.artifacts
        manifest = json.loads((folder / 'manifest.json').read_text())
        if manifest['dataset_sha256'] != digest(settings.dataset) or manifest['column_map'] != settings.columns:
            raise ValueError('Dataset/configuration changed. Run python -m src.prepare again.')
        if manifest['source_sha256'] != source_signature():
            raise ValueError('ML source changed. Rebuild artifacts with python -m src.prepare.')
        if manifest['protocol'] != 'delayed-classification-v1':
            raise ValueError('Unsupported prediction provenance protocol')
        for package, version in manifest.get('dependencies', {}).items():
            if importlib.metadata.version(package) != version:
                raise ValueError(f'{package} version differs from training; rebuild artifacts.')
        for name in ['predictions.csv', 'bundle.joblib']:
            if digest(folder / name) != manifest['artifact_sha256'][name]:
                raise ValueError(f'Artifact changed: {name}; rebuild artifacts.')
        if digest(settings.drifts) != manifest['drifts_sha256']:
            raise ValueError('Drift output changed; rebuild artifacts.')
        raw = pd.read_csv(folder / 'predictions.csv', parse_dates=['timestamp'])
        if raw.timestamp.duplicated().any():
            raise ValueError('Duplicate prediction timestamps')
        expected = data[data.timestamp >= pd.Timestamp(CUTOFF)]
        if not raw.timestamp.equals(expected.timestamp.reset_index(drop=True)):
            raise ValueError('Prediction timestamps do not match the evaluation split')
        self.frame = expected.merge(raw, on='timestamp', validate='one_to_one')
        if not np.isfinite(self.frame[['static', 'adapted']].to_numpy()).all():
            raise ValueError('Non-finite predictions')
        # joblib is executable: load only artifacts generated locally by src.prepare.
        self.bundle = joblib.load(folder / 'bundle.joblib')
        self.manifest = manifest

    def selected_model(self, timestamp, adapted):
        chosen = self.bundle['static']
        if adapted:
            for entry in self.bundle['adapted']:
                if timestamp >= entry['available_at']:
                    chosen = entry
        return chosen

    def infer(self, timestamp, features, adapted=False):
        entry = self.selected_model(timestamp, adapted)
        row = pd.DataFrame([{'timestamp': timestamp, **features}])
        row = model_frame(row)
        for col, mean in entry['means'].items():
            if col not in row or row[col].isna().any():
                row[col] = mean
        return float(predict(entry['model'], row, **entry['flags'])[0]), entry['strategy']

def ape(actual, prediction):
    actual, prediction = np.asarray(actual, dtype=float), np.asarray(prediction, dtype=float)
    return np.divide(np.abs(actual-prediction)*100, np.abs(actual),
                     out=np.full(actual.shape, np.nan), where=np.isfinite(actual) & (actual != 0))
