"""Completa contratos de origem e séries operacionais do MVP."""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

CATALOGS = ("wells", "service_sectors", "well_sectors")


def upgrade():
    for table in CATALOGS:
        op.add_column(table, sa.Column("source", sa.String(80)))
        op.add_column(table, sa.Column("data_classification", sa.String(16), nullable=False, server_default="UNKNOWN"))
    op.add_column("groundwater_measurements", sa.Column("dynamic_level_m", sa.Numeric(10, 3)))
    op.create_check_constraint("ck_groundwater_dynamic", "groundwater_measurements", "dynamic_level_m IS NULL OR dynamic_level_m >= water_level_m")
    op.add_column("operational_measurements", sa.Column("daily_demand_m3", sa.Numeric(14, 3)))
    op.add_column("operational_measurements", sa.Column("utilization", sa.Numeric(14, 5)))
    op.add_column("operational_measurements", sa.Column("operational_failure", sa.Boolean()))
    op.create_check_constraint("ck_operational_demand", "operational_measurements", "daily_demand_m3 IS NULL OR daily_demand_m3 >= 0")
    op.create_check_constraint("ck_operational_utilization", "operational_measurements", "utilization IS NULL OR utilization >= 0")


def downgrade():
    for name in ("ck_operational_demand", "ck_operational_utilization"):
        op.drop_constraint(name, "operational_measurements", type_="check")
    for name in ("operational_failure", "utilization", "daily_demand_m3"):
        op.drop_column("operational_measurements", name)
    op.drop_constraint("ck_groundwater_dynamic", "groundwater_measurements", type_="check")
    op.drop_column("groundwater_measurements", "dynamic_level_m")
    for table in reversed(CATALOGS):
        op.drop_column(table, "data_classification")
        op.drop_column(table, "source")
