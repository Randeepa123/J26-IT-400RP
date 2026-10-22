"""FastAPI application. Start: uvicorn backend:app --host 127.0.0.1 --port 8000."""
from contextlib import asynccontextmanager
import json
import logging
from typing import Literal
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from src.config import Settings, REGIMES, CUTOFF
from src.data_loader import load_data
from src.drift_service import load_drifts
from src.prediction_service import PredictionService, ape
from src.metrics_service import metrics, recovery, scores
from src.simulation_service import features, simulate
from src.forecast_service import forecast
from src.schemas import HealthResponse, PredictionResponse, RecordsResponse, SimulationRequest, SimulationResponse, ForecastResponse, DashboardResponse

load_dotenv()
log = logging.getLogger('pucsl.api')
logging.basicConfig(level=logging.INFO, format='%(message)s')

def clean(value):
    """Convert tabular nulls and timestamps into strict JSON values."""
    if isinstance(value, pd.DataFrame): return json.loads(value.to_json(orient='records', date_format='iso'))
    return json.loads(json.dumps(value, default=str))

def create_app(settings=None):
    settings = settings or Settings()
    @asynccontextmanager
    async def lifespan(app):
        app.state.data = pd.DataFrame()
        app.state.drifts = pd.DataFrame()
        app.state.service = None
        app.state.quality = {}
        app.state.warnings = []
        try:
            app.state.data, app.state.quality = load_data(settings)
            app.state.warnings.append('Original preprocessing created zero-filled gaps; original <200 MW exclusion is retained.')
            app.state.drifts = load_drifts(settings.drifts)
            app.state.service = PredictionService(settings, app.state.data)
            app.state.warnings.extend(app.state.service.manifest['assumptions'])
            log.info(json.dumps({'event':'startup_ready','quality':app.state.quality,'drifts':len(app.state.drifts)}))
        except (ValueError, OSError, KeyError, TypeError) as exc:
            log.error(json.dumps({'event':'startup_not_ready','message':str(exc)}))
            app.state.warnings.append(str(exc))
        yield
    app = FastAPI(title='PUCSL Grid Drift Adaptation API', lifespan=lifespan)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content={'error': {'code': exc.status_code, 'message': str(exc.detail)}})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(status_code=422, content={'error': {'code':422, 'message':str(exc)}})

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        log.exception('request_failed path=%s', request.url.path)
        return JSONResponse(status_code=500, content={'error': {'code':500, 'message':'Operation failed; inspect backend logs.'}})

    def ready(request: Request):
        if request.app.state.service is None:
            raise HTTPException(503, '; '.join(request.app.state.warnings))
        return request.app.state.service

    def selection(start_date: str | None = None, end_date: str | None = None,
                  regimes: list[str] | None = Query(None)):
        try:
            start = pd.Timestamp(start_date) if start_date else None
            end = pd.Timestamp(end_date) if end_date else None
            for stamp in [start, end]:
                if stamp is not None and (pd.isna(stamp) or stamp.tzinfo is not None):
                    raise ValueError('Use local Asia/Colombo timestamps without a UTC offset')
            if start is not None and end is not None and start > end: raise ValueError('start_date must be <= end_date')
            if end_date and len(end_date)==10: end = end+pd.Timedelta(days=1)-pd.Timedelta(nanoseconds=1)
            if regimes and not set(regimes).issubset({r[0] for r in REGIMES}): raise ValueError('Unknown regime')
        except (ValueError, TypeError, OverflowError) as exc:
            raise HTTPException(422, f'Invalid date range or regime: {exc}') from exc
        return start, end, regimes

    def filtered(frame, selected, column='timestamp'):
        start, end, regimes = selected
        result = frame
        if start is not None: result = result[result[column]>=start]
        if end is not None: result = result[result[column]<=end]
        if regimes is not None: result = result[result.regime.isin(regimes)]
        return result

    @app.get('/health', response_model=HealthResponse)
    def health(request: Request):
        state=request.app.state
        df=state.data
        ok=state.service is not None
        payload=dict(status='ready' if ok else 'not_ready', alive=True, ready=ok, dataset_loaded=not df.empty,
            observations=len(df), dataset_start=str(df.timestamp.min()) if len(df) else None,
            dataset_end=str(df.timestamp.max()) if len(df) else None, drift_points=len(state.drifts),
            model_artifacts_available=ok, configuration=state.service.manifest if ok else {'cutoff':CUTOFF},
            data_quality=state.quality, warnings=state.warnings)
        return JSONResponse(status_code=200 if ok else 503, content=HealthResponse(**payload).model_dump())

    @app.get('/predict', response_model=PredictionResponse)
    def predictions(model_type: Literal['static','adapted']='adapted', selected=Depends(selection),
                    offset: int=Query(0,ge=0), limit: int=Query(10000,ge=1,le=50000), service=Depends(ready)):
        df=filtered(service.frame, selected)
        page=df.iloc[offset:offset+limit].copy()
        page['predicted_generation_mw']=page[model_type]
        page['ape_percent']=ape(page.actual_generation_mw,page[model_type])
        columns=['timestamp','actual_generation_mw','predicted_generation_mw','ape_percent','regime']
        if 'solar_mw' in page: columns.append('solar_mw')
        return dict(model_type=model_type,start_date=str(selected[0] or service.frame.timestamp.min()),
                    end_date=str(selected[1] or service.frame.timestamp.max()),count=len(page),total=len(df),data=clean(page[columns]))

    @app.get('/evaluation/regimes', response_model=RecordsResponse)
    @app.get('/metrics', response_model=RecordsResponse)
    def evaluation(selected=Depends(selection), service=Depends(ready)):
        return dict(data=metrics(filtered(service.frame,selected)), methodology='Paired test observations; zero actual excluded from MAPE, included in RMSE. MAPE in percent; regime end exclusive.')

    @app.get('/dashboard/series', response_model=DashboardResponse)
    def dashboard_series(selected=Depends(selection), max_points:int=Query(2500,ge=100,le=10000), service=Depends(ready)):
        df=filtered(service.frame,selected).copy()
        summary={'static':scores(df,'static'),'adapted':scores(df,'adapted'),
                 'peak_solar_mw':float(df.solar_mw.max()) if 'solar_mw' in df and df.solar_mw.notna().any() else None}
        for model in ['static','adapted']:
            df[model+'_ape']=ape(df.actual_generation_mw,df[model])
            df[model+'_rolling_mape']=pd.Series(df[model+'_ape'].to_numpy(),index=df.timestamp).rolling('14D',min_periods=96).mean().to_numpy()
        columns=['timestamp','actual_generation_mw','static','adapted','regime','static_ape','adapted_ape','static_rolling_mape','adapted_rolling_mape']
        indices=np.linspace(0,len(df)-1,min(len(df),max_points),dtype=int) if len(df) else []
        sampled=df.iloc[indices]
        return dict(observations=len(df),displayed_points=len(sampled),summary=summary,data=clean(sampled[columns]),
                    methodology='Summary metrics and trailing 14-day MAPE use every selected observation before visual sampling. Rolling minimum: 96 nonzero observations; initial windows may be partial. CSV prediction export uses /predict pagination for full resolution.')

    @app.get('/drifts', response_model=RecordsResponse)
    def events(request:Request, selected=Depends(selection), drift_type: str | None=None,
               match_status: Literal['confirmed','plausible','unmatched','unknown'] | None=None):
        if request.app.state.drifts.empty and not settings.drifts.exists(): raise HTTPException(503,'Drift file unavailable; run python -m src.prepare')
        df=filtered(request.app.state.drifts,selected,'drift_date')
        if drift_type: df=df[df.drift_type==drift_type]
        if match_status: df=df[df.match_status==match_status]
        return dict(data=clean(df), methodology='ADWIN output. Classification uses 30 subsequent days; available_at records that delay. No event confirmation from temporal proximity.')

    @app.get('/regimes', response_model=RecordsResponse)
    def regimes(request:Request):
        data=request.app.state.data
        if data.empty: raise HTTPException(503,'Dataset unavailable')
        return dict(data=[dict(regime=n,start=s or str(data.timestamp.min()),end=e or str(data.timestamp.max()+pd.Timedelta(nanoseconds=1))) for n,s,e in REGIMES], methodology='Existing main.py regime boundaries; final boundary includes last observation; deployment begins 2022-01-01.')

    @app.get('/simulation/features', response_model=RecordsResponse)
    def simulation_features(service=Depends(ready)):
        return dict(data=features(service.data), methodology='Observed dataset ranges and units from enrichment code. All listed inputs required; time encodings derived by original baseline.make_features.')

    @app.get('/forecast', response_model=ForecastResponse)
    def future_forecast(horizon_hours: int=Query(24, json_schema_extra={'enum':[24,168]}), origin: Literal['now','dataset_end']='now', service=Depends(ready)):
        try:
            return forecast(service, horizon_hours, origin)
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from exc

    @app.post('/simulate', response_model=SimulationResponse)
    def simulation(payload:SimulationRequest,service=Depends(ready)):
        try: return simulate(service,payload)
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc

    @app.get('/evaluation/recovery', response_model=RecordsResponse)
    @app.get('/metrics/adaptation-lag', response_model=RecordsResponse)
    def adaptation_lag(request:Request,selected=Depends(selection),service=Depends(ready)):
        events=filtered(request.app.state.drifts,selected,'drift_date')
        # Calculate against the full chronological series and full event table before filtering.
        rows=recovery(service.frame,request.app.state.drifts,settings)
        dates=set(events.drift_date)
        return dict(data=[r for r in rows if pd.Timestamp(r['drift_date']) in dates], methodology='Trailing time-aware MAPE; full window after model availability; consecutive daily checks; gaps break recovery; censored at next drift. Lag measured to confirmation, in days.')
    return app

app=create_app()
