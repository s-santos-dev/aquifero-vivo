from typing import Literal
from datetime import date
from uuid import UUID
from pydantic import BaseModel, Field
from app.schemas.risk import RiskResponse, RiskInput

Classification = Literal['NORMAL', 'ATTENTION', 'HIGH', 'CRITICAL', 'INSUFFICIENT_DATA']


class Recommendation(BaseModel):
    rule_id: str
    justification: str
    suggestions: list[str]
    evidence: list[RiskInput] = Field(default_factory=list)


class RecommendationsResponse(BaseModel):
    risk: RiskResponse
    rules_version: str = 'investigation-v1.0.0'
    recommendations: list[Recommendation]


class PriorityWell(RiskResponse):
    municipality: str | None
    sector_id: UUID | None
    sector_code: str | None
    sector_name: str | None
    recommendations: list[Recommendation]


class PriorityPage(BaseModel):
    items: list[PriorityWell]
    total: int
    page: int
    page_size: int
    pages: int
    reference_date: date | None
    distribution: dict[str, int]
    evaluated: int
    insufficient: int
    high_priority: int


class DerivedAlert(BaseModel):
    id: str
    kind: Literal['INVESTIGATION', 'DATA_QUALITY']
    message: str
    evaluation: PriorityWell


class AlertPage(BaseModel):
    items: list[DerivedAlert]
    total: int
    page: int
    page_size: int
    pages: int
    reference_date: date | None
