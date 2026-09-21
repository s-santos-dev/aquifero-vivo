from __future__ import annotations

import json
import math
import uuid
from datetime import date, datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Boolean, Integer, Numeric, String, cast, func, literal, or_, select, union_all
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from app.database import get_db
from app.indicators.service import sector_indicators, well_indicators
from app.models import (
    GroundwaterMeasurement,
    OperationalMeasurement,
    RainfallMeasurement,
    ServiceSector,
    Well,
    WellSector,
)
from app.schemas.api import (
    DataClassification,
    DashboardSummaryResponse,
    MeasurementPage,
    MeasurementResponse,
    MeasurementType,
    SectorPage,
    SectorResponse,
    WellPage,
    WellResponse,
)
from app.schemas.indicators import IndicatorResponse


router = APIRouter(prefix="/api/v1")
DbSession = Annotated[Session, Depends(get_db)]
PageNumber = Annotated[int, Query(ge=1, description="Número da página")]
PageSize = Annotated[int, Query(ge=1, le=100, description="Itens por página (máximo 100)")]


def _page(items: list[Any], total: int, page: int, page_size: int) -> dict[str, Any]:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


def _geometry(value: str | dict[str, Any]) -> dict[str, Any]:
    return json.loads(value) if isinstance(value, str) else value


def _well_response(well: Well, location: str | dict[str, Any]) -> WellResponse:
    return WellResponse(
        id=well.id,
        source=well.source,
        data_classification=well.data_classification,
        code=well.code,
        name=well.name,
        location=_geometry(location),
        municipality=well.municipality,
        state=well.state,
        depth_m=well.depth_m,
        is_active=well.is_active,
        created_at=well.created_at,
        updated_at=well.updated_at,
    )


def _sector_response(sector: ServiceSector, boundary: str | dict[str, Any]) -> SectorResponse:
    return SectorResponse(
        id=sector.id,
        source=sector.source,
        data_classification=sector.data_classification,
        code=sector.code,
        name=sector.name,
        description=sector.description,
        boundary=_geometry(boundary),
        created_at=sector.created_at,
        updated_at=sector.updated_at,
    )


@router.get("/dashboard/summary", response_model=DashboardSummaryResponse, tags=["dashboard"],
            summary="Resumo operacional para a visão geral")
def dashboard_summary(db: DbSession) -> DashboardSummaryResponse:
    total_wells = db.scalar(select(func.count()).select_from(Well)) or 0
    active_wells = db.scalar(select(func.count()).select_from(Well).where(Well.is_active.is_(True))) or 0
    total_sectors = db.scalar(select(func.count()).select_from(ServiceSector)) or 0
    total_measurements = sum(
        db.scalar(select(func.count()).select_from(model)) or 0
        for model in (GroundwaterMeasurement, OperationalMeasurement, RainfallMeasurement)
    )
    return DashboardSummaryResponse(
        total_wells=total_wells,
        active_wells=active_wells,
        inactive_wells=total_wells - active_wells,
        total_sectors=total_sectors,
        total_measurements=total_measurements,
    )


@router.get(
    "/wells",
    response_model=WellPage,
    tags=["wells"],
    summary="Lista poços",
    description="Lista poços com paginação e filtros cadastrais.",
)
def list_wells(
    db: DbSession,
    page: PageNumber = 1,
    page_size: PageSize = 20,
    q: Annotated[str | None, Query(min_length=1, description="Busca em código ou nome")] = None,
    municipality: Annotated[str | None, Query(description="Município exato")] = None,
    sector_id: Annotated[uuid.UUID | None, Query(description="Setor de atendimento vigente")] = None,
    state: Annotated[str | None, Query(min_length=2, max_length=2, description="UF")] = None,
    is_active: Annotated[bool | None, Query(description="Situação operacional")] = None,
) -> dict[str, Any]:
    filters = []
    if q:
        pattern = f"%{q}%"
        filters.append(or_(Well.code.ilike(pattern), Well.name.ilike(pattern)))
    if municipality:
        filters.append(Well.municipality.ilike(municipality))
    if sector_id:
        now = datetime.now(timezone.utc)
        filters.append(
            select(WellSector.id)
            .where(
                WellSector.well_id == Well.id,
                WellSector.sector_id == sector_id,
                WellSector.valid_from <= now,
                or_(WellSector.valid_to.is_(None), WellSector.valid_to > now),
            )
            .exists()
        )
    if state:
        filters.append(func.upper(Well.state) == state.upper())
    if is_active is not None:
        filters.append(Well.is_active.is_(is_active))

    total = db.scalar(select(func.count()).select_from(Well).where(*filters)) or 0
    statement = (
        select(Well, func.ST_AsGeoJSON(Well.location))
        .where(*filters)
        .order_by(Well.code, Well.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [_well_response(well, location) for well, location in db.execute(statement)]
    return _page(items, total, page, page_size)


@router.get(
    "/wells/{well_id}",
    response_model=WellResponse,
    responses={404: {"description": "Poço não encontrado"}},
    tags=["wells"],
    summary="Obtém um poço",
)
def get_well(well_id: uuid.UUID, db: DbSession) -> WellResponse:
    row = db.execute(
        select(Well, func.ST_AsGeoJSON(Well.location)).where(Well.id == well_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poço não encontrado")
    return _well_response(row[0], row[1])


@router.get("/wells/{well_id}/indicators", response_model=IndicatorResponse, tags=["indicators"],
            summary="Indicadores históricos de um poço")
def get_well_indicators(well_id: uuid.UUID, db: DbSession,
                        reference_date: Annotated[date | None, Query(description="Data de referência em UTC")] = None):
    well = db.get(Well, well_id)
    if well is None:
        raise HTTPException(status_code=404, detail="Poço não encontrado")
    result = well_indicators(db, well, reference_date)
    if result is None:
        raise HTTPException(status_code=404, detail="Poço sem medições")
    return result


@router.get(
    "/sectors",
    response_model=SectorPage,
    tags=["sectors"],
    summary="Lista setores",
    description="Lista setores de atendimento com paginação e busca por código ou nome.",
)
def list_sectors(
    db: DbSession,
    page: PageNumber = 1,
    page_size: PageSize = 20,
    q: Annotated[str | None, Query(min_length=1, description="Busca em código ou nome")] = None,
) -> dict[str, Any]:
    filters = []
    if q:
        pattern = f"%{q}%"
        filters.append(or_(ServiceSector.code.ilike(pattern), ServiceSector.name.ilike(pattern)))

    total = db.scalar(select(func.count()).select_from(ServiceSector).where(*filters)) or 0
    statement = (
        select(ServiceSector, func.ST_AsGeoJSON(ServiceSector.boundary))
        .where(*filters)
        .order_by(ServiceSector.code, ServiceSector.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [_sector_response(sector, boundary) for sector, boundary in db.execute(statement)]
    return _page(items, total, page, page_size)


@router.get(
    "/sectors/{sector_id}",
    response_model=SectorResponse,
    responses={404: {"description": "Setor não encontrado"}},
    tags=["sectors"],
    summary="Obtém um setor",
)
def get_sector(sector_id: uuid.UUID, db: DbSession) -> SectorResponse:
    row = db.execute(
        select(ServiceSector, func.ST_AsGeoJSON(ServiceSector.boundary)).where(
            ServiceSector.id == sector_id
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setor não encontrado")
    return _sector_response(row[0], row[1])


@router.get("/sectors/{sector_id}/indicators", response_model=IndicatorResponse, tags=["indicators"],
            summary="Indicadores históricos de um setor")
def get_sector_indicators(sector_id: uuid.UUID, db: DbSession,
                          reference_date: Annotated[date | None, Query(description="Data de referência em UTC")] = None):
    sector = db.get(ServiceSector, sector_id)
    if sector is None:
        raise HTTPException(status_code=404, detail="Setor não encontrado")
    result = sector_indicators(db, sector, reference_date)
    if result is None:
        raise HTTPException(status_code=404, detail="Setor sem medições")
    return result


def _measurement_selects(
    measurement_types: list[MeasurementType],
    well_id: uuid.UUID | None,
    sector_id: uuid.UUID | None,
    measured_from: datetime | None,
    measured_to: datetime | None,
    classification: DataClassification | None,
    source: str | None,
):
    null_uuid = cast(literal(None), UUID(as_uuid=True))
    null_number = cast(literal(None), Numeric())
    null_integer = cast(literal(None), Integer())
    null_string = cast(literal(None), String())

    def common_filters(model: Any) -> list[Any]:
        result = []
        if measured_from:
            result.append(model.measured_at >= measured_from)
        if measured_to:
            result.append(model.measured_at <= measured_to)
        if classification:
            result.append(model.data_classification == classification)
        if source:
            result.append(model.source.ilike(source))
        return result

    statements = []
    if "groundwater" in measurement_types and sector_id is None:
        filters = common_filters(GroundwaterMeasurement)
        if well_id:
            filters.append(GroundwaterMeasurement.well_id == well_id)
        statements.append(
            select(
                GroundwaterMeasurement.dynamic_level_m.label("dynamic_level_m"),
                null_number.label("daily_demand_m3"),
                null_number.label("utilization"),
                cast(literal(None), Boolean()).label("operational_failure"),
                GroundwaterMeasurement.id.label("id"), literal("groundwater").label("type"),
                GroundwaterMeasurement.well_id.label("well_id"), null_uuid.label("service_sector_id"),
                GroundwaterMeasurement.measured_at.label("measured_at"), GroundwaterMeasurement.data_classification.label("data_classification"),
                GroundwaterMeasurement.source.label("source"), GroundwaterMeasurement.water_level_m.label("water_level_m"),
                GroundwaterMeasurement.temperature_c.label("temperature_c"), GroundwaterMeasurement.ph.label("ph"),
                GroundwaterMeasurement.conductivity_us_cm.label("conductivity_us_cm"), null_number.label("flow_rate_m3_h"),
                null_number.label("pumped_volume_m3"), null_number.label("runtime_hours"), null_string.label("operating_status"),
                null_number.label("precipitation_mm"), null_integer.label("accumulation_minutes"), null_string.label("station_code"),
                null_string.label("location"), GroundwaterMeasurement.created_at.label("created_at"), GroundwaterMeasurement.updated_at.label("updated_at"),
            ).where(*filters)
        )
    if "operational" in measurement_types and sector_id is None:
        filters = common_filters(OperationalMeasurement)
        if well_id:
            filters.append(OperationalMeasurement.well_id == well_id)
        statements.append(
            select(
                null_number.label("dynamic_level_m"),
                OperationalMeasurement.daily_demand_m3.label("daily_demand_m3"),
                OperationalMeasurement.utilization.label("utilization"),
                OperationalMeasurement.operational_failure.label("operational_failure"),
                OperationalMeasurement.id.label("id"), literal("operational").label("type"),
                OperationalMeasurement.well_id.label("well_id"), null_uuid.label("service_sector_id"),
                OperationalMeasurement.measured_at.label("measured_at"), OperationalMeasurement.data_classification.label("data_classification"),
                OperationalMeasurement.source.label("source"), null_number.label("water_level_m"), null_number.label("temperature_c"),
                null_number.label("ph"), null_number.label("conductivity_us_cm"), OperationalMeasurement.flow_rate_m3_h.label("flow_rate_m3_h"),
                OperationalMeasurement.pumped_volume_m3.label("pumped_volume_m3"), OperationalMeasurement.runtime_hours.label("runtime_hours"),
                OperationalMeasurement.operating_status.label("operating_status"), null_number.label("precipitation_mm"),
                null_integer.label("accumulation_minutes"), null_string.label("station_code"), null_string.label("location"),
                OperationalMeasurement.created_at.label("created_at"), OperationalMeasurement.updated_at.label("updated_at"),
            ).where(*filters)
        )
    if "rainfall" in measurement_types and well_id is None:
        filters = common_filters(RainfallMeasurement)
        if sector_id:
            filters.append(RainfallMeasurement.service_sector_id == sector_id)
        statements.append(
            select(
                null_number.label("dynamic_level_m"),
                null_number.label("daily_demand_m3"),
                null_number.label("utilization"),
                cast(literal(None), Boolean()).label("operational_failure"),
                RainfallMeasurement.id.label("id"), literal("rainfall").label("type"), null_uuid.label("well_id"),
                RainfallMeasurement.service_sector_id.label("service_sector_id"), RainfallMeasurement.measured_at.label("measured_at"),
                RainfallMeasurement.data_classification.label("data_classification"), RainfallMeasurement.source.label("source"),
                null_number.label("water_level_m"), null_number.label("temperature_c"), null_number.label("ph"),
                null_number.label("conductivity_us_cm"), null_number.label("flow_rate_m3_h"), null_number.label("pumped_volume_m3"),
                null_number.label("runtime_hours"), null_string.label("operating_status"), RainfallMeasurement.precipitation_mm.label("precipitation_mm"),
                RainfallMeasurement.accumulation_minutes.label("accumulation_minutes"), RainfallMeasurement.station_code.label("station_code"),
                func.ST_AsGeoJSON(RainfallMeasurement.location).label("location"), RainfallMeasurement.created_at.label("created_at"),
                RainfallMeasurement.updated_at.label("updated_at"),
            ).where(*filters)
        )
    return statements


@router.get(
    "/measurements",
    response_model=MeasurementPage,
    tags=["measurements"],
    summary="Lista medições",
    description="Consulta unificada das medições subterrâneas, operacionais e pluviométricas.",
)
def list_measurements(
    db: DbSession,
    page: PageNumber = 1,
    page_size: PageSize = 20,
    type: Annotated[list[MeasurementType] | None, Query(description="Tipo; pode ser repetido")] = None,
    well_id: Annotated[uuid.UUID | None, Query(description="Poço das medições subterrâneas/operacionais")] = None,
    sector_id: Annotated[uuid.UUID | None, Query(description="Setor das medições pluviométricas")] = None,
    measured_from: Annotated[datetime | None, Query(description="Instante inicial, inclusivo")] = None,
    measured_to: Annotated[datetime | None, Query(description="Instante final, inclusivo")] = None,
    classification: Annotated[DataClassification | None, Query(description="Classificação da origem")] = None,
    source: Annotated[str | None, Query(min_length=1, description="Fonte exata, sem diferenciar maiúsculas")] = None,
) -> dict[str, Any]:
    if measured_from and measured_to and measured_from > measured_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="measured_from deve ser anterior ou igual a measured_to",
        )

    measurement_types = list(dict.fromkeys(type or ["groundwater", "operational", "rainfall"]))
    statements = _measurement_selects(
        measurement_types, well_id, sector_id, measured_from, measured_to, classification, source
    )
    if not statements:
        return _page([], 0, page, page_size)

    combined = union_all(*statements).subquery("measurements")
    total = db.scalar(select(func.count()).select_from(combined)) or 0
    statement = (
        select(combined)
        .order_by(combined.c.measured_at.desc(), combined.c.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for row in db.execute(statement).mappings():
        payload = dict(row)
        if payload["location"] is not None:
            payload["location"] = _geometry(payload["location"])
        items.append(MeasurementResponse.model_validate(payload))
    return _page(items, total, page, page_size)
