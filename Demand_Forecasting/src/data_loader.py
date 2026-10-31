"""Strict CSV validation without filling target observations."""
import hashlib
import numpy as np
import pandas as pd
from .config import REGIMES

ALIASES = {'date': 'timestamp', 'total_generation_mw': 'actual_generation_mw',
           'solar_generation_mw': 'solar_mw', 'temperature_2m_mean': 'temperature',
           'precipitation_sum': 'precipitation'}

def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def load_data(settings):
    if not settings.dataset.exists():
        raise ValueError(f'Dataset missing: {settings.dataset}. Set DATA_PATH.')
    df = pd.read_csv(settings.dataset, low_memory=False)
    mapping = {**ALIASES, **settings.columns}
    # Hourly-weather version takes priority over backward-compatible aliases.
    if 'temperature_2m' in df:
        mapping.pop('temperature_2m_mean', None)
        mapping['temperature_2m'] = 'temperature'
    df = df.rename(columns={k: v for k, v in mapping.items() if k in df and v not in df})
    if 'temperature' in df:
        df = df.drop(columns=['temperature_2m_mean', 'temperature_2m'], errors='ignore')
    if 'precipitation' in df:
        df = df.drop(columns=['precipitation_sum'], errors='ignore')
    required = {'timestamp', 'actual_generation_mw'}
    if not required.issubset(df):
        raise ValueError(f'Missing required columns: {sorted(required - set(df))}; configure COLUMN_MAP.')
    rows = len(df)
    df['timestamp'] = pd.to_datetime(df.timestamp, errors='coerce', format='mixed')
    if getattr(df.timestamp.dt, 'tz', None) is not None:
        df['timestamp'] = df.timestamp.dt.tz_convert('Asia/Colombo').dt.tz_localize(None)
    for col in ['actual_generation_mw', 'solar_mw', 'temperature', 'precipitation', 'shortwave_radiation', 'is_holiday']:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors='coerce').replace([np.inf, -np.inf], np.nan)
    invalid = df.timestamp.isna() | df.actual_generation_mw.isna()
    invalid_count = int(invalid.sum())
    df = df.loc[~invalid].sort_values('timestamp', kind='stable')
    duplicates = int(df.duplicated('timestamp').sum())
    df = df.drop_duplicates('timestamp', keep='first')
    # Existing main.py excludes <200 MW intervals (upstream resampling fills gaps with zero).
    low = int((df.actual_generation_mw < 200).sum())
    df = df[df.actual_generation_mw >= 200].reset_index(drop=True)
    if df.empty:
        raise ValueError('No valid observations remain after original >=200 MW quality filter.')
    df['regime'] = ''
    for name, start, end in REGIMES:
        mask = pd.Series(True, index=df.index)
        if start: mask &= df.timestamp >= pd.Timestamp(start)
        if end: mask &= df.timestamp < pd.Timestamp(end)
        df.loc[mask, 'regime'] = name
    quality = dict(rows_loaded=rows, invalid=invalid_count, duplicated=duplicates,
                   below_200_mw=low, dropped=rows-len(df), valid=len(df))
    return df, quality

def model_frame(df):
    """Restore original feature names for the existing ML modules."""
    return df.rename(columns={'timestamp': 'date', 'actual_generation_mw': 'total_generation_mw',
                              'solar_mw': 'solar_generation_mw', 'temperature': 'temperature_2m_mean',
                              'precipitation': 'precipitation_sum'})
