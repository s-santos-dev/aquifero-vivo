"""Paginated public climate API; distances describe comparison candidates only."""
import math
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ClimateStation, RainfallObservation, Well
from app.schemas.api import Page as CollectionPage
from app.schemas.climate import ClimateStationResponse, NearbyClimatePage, RainfallPage, RainfallIndicatorsResponse
from .service import daily_series, accumulations, DAILY_RULE

router = APIRouter(prefix="/api/v1", tags=["climate"])
Db = Annotated[Session, Depends(get_db)]
Page = Annotated[int, Query(ge=1)]
Size = Annotated[int, Query(ge=1, le=100)]


def page_result(items, total, page, page_size):
    return dict(items=items,total=total,page=page,page_size=page_size,pages=math.ceil(total/page_size))


def station_or_404(db, station_id):
    station = db.get(ClimateStation,station_id)
    if not station:
        raise HTTPException(404,"Estação climática não encontrada")
    return station


def station_payload(db, station):
    lon,lat = db.execute(select(func.ST_X(ClimateStation.location),func.ST_Y(ClimateStation.location)).where(ClimateStation.id==station.id)).one()
    query = select(func.min(RainfallObservation.measured_at),func.max(RainfallObservation.measured_at),func.count(),
                   func.count().filter(RainfallObservation.availability=="OBSERVED")).where(RainfallObservation.station_id==station.id)
    first,last,total,observed = db.execute(query).one()
    expected = int((last-first).total_seconds()/3600)+1 if first else 0
    # Dates describe intervals, not the clock date of their ending reading.
    return dict(id=station.id,official_code=station.official_code,name=station.name,source=station.source,
        observation_type=station.observation_type,latitude=lat,longitude=lon,spatial_reference="EPSG:4326",
        data_classification="PUBLIC",is_synthetic=False,timezone="UTC",unit="mm",frequency="hourly_previous_interval",
        period=dict(start=(first-timedelta(hours=1)).date() if first else None,end=(last-timedelta(hours=1)).date() if last else None,
                    first_timestamp=first,last_timestamp=last),
        coverage=dict(records=total,observed_hours=observed,expected_hours=expected,missing_values=total-observed,
                      absent_hours=expected-total,observed_fraction=observed/expected if expected else None),
        quality_status="NOT_PROVIDED",source_metadata=station.source_metadata,eligible_for_risk=False)


@router.get("/climate/stations", response_model=CollectionPage[ClimateStationResponse])
def stations(db: Db, page: Page=1, page_size: Size=20, q: str | None=None):
    query = select(ClimateStation)
    if q:
        query=query.where(ClimateStation.name.ilike("%"+q+"%") | ClimateStation.official_code.ilike("%"+q+"%"))
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    items=db.scalars(query.order_by(ClimateStation.official_code).offset((page-1)*page_size).limit(page_size)).all()
    return page_result([station_payload(db,s) for s in items],total,page,page_size)


@router.get("/climate/stations/{station_id}", response_model=ClimateStationResponse)
def station_detail(station_id: UUID, db: Db):
    return station_payload(db,station_or_404(db,station_id))


def period(db, station_id, start, end):
    if end is None:
        last=db.scalar(select(func.max(RainfallObservation.measured_at)).where(RainfallObservation.station_id==station_id))
        end=(last-timedelta(hours=1)).date() if last else date.today()
    start=start or end-timedelta(days=89)
    if start>end or (end-start).days>365:
        raise HTTPException(422,"Selecione até 366 dias, início anterior ao fim")
    return start,end


def interval_query(station_id, start, end):
    begin=datetime.combine(start,datetime.min.time(),timezone.utc)
    finish=datetime.combine(end+timedelta(days=1),datetime.min.time(),timezone.utc)
    return select(RainfallObservation).where(RainfallObservation.station_id==station_id,RainfallObservation.measured_at>begin,RainfallObservation.measured_at<=finish)


@router.get("/climate/stations/{station_id}/rainfall", response_model=RainfallPage)
def rainfall_history(station_id: UUID, db: Db, start: date | None=None, end: date | None=None,
                     resolution: Literal["hourly","daily"]="daily", page: Page=1, page_size: Size=20):
    station=station_or_404(db,station_id)
    start,end=period(db,station_id,start,end)
    query=interval_query(station_id,start,end)
    if resolution=="hourly":
        total=db.scalar(select(func.count()).select_from(query.subquery()))
        rows=db.scalars(query.order_by(RainfallObservation.measured_at).offset((page-1)*page_size).limit(page_size)).all()
        items=[dict(id=r.id,measured_at=r.measured_at,value_mm=str(r.value_mm) if r.value_mm is not None else None,
                    unit=r.unit,source=r.source,availability=r.availability,source_metadata=r.source_metadata) for r in rows]
        coverage=None
    else:
        # Fetch only intervals for this page of days, never a station's unbounded history.
        total=(end-start).days+1
        page_start=start+timedelta(days=(page-1)*page_size)
        page_end=min(end,page_start+timedelta(days=page_size-1))
        rows=db.scalars(interval_query(station_id,page_start,page_end).order_by(RainfallObservation.measured_at)).all() if page_start<=end else []
        items=daily_series(rows,page_start,page_end) if page_start<=end else []
        coverage=dict(scope="page",complete_days=sum(i["availability"]=="COMPLETE" for i in items),expected_days=len(items))
    return dict(**page_result(items,total,page,page_size),station=station_payload(db,station),start=start,end=end,
        resolution=resolution,coverage=coverage,aggregation_rule=DAILY_RULE if resolution=="daily" else None,
        notice="Acumulados diários UTC exigem 24 intervalos. Qualidade instrumental não informada. Sem inferência causal.")


@router.get("/climate/stations/{station_id}/indicators", response_model=RainfallIndicatorsResponse)
def indicators(station_id: UUID, db: Db, reference_date: date):
    station_or_404(db,station_id)
    start=reference_date-timedelta(days=89)
    rows=db.scalars(interval_query(station_id,start,reference_date)).all()
    return dict(reference_date=reference_date,timezone="UTC",aggregation_rule=DAILY_RULE,
                accumulations=accumulations(daily_series(rows,start,reference_date),reference_date),
                notice="Indicadores descritivos; não são normal climatológica, seca oficial ou recarga.")


@router.get("/wells/{well_id}/nearby-climate", response_model=NearbyClimatePage)
def nearby(well_id: UUID, db: Db, radius_km: Annotated[float,Query(gt=0,le=500)]=100,
           start: date | None=None, end: date | None=None, page: Page=1, page_size: Size=20):
    well=db.get(Well,well_id)
    if not well:
        raise HTTPException(404,"Poço não encontrado")
    if (start is None)!=(end is None) or (start and (start>end or (end-start).days>365)):
        raise HTTPException(422,"Informe início e fim compatíveis, até 366 dias")
    station_geo=cast(ClimateStation.location,Geography(srid=4326))
    well_geo=cast(select(Well.location).where(Well.id==well.id).scalar_subquery(),Geography(srid=4326))
    distance=func.ST_Distance(station_geo,well_geo)
    query=select(ClimateStation,distance.label("distance_m")).where(func.ST_DWithin(station_geo,well_geo,radius_km*1000))
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    items=[]
    for station,meters in db.execute(query.order_by(distance,ClimateStation.id).offset((page-1)*page_size).limit(page_size)):
        payload=station_payload(db,station)
        payload.update(distance_km=meters/1000,distance_method="PostGIS ST_Distance geography, WGS84 spheroid")
        if start:
            rows=db.scalars(interval_query(station.id,start,end)).all()
            days=daily_series(rows,start,end)
            payload["requested_coverage"]=dict(start=start,end=end,expected_days=len(days),complete_days=sum(d["availability"]=="COMPLETE" for d in days))
        items.append(payload)
    return dict(**page_result(items,total,page,page_size),notice="Proximidade territorial para comparação; não representa chuva no poço nem causalidade. Fuso RIMAS permanece desconhecido.")
