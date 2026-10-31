"""Authoritative drift output; temporal event proximity is never confirmation."""
import pandas as pd
from .config import STRATEGIES

def load_drifts(path):
    if not path.exists():
        raise ValueError(f'Drift file missing: {path}. Run python -m src.prepare or set DRIFT_PATH.')
    df = pd.read_csv(path).rename(columns={'date': 'drift_date', 'label': 'drift_type'})
    if not {'drift_date', 'drift_type'}.issubset(df):
        raise ValueError('Drift CSV requires date,label (or drift_date,drift_type)')
    df['drift_date'] = pd.to_datetime(df.drift_date, errors='coerce')
    if df.drift_date.isna().any() or not df.drift_type.isin([*STRATEGIES, 'unclassified']).all():
        raise ValueError('Invalid drift timestamps or classifications')
    if df.drift_date.duplicated().any():
        raise ValueError('Duplicate drift timestamps')
    for col in ['historical_event', 'event_source', 'notes', 'confidence']:
        if col not in df: df[col] = None
    if 'event_match' not in df: df['event_match'] = None
    # Confirmation needs both an explicit true match and recorded supporting evidence.
    confirmed = df.event_match.astype(str).str.lower().isin(['true', '1']) & df.event_source.notna() & df.historical_event.notna()
    unmatched = df.event_match.astype(str).str.lower().isin(['false', '0'])
    plausible = df.historical_event.notna() & ~confirmed & ~unmatched
    df['event_match'] = [True if ok else False if no else None for ok, no in zip(confirmed, unmatched)]
    df['match_status'] = ['confirmed' if ok else 'unmatched' if no else 'plausible' if maybe else 'unknown'
                          for ok, no, maybe in zip(confirmed, unmatched, plausible)]
    df['strategy'] = df.drift_type.map(STRATEGIES)
    if 'regime' not in df: df['regime'] = None
    return df.sort_values('drift_date').reset_index(drop=True)
