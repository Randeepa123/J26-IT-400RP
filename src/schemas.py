"""Validated API contracts."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    timestamp: datetime
    features: dict[str, float] = Field(default_factory=dict)

class PredictionRow(BaseModel):
    timestamp: datetime
    actual_generation_mw: float
    predicted_generation_mw: float
    ape_percent: float | None
    regime: str
    solar_mw: float | None = None

class PredictionResponse(BaseModel):
    model_type: Literal['static', 'adapted']
    start_date: str
    end_date: str
    count: int
    total: int
    data: list[PredictionRow]

class HealthResponse(BaseModel):
    status: str
    alive: bool = True
    ready: bool
    dataset_loaded: bool
    observations: int
    dataset_start: str | None
    dataset_end: str | None
    drift_points: int
    model_artifacts_available: bool
    configuration: dict
    data_quality: dict
    warnings: list[str]

class RecordsResponse(BaseModel):
    data: list[dict]
    methodology: str

class SimulationResponse(BaseModel):
    timestamp: datetime
    static_generation_mw: float
    adapted_generation_mw: float
    difference_mw: float
    difference_percent: float | None
    strategy: str
    validation: list[str]

class ForecastRow(BaseModel):
    timestamp: datetime
    static_generation_mw: float
    adapted_generation_mw: float
    assumed_features: dict[str, float]

class ForecastResponse(BaseModel):
    horizon_hours: Literal[24, 168]
    interval_minutes: int = 15
    count: int
    forecast_origin: datetime
    data_as_of: datetime
    start: datetime
    end: datetime
    adapted_strategy: str
    feature_method: str
    assumptions: list[str]
    warnings: list[str]
    data: list[ForecastRow]

class DashboardResponse(BaseModel):
    observations: int
    displayed_points: int
    summary: dict
    data: list[dict]
    methodology: str
