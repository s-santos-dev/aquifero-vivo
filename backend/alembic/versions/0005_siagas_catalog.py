"""Public registry provenance; unknown operational status is nullable."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("wells", sa.Column("source_record_id", sa.String(64)))
    op.add_column("wells", sa.Column("source_metadata", JSONB))
    op.create_unique_constraint("uq_wells_source_record", "wells", ["source", "source_record_id"])
    op.alter_column("wells", "is_active", existing_type=sa.Boolean(), nullable=True)


def downgrade():
    # Refuse a lossy downgrade rather than invent status for public records.
    op.alter_column("wells", "is_active", existing_type=sa.Boolean(), nullable=False)
    op.drop_constraint("uq_wells_source_record", "wells", type_="unique")
    op.drop_column("wells", "source_metadata")
    op.drop_column("wells", "source_record_id")
