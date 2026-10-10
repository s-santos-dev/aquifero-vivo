import copy
import hashlib
from fastapi.testclient import TestClient
from sqlalchemy import select,func
import pytest
from app.database import get_db
from app.main import app
from app.models import ClimateStation,RainfallObservation,GroundwaterObservation
from app.ingestion.climate.load import load,snapshot
from app.ingestion.climate.transform import transform
from app.simulation import SimulationConfig,generate_dataset
from app.simulation.seed_database import seed_dataset
from app.ingestion.rimas.transform import transform as rimas_transform
from app.ingestion.rimas.load import load as rimas_load
from test_simulation_database import db,pytestmark
from test_climate import climate,change
from test_rimas import rimas


def climate_snapshot(db):
    return [(r.id,r.created_at,r.updated_at,r.source_metadata) for r in db.scalars(select(RainfallObservation).order_by(RainfallObservation.id))]


def test_load_idempotence_api_spatial_filters_and_preservation(db,climate,rimas):
    seed_dataset(db,generate_dataset(SimulationConfig(well_count=2,sector_count=1,days=60)))
    well,rimas_rows,_=rimas_transform(*rimas);rimas_load(db,well,rimas_rows)
    before=snapshot(db)
    assert load(db,*climate)['created_observations']==24
    assert snapshot(db)==before
    original=climate_snapshot(db)
    b,m=climate;m=copy.deepcopy(m);m['batch']='repeated-batch'
    assert load(db,b,m)['unchanged_observations']==24
    assert climate_snapshot(db)==original and snapshot(db)==before
    station_id=transform(*climate)[0]['id']
    app.dependency_overrides[get_db]=lambda:db
    try:
        with TestClient(app) as client:
            stations=client.get('/api/v1/climate/stations?q=A237&page_size=1').json()
            assert stations['total']==1 and stations['items'][0]['source']=='INMET'
            assert client.get('/api/v1/climate/stations?q=absent').json()['total']==0
            assert client.get(f'/api/v1/climate/stations/{station_id}').json()['coverage']['observed_hours']==24
            path=f'/api/v1/climate/stations/{station_id}/rainfall'
            hourly=client.get(path+'?resolution=hourly&start=2025-01-01&end=2025-01-01&page_size=5').json()
            assert hourly['total']==24 and len(hourly['items'])==5 and hourly['pages']==5
            assert hourly['items'][0]['value_mm']=='0.0000'
            assert hourly['items'][0]['source_metadata']['original_date']=='2025/01/01'
            assert client.get(path+'?resolution=hourly&start=2024-01-01&end=2024-01-01').json()['total']==0
            daily=client.get(path+'?start=2025-01-01&end=2025-01-02&page_size=1&page=2').json()
            assert daily['items'][0]['value_mm'] is None and daily['total']==2
            assert daily['items'][0]['observed_hours']==0
            for query in ('?start=2025-02-01&end=2025-01-01','?page_size=101','?resolution=monthly','?start=2020-01-01&end=2025-01-01'):
                assert client.get(path+query).status_code==422
            nearby=client.get(f'/api/v1/wells/{well["id"]}/nearby-climate?start=2025-01-01&end=2025-01-02').json()
            assert nearby['total']==1
            assert 66<nearby['items'][0]['distance_km']<68
            assert nearby['items'][0]['requested_coverage']['complete_days']==1
            assert client.get(f'/api/v1/wells/{well["id"]}/nearby-climate?radius_km=10').json()['total']==0
            assert client.get(f'/api/v1/wells/{well["id"]}/nearby-climate?start=2025-01-01').status_code==422
            indicators=client.get(f'/api/v1/climate/stations/{station_id}/indicators?reference_date=2025-01-01').json()
            assert indicators['accumulations']['7']['status']=='INSUFFICIENT_DATA'
            assert client.get(f'/api/v1/wells/{well["id"]}/risk').json()['status']=='INSUFFICIENT_DATA'
    finally:app.dependency_overrides.clear()
    assert db.scalar(select(func.count()).select_from(GroundwaterObservation))==5


def test_conflicting_revision_rejected_without_writes(db,climate):
    load(db,*climate);original=climate_snapshot(db)
    b,m=climate;line=b.decode('latin1').splitlines()[10];fields=line.split(';');fields[2]='10'
    with pytest.raises(ValueError,match='divergente'):load(db,*change(b,m,line,';'.join(fields)))
    assert climate_snapshot(db)==original


def test_missing_observation_preserved_but_no_daily_total(db,climate):
    b,m=climate;line=b.decode('latin1').splitlines()[10];fields=line.split(';');fields[2]=''
    assert load(db,*change(b,m,line,';'.join(fields)))['created_observations']==24
    assert db.scalar(select(func.count()).select_from(RainfallObservation).where(RainfallObservation.availability=='MISSING'))==1


def test_bad_batch_preflight_does_not_create_station(db,climate):
    b,m=climate;line=b.decode('latin1').splitlines()[10];fields=line.split(';');fields[2]='-1'
    with pytest.raises(ValueError,match='rejeições'):load(db,*change(b,m,line,';'.join(fields)))
    assert db.scalar(select(func.count()).select_from(ClimateStation))==0


def test_not_found(db):
    app.dependency_overrides[get_db]=lambda:db
    try:
        with TestClient(app) as client:
            for path in ('/climate/stations/00000000-0000-0000-0000-000000000000','/climate/stations/00000000-0000-0000-0000-000000000000/rainfall','/wells/00000000-0000-0000-0000-000000000000/nearby-climate'):
                assert client.get('/api/v1'+path).status_code==404
    finally:app.dependency_overrides.clear()


@pytest.mark.parametrize('availability,value',[('OBSERVED',None),('OBSERVED',-1),('MISSING',0),('REJECTED',None)])
def test_database_observation_integrity(db,climate,availability,value):
    from sqlalchemy.exc import IntegrityError
    from datetime import timedelta
    from uuid import uuid4
    load(db,*climate)
    old=db.scalar(select(RainfallObservation))
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(RainfallObservation(id=uuid4(),station_id=old.station_id,measured_at=old.measured_at+timedelta(days=100),value_mm=value,
                unit='mm',source='INMET',availability=availability,source_metadata=old.source_metadata));db.flush()
