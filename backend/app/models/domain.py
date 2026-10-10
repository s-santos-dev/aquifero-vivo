from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class CatalogProvenance:
    # UNKNOWN preserves legacy provenance instead of falsely labeling it REAL.
    source: Mapped[str | None] = mapped_column(String(80))
    data_classification: Mapped[str] = mapped_column(
        String(16), nullable=False, default="UNKNOWN", server_default="UNKNOWN"
    )


class Well(CatalogProvenance, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "wells"
    __table_args__ = (
        Index("ix_wells_location_gist", "location", postgresql_using="gist"),
        UniqueConstraint("source", "source_record_id", name="uq_wells_source_record"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[WKBElement] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=False
    )
    municipality: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(2))
    depth_m: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    source_record_id: Mapped[str | None] = mapped_column(String(64))
    source_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_active: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, default=True, server_default=text("true")
    )

    groundwater_measurements: Mapped[list[GroundwaterMeasurement]] = relationship(
        back_populates="well", cascade="all, delete-orphan"
    )
    operational_measurements: Mapped[list[OperationalMeasurement]] = relationship(
        back_populates="well", cascade="all, delete-orphan"
    )
    sector_links: Mapped[list[WellSector]] = relationship(
        back_populates="well", cascade="all, delete-orphan"
    )
    risk_assessments: Mapped[list[RiskAssessment]] = relationship(
        back_populates="well", cascade="all, delete-orphan"
    )
    alerts: Mapped[list[Alert]] = relationship(
        back_populates="well", cascade="all, delete-orphan"
    )


class GroundwaterMeasurement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "groundwater_measurements"
    __table_args__ = (
        CheckConstraint("water_level_m >= 0", name="ck_groundwater_level_nonnegative"),
        CheckConstraint(
            "data_classification IN ('REAL', 'PUBLIC', 'SIMULATED')",
            name="ck_groundwater_data_classification",
        ),
        CheckConstraint("dynamic_level_m IS NULL OR dynamic_level_m >= water_level_m", name="ck_groundwater_dynamic"),
        Index("ix_groundwater_well_measured_at", "well_id", "measured_at"),
        Index("ix_groundwater_measured_at", "measured_at"),
    )

    well_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wells.id", ondelete="CASCADE"), nullable=False
    )
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    water_level_m: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    dynamic_level_m: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    ph: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    conductivity_us_cm: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    source: Mapped[str | None] = mapped_column(String(80))
    data_classification: Mapped[str] = mapped_column(String(16), nullable=False)

    well: Mapped[Well] = relationship(back_populates="groundwater_measurements")


class GroundwaterObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Original public readings; deliberately outside daily indicator inputs."""
    __tablename__ = "groundwater_observations"
    __table_args__ = (
        UniqueConstraint("source", "dataset", "station_code", "source_record_id", name="uq_observation_source_record"),
        CheckConstraint("source = 'RIMAS' AND data_classification = 'PUBLIC'", name="ck_observation_origin"),
        CheckConstraint("unit = 'm'", name="ck_observation_unit"),
        Index("ix_observation_well_measured_at", "well_id", "measured_at"),
    )
    well_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wells.id", ondelete="CASCADE"), nullable=False)
    # Portal CSV supplies a wall-clock time without a timezone: never invent UTC.
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    observed_level_m: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    data_classification: Mapped[str] = mapped_column(String(16), nullable=False)
    dataset: Mapped[str] = mapped_column(String(40), nullable=False)
    station_code: Mapped[str] = mapped_column(String(64), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(64), nullable=False)
    pumping: Mapped[str | None] = mapped_column(String(1))
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ServiceSector(CatalogProvenance, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_sectors"
    __table_args__ = (
        Index("ix_service_sectors_boundary_gist", "boundary", postgresql_using="gist"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    boundary: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False
    )

    well_links: Mapped[list[WellSector]] = relationship(
        back_populates="sector", cascade="all, delete-orphan"
    )
    rainfall_measurements: Mapped[list[RainfallMeasurement]] = relationship(
        back_populates="service_sector"
    )


class WellSector(CatalogProvenance, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "well_sectors"
    __table_args__ = (
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="ck_well_sector_period"
        ),
        UniqueConstraint("well_id", "sector_id", "valid_from", name="uq_well_sector_period"),
        Index("ix_well_sectors_sector_id", "sector_id"),
        Index("ix_well_sectors_well_validity", "well_id", "valid_from", "valid_to"),
    )

    well_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wells.id", ondelete="CASCADE"), nullable=False
    )
    sector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_sectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    well: Mapped[Well] = relationship(back_populates="sector_links")
    sector: Mapped[ServiceSector] = relationship(back_populates="well_links")


class RainfallMeasurement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rainfall_measurements"
    __table_args__ = (
        CheckConstraint("precipitation_mm >= 0", name="ck_rainfall_nonnegative"),
        CheckConstraint(
            "data_classification IN ('REAL', 'PUBLIC', 'SIMULATED')",
            name="ck_rainfall_data_classification",
        ),
        Index("ix_rainfall_sector_measured_at", "service_sector_id", "measured_at"),
        Index("ix_rainfall_measured_at", "measured_at"),
        Index("ix_rainfall_location_gist", "location", postgresql_using="gist"),
    )

    service_sector_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_sectors.id", ondelete="SET NULL")
    )
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    precipitation_mm: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    accumulation_minutes: Mapped[int | None]
    station_code: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str | None] = mapped_column(String(80))
    data_classification: Mapped[str] = mapped_column(String(16), nullable=False)
    location: Mapped[WKBElement] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=False
    )

    service_sector: Mapped[ServiceSector | None] = relationship(
        back_populates="rainfall_measurements"
    )


class OperationalMeasurement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "operational_measurements"
    __table_args__ = (
        CheckConstraint(
            "flow_rate_m3_h IS NULL OR flow_rate_m3_h >= 0",
            name="ck_operational_flow_nonnegative",
        ),
        CheckConstraint(
            "pumped_volume_m3 IS NULL OR pumped_volume_m3 >= 0",
            name="ck_operational_volume_nonnegative",
        ),
        CheckConstraint(
            "runtime_hours IS NULL OR runtime_hours >= 0",
            name="ck_operational_runtime_nonnegative",
        ),
        CheckConstraint(
            "data_classification IN ('REAL', 'PUBLIC', 'SIMULATED')",
            name="ck_operational_data_classification",
        ),
        CheckConstraint("daily_demand_m3 IS NULL OR daily_demand_m3 >= 0", name="ck_operational_demand"),
        CheckConstraint("utilization IS NULL OR utilization >= 0", name="ck_operational_utilization"),
        Index("ix_operational_well_measured_at", "well_id", "measured_at"),
        Index("ix_operational_measured_at", "measured_at"),
    )

    well_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wells.id", ondelete="CASCADE"), nullable=False
    )
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    flow_rate_m3_h: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    pumped_volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    runtime_hours: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    daily_demand_m3: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    utilization: Mapped[Decimal | None] = mapped_column(Numeric(14, 5))
    operational_failure: Mapped[bool | None] = mapped_column(Boolean)
    operating_status: Mapped[str | None] = mapped_column(String(40))
    source: Mapped[str | None] = mapped_column(String(80))
    data_classification: Mapped[str] = mapped_column(String(16), nullable=False)

    well: Mapped[Well] = relationship(back_populates="operational_measurements")


class RiskAssessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_risk_score_range"),
        CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_risk_level",
        ),
        Index("ix_risk_assessments_well_assessed_at", "well_id", "assessed_at"),
        Index("ix_risk_assessments_assessed_at", "assessed_at"),
        Index("ix_risk_assessments_level", "risk_level"),
    )

    well_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wells.id", ondelete="CASCADE"), nullable=False
    )
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(40), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    well: Mapped[Well] = relationship(back_populates="risk_assessments")
    factors: Mapped[list[RiskFactor]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )
    alerts: Mapped[list[Alert]] = relationship(back_populates="risk_assessment")


class RiskFactor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risk_factors"
    __table_args__ = (
        UniqueConstraint("risk_assessment_id", "code", name="uq_risk_factor_code"),
        Index("ix_risk_factors_assessment_id", "risk_assessment_id"),
    )

    risk_assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    raw_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    normalized_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    contribution: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    assessment: Mapped[RiskAssessment] = relationship(back_populates="factors")


class Alert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info', 'warning', 'critical')", name="ck_alert_severity"
        ),
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved')", name="ck_alert_status"
        ),
        Index("ix_alerts_well_triggered_at", "well_id", "triggered_at"),
        Index("ix_alerts_status_triggered_at", "status", "triggered_at"),
        Index("ix_alerts_risk_assessment_id", "risk_assessment_id"),
    )

    well_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wells.id", ondelete="CASCADE"), nullable=False
    )
    risk_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_assessments.id", ondelete="SET NULL"),
    )
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="open", server_default=text("'open'")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    well: Mapped[Well] = relationship(back_populates="alerts")
    risk_assessment: Mapped[RiskAssessment | None] = relationship(back_populates="alerts")
