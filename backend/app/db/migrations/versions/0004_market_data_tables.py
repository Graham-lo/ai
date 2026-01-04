"""add market data tables and bybit trade logs

Revision ID: 0004_market_data_tables
Revises: 0003_report_runs_chart_spec
Create Date: 2026-01-04 18:10:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0004_market_data_tables"
down_revision = "0003_report_runs_chart_spec"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bybit_trade_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exchange_id", sa.String(length=50), nullable=False),
        sa.Column("account_type", sa.String(length=30), nullable=False),
        sa.Column("currency", sa.String(length=20), nullable=False),
        sa.Column("contract", sa.String(length=50), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.String(length=50), nullable=False),
        sa.Column("position", sa.String(length=50), nullable=False),
        sa.Column("filled_price", sa.String(length=50), nullable=False),
        sa.Column("funding", sa.String(length=50), nullable=False),
        sa.Column("fee_paid", sa.String(length=50), nullable=False),
        sa.Column("cash_flow", sa.String(length=50), nullable=False),
        sa.Column("change", sa.String(length=50), nullable=False),
        sa.Column("wallet_balance", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("order_id", sa.String(length=120), nullable=False),
        sa.Column("trade_id", sa.String(length=120), nullable=False),
        sa.Column("ts_utc", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_bybit_trade_logs_account_id", "bybit_trade_logs", ["account_id"])
    op.create_index("ix_bybit_trade_logs_contract", "bybit_trade_logs", ["contract"])
    op.create_index("ix_bybit_trade_logs_exchange_id", "bybit_trade_logs", ["exchange_id"])
    op.create_index("ix_bybit_trade_logs_ts_utc", "bybit_trade_logs", ["ts_utc"])
    op.create_unique_constraint(
        "uq_bybit_trade_log",
        "bybit_trade_logs",
        ["account_id", "trade_id", "ts_utc", "type", "action"],
    )

    op.create_table(
        "market_klines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("interval", sa.String(length=10), nullable=False),
        sa.Column("open_time", sa.BigInteger(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("close_time", sa.BigInteger(), nullable=False),
        sa.Column("quote_volume", sa.Float(), nullable=False),
        sa.Column("trades", sa.BigInteger(), nullable=False),
        sa.Column("taker_buy_base", sa.Float(), nullable=False),
        sa.Column("taker_buy_quote", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_market_klines_symbol", "market_klines", ["symbol"])
    op.create_index("ix_market_klines_interval", "market_klines", ["interval"])
    op.create_index("ix_market_klines_open_time", "market_klines", ["open_time"])
    op.create_unique_constraint(
        "uq_market_klines", "market_klines", ["symbol", "interval", "open_time"]
    )

    op.create_table(
        "market_mark_klines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("interval", sa.String(length=10), nullable=False),
        sa.Column("open_time", sa.BigInteger(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("close_time", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_market_mark_klines_symbol", "market_mark_klines", ["symbol"])
    op.create_index("ix_market_mark_klines_interval", "market_mark_klines", ["interval"])
    op.create_index("ix_market_mark_klines_open_time", "market_mark_klines", ["open_time"])
    op.create_unique_constraint(
        "uq_market_mark_klines", "market_mark_klines", ["symbol", "interval", "open_time"]
    )

    op.create_table(
        "market_funding_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("funding_time", sa.BigInteger(), nullable=False),
        sa.Column("funding_rate", sa.Float(), nullable=False),
        sa.Column("mark_price", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_market_funding_rates_symbol", "market_funding_rates", ["symbol"])
    op.create_index("ix_market_funding_rates_funding_time", "market_funding_rates", ["funding_time"])
    op.create_unique_constraint(
        "uq_market_funding", "market_funding_rates", ["symbol", "funding_time"]
    )

    op.create_table(
        "market_open_interest",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("period", sa.String(length=10), nullable=False),
        sa.Column("timestamp", sa.BigInteger(), nullable=False),
        sa.Column("sum_open_interest", sa.Float(), nullable=False),
        sa.Column("sum_open_interest_value", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_market_open_interest_symbol", "market_open_interest", ["symbol"])
    op.create_index("ix_market_open_interest_period", "market_open_interest", ["period"])
    op.create_index("ix_market_open_interest_timestamp", "market_open_interest", ["timestamp"])
    op.create_unique_constraint(
        "uq_market_oi", "market_open_interest", ["symbol", "period", "timestamp"]
    )


def downgrade() -> None:
    op.drop_table("market_open_interest")
    op.drop_table("market_funding_rates")
    op.drop_table("market_mark_klines")
    op.drop_table("market_klines")
    op.drop_table("bybit_trade_logs")
