"""Public climate observations are independent of operational rainfall/sectors."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class ClimateStation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "climate_stations"
    __table_args__ = (
        UniqueConstraint("source", "official_code", name="uq_climate_station_identity"),
        CheckConstraint("source = 'INMET' AND observation_type = 'STATION_OBSERVATION'", name="ck_climate_station_origin"),
        Index("ix_climate_station_location", "location", postgresql_using="gist"),
    )
    official_code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    observation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    location: Mapped[object] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False), nullable=False)
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False)


class RainfallObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rainfall_observations"
    __table_args__ = (
        UniqueConstraint("station_id", "measured_at", name="uq_rainfall_observation_interval"),
        Index("ix_rainfall_observation_station_time", "station_id", "measured_at"),
        CheckConstraint("source = 'INMET' AND unit = 'mm'", name="ck_rainfall_observation_origin"),
        CheckConstraint("(availability = 'OBSERVED' AND value_mm IS NOT NULL AND value_mm >= 0 AND value_mm < 10000000) OR (availability = 'MISSING' AND value_mm IS NULL)", name="ck_rainfall_observation_value"),
    )
    station_id: Mapped[UUID] = mapped_column(ForeignKey("climate_stations.id", ondelete="RESTRICT"), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value_mm: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    availability: Mapped[str] = mapped_column(String(16), nullable=False)
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False)
