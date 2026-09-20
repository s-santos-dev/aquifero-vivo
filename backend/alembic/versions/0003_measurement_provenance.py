"""Adiciona classificação explícita de proveniência às medições."""

import sqlalchemy as sa
from alembic import op


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


TABLES = (
    ("groundwater_measurements", "ck_groundwater_data_classification"),
    ("rainfall_measurements", "ck_rainfall_data_classification"),
    ("operational_measurements", "ck_operational_data_classification"),
)


def upgrade() -> None:
    for table_name, constraint_name in TABLES:
        op.add_column(
            table_name,
            sa.Column(
                "data_classification",
                sa.String(16),
                nullable=True,
            ),
        )
        # Não é possível inferir com segurança a origem de linhas antigas. A
        # migração falha deliberadamente em vez de classificá-las como reais.
        op.execute(
            sa.text(
                f"""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM {table_name} LIMIT 1) THEN
                        RAISE EXCEPTION
                            'classifique explicitamente as linhas existentes de {table_name} antes da migration 0003';
                    END IF;
                END
                $$
                """
            )
        )
        op.create_check_constraint(
            constraint_name,
            table_name,
            "data_classification IN ('REAL', 'PUBLIC', 'SIMULATED')",
        )
        op.alter_column(table_name, "data_classification", nullable=False)


def downgrade() -> None:
    for table_name, constraint_name in reversed(TABLES):
        op.drop_constraint(constraint_name, table_name, type_="check")
        op.drop_column(table_name, "data_classification")
