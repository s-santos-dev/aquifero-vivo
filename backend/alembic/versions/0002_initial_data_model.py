"""Cria o modelo de dados inicial do Aquífero Vivo."""

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "wells",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamps(),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.Geometry("POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("municipality", sa.String(120)),
        sa.Column("state", sa.String(2)),
        sa.Column("depth_m", sa.Numeric(10, 2)),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_wells_location_gist", "wells", ["location"], postgresql_using="gist")

    op.create_table(
        "service_sectors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamps(),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "boundary",
            geoalchemy2.Geometry("MULTIPOLYGON", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(
        "ix_service_sectors_boundary_gist",
        "service_sectors",
        ["boundary"],
        postgresql_using="gist",
    )

    op.create_table(
        "groundwater_measurements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamps(),
        sa.Column("well_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("water_level_m", sa.Numeric(10, 3), nullable=False),
        sa.Column("temperature_c", sa.Numeric(6, 2)),
        sa.Column("ph", sa.Numeric(4, 2)),
        sa.Column("conductivity_us_cm", sa.Numeric(12, 2)),
        sa.Column("source", sa.String(80)),
        sa.CheckConstraint("water_level_m >= 0", name="ck_groundwater_level_nonnegative"),
        sa.ForeignKeyConstraint(["well_id"], ["wells.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_groundwater_measured_at", "groundwater_measurements", ["measured_at"])
    op.create_index(
        "ix_groundwater_well_measured_at",
        "groundwater_measurements",
        ["well_id", "measured_at"],
    )

    op.create_table(
        "rainfall_measurements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamps(),
        sa.Column("service_sector_id", postgresql.UUID(as_uuid=True)),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("precipitation_mm", sa.Numeric(10, 3), nullable=False),
        sa.Column("accumulation_minutes", sa.Integer()),
        sa.Column("station_code", sa.String(64)),
        sa.Column("source", sa.String(80)),
        sa.Column(
            "location",
            geoalchemy2.Geometry("POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.CheckConstraint("precipitation_mm >= 0", name="ck_rainfall_nonnegative"),
        sa.ForeignKeyConstraint(
            ["service_sector_id"], ["service_sectors.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rainfall_location_gist", "rainfall_measurements", ["location"], postgresql_using="gist")
    op.create_index("ix_rainfall_measured_at", "rainfall_measurements", ["measured_at"])
    op.create_index(
        "ix_rainfall_sector_measured_at",
        "rainfall_measurements",
        ["service_sector_id", "measured_at"],
    )

    op.create_table(
        "operational_measurements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamps(),
        sa.Column("well_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("flow_rate_m3_h", sa.Numeric(12, 3)),
        sa.Column("pumped_volume_m3", sa.Numeric(14, 3)),
        sa.Column("runtime_hours", sa.Numeric(10, 3)),
        sa.Column("operating_status", sa.String(40)),
        sa.Column("source", sa.String(80)),
        sa.CheckConstraint("flow_rate_m3_h IS NULL OR flow_rate_m3_h >= 0", name="ck_operational_flow_nonnegative"),
        sa.CheckConstraint("pumped_volume_m3 IS NULL OR pumped_volume_m3 >= 0", name="ck_operational_volume_nonnegative"),
        sa.CheckConstraint("runtime_hours IS NULL OR runtime_hours >= 0", name="ck_operational_runtime_nonnegative"),
        sa.ForeignKeyConstraint(["well_id"], ["wells.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operational_measured_at", "operational_measurements", ["measured_at"])
    op.create_index(
        "ix_operational_well_measured_at",
        "operational_measurements",
        ["well_id", "measured_at"],
    )

    op.create_table(
        "well_sectors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamps(),
        sa.Column("well_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sector_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_well_sector_period"),
        sa.ForeignKeyConstraint(["sector_id"], ["service_sectors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["well_id"], ["wells.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("well_id", "sector_id", "valid_from", name="uq_well_sector_period"),
    )
    op.create_index("ix_well_sectors_sector_id", "well_sectors", ["sector_id"])
    op.create_index(
        "ix_well_sectors_well_validity",
        "well_sectors",
        ["well_id", "valid_from", "valid_to"],
    )

    op.create_table(
        "risk_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamps(),
        sa.Column("well_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("methodology_version", sa.String(40), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_risk_score_range"),
        sa.CheckConstraint("risk_level IN ('low', 'medium', 'high', 'critical')", name="ck_risk_level"),
        sa.ForeignKeyConstraint(["well_id"], ["wells.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risk_assessments_assessed_at", "risk_assessments", ["assessed_at"])
    op.create_index("ix_risk_assessments_level", "risk_assessments", ["risk_level"])
    op.create_index(
        "ix_risk_assessments_well_assessed_at",
        "risk_assessments",
        ["well_id", "assessed_at"],
    )

    op.create_table(
        "risk_factors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamps(),
        sa.Column("risk_assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("raw_value", sa.Numeric(16, 4)),
        sa.Column("normalized_value", sa.Numeric(10, 6)),
        sa.Column("weight", sa.Numeric(10, 6)),
        sa.Column("contribution", sa.Numeric(10, 6)),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text())),
        sa.ForeignKeyConstraint(
            ["risk_assessment_id"], ["risk_assessments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("risk_assessment_id", "code", name="uq_risk_factor_code"),
    )
    op.create_index("ix_risk_factors_assessment_id", "risk_factors", ["risk_assessment_id"])

    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamps(),
        sa.Column("well_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("risk_assessment_id", postgresql.UUID(as_uuid=True)),
        sa.Column("alert_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), server_default=sa.text("'open'"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("severity IN ('info', 'warning', 'critical')", name="ck_alert_severity"),
        sa.CheckConstraint("status IN ('open', 'acknowledged', 'resolved')", name="ck_alert_status"),
        sa.ForeignKeyConstraint(
            ["risk_assessment_id"], ["risk_assessments.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["well_id"], ["wells.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_risk_assessment_id", "alerts", ["risk_assessment_id"])
    op.create_index("ix_alerts_status_triggered_at", "alerts", ["status", "triggered_at"])
    op.create_index("ix_alerts_well_triggered_at", "alerts", ["well_id", "triggered_at"])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("risk_factors")
    op.drop_table("risk_assessments")
    op.drop_table("well_sectors")
    op.drop_table("operational_measurements")
    op.drop_table("rainfall_measurements")
    op.drop_table("groundwater_measurements")
    op.drop_table("service_sectors")
    op.drop_table("wells")
