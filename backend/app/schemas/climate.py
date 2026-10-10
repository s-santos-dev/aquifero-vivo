from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel
from app.schemas.api import Page


class ClimateStationResponse(BaseModel):
    id: UUID
    official_code: str
    name: str
    source: Literal["INMET"]
    observation_type: Literal["STATION_OBSERVATION"]
    latitude: float
    longitude: float
    spatial_reference: str
    data_classification: Literal["PUBLIC"]
    is_synthetic: Literal[False]
    timezone: Literal["UTC"]
    unit: Literal["mm"]
    frequency: str
    period: dict[str, Any]
    coverage: dict[str, Any]
    quality_status: Literal["NOT_PROVIDED"]
    source_metadata: dict[str, Any]
    eligible_for_risk: Literal[False]


class NearbyStationResponse(ClimateStationResponse):
    distance_km: float
    distance_method: str
    requested_coverage: dict[str, Any] | None = None


class NearbyClimatePage(Page[NearbyStationResponse]):
    notice: str


class HourlyRainfallResponse(BaseModel):
    id: UUID
    measured_at: datetime
    value_mm: str | None
    unit: Literal["mm"]
    source: Literal["INMET"]
    availability: Literal["OBSERVED", "MISSING"]
    source_metadata: dict[str, Any]


class DailyRainfallResponse(BaseModel):
    date: date
    value_mm: str | None
    unit: Literal["mm"]
    availability: Literal["COMPLETE", "INSUFFICIENT_DATA"]
    observed_hours: int
    expected_hours: int
    missing_hours: int
    ambiguous_hours: int
    timezone: Literal["UTC"]
    aggregation_rule: str
    quality_status: Literal["NOT_PROVIDED"]
    contributor_ids: list[str]


class RainfallPage(Page[HourlyRainfallResponse | DailyRainfallResponse]):
    station: ClimateStationResponse
    start: date
    end: date
    resolution: Literal["hourly", "daily"]
    coverage: dict[str, Any] | None
    aggregation_rule: str | None
    notice: str


class RainfallIndicatorsResponse(BaseModel):
    reference_date: date
    timezone: Literal["UTC"]
    aggregation_rule: str
    accumulations: dict[str, Any]
    notice: str
