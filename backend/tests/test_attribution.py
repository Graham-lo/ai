from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from app.attribution.joiner import build_trade_attribution_table
from app.connectors.binance_um import BinanceUMClient
from app.storage.cache import MarketDataCache


def _dummy_client() -> BinanceUMClient:
    client = BinanceUMClient()

    def empty_list(*_args, **_kwargs):
        return []

    client.get_klines = empty_list  # type: ignore[assignment]
    client.get_funding_rates = empty_list  # type: ignore[assignment]
    client.get_open_interest_hist = empty_list  # type: ignore[assignment]
    return client


def test_attribution_row_count(tmp_path):
    rows = [
        {
            "Currency": "USDT",
            "Contract": "ETHUSDT",
            "Type": "TRADE",
            "Direction": "BUY",
            "Quantity": "1",
            "Position": "1",
            "Filled Price": "2000",
            "Funding": "0",
            "Fee Paid": "-1",
            "Cash Flow": "0",
            "Change": "5",
            "Wallet Balance": "0",
            "Action": "CLOSE",
            "OrderId": "1",
            "TradeId": "1",
            "Time": "2026-01-03 16:00:00.000",
        },
        {
            "Currency": "USDT",
            "Contract": "ETHUSDT",
            "Type": "TRADE",
            "Direction": "SELL",
            "Quantity": "1",
            "Position": "1",
            "Filled Price": "2100",
            "Funding": "0",
            "Fee Paid": "-1",
            "Cash Flow": "0",
            "Change": "4",
            "Wallet Balance": "0",
            "Action": "CLOSE",
            "OrderId": "2",
            "TradeId": "2",
            "Time": "2026-01-04 16:00:00.000",
        },
    ]
    df = pd.DataFrame(rows)
    df["Time"] = pd.to_datetime(df["Time"], utc=True)
    df["time_ms"] = (df["Time"].astype("int64") // 1_000_000).astype("int64")
    df["symbol"] = df["Contract"]
    df["action_norm"] = df["Action"].str.upper()
    df["type_norm"] = df["Type"].str.upper()
    df["direction_norm"] = df["Direction"].str.upper()

    client = _dummy_client()
    cache = MarketDataCache(tmp_path)
    start_ms = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    end_ms = int(datetime(2026, 1, 5, tzinfo=timezone.utc).timestamp() * 1000)
    result = build_trade_attribution_table(df, client, cache, start_ms, end_ms, ["ETHUSDT"])
    assert len(result) == 2


def test_funding_not_double_counted(tmp_path):
    rows = [
        {
            "Currency": "USDT",
            "Contract": "ETHUSDT",
            "Type": "SETTLEMENT",
            "Direction": "BUY",
            "Quantity": "0",
            "Position": "0",
            "Filled Price": "0",
            "Funding": "-2",
            "Fee Paid": "0",
            "Cash Flow": "0",
            "Change": "-2",
            "Wallet Balance": "0",
            "Action": "SETTLEMENT",
            "OrderId": "s1",
            "TradeId": "s1",
            "Time": "2026-01-02 00:00:00.000",
        },
        {
            "Currency": "USDT",
            "Contract": "ETHUSDT",
            "Type": "SETTLEMENT",
            "Direction": "BUY",
            "Quantity": "0",
            "Position": "0",
            "Filled Price": "0",
            "Funding": "-3",
            "Fee Paid": "0",
            "Cash Flow": "0",
            "Change": "-3",
            "Wallet Balance": "0",
            "Action": "SETTLEMENT",
            "OrderId": "s2",
            "TradeId": "s2",
            "Time": "2026-01-03 00:00:00.000",
        },
        {
            "Currency": "USDT",
            "Contract": "ETHUSDT",
            "Type": "TRADE",
            "Direction": "BUY",
            "Quantity": "1",
            "Position": "1",
            "Filled Price": "2000",
            "Funding": "0",
            "Fee Paid": "-1",
            "Cash Flow": "0",
            "Change": "5",
            "Wallet Balance": "0",
            "Action": "CLOSE",
            "OrderId": "1",
            "TradeId": "1",
            "Time": "2026-01-02 16:00:00.000",
        },
        {
            "Currency": "USDT",
            "Contract": "ETHUSDT",
            "Type": "TRADE",
            "Direction": "SELL",
            "Quantity": "1",
            "Position": "1",
            "Filled Price": "2100",
            "Funding": "0",
            "Fee Paid": "-1",
            "Cash Flow": "0",
            "Change": "4",
            "Wallet Balance": "0",
            "Action": "CLOSE",
            "OrderId": "2",
            "TradeId": "2",
            "Time": "2026-01-03 16:00:00.000",
        },
    ]
    df = pd.DataFrame(rows)
    df["Time"] = pd.to_datetime(df["Time"], utc=True)
    df["time_ms"] = (df["Time"].astype("int64") // 1_000_000).astype("int64")
    df["symbol"] = df["Contract"]
    df["action_norm"] = df["Action"].str.upper()
    df["type_norm"] = df["Type"].str.upper()
    df["direction_norm"] = df["Direction"].str.upper()

    client = _dummy_client()
    cache = MarketDataCache(tmp_path)
    start_ms = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    end_ms = int(datetime(2026, 1, 5, tzinfo=timezone.utc).timestamp() * 1000)
    result = build_trade_attribution_table(df, client, cache, start_ms, end_ms, ["ETHUSDT"])
    assert abs(result["funding"].sum() + 5.0) < 1e-6
