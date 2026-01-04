"""init

Revision ID: 0001_init
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("exchange_id", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("account_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("credentials_encrypted", postgresql.BYTEA(), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_accounts_exchange_id", "accounts", ["exchange_id"], unique=False)

    op.create_table(
        "fills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ts_utc", sa.DateTime(), nullable=False),
        sa.Column("exchange_id", sa.String(length=50), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_type", sa.String(length=30), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("notional", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False),
        sa.Column("fee_asset", sa.String(length=20), nullable=False),
        sa.Column("maker_taker", sa.String(length=10), nullable=True),
        sa.Column("order_id", sa.String(length=100), nullable=True),
        sa.Column("trade_id", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_fills_account_id", "fills", ["account_id"], unique=False)
    op.create_index("ix_fills_symbol", "fills", ["symbol"], unique=False)
    op.create_index("ix_fills_ts_utc", "fills", ["ts_utc"], unique=False)
    op.create_unique_constraint("uq_fills_trade", "fills", ["exchange_id", "account_id", "trade_id"])
    op.create_unique_constraint(
        "uq_fills_fallback",
        "fills",
        ["exchange_id", "account_id", "ts_utc", "symbol", "side", "price", "qty"],
    )

    op.create_table(
        "cashflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ts_utc", sa.DateTime(), nullable=False),
        sa.Column("exchange_id", sa.String(length=50), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_type", sa.String(length=30), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("asset", sa.String(length=20), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=True),
        sa.Column("flow_id", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_cashflows_account_id", "cashflows", ["account_id"], unique=False)
    op.create_index("ix_cashflows_type", "cashflows", ["type"], unique=False)
    op.create_index("ix_cashflows_ts_utc", "cashflows", ["ts_utc"], unique=False)
    op.create_unique_constraint("uq_cashflows_flow", "cashflows", ["exchange_id", "account_id", "flow_id"])
    op.create_unique_constraint(
        "uq_cashflows_fallback",
        "cashflows",
        ["exchange_id", "account_id", "ts_utc", "type", "amount", "asset", "symbol"],
    )

    op.create_table(
        "report_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("start", sa.DateTime(), nullable=True),
        sa.Column("end", sa.DateTime(), nullable=True),
        sa.Column("preset", sa.String(length=30), nullable=True),
        sa.Column("net_mode", sa.String(length=30), nullable=False),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("anomalies_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("report_md", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("start", sa.DateTime(), nullable=True),
        sa.Column("end", sa.DateTime(), nullable=True),
        sa.Column("preset", sa.String(length=30), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("counts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sync_runs")
    op.drop_table("report_runs")
    op.drop_table("cashflows")
    op.drop_table("fills")
    op.drop_table("accounts")
