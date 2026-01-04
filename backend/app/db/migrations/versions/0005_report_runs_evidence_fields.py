"""add facts/evidence fields to report_runs

Revision ID: 0005_report_runs_evidence_fields
Revises: 0004_market_data_tables
Create Date: 2026-01-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0005_report_runs_evidence_fields"
down_revision = "0004_market_data_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("report_runs", sa.Column("facts_path", sa.Text(), nullable=True))
    op.add_column("report_runs", sa.Column("evidence_path", sa.Text(), nullable=True))
    op.add_column("report_runs", sa.Column("evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("report_runs", sa.Column("schema_version", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("report_runs", "schema_version")
    op.drop_column("report_runs", "evidence_json")
    op.drop_column("report_runs", "evidence_path")
    op.drop_column("report_runs", "facts_path")
