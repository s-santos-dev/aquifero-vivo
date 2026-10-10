import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class ORMReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PointGeometry(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float] = Field(
        description="Longitude e latitude, nesta ordem, no SRID 4326"
    )


    @field_validator("coordinates")
    @classmethod
    def valid_coordinates(cls, value):
        import math
        lon, lat = value
        if not (math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("Coordenadas inválidas")
        return value


class MultiPolygonGeometry(BaseModel):
    type: Literal["MultiPolygon"] = "MultiPolygon"
    coordinates: list[list[list[tuple[float, float]]]]


class CatalogProvenance(BaseModel):
    source: str | None = Field(default=None, max_length=80)
    data_classification: Literal["UNKNOWN", "REAL", "PUBLIC", "SIMULATED"] = "UNKNOWN"

    @computed_field
    @property
    def is_synthetic(self) -> bool:
        return self.data_classification == "SIMULATED"


class WellBase(CatalogProvenance):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    location: PointGeometry
    municipality: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    depth_m: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = True


class WellCreate(WellBase):
    pass


class WellRead(WellBase, ORMReadSchema):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class GroundwaterMeasurementBase(BaseModel):
    well_id: uuid.UUID
    measured_at: datetime
    water_level_m: Decimal = Field(ge=0)
    dynamic_level_m: Decimal | None = Field(default=None, ge=0)
    temperature_c: Decimal | None = None
    ph: Decimal | None = Field(default=None, ge=0, le=14)
    conductivity_us_cm: Decimal | None = Field(default=None, ge=0)
    source: str | None = Field(default=None, max_length=80)
    data_classification: Literal["REAL", "PUBLIC", "SIMULATED"]


class GroundwaterMeasurementCreate(GroundwaterMeasurementBase):
    pass


class GroundwaterMeasurementRead(GroundwaterMeasurementBase, ORMReadSchema):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class RainfallMeasurementBase(BaseModel):
    service_sector_id: uuid.UUID | None = None
    measured_at: datetime
    precipitation_mm: Decimal = Field(ge=0)
    accumulation_minutes: int | None = Field(default=None, gt=0)
    station_code: str | None = Field(default=None, max_length=64)
    source: str | None = Field(default=None, max_length=80)
    data_classification: Literal["REAL", "PUBLIC", "SIMULATED"]
    location: PointGeometry


class RainfallMeasurementCreate(RainfallMeasurementBase):
    pass


class RainfallMeasurementRead(RainfallMeasurementBase, ORMReadSchema):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class OperationalMeasurementBase(BaseModel):
    well_id: uuid.UUID
    measured_at: datetime
    flow_rate_m3_h: Decimal | None = Field(default=None, ge=0)
    pumped_volume_m3: Decimal | None = Field(default=None, ge=0)
    runtime_hours: Decimal | None = Field(default=None, ge=0)
    daily_demand_m3: Decimal | None = Field(default=None, ge=0)
    utilization: Decimal | None = Field(default=None, ge=0)
    operational_failure: bool | None = None
    operating_status: str | None = Field(default=None, max_length=40)
    source: str | None = Field(default=None, max_length=80)
    data_classification: Literal["REAL", "PUBLIC", "SIMULATED"]


class OperationalMeasurementCreate(OperationalMeasurementBase):
    pass


class OperationalMeasurementRead(OperationalMeasurementBase, ORMReadSchema):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ServiceSectorBase(CatalogProvenance):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    boundary: MultiPolygonGeometry


class ServiceSectorCreate(ServiceSectorBase):
    pass


class ServiceSectorRead(ServiceSectorBase, ORMReadSchema):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class WellSectorBase(CatalogProvenance):
    well_id: uuid.UUID
    sector_id: uuid.UUID
    valid_from: datetime
    valid_to: datetime | None = None


class WellSectorCreate(WellSectorBase):
    pass


class WellSectorRead(WellSectorBase, ORMReadSchema):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class RiskAssessmentBase(BaseModel):
    well_id: uuid.UUID
    assessed_at: datetime
    score: Decimal = Field(ge=0, le=100)
    risk_level: Literal["low", "medium", "high", "critical"]
    methodology_version: str = Field(min_length=1, max_length=40)
    valid_until: datetime | None = None
    notes: str | None = None


class RiskAssessmentCreate(RiskAssessmentBase):
    pass


class RiskAssessmentRead(RiskAssessmentBase, ORMReadSchema):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class RiskFactorBase(BaseModel):
    risk_assessment_id: uuid.UUID
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    raw_value: Decimal | None = None
    normalized_value: Decimal | None = None
    weight: Decimal | None = None
    contribution: Decimal | None = None
    details: dict[str, Any] | None = None


class RiskFactorCreate(RiskFactorBase):
    pass


class RiskFactorRead(RiskFactorBase, ORMReadSchema):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AlertBase(BaseModel):
    well_id: uuid.UUID
    risk_assessment_id: uuid.UUID | None = None
    alert_type: str = Field(min_length=1, max_length=64)
    severity: Literal["info", "warning", "critical"]
    status: Literal["open", "acknowledged", "resolved"] = "open"
    title: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1)
    triggered_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None


class AlertCreate(AlertBase):
    pass


class AlertRead(AlertBase, ORMReadSchema):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
