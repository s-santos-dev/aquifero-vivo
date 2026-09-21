"""Bounded read-only queries feeding the indicator calculations."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.indicators.calculation import aggregate, groundwater_metrics, metric, operational_metrics, rainfall_metrics, trend
from app.models import GroundwaterMeasurement, OperationalMeasurement, RainfallMeasurement, ServiceSector, Well, WellSector
from app.schemas.indicators import IndicatorResponse


def _end(day: date) -> datetime:
    return datetime.combine(day, time.max, timezone.utc)


def _start(day: date) -> datetime:
    return datetime.combine(day, time.min, timezone.utc)


def _source_filters(model, catalog):
    return [model.data_classification == catalog.data_classification, model.source == catalog.source]


def _latest(db: Session, model, owner_column, owner_ids: list[uuid.UUID], catalog, cutoff: date | None) -> date | None:
    if not owner_ids:
        return None
    filters = [owner_column.in_(owner_ids), *_source_filters(model, catalog)]
    if cutoff:
        filters.append(model.measured_at <= _end(cutoff))
    value = db.scalar(select(func.max(model.measured_at)).where(*filters))
    return value.date() if value else None


def _rows(db: Session, model, owner_column, owner_ids: list[uuid.UUID], catalog, day: date, lookback: int):
    if not owner_ids:
        return []
    return db.scalars(
        select(model).where(
            owner_column.in_(owner_ids),
            model.measured_at >= _start(day - timedelta(days=lookback - 1)),
            model.measured_at <= _end(day),
            *_source_filters(model, catalog),
        ).order_by(model.measured_at)
    ).all()


def _membership(db: Session, well_id: uuid.UUID, day: date) -> uuid.UUID | None:
    at = _end(day)
    return db.scalar(
        select(WellSector.sector_id).where(
            WellSector.well_id == well_id,
            WellSector.valid_from <= at,
            or_(WellSector.valid_to.is_(None), WellSector.valid_to > at),
        ).order_by(WellSector.valid_from.desc(), WellSector.id).limit(1)
    )


def well_indicators(db: Session, well: Well, requested: date | None) -> IndicatorResponse | None:
    if requested is None:
        dates = [
            _latest(db, GroundwaterMeasurement, GroundwaterMeasurement.well_id, [well.id], well, None),
            _latest(db, OperationalMeasurement, OperationalMeasurement.well_id, [well.id], well, None),
        ]
        day = max((value for value in dates if value is not None), default=None)
    else:
        day = requested
    if day is None:
        return None
    groundwater = _rows(db, GroundwaterMeasurement, GroundwaterMeasurement.well_id, [well.id], well, day, 180)
    operations = _rows(db, OperationalMeasurement, OperationalMeasurement.well_id, [well.id], well, day, 180)
    sector_id = _membership(db, well.id, day)
    sector = db.get(ServiceSector, sector_id) if sector_id else None
    rainfall = _rows(db, RainfallMeasurement, RainfallMeasurement.service_sector_id, [sector_id], sector, day, 180) if sector else []
    return IndicatorResponse(
        entity_id=well.id, reference_date=day, data_classification=well.data_classification,
        source=well.source, sector_id=sector_id,
        groundwater=groundwater_metrics(groundwater, day),
        operations=operational_metrics(operations, day),
        rainfall=rainfall_metrics(rainfall, day),
    )


def _sector_daily(rows, well_ids: set[uuid.UUID], field: str) -> dict[date, float | None]:
    """Sum only complete days with exactly one non-null value per current well."""
    grouped: dict[date, dict[uuid.UUID, list[float | None]]] = {}
    for row in rows:
        value = getattr(row, field)
        grouped.setdefault(row.measured_at.date(), {}).setdefault(row.well_id, []).append(float(value) if value is not None else None)
    result = {}
    for day, values in grouped.items():
        valid = set(values) == well_ids and all(len(item) == 1 and item[0] is not None for item in values.values())
        result[day] = sum(item[0] for item in values.values()) if valid else None
    return result


def sector_indicators(db: Session, sector: ServiceSector, requested: date | None) -> IndicatorResponse | None:
    # Without a date, rainfall is the sector clock; it is independent of the number of wells.
    day = requested or _latest(db, RainfallMeasurement, RainfallMeasurement.service_sector_id, [sector.id], sector, None)
    if day is None:
        return None
    at = _end(day)
    well_ids = set(db.scalars(select(WellSector.well_id).where(
        WellSector.sector_id == sector.id, WellSector.valid_from <= at,
        or_(WellSector.valid_to.is_(None), WellSector.valid_to > at),
    )).all())
    rain = _rows(db, RainfallMeasurement, RainfallMeasurement.service_sector_id, [sector.id], sector, day, 180)
    # A sector can contain more than one data source. Do not combine operational sources.
    eligible = set(db.scalars(select(Well.id).where(Well.id.in_(well_ids), Well.data_classification == sector.data_classification, Well.source == sector.source)).all()) if well_ids else set()
    operations = _rows(db, OperationalMeasurement, OperationalMeasurement.well_id, list(eligible), sector, day, 180)
    totals = {}
    for key, field, unit in (("demand", "daily_demand_m3", "m³/dia"), ("pumped_volume", "pumped_volume_m3", "m³/dia")):
        series = _sector_daily(operations, eligible, field) if eligible else {}
        for length in (7, 30, 90):
            totals[f"total_{key}_avg_{length}d"] = aggregate(series, day, length, unit, "avg")
        totals[f"total_{key}_trend_30d"] = trend(series, day, 30, unit)
    totals["well_count"] = metric(float(len(well_ids)), "poços", 1, 1)
    return IndicatorResponse(
        entity_id=sector.id, reference_date=day, data_classification=sector.data_classification,
        source=sector.source, sector_id=sector.id, rainfall=rainfall_metrics(rain, day), aggregation=totals,
    )
