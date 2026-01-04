import csv
import io
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from app.db.models import Cashflow, Fill


def fills_to_csv(fills: Iterable[Fill]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ts_utc",
        "exchange_id",
        "account_id",
        "account_type",
        "symbol",
        "side",
        "price",
        "qty",
        "notional",
        "fee",
        "fee_asset",
        "maker_taker",
        "order_id",
        "trade_id",
    ])
    for fill in fills:
        writer.writerow([
            fill.ts_utc,
            fill.exchange_id,
            fill.account_id,
            fill.account_type,
            fill.symbol,
            fill.side,
            fill.price,
            fill.qty,
            fill.notional,
            fill.fee,
            fill.fee_asset,
            fill.maker_taker,
            fill.order_id,
            fill.trade_id,
        ])
    return output.getvalue()


def cashflows_to_csv(cashflows: Iterable[Cashflow]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ts_utc",
        "exchange_id",
        "account_id",
        "account_type",
        "type",
        "amount",
        "asset",
        "symbol",
        "flow_id",
    ])
    for cf in cashflows:
        writer.writerow([
            cf.ts_utc,
            cf.exchange_id,
            cf.account_id,
            cf.account_type,
            cf.type,
            cf.amount,
            cf.asset,
            cf.symbol,
            cf.flow_id,
        ])
    return output.getvalue()


def bybit_transaction_log_entries(fills: Iterable[Fill], cashflows: Iterable[Cashflow]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for fill in fills:
        rows.append(
            {
                "Currency": fill.fee_asset or "--",
                "Contract": fill.symbol or "--",
                "Type": "TRADE",
                "Direction": (fill.side or "--").upper(),
                "Quantity": _fmt_number(fill.qty),
                "Position": "--",
                "Filled Price": _fmt_number(fill.price),
                "Funding": _fmt_number(0),
                "Fee Paid": _fmt_number(-abs(_to_decimal(fill.fee))),
                "Cash Flow": "--",
                "Change": "--",
                "Wallet Balance": "--",
                "Action": "TRADE",
                "OrderId": fill.order_id or "--",
                "TradeId": fill.trade_id or "--",
                "Time": _fmt_time(fill.ts_utc),
            }
        )
    for cf in cashflows:
        if cf.type != "funding":
            continue
        rows.append(
            {
                "Currency": cf.asset or "--",
                "Contract": cf.symbol or "--",
                "Type": "SETTLEMENT",
                "Direction": "BUY" if _to_decimal(cf.amount) >= 0 else "SELL",
                "Quantity": "--",
                "Position": "--",
                "Filled Price": "--",
                "Funding": _fmt_number(cf.amount),
                "Fee Paid": _fmt_number(0),
                "Cash Flow": _fmt_number(cf.amount),
                "Change": _fmt_number(cf.amount),
                "Wallet Balance": "--",
                "Action": "SETTLEMENT",
                "OrderId": cf.flow_id or "--",
                "TradeId": cf.flow_id or "--",
                "Time": _fmt_time(cf.ts_utc),
            }
        )
    rows.sort(key=lambda row: row["Time"], reverse=True)
    return rows


def bybit_transaction_log_csv(fills: Iterable[Fill], cashflows: Iterable[Cashflow]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    header = [
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
    writer.writerow(header)
    for row in bybit_transaction_log_entries(fills, cashflows):
        writer.writerow([row[col] for col in header])
    return output.getvalue()


def bybit_transaction_log_csv_from_rows(rows: list[dict[str, str]]) -> str:
    header = [
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
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    for row in rows:
        writer.writerow([row.get(col, "--") for col in header])
    return output.getvalue()


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _fmt_number(value) -> str:
    if value == "--":
        return value
    dec = _to_decimal(value)
    return format(dec, "f")


def _fmt_time(value: datetime) -> str:
    if value is None:
        return "--"
    ts = value.strftime("%Y-%m-%d %H:%M:%S.%f")
    return ts[:-3]
