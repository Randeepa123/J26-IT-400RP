# Repository audit and research protocol

Inspected on 2026-10-20 before implementation. Original source/data remain in `drift_project/`; application entry points are at repository root.

## Inventory

- Enriched 15-minute CSV: 350,593 records, 2016-10-14 00:00 through 2026-10-14 00:00. The original >=200 MW filter retains 285,730 records through 2026-10-13 00:00.
- Daily clean/enriched files and weekly raw plant dispatch chunks are present. No drift outputs, evaluation predictions or trained model artifacts existed at audit time.
- `date` is local Sri Lanka time. `total_generation_mw` sums plant dispatch columns; `solar_generation_mw` sums mapped solar sources. Weather is `temperature_2m_mean` (daily mean °C), `precipitation_sum` (daily mm), plus max/min temperature and rain. Holiday flags use Sri Lankan holidays.
- Actual CSV matches the older daily-weather builder (`build_15min_datasetV1.py`), not the hourly-weather builder. Daily aggregates repeat across 15-minute intervals. They cannot substantiate a claim of advance weather forecasting.
- Both builders resample plant dispatch and fill gaps with zero before calculating total generation. The application retains `main.py`'s <200 MW exclusion and reports it. This CSV cannot distinguish artificial zeros from genuine low-output intervals. The dashboard never fills a target value.

## Existing experiment

`main.py` fits Ridge(alpha=10) before 2022-01-01 and tests thereafter. No validation split or hyperparameter search exists. Features: linear annual trend; annual, weekly, daily and half-daily trigonometric encodings; holiday and available weather. ADWIN warms on errors since 2021-07-01, processes daily clipped/scaled/smoothed errors and uses a 60-day cooldown.

Classification reads 30 days before/after drift; transition duration and normalized mean shift distinguish abrupt from gradual. Following-30-day solar ablation calls structural drift at relative error reduction >=1.5%. These are algorithmic labels, not verified causes or calibrated confidence.

Routing: abrupt -> Hard Reset; gradual/incremental -> Decayed Reweighting; structural -> Feature-Augmented Ridge. Reset trains -45 to +15 days; weighted strategies train -180 to +14 days with original half-lives and Ridge alpha. They disable annual trend. Original orchestration applies these models at drift time despite future labels/training values. `evaluate.py` reports fractional MAPE and approximate seven-day recovery without sustained confirmation. Its final regime excludes the last timestamp.

## Application protocol: delayed-classification-v1

Reuses `baseline.py`, `adapt.py`, `drift.py` through explicit offline preparation. Removes notebook `%%writefile` syntax from drift.py and adds package-import compatibility to adapt.py; original algorithm functions otherwise remain intact. Existing main.py remains available as the retrospective research script.

**This is a new evaluation protocol, not reproduction of the original leaked scores.** Classified drift becomes actionable at drift +30 days, after classification and ablation evidence is available. Original adaptation training windows then contain only past observations. Until availability, predictions use the preceding frozen model. Simulation selects the same model state. Offline labels must not be interpreted as available at detection time. Events too close to dataset end have incomplete evidence and never activate adaptation.

Missing feature values use model-training-context means instead of evaluation-batch means. Original solar clipping [0,1000] is applied only to model input; UI solar retains observed values. Contemporaneous solar is part of total generation, so solar-augmented results are conditional estimates, not proven advance forecasts. Operational feature availability requires validation.

Regimes preserve main.py boundaries: pre_crisis before 2022-03-01, crisis until 2022-08-01, tariff_adjustment until 2023-06-01, solar_growth thereafter. Evaluation starts 2022-01-01 and includes the last valid timestamp. Regime names are experimental segmentation rather than verified causal attribution.

No verified event catalogue exists. The app does not use main.py's hardcoded fallback events or ±45-day proximity matches as confirmation. Optional `historical_event,event_match,event_source` metadata require explicit match plus evidence for confirmation. Missing evidence stays unknown. Tau/delta/structural reduction are diagnostics, not confidence.

Recovery extends the existing seven-day concept: configurable trailing time-aware seven-day observation-level MAPE <=9.5%, at least 24 valid observations per daily check, for three consecutive calendar days. A full window must elapse after availability. Missing days break the streak. Recovery is censored at the next detected event; confirmation is the last observed timestamp of the final successful day. This is a research assumption, not an established validated recovery definition. Display filters select events without altering recovery history.

## Provenance

Preparation saves drift events, paired timestamp predictions, trusted local joblib state and manifest: dataset/config/source/output SHA-256, actual split dates, feature schema, versions, quality counts and assumptions. Startup verifies hashes; stale artifacts disable prediction readiness. Preparation never runs during startup. Joblib is executable pickle data: use only locally prepared trusted files. Hashes establish consistency, not authenticity against malicious modification.

No production data are downloaded, synthesized or replaced. Temporary synthetic fixtures are restricted to tests. The nested README is retained for historical context, including its earlier synthetic-only validation statements.

## Future forecasting extension

`src/forecast_service.py` adds 24-hour and seven-day forecasts without retraining or changing historical evaluation. It uses the saved static/latest adapted models and original feature transforms. The default origin is current Asia/Colombo time, with first output at the next 15-minute boundary. A dataset-end origin is also available. Model state is frozen at the last available observation/issuance time; model states becoming available within the horizon cannot leak into forecasts.

No future measured weather/solar exists locally. Future weather is therefore explicitly estimated from equal-weight daily means over the trailing seven observed days. Solar/radiation use mean intraday profiles from the trailing 28 observed days; unobserved slots use the recent mean and generate a warning. Holiday features use the Sri Lankan calendar. All assumed values are returned and exportable. This is a documented conditional input scenario, not a claim of validated meteorological prediction or horizon-specific model accuracy. Missing recent features fail explicitly. Negative Ridge outputs, if any, remain visible with a warning instead of silently clipping model predictions. No future actuals, error scores, inferred drift events or fabricated uncertainty bands are returned.
