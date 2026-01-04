"""add llm fields to report_runs

Revision ID: 0002_report_runs_llm_fields
Revises: 0001_init
Create Date: 2026-01-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "0002_report_runs_llm_fields"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("report_runs", sa.Column("report_md_llm", sa.Text(), nullable=True))
    op.add_column("report_runs", sa.Column("llm_model", sa.String(length=50), nullable=True))
    op.add_column("report_runs", sa.Column("llm_generated_at", sa.DateTime(), nullable=True))
    op.add_column("report_runs", sa.Column("llm_status", sa.String(length=20), nullable=True))
    op.add_column("report_runs", sa.Column("llm_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("report_runs", "llm_error")
    op.drop_column("report_runs", "llm_status")
    op.drop_column("report_runs", "llm_generated_at")
    op.drop_column("report_runs", "llm_model")
    op.drop_column("report_runs", "report_md_llm")
