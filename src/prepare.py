"""Explicit offline experiment build. Never called by API startup."""
import json
import platform
import importlib.metadata
import joblib
import numpy as np
import pandas as pd
from drift_project.src.baseline import train_baseline, predict
from drift_project.src.adapt import route_and_adapt
from drift_project.src.drift import detect_drift_points, classify_point, confirm_structural
from .config import Settings, CUTOFF, STRATEGIES
from .data_loader import load_data, model_frame, digest
from .prediction_service import source_signature

FLAGS = {'use_holiday': True, 'use_weather': True}

def fill_context(frame, reference=None):
    """Use only training-context means, avoiding evaluation-batch mean leakage."""
    cols = [c for c in ['temperature_2m_mean', 'precipitation_sum', 'shortwave_radiation',
                       'is_holiday', 'solar_generation_mw'] if c in frame]
    means = reference if reference is not None else {c: float(frame[c].mean()) if frame[c].notna().any() else 0.0 for c in cols}
    return frame.fillna(means), means

def prepare(settings=None):
    settings = settings or Settings()
    data, quality = load_data(settings)
    df = model_frame(data)
    if 'solar_generation_mw' in df:
        df['solar_generation_mw'] = df.solar_generation_mw.clip(0, 1000)
    train, test = df[df.date < CUTOFF].copy(), df[df.date >= CUTOFF].copy()
    if len(train) < 96 or test.empty:
        raise ValueError('Need at least 96 pre-2022 training observations and a nonempty test split')
    train, means = fill_context(train)
    model, names = train_baseline(train, **FLAGS)
    eval_frame, _ = fill_context(test, means)
    static = predict(model, eval_frame, **FLAGS)
    warm = train[train.date >= '2021-07-01']
    warm_errors = pd.Series(np.abs(warm.total_generation_mw-predict(model, warm, **FLAGS)).to_numpy()/warm.total_generation_mw.to_numpy(), index=warm.date)
    errors = pd.Series(np.abs(test.total_generation_mw.to_numpy()-static)/test.total_generation_mw.to_numpy(), index=test.date)
    all_errors = pd.concat([warm_errors, errors])
    dates = detect_drift_points(errors, warmup_errors=warm_errors)
    classified = []
    for dp in dates:
        label, tau, delta = classify_point(dp, all_errors)
        def ablation(dt):
            tr = df[(df.date >= dt-pd.Timedelta(days=180)) & (df.date < dt)]
            te = df[(df.date >= dt) & (df.date < dt+pd.Timedelta(days=30))]
            if len(tr) < 96 or len(te) < 96: return pd.Series(dtype=float), pd.Series(dtype=float)
            tr, avg = fill_context(tr)
            te, _ = fill_context(te, avg)
            results = []
            for solar in [False, True]:
                flags = {**FLAGS, 'use_solar': solar, 'include_trend_annual': False}
                m, _ = train_baseline(tr, **flags)
                results.append(pd.Series(np.abs(te.total_generation_mw.to_numpy()-predict(m, te, **flags))/te.total_generation_mw.to_numpy(), index=te.date))
            return results
        structural, reduction = confirm_structural(dp, test, all_errors, ablation)
        available = dp + pd.Timedelta(days=30)
        classified.append(dict(date=dp, label=structural or label, tau=tau, delta=delta,
                               structural_reduction=reduction, available_at=available,
                               regime=data.loc[data.timestamp.searchsorted(dp), 'regime'] if dp <= data.timestamp.max() else None))
    drifts = pd.DataFrame(classified, columns=['date','label','tau','delta','structural_reduction','available_at','regime'])
    adapted = static.copy()
    bundle = {'static': dict(model=model, flags=FLAGS, means=means, strategy='Static Baseline', feature_names=names), 'adapted': []}
    for event in classified:
        if event['label'] not in STRATEGIES or event['available_at'] > test.date.max(): continue
        # Original adaptation's +14/+15 day training windows are now entirely past.
        history = df[df.date < event['available_at']].copy()
        end = event['date'] + pd.Timedelta(days=15 if event['label']=='abrupt' else 14)
        start = event['date'] - pd.Timedelta(days=45 if event['label']=='abrupt' else 180)
        context = history[(history.date >= start) & (history.date <= end)]
        if len(context) < 96: continue
        _, avg = fill_context(context)
        history, _ = fill_context(history, avg)
        m = route_and_adapt(event['label'], history, event['date'], **FLAGS)
        flags = m._adapt_flags
        mask = test.date >= event['available_at']
        segment, _ = fill_context(test.loc[mask], avg)
        adapted[mask.to_numpy()] = predict(m, segment, **flags)
        bundle['adapted'].append(dict(model=m, flags=flags, means=avg, available_at=event['available_at'], strategy=STRATEGIES[event['label']], trained_through=context.date.max()))
    settings.artifacts.mkdir(parents=True, exist_ok=True)
    settings.drifts.parent.mkdir(parents=True, exist_ok=True)
    drifts.to_csv(settings.drifts, index=False)
    pd.DataFrame({'timestamp': test.date, 'static': static, 'adapted': adapted}).to_csv(settings.artifacts/'predictions.csv', index=False)
    joblib.dump(bundle, settings.artifacts/'bundle.joblib')
    manifest = dict(protocol='delayed-classification-v1', dataset_sha256=digest(settings.dataset),
                    source_sha256=source_signature(), column_map=settings.columns, drifts_sha256=digest(settings.drifts),
                    artifact_sha256={n: digest(settings.artifacts/n) for n in ['predictions.csv','bundle.joblib']},
                    train_start=str(train.date.min()), train_end=str(train.date.max()),
                    test_start=str(test.date.min()), test_end=str(test.date.max()), validation_split=None,
                    feature_names=names, quality=quality, python=platform.python_version(),
                    dependencies={p: importlib.metadata.version(p) for p in ['numpy','pandas','scikit-learn','river','joblib']},
                    assumptions=['Classification available 30 days after detection; adaptation begins then.',
                                 'Weather inputs are observed daily aggregates, not day-ahead weather forecasts.',
                                 'Solar clipped to [0,1000] for model input as in original main.py; UI retains observed solar.',
                                 'Training-context feature means replace missing weather; no target imputation.',
                                 'No verified historical event catalogue is present.'])
    (settings.artifacts/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2))

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    prepare()
