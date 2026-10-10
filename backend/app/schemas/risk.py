import uuid
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field


class RiskInput(BaseModel):
    section: str
    indicator: str
    value: float | None
    unit: str | None
    status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    normalized: float | None = Field(ge=0, le=100)


class RiskFactor(BaseModel):
    group: str
    name: str
    status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    indicators: list[RiskInput]
    subscore: float | None = Field(ge=0, le=100)
    weight: float
    effective_weight: float | None
    contribution: float | None
    explanation: str


class RiskResponse(BaseModel):
    well_id: uuid.UUID
    well_code: str
    reference_date: date | None
    data_classification: str
    source: str | None
    model_version: str
    experimental: bool = True
    score: float | None = Field(ge=0, le=100)
    status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    classification: Literal["NORMAL", "ATTENTION", "HIGH", "CRITICAL"] | None
    coverage: float = Field(ge=0, le=1)
    minimum_coverage: float
    subscores: dict[str, float | None]
    factors: list[RiskFactor]
    unavailable_groups: list[str]
