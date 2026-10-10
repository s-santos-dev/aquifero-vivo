"""Bounded batch reads, one clock, and the existing indicator/risk engines."""
from collections import defaultdict, Counter
from datetime import timedelta
from sqlalchemy import select, func, or_
from app.models import Well, WellSector, ServiceSector, GroundwaterMeasurement, OperationalMeasurement, RainfallMeasurement
from app.indicators.service import _start, _end
from app.indicators.calculation import groundwater_metrics, operational_metrics, rainfall_metrics
from app.schemas.indicators import IndicatorResponse
from app.schemas.priority import PriorityWell, DerivedAlert
from app.risk.scoring import evaluate
from app.risk.recommendations import recommendations


def key(item):
    order = {'CRITICAL': 0, 'HIGH': 1, 'ATTENTION': 2, 'NORMAL': 3}
    return (order.get(item.classification, 4), -(item.score or 0), item.well_code, str(item.well_id))


def assessments(db, requested=None):
    wells = db.scalars(select(Well).order_by(Well.code, Well.id)).all()
    if not wells:
        return [], requested
    day = requested
    if day is None:
        dates = [db.scalar(select(func.max(model.measured_at)).join(Well, model.well_id == Well.id).where(model.source.is_not_distinct_from(Well.source), model.data_classification == Well.data_classification)) for model in (GroundwaterMeasurement, OperationalMeasurement)]
        day = max((v.date() for v in dates if v), default=None)
    sectors = {s.id: s for s in db.scalars(select(ServiceSector)).all()}
    memberships = {}
    if day:
        for link in db.scalars(select(WellSector).where(WellSector.valid_from <= _end(day), or_(WellSector.valid_to.is_(None), WellSector.valid_to > _end(day))).order_by(WellSector.valid_from.desc(), WellSector.id)):
            memberships.setdefault(link.well_id, link.sector_id)
    grouped = []
    for model, owner, catalog in ((GroundwaterMeasurement, 'well_id', Well), (OperationalMeasurement, 'well_id', Well), (RainfallMeasurement, 'service_sector_id', ServiceSector)):
        buckets = defaultdict(list)
        if day:
            # Only 60 days are needed by the v1 risk inputs, not the full history.
            rows = db.scalars(select(model).join(catalog, getattr(model, owner) == catalog.id).where(model.measured_at >= _start(day - timedelta(days=59)), model.measured_at <= _end(day), model.source.is_not_distinct_from(catalog.source), model.data_classification == catalog.data_classification).order_by(model.measured_at))
            for row in rows:
                buckets[getattr(row, owner)].append(row)
        grouped.append(buckets)
    rain_cache = {sid: rainfall_metrics(rows, day) for sid, rows in grouped[2].items()} if day else {}
    items = []
    for well in wells:
        sid = memberships.get(well.id)
        sector = sectors.get(sid)
        compatible = sector and (sector.source, sector.data_classification) == (well.source, well.data_classification)
        indicators = IndicatorResponse(entity_id=well.id, reference_date=day, data_classification=well.data_classification, source=well.source, sector_id=sid, groundwater=groundwater_metrics(grouped[0][well.id], day), operations=operational_metrics(grouped[1][well.id], day), rainfall=rain_cache.get(sid, {}) if compatible else {}) if day else None
        risk = evaluate(indicators, well.id, well.code, well.data_classification, well.source)
        items.append(PriorityWell(**risk.model_dump(), municipality=well.municipality, sector_id=sid, sector_code=sector.code if sector else None, sector_name=sector.name if sector else None, recommendations=recommendations(risk)))
    return sorted(items, key=key), day


def filtered(items, classification=None, sector_id=None, municipality=None):
    return [v for v in items if (not classification or (v.classification or v.status) == classification) and (not sector_id or v.sector_id == sector_id) and (not municipality or (v.municipality or '').casefold() == municipality.casefold())]


def distribution(items):
    counts = Counter(v.classification or v.status for v in items)
    return {name: counts[name] for name in ('NORMAL', 'ATTENTION', 'HIGH', 'CRITICAL', 'INSUFFICIENT_DATA')}


def alerts(items):
    result = []
    for item in items:
        if item.status == 'INSUFFICIENT_DATA':
            kind, message = 'DATA_QUALITY', 'Não foi possível avaliar este poço com a cobertura mínima exigida. Verifique a disponibilidade das medições.'
        elif item.classification in ('HIGH', 'CRITICAL'):
            kind, message = 'INVESTIGATION', 'Os indicadores disponíveis justificam investigação prioritária segundo o índice experimental. Recomenda-se revisão técnica das condições de operação.'
        else:
            continue
        result.append(DerivedAlert(id=f'{item.well_id}:{item.reference_date}:{item.model_version}:{kind}', kind=kind, message=message, evaluation=item))
    return result
