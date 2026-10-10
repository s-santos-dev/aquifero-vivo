"""Reject an OBSERVED row with NULL even under SQL three-valued logic."""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = depends_on = None


def upgrade():
    op.drop_constraint("ck_rainfall_observation_value", "rainfall_observations", type_="check")
    op.create_check_constraint("ck_rainfall_observation_value", "rainfall_observations", "(availability = 'OBSERVED' AND value_mm IS NOT NULL AND value_mm >= 0 AND value_mm < 10000000) OR (availability = 'MISSING' AND value_mm IS NULL)")


def downgrade():
    op.drop_constraint("ck_rainfall_observation_value", "rainfall_observations", type_="check")
    op.create_check_constraint("ck_rainfall_observation_value", "rainfall_observations", "(availability = 'OBSERVED' AND value_mm >= 0 AND value_mm < 10000000) OR (availability = 'MISSING' AND value_mm IS NULL)")
