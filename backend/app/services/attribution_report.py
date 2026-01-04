from __future__ import annotations

from datetime import datetime, timedelta
from io import StringIO

import pandas as pd
from sqlalchemy.orm import Session

from app.attribution.joiner import load_bybit_trade_log
from app.db.models import BybitTradeLog, Cashflow, Fill


def _build_bybit_df_from_db(
    db: Session,
    account_ids: list[str] | None,
    exchange_id: str | None,
    start: datetime,
    end: datetime,
    symbols: list[str],
) -> tuple[pd.DataFrame, bool]:
    logs_query = db.query(BybitTradeLog)
    if account_ids:
        logs_query = logs_query.filter(BybitTradeLog.account_id.in_(account_ids))
    if exchange_id:
        logs_query = logs_query.filter(BybitTradeLog.exchange_id == exchange_id)
    logs_query = logs_query.filter(BybitTradeLog.ts_utc >= start, BybitTradeLog.ts_utc <= end)
    if symbols:
        logs_query = logs_query.filter(BybitTradeLog.contract.in_(symbols))
    logs = logs_query.all()
    if logs:
        rows = []
        for log in logs:
            rows.append(
                {
                    "Currency": log.currency or "USDT",
                    "Contract": log.contract or "",
                    "Type": log.type or "",
                    "Direction": log.direction or "",
                    "Quantity": log.quantity or "",
                    "Position": log.position or "",
                    "Filled Price": log.filled_price or "",
                    "Funding": log.funding or "",
                    "Fee Paid": log.fee_paid or "",
                    "Cash Flow": log.cash_flow or "",
                    "Change": log.change or "",
                    "Wallet Balance": log.wallet_balance or "",
                    "Action": log.action or "",
                    "OrderId": log.order_id or "",
                    "TradeId": log.trade_id or "",
                    "Time": log.ts_utc.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                }
            )
        df = pd.DataFrame(rows)
        realized_present = pd.to_numeric(df.get("Change"), errors="coerce").fillna(0).ne(0).any()
        return load_bybit_trade_log(StringIO(df.to_csv(index=False))), realized_present

    fills_query = db.query(Fill)
    cash_query = db.query(Cashflow)
    if account_ids:
        fills_query = fills_query.filter(Fill.account_id.in_(account_ids))
        cash_query = cash_query.filter(Cashflow.account_id.in_(account_ids))
    if exchange_id:
        fills_query = fills_query.filter(Fill.exchange_id == exchange_id)
        cash_query = cash_query.filter(Cashflow.exchange_id == exchange_id)
    fills_query = fills_query.filter(Fill.ts_utc >= start, Fill.ts_utc <= end)
    cash_query = cash_query.filter(Cashflow.ts_utc >= start, Cashflow.ts_utc <= end)
    if symbols:
        fills_query = fills_query.filter(Fill.symbol.in_(symbols))
        cash_query = cash_query.filter(Cashflow.symbol.in_(symbols))
    fills = fills_query.all()
    cashflows = cash_query.all()

    rows: list[dict] = []
    realized = [cf for cf in cashflows if cf.type == "realized_pnl"]
    realized_present = len(realized) > 0
    realized_df = pd.DataFrame(
        [
            {
                "symbol": cf.symbol,
                "time": cf.ts_utc,
                "amount": float(cf.amount),
            }
            for cf in realized
            if cf.symbol
        ]
    )
    for fill in fills:
        rows.append(
            {
                "Currency": fill.fee_asset or "USDT",
                "Contract": fill.symbol,
                "Type": "TRADE",
                "Direction": (fill.side or "").upper(),
                "Quantity": str(fill.qty),
                "Position": "--",
                "Filled Price": str(fill.price),
                "Funding": "0",
                "Fee Paid": str(-abs(fill.fee)),
                "Cash Flow": "--",
                "Change": "0",
                "Wallet Balance": "--",
                "Action": "CLOSE",
                "OrderId": fill.order_id or "--",
                "TradeId": fill.trade_id or "--",
                "Time": fill.ts_utc.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            }
        )
    for cf in cashflows:
        if cf.type != "funding":
            continue
        rows.append(
            {
                "Currency": cf.asset or "USDT",
                "Contract": cf.symbol or "--",
                "Type": "SETTLEMENT",
                "Direction": "BUY" if cf.amount >= 0 else "SELL",
                "Quantity": "--",
                "Position": "--",
                "Filled Price": "--",
                "Funding": str(cf.amount),
                "Fee Paid": "0",
                "Cash Flow": str(cf.amount),
                "Change": str(cf.amount),
                "Wallet Balance": "--",
                "Action": "SETTLEMENT",
                "OrderId": cf.flow_id or "--",
                "TradeId": cf.flow_id or "--",
                "Time": cf.ts_utc.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            }
        )
    df = pd.DataFrame(rows)
    if realized_present and not realized_df.empty:
        realized_df["time"] = pd.to_datetime(realized_df["time"], utc=True)
        for idx, row in df.iterrows():
            if row["Type"] != "TRADE":
                continue
            symbol = row["Contract"]
            ts = pd.to_datetime(row["Time"], utc=True)
            window = realized_df[
                (realized_df["symbol"] == symbol)
                & (realized_df["time"] >= ts - timedelta(minutes=5))
                & (realized_df["time"] <= ts + timedelta(minutes=5))
            ]
            if not window.empty:
                df.at[idx, "Change"] = str(float(window["amount"].sum()))
    return load_bybit_trade_log(StringIO(df.to_csv(index=False))), realized_present
