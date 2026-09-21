from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, computed_field

from app.schemas.domain import CatalogProvenance, MultiPolygonGeometry, PointGeometry


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """A single page of a collection."""

    items: list[T]
    total: int = Field(ge=0, description="Total de registros que atendem aos filtros")
    page: int = Field(ge=1, description="Página atual")
    page_size: int = Field(ge=1, description="Quantidade máxima de itens por página")
    pages: int = Field(ge=0, description="Total de páginas")


class WellResponse(CatalogProvenance):
    id: uuid.UUID
    code: str
    name: str
    location: PointGeometry
    municipality: str | None
    state: str | None
    depth_m: Decimal | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SectorResponse(CatalogProvenance):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    boundary: MultiPolygonGeometry
    created_at: datetime
    updated_at: datetime


class DashboardSummaryResponse(BaseModel):
    """Small aggregate used by the operational overview; it never returns measurements."""

    total_wells: int = Field(ge=0)
    active_wells: int = Field(ge=0)
    inactive_wells: int = Field(ge=0)
    total_sectors: int = Field(ge=0)
    total_measurements: int = Field(ge=0)


MeasurementType = Literal["groundwater", "operational", "rainfall"]
DataClassification = Literal["REAL", "PUBLIC", "SIMULATED"]


class MeasurementResponse(BaseModel):
    """A measurement from any of the three time-series tables.

    Fields that do not apply to the value in ``type`` are returned as null.
    """

    id: uuid.UUID
    type: MeasurementType
    well_id: uuid.UUID | None = None
    service_sector_id: uuid.UUID | None = None
    measured_at: datetime
    data_classification: DataClassification
    source: str | None = None
    @computed_field
    @property
    def is_synthetic(self) -> bool:
        return self.data_classification == "SIMULATED"

    dynamic_level_m: Decimal | None = None
    daily_demand_m3: Decimal | None = None
    utilization: Decimal | None = None
    operational_failure: bool | None = None
    water_level_m: Decimal | None = None
    temperature_c: Decimal | None = None
    ph: Decimal | None = None
    conductivity_us_cm: Decimal | None = None
    flow_rate_m3_h: Decimal | None = None
    pumped_volume_m3: Decimal | None = None
    runtime_hours: Decimal | None = None
    operating_status: str | None = None
    precipitation_mm: Decimal | None = None
    accumulation_minutes: int | None = None
    station_code: str | None = None
    location: PointGeometry | None = None
    created_at: datetime
    updated_at: datetime


WellPage = Page[WellResponse]
SectorPage = Page[SectorResponse]
MeasurementPage = Page[MeasurementResponse]
