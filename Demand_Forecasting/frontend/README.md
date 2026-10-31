# PUCSL Grid Intelligence — React dashboard

Primary dashboard for the existing PUCSL FastAPI/Python research pipeline. Built with React, TypeScript, Vite, Tailwind CSS, official shadcn/ui components, TanStack Query and Apache ECharts. Fonts are bundled locally; no third-party API or remote asset is required at runtime. The previous Streamlit dashboard remains available as an alternative.

## Run locally

Use Node.js 22.12+ or 24 LTS and the existing Python environment. This machine was verified with Node 24.15.0 and npm 11.12.1. From the repository root, start the backend in its own terminal:

```powershell
.venv/Scripts/python.exe -m uvicorn backend:app --host 127.0.0.1 --port 8000 --reload
```

In a second terminal:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open **http://127.0.0.1:5173**. On Linux/macOS use `npm` instead of `npm.cmd` and `.venv/bin/python` for Python. `npm.cmd` avoids the Windows PowerShell execution-policy restriction on npm.ps1.

The API/model artifacts from the existing implementation are reused. If `/health` reports missing or stale artifacts, run `python -m src.prepare` from repository root and restart the backend. The React application never trains models, modifies research CSVs or fabricates missing results.

## Architecture and API integration

Browser requests use `/api`. Vite development and preview proxy these requests to FastAPI on port 8000, keeping the browser on the same origin without enabling broad CORS permissions. Copy `.env.example` to `.env.local` to override `API_PROXY_TARGET` (server environment) or `VITE_API_URL` (browser build setting). Vite's proxy target may also be set in the process environment. For deployment behind another web server, reverse-proxy `/api/*` to FastAPI and serve the SPA with index.html fallback for navigation routes.

| Workspace view | Actual API sources |
|---|---|
| Overview | `/health`, `/dashboard/series`, `/forecast`, `/evaluation/regimes`, `/drifts` |
| Generation forecast | `/forecast` for 24h/168h and `/dashboard/series` for historical comparison |
| Drift intelligence | `/drifts` plus date, regime, classification and evidence filters |
| Model performance | `/evaluation/regimes`, including unavailable regimes and signed improvements |
| Adaptation recovery | `/evaluation/recovery`, filtered to the selected authoritative drift events |
| Prediction simulation | `/simulation/features`, `POST /simulate` using the original frozen models |
| Research methodology | `/health` provenance, data quality and research assumptions |

`/evaluation/regimes` and `/evaluation/recovery` are aliases of the existing `/metrics` and `/metrics/adaptation-lag` handlers. The local browser protection classified `/metrics` URLs as telemetry and returned HTTP 499; descriptive evaluation routes avoid that accidental classification while preserving every original endpoint and calculation. No security setting is changed. An unreadable 499 response still produces a visible error rather than a fallback result.

The chart endpoint computes summary metrics and 14-day rolling MAPE from all selected observations before returning at most 2,500 display points. Historical prediction CSV export pages through `/predict` for full resolution. Forecast exports include all 96/672 intervals, assumed future inputs, forecast origin and dataset timestamp. Regime, drift and recovery CSVs export the selected records.

All displayed timestamps are Asia/Colombo regardless of browser timezone. Future forecasts have their own horizon, model and origin controls. Historical filters do not rewrite future forecasts. Historical model selection controls the MAPE/RMSE KPIs; comparison charts show both aligned models. Event filters affect drift views/recovery selection, rather than removing unrelated evaluation observations. Empty selections and missing inputs produce explicit empty/error states.

## Build and checks

```powershell
npm.cmd run build
npm.cmd run preview
npm.cmd run test
```

Preview serves the production build at **http://127.0.0.1:5173**, with the same API proxy. Stop the development server before preview because they use the same port. The build performs strict TypeScript checking before bundling. Assets and local fonts are emitted under `dist/`; application, interface, renderer and ECharts modules are split for caching.

Browser interaction tests require both backend and frontend servers running:

```powershell
npm.cmd run test:e2e
```

The Windows test configuration uses the installed Chrome browser; Linux/macOS defaults to Playwright Chromium. Install a browser with `npx playwright install chromium` if needed and set `PLAYWRIGHT_BROWSER_CHANNEL=chromium` in your shell (`$env:PLAYWRIGHT_BROWSER_CHANNEL='chromium'` in PowerShell). Browser tests use the real research data: no production API mocking or synthetic dashboard metrics. They cover forecast horizons/CSV, all scientific views, simulation, filters, dialogs, reduced-motion mode and 1024/768/390px layouts. Screenshots/traces are saved to gitignored `test-results/`.

## Visual design and reference status

Original PUCSL research identity: warm off-white workspace, forest/sage accents, charcoal headings, rounded white cards, generous chart surfaces, restrained motion, mobile sidebar and polished skeletons. ECharts provides tooltips, zoom/pan, forecast comparisons, paired regime bars, classification composition and sustained-recovery plots. Text alternatives, semantic headings, labelled controls and reduced-motion handling are included.

Verified production screenshots: [desktop](../docs/screenshots/dashboard-desktop.png), [mobile](../docs/screenshots/dashboard-mobile.png). All four browser scenarios passed against both development and compiled production servers. See the root VALIDATION.md for the full report.

Laptop fitting is handled in `src/layout.css`: the sidebar scrolls independently and collapses below 1200px, secondary sidebar decoration is omitted in short windows, controls wrap within cards, and the forecast plot scales with window height. Dedicated layout tests cover every research view at 1366×768, 1280×720 and smaller CSS viewports equivalent to common browser zoom levels. Content below the fold remains normally scrollable; wide data tables scroll inside their cards.

All six dedicated layout checks pass across all seven views. See the [updated laptop preview](../docs/screenshots/dashboard-laptop.png). Page navigation also resets the main scroll position.

The requested [Gridora Dribbble reference](https://dribbble.com/shots/27762000-Dashboard-Renewable-Energy-Forecasting) was inaccessible to the web tool. No screenshot existed in the repository, and one was requested from the user. This implementation follows the supplied visual brief; it does **not** claim image-by-image fidelity to an unseen reference. No proprietary Gridora branding, illustrations or assets are copied. A supplied screenshot can guide a subsequent visual alignment pass.

Official setup references: [shadcn/ui for Vite](https://ui.shadcn.com/docs/installation/vite), [Apache ECharts handbook](https://echarts.apache.org/handbook/en/how-to/chart-types/line/basic-line/). Components under `src/components/ui` were retrieved using the official shadcn CLI and then composed with project-specific styles.

The research limitations in the root AUDIT.md remain applicable: daily observed weather, future exogenous estimates, delayed classification, upstream zero filling, no verified event catalogue and no calibrated uncertainty bands.
