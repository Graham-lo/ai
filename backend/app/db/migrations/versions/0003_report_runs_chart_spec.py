"""add chart_spec_json to report_runs

Revision ID: 0003_report_runs_chart_spec
Revises: 0002_report_runs_llm_fields
Create Date: 2026-01-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "0003_report_runs_chart_spec"
down_revision = "0002_report_runs_llm_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("report_runs", sa.Column("chart_spec_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("report_runs", "chart_spec_json")
