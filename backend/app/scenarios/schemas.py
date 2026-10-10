from datetime import date
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.indicators import IndicatorResponse
from app.schemas.risk import RiskResponse
from app.schemas.priority import Recommendation
from app.scenarios.config import MIN_CHANGE, MAX_CHANGE


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    rainfall_change_pct: float = Field(default=0, ge=MIN_CHANGE, le=MAX_CHANGE)
    demand_change_pct: float = Field(default=0, ge=MIN_CHANGE, le=MAX_CHANGE)
    pumping_change_pct: float = Field(default=0, ge=MIN_CHANGE, le=MAX_CHANGE)


class SimulationRequest(Parameters):
    well_id: UUID
    reference_date: date | None = None
    horizons: list[Literal[30, 60, 90]] = Field(default_factory=lambda: [30, 60, 90], min_length=1, max_length=3)

    @field_validator("horizons")
    @classmethod
    def unique_horizons(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("Horizontes não podem se repetir")
        return sorted(values)


class FactorChange(BaseModel):
    group: str
    name: str
    baseline: float | None
    hypothetical: float | None
    delta_points: float | None
    contribution_delta: float | None
    explanation: str


class HorizonResult(BaseModel):
    horizon: Literal[30, 60, 90]
    label: str
    applied_parameters: Parameters
    risk: RiskResponse
    indicators: IndicatorResponse | None
    delta_points: float | None
    delta_pct: float | None
    factors: list[FactorChange]
    warnings: list[str]
    recommendations: list[Recommendation] = Field(default_factory=list)


class SimulationResponse(BaseModel):
    well_id: UUID
    well_code: str
    reference_date: date | None
    data_classification: str
    source: str | None
    simulation_version: str
    nature: Literal["HYPOTHETICAL_SENSITIVITY"] = "HYPOTHETICAL_SENSITIVITY"
    parameters: SimulationRequest
    baseline: RiskResponse
    baseline_indicators: IndicatorResponse | None
    results: list[HorizonResult]
    assumptions: list[str]
    warnings: list[str]
