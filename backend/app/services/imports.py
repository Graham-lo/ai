import csv
from datetime import datetime, timezone
from decimal import Decimal
from io import StringIO
from typing import Iterable

from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import Cashflow, Fill


BYBIT_COLUMNS = [
    "Currency",
    "Contract",
    "Type",
    "Direction",
    "Quantity",
    "Position",
    "Filled Price",
    "Funding",
    "Fee Paid",
    "Cash Flow",
    "Change",
    "Wallet Balance",
    "Action",
    "OrderId",
    "TradeId",
    "Time",
]


def parse_bybit_transaction_log(content: str, account_id, exchange_id: str, account_type: str) -> tuple[list[Fill], list[Cashflow]]:
    fills: list[Fill] = []
    cashflows: list[Cashflow] = []
    for row in _iter_bybit_rows(content):
        row_type = (row.get("Type") or "").upper()
        symbol = (row.get("Contract") or "").strip()
        ts = _parse_time(row.get("Time"))
        currency = (row.get("Currency") or "").strip()
        if row_type == "TRADE":
            qty = _to_decimal(row.get("Quantity"))
            price = _to_decimal(row.get("Filled Price"))
            fee_paid = _to_decimal(row.get("Fee Paid"))
            notional = price * qty
            fills.append(
                Fill(
                    ts_utc=ts,
                    exchange_id=exchange_id,
                    account_id=account_id,
                    account_type=account_type,
                    symbol=symbol,
                    side=_side_from_direction(row.get("Direction")),
                    price=float(price),
                    qty=float(qty),
                    notional=float(notional),
                    fee=float(abs(fee_paid)),
                    fee_asset=currency or "USDT",
                    maker_taker=None,
                    order_id=row.get("OrderId"),
                    trade_id=row.get("TradeId"),
                )
            )
        elif row_type == "SETTLEMENT":
            funding = _to_decimal(row.get("Funding"))
            cashflows.append(
                Cashflow(
                    ts_utc=ts,
                    exchange_id=exchange_id,
                    account_id=account_id,
                    account_type=account_type,
                    type="funding",
                    amount=float(funding),
                    asset=currency or "USDT",
                    symbol=symbol or None,
                    flow_id=row.get("TradeId") or row.get("OrderId"),
                )
            )
    return fills, cashflows


def _iter_bybit_rows(content: str) -> Iterable[dict]:
    reader = csv.DictReader(StringIO(content))
    if reader.fieldnames and "Type" in reader.fieldnames:
        yield from reader
        return
    raw_reader = csv.reader(StringIO(content))
    for row in raw_reader:
        if not row:
            continue
        if len(row) < len(BYBIT_COLUMNS):
            continue
        mapped = dict(zip(BYBIT_COLUMNS, row))
        yield mapped


def upsert_imported_data(db: Session, fills: Iterable[Fill], cashflows: Iterable[Cashflow]) -> dict[str, int]:
    fill_rows = [_fill_row(fill) for fill in fills]
    cash_rows = [_cash_row(cf) for cf in cashflows]
    inserted_fills = _insert_ignore(db, Fill, fill_rows)
    inserted_cashflows = _insert_ignore(db, Cashflow, cash_rows)
    db.commit()
    return {"fills": inserted_fills, "cashflows": inserted_cashflows}


def _parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(tz=timezone.utc)
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(tz=timezone.utc)


def _to_decimal(value: str | None) -> Decimal:
    if value in (None, "", "--"):
        return Decimal("0")
    return Decimal(str(value))


def _side_from_direction(value: str | None) -> str:
    direction = (value or "").upper()
    if direction in ("BUY", "LONG"):
        return "buy"
    if direction in ("SELL", "SHORT"):
        return "sell"
    return "buy"


def _insert_ignore(session: Session, model, rows: list[dict]) -> int:
    if not rows:
        return 0
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        stmt = pg_insert(model).values(rows).on_conflict_do_nothing()
        result = session.execute(stmt)
        return result.rowcount or 0
    stmt = insert(model).values(rows)
    if dialect == "sqlite":
        stmt = stmt.prefix_with("OR IGNORE")
    result = session.execute(stmt)
    return result.rowcount or 0


def _fill_row(fill: Fill) -> dict:
    return {
        "ts_utc": fill.ts_utc,
        "exchange_id": fill.exchange_id,
        "account_id": fill.account_id,
        "account_type": fill.account_type,
        "symbol": fill.symbol,
        "side": fill.side,
        "price": fill.price,
        "qty": fill.qty,
        "notional": fill.notional,
        "fee": fill.fee,
        "fee_asset": fill.fee_asset,
        "maker_taker": fill.maker_taker,
        "order_id": fill.order_id,
        "trade_id": fill.trade_id,
    }


def _cash_row(cf: Cashflow) -> dict:
    return {
        "ts_utc": cf.ts_utc,
        "exchange_id": cf.exchange_id,
        "account_id": cf.account_id,
        "account_type": cf.account_type,
        "type": cf.type,
        "amount": cf.amount,
        "asset": cf.asset,
        "symbol": cf.symbol,
        "flow_id": cf.flow_id,
    }
