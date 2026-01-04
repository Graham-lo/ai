import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exchange_id: Mapped[str] = mapped_column(String(50), index=True)
    label: Mapped[str] = mapped_column(String(100))
    account_types: Mapped[list[str]] = mapped_column(JSONB)
    credentials_encrypted: Mapped[bytes] = mapped_column(BYTEA)
    options: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Fill(Base):
    __tablename__ = "fills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ts_utc: Mapped[datetime] = mapped_column(DateTime, index=True)
    exchange_id: Mapped[str] = mapped_column(String(50), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"), index=True)
    account_type: Mapped[str] = mapped_column(String(30))
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    side: Mapped[str] = mapped_column(String(10))
    price: Mapped[float] = mapped_column(Float)
    qty: Mapped[float] = mapped_column(Float)
    notional: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float)
    fee_asset: Mapped[str] = mapped_column(String(20))
    maker_taker: Mapped[str | None] = mapped_column(String(10))
    order_id: Mapped[str | None] = mapped_column(String(100))
    trade_id: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        UniqueConstraint("exchange_id", "account_id", "trade_id", name="uq_fills_trade"),
        UniqueConstraint(
            "exchange_id",
            "account_id",
            "ts_utc",
            "symbol",
            "side",
            "price",
            "qty",
            name="uq_fills_fallback",
        ),
    )


class Cashflow(Base):
    __tablename__ = "cashflows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ts_utc: Mapped[datetime] = mapped_column(DateTime, index=True)
    exchange_id: Mapped[str] = mapped_column(String(50), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"), index=True)
    account_type: Mapped[str] = mapped_column(String(30))
    type: Mapped[str] = mapped_column(String(30), index=True)
    amount: Mapped[float] = mapped_column(Float)
    asset: Mapped[str] = mapped_column(String(20))
    symbol: Mapped[str | None] = mapped_column(String(50))
    flow_id: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        UniqueConstraint("exchange_id", "account_id", "flow_id", name="uq_cashflows_flow"),
        UniqueConstraint(
            "exchange_id",
            "account_id",
            "ts_utc",
            "type",
            "amount",
            "asset",
            "symbol",
            name="uq_cashflows_fallback",
        ),
    )


class ReportRun(Base):
    __tablename__ = "report_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_scope: Mapped[dict] = mapped_column(JSONB)
    start: Mapped[datetime | None] = mapped_column(DateTime)
    end: Mapped[datetime | None] = mapped_column(DateTime)
    preset: Mapped[str | None] = mapped_column(String(30))
    net_mode: Mapped[str] = mapped_column(String(30))
    summary_json: Mapped[dict] = mapped_column(JSONB)
    anomalies_json: Mapped[list] = mapped_column(JSONB)
    report_md: Mapped[str] = mapped_column(Text)
    report_md_llm: Mapped[str | None] = mapped_column(Text)
    chart_spec_json: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str | None] = mapped_column(String(50))
    llm_generated_at: Mapped[datetime | None] = mapped_column(DateTime)
    llm_status: Mapped[str | None] = mapped_column(String(20))
    llm_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_scope: Mapped[dict] = mapped_column(JSONB)
    start: Mapped[datetime | None] = mapped_column(DateTime)
    end: Mapped[datetime | None] = mapped_column(DateTime)
    preset: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    counts: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
