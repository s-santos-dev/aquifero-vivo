from geoalchemy2 import Geometry
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID

from app import models
from app.database import Base
from app.schemas import PointGeometry, WellCreate


EXPECTED_TABLES = {
    "alerts",
    "groundwater_measurements",
    "operational_measurements",
    "rainfall_measurements",
    "risk_assessments",
    "risk_factors",
    "service_sectors",
    "well_sectors",
    "wells",
}


def test_all_domain_entities_are_registered():
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_all_entities_have_uuid_and_audit_timestamps():
    for table in Base.metadata.tables.values():
        assert isinstance(table.c.id.type, UUID)
        assert table.c.id.primary_key
        assert table.c.created_at.type.timezone is True
        assert table.c.updated_at.type.timezone is True
        assert table.c.created_at.nullable is False
        assert table.c.updated_at.nullable is False


def test_spatial_columns_use_srid_4326_and_gist_indexes():
    spatial_columns = {
        "wells": "location",
        "rainfall_measurements": "location",
        "service_sectors": "boundary",
    }
    for table_name, column_name in spatial_columns.items():
        table = Base.metadata.tables[table_name]
        geometry = table.c[column_name].type
        assert isinstance(geometry, Geometry)
        assert geometry.srid == 4326
        assert any(
            index.dialect_options["postgresql"].get("using") == "gist"
            and column_name in index.columns
            for index in table.indexes
        )


def test_temporal_queries_have_composite_indexes():
    expected = {
        "groundwater_measurements": ("well_id", "measured_at"),
        "operational_measurements": ("well_id", "measured_at"),
        "rainfall_measurements": ("service_sector_id", "measured_at"),
        "risk_assessments": ("well_id", "assessed_at"),
        "alerts": ("well_id", "triggered_at"),
    }
    for table_name, columns in expected.items():
        table = Base.metadata.tables[table_name]
        index_columns = {tuple(column.name for column in index.columns) for index in table.indexes}
        assert columns in index_columns


def test_measurements_have_explicit_data_classification_constraint():
    for table_name in (
        "groundwater_measurements",
        "operational_measurements",
        "rainfall_measurements",
    ):
        table = Base.metadata.tables[table_name]
        assert table.c.data_classification.nullable is False
        constraints = {constraint.name for constraint in table.constraints}
        assert f"ck_{table_name.removesuffix('_measurements')}_data_classification" in constraints


def test_relationships_are_bidirectional():
    assert inspect(models.Well).relationships.groundwater_measurements.back_populates == "well"
    assert inspect(models.Well).relationships.operational_measurements.back_populates == "well"
    assert inspect(models.Well).relationships.sector_links.back_populates == "well"
    assert inspect(models.ServiceSector).relationships.well_links.back_populates == "sector"
    assert inspect(models.RiskAssessment).relationships.factors.back_populates == "assessment"
    assert inspect(models.RiskAssessment).relationships.alerts.back_populates == "risk_assessment"


def test_pydantic_schemas_are_independent_from_orm_models():
    payload = WellCreate(
        code="P-001",
        name="Poço Centro",
        location=PointGeometry(coordinates=(-38.5434, -3.7172)),
        depth_m="85.50",
    )
    assert payload.code == "P-001"
    assert payload.location.coordinates == (-38.5434, -3.7172)
    assert not isinstance(payload, models.Well)
