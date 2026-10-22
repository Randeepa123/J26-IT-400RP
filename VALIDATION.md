# Validation report — 2026-10-20

## Executed checks

- CPython 3.15.0, Windows x64. Project virtual environment uses existing locally installed numerical packages, with matching versions pinned in `requirements.txt`. New dashboard/API/test dependencies were installed into `.venv`. `requirements.lock.txt` records the complete resolved environment. A separate clean-environment installation and Linux/macOS execution were not performed.
- Real-data offline preparation completed successfully. Raw observations: **350,593**; below-200 MW exclusions: **64,863**; remaining: **285,730**. Invalid targets/timestamps and duplicate timestamps: **0**.
- Training: **2016-10-14 00:00:00–2021-12-31 23:45:00** (118,291 observations). Evaluation: **2022-01-01 00:00:00–2026-10-13 00:00:00** (**167,439** observations). No separate validation split.
- ADWIN detected **7** events: six gradual, one abrupt; no structural classifications. Seven frozen adapted model snapshots were produced. Structural adaptation is tested using an isolated synthetic fixture and the actual implementation, but no structural result is claimed for the real data.
- `python -m pytest -q`: **22 passed**, one upstream Starlette warning about future migration from httpx to httpx2. No failing tests. This warning does not affect current TestClient behavior.
- `python -m compileall -q backend.py app.py src tests scripts`: passed.
- `python -m pip check`: no broken requirements.
- Live Uvicorn API: health, predictions, metrics, drifts, regimes, simulation feature schema, simulation POST and adaptation recovery responded successfully. Pagination supports the entire evaluation period. All seven model snapshots train strictly before activation and simulation reproduces the corresponding stored adapted prediction.
- Streamlit AppTest rendered all five tabs with no exceptions/errors. Default comparison, static selection, structural-event filtering and deselect-all-regimes empty state passed. The standalone headless Streamlit server also started successfully.
- The first live smoke pass caught an empty recovery response caused by string-format comparison of midnight timestamps. This was fixed by comparing Timestamp objects; a regression assertion now requires both test fixture events. The final real-data response contains all seven recovery records. The smoke runner's relative AppTest path was also corrected to an absolute path.

## Real measured results

These are this application's **delayed-classification-v1** evaluation, not the original retrospective experiment's scores. Read the protocol and limitations in `AUDIT.md` before interpreting them.

| Regime | Paired observations | Static MAPE (%) | Adapted MAPE (%) | Static RMSE (MW) | Adapted RMSE (MW) |
|---|---:|---:|---:|---:|---:|
| pre_crisis | 5,664 | 8.52 | 8.52 | 201.69 | 201.69 |
| crisis | 14,631 | 13.66 | 13.32 | 277.49 | 264.70 |
| tariff_adjustment | 29,184 | 14.81 | 13.93 | 269.86 | 248.55 |
| solar_growth | 117,960 | 13.22 | 10.61 | 303.25 | 268.55 |

The documented sustained recovery criterion reports recovery for seven events, between about 39.99 and 89.99 days after detection. This includes the deliberate 30-day classification availability delay. It does not prove causal attribution or a generally validated recovery threshold.

## Reproduce

```powershell
.venv/Scripts/python.exe -m src.prepare
.venv/Scripts/python.exe -m pytest -q
```

With the backend already running in a separate terminal:

```powershell
.venv/Scripts/python.exe scripts/validate_local.py
```

The smoke script reads actual artifacts and calls the live API, then runs Streamlit AppTest. It does not modify production data. It assumes repository-root execution and the supplied local configuration. Tests require no live backend.

## Implementation inventory

- New entry points: `backend.py`, `app.py`.
- New services: `src/config.py`, `data_loader.py`, `prediction_service.py`, `metrics_service.py`, `drift_service.py`, `simulation_service.py`, `schemas.py`, `api_client.py`; explicit offline builder `src/prepare.py` and package initializer.
- New verification: `tests/conftest.py`, health/prediction/metrics/drift/simulation/frontend tests, strategy integration tests, and `scripts/validate_local.py`.
- New setup/docs: `.env.example`, `.gitignore`, `pytest.ini`, `requirements.txt`, `requirements.lock.txt`, `AUDIT.md`, this report. Root README replaced with actual setup and methodology.
- Modified original research files: `drift_project/src/drift.py` removes notebook magic; `drift_project/src/adapt.py` supports both package and direct-script imports. Existing baseline/evaluation/main implementations remain intact.
- Generated local artifacts (gitignored): `models/manifest.json`, `predictions.csv`, `classified_drift_points.csv`, `bundle.joblib`. They are rebuilt explicitly from the original data. Data CSVs were not modified. Existing unrelated `git backdate.txt` was left untouched.

## Limits and missing evidence

No browser visual review or screenshot was available; rendering and interaction checks used Streamlit's supported test runner. Clean-machine installation, macOS and Linux execution remain unverified. No verified historical event catalogue exists, so all generated event matches remain unknown. Observed daily weather, contemporaneous solar, zero-filled upstream targets, provisional regime attribution and the new delayed/sustained protocol limit scientific claims; all are disclosed in the API/UI and audit. No application feature is replaced with fabricated production data.

Dependency compatibility was resolved using actual binary-wheel installation and runtime checks. Upstream background: [scikit-learn installation documentation](https://scikit-learn.org/stable/install.html) and [Streamlit installation documentation](https://docs.streamlit.io/get-started/installation/command-line).

## Future forecast extension validation

- `python -m pytest -q`: **29 passed**, same single upstream Starlette/httpx deprecation warning. New tests cover both horizons (96/672 intervals), next-quarter-hour timestamps, inference with actual Ridge model state, stale-data warnings, invalid horizons/origins, Sri Lankan holidays, missing weather failure, absence of fabricated future actuals/errors, nonmutation and exclusion of model states not available at issuance.
- Live `/forecast?horizon_hours=24` and `/forecast?horizon_hours=168` returned HTTP 200 with 96 and 672 rows. The current-time seven-day request began 2026-10-20 19:15 local time and ended 2026-10-27 19:00, while correctly disclosing last observed data at 2026-10-13 00:00 and a 7.8-day freshness gap. These timestamps describe this particular validation call; later requests use their current issuance time.
- The updated live smoke script passed, including Streamlit AppTest switching to Next 7 days and dataset-end origin, followed by the historical model/filter/empty-state checks. No dashboard errors or exceptions occurred.
- `src/forecast_service.py` adds conditional future inference; `src/schemas.py` and `backend.py` add the validated `/forecast` contract. `app.py` adds an expanded future section independent of historical filters, both horizon controls, origin selection, model charts, metrics, assumed-input tables and CSV export. `tests/test_forecast.py` and the live smoke runner cover the extension. No model artifacts or historical evaluation data were changed, and no retraining is needed for this UI/API addition.
- Weather/solar are explicitly declared recent-history input estimates. No live meteorological service, rolling-origin forecast-accuracy study or calibrated uncertainty estimate is claimed. Refreshing data and explicitly preparing artifacts remains necessary to incorporate newer observations.

## React dashboard extension — 2026-10-20

The primary interface is now `frontend/`: React 19, strict TypeScript, Vite, Tailwind CSS, official shadcn/ui components, TanStack Query and Apache ECharts. Existing FastAPI/Python model services and artifacts are preserved; Streamlit remains available. The requested Dribbble page could not be accessed and no repository reference image was supplied. A screenshot was requested; the implementation follows the user's written design requirements without claiming visual inspection of that reference.

### Executed validation

- **32 Python tests passed**, including compact chart sampling/full-sample metric invariance, date/empty-state validation and evaluation-route alias equivalence. One existing upstream Starlette/httpx deprecation warning remains.
- **5 frontend unit tests passed**: repeated regime filters, Sri Lankan timestamp normalization including date-only values, explicit missing dates, complete escaped/formula-safe CSVs and API failure handling.
- **4 real-browser scenarios passed** in installed Chrome against the real FastAPI/data/model artifacts: both future horizons and CSV download; navigation to model/drift/recovery views and real simulation submission; event/regime filtering, explicit empty states, assumptions dialog and reduced-motion mode; tablet/mobile layouts at 1024, 768 and 390px, including mobile navigation and no horizontal page overflow. No production API responses were mocked.
- **Production build passed**: strict TypeScript checking followed by Vite bundling. Application entry is approximately 111 kB minified (37 kB gzip), interface 382 kB, chart renderer 176 kB and chart engine 446 kB. Fonts are bundled locally and only the required Latin files are emitted. No oversized-chunk warnings remain.
- Desktop and mobile screenshots were generated and visually inspected. Screenshots show actual data and forecasts, including the stale-observation warning. These checks apply to this new React interface; they supersede the earlier no-browser-review limitation for the initial Streamlit implementation.
- The same four browser scenarios also passed against the **compiled production preview**, verifying split JavaScript bundles, locally served fonts, SPA navigation and the API proxy. Production HTML and proxied health returned HTTP 200. Final screenshots are retained in `docs/screenshots/dashboard-desktop.png` and `docs/screenshots/dashboard-mobile.png`.
- `git diff --check` and Python source compilation passed. Linux/macOS and a fresh-machine installation remain unverified.

Browser checks found and fixed date-only drift metadata crashing date formatting, missing semantic panel headings, ECharts overriding chart descriptions, forecast-badge styling and tablet toolbar overflow. Local web protection returned HTTP 499 for `/metrics` browser URLs; explicit `/evaluation/regimes` and `/evaluation/recovery` aliases now call the original handlers. Original routes remain available, calculations are identical, and no security configuration was altered.

### Implementation inventory

- New React shell, responsive sidebar, overview KPIs, forecast chart/horizon controls, drift classifications/evidence, paired regime comparison, sustained recovery, simulation form/results and methodology views.
- New TypeScript API/types/formatting/CSV layer, local fonts and original favicon, shadcn primitives, ECharts renderer, component styles and accessible loading/error/empty states.
- New frontend package lock, Vite/Tailwind/TypeScript/shadcn configuration, environment example, unit/browser tests and setup documentation.
- FastAPI adds `/dashboard/series` (full-sample metrics/rolling errors before display sampling) plus the two evaluation aliases. It performs no model retraining and changes no historical evaluation output.
- Historical export retains full resolution through `/predict` pagination; forecast, metric, drift and recovery exports use actual API records. Future assumptions remain disclosed. No future actual observations or fabricated error metrics are introduced.

## Laptop layout correction

The user reported screens not fitting on a laptop/smaller desktop. The expanded audit reproduced a fixed sidebar extending below a 720px-high viewport and date controls overflowing at 320px. Existing panel sizing also depended on a fixed overview-card height.

`frontend/src/layout.css` now makes the sidebar independently scrollable, collapses it below 1200px, removes secondary sidebar decoration in short windows, permits natural card heights and wrapping controls, constrains date/number inputs to their containers and scales the forecast plot with window height. Navigation resets the main scroll position on route changes so a new view does not inherit the previous view's scroll offset. No data, model or metric calculations changed.

- The original four real-browser interaction scenarios passed with the responsive stylesheet.
- **Six dedicated layout regressions passed**, covering **all seven views** at 1366×768, 1280×720, 1093×614, 1024×576, 911×512 and 320×568. The middle widths represent reduced CSS viewport space at common zoom levels, rather than a claim of testing browser zoom settings directly. Checks include page overflow, clipped horizontal controls, vertical card clipping, sidebar reachability and navigation from scrolled pages.
- An initial combined 42-view test exceeded its three-minute overall time budget at the final view; it was split into independent per-viewport tests using normal in-app navigation. All six passed without extending the global timeout.
- The final strict TypeScript/Vite production build passed. `git diff --check` passed.
- The 1280×720 screenshot was visually inspected and retained as `docs/screenshots/dashboard-laptop.png`. Normal vertical page scrolling and local table scrolling remain available; content is not hidden to force an entire dashboard into one screen.
