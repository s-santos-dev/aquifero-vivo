"""Preserve original RIMAS observations without assigning static-level semantics."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = depends_on = None


def upgrade():
    op.create_table("groundwater_observations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("well_id", UUID(as_uuid=True), sa.ForeignKey("wells.id", ondelete="CASCADE"), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("observed_level_m", sa.Numeric(12, 4), nullable=False),
        sa.Column("unit", sa.String(8), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("data_classification", sa.String(16), nullable=False),
        sa.Column("dataset", sa.String(40), nullable=False),
        sa.Column("station_code", sa.String(64), nullable=False),
        sa.Column("source_record_id", sa.String(64), nullable=False),
        sa.Column("pumping", sa.String(1)),
        sa.Column("source_metadata", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source", "dataset", "station_code", "source_record_id", name="uq_observation_source_record"),
        sa.CheckConstraint("source = 'RIMAS' AND data_classification = 'PUBLIC'", name="ck_observation_origin"),
        sa.CheckConstraint("unit = 'm'", name="ck_observation_unit"))
    op.create_index("ix_observation_well_measured_at", "groundwater_observations", ["well_id", "measured_at"])


def downgrade():
    op.drop_table("groundwater_observations")
