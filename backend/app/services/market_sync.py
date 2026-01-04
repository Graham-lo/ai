from __future__ import annotations

from datetime import datetime

from app.attribution.joiner import INTERVALS, WINDOWS
from app.connectors.binance_um import BinanceUMClient
from app.core.config import settings
from app.schemas.report import ReportRequest
from app.storage.cache import MarketDataCache, compute_missing_ranges
from app.storage.market_store import MarketDataStore
from app.services.report_service import resolve_range


def sync_market_data(
    market_store: MarketDataStore,
    cache: MarketDataCache,
    symbols: list[str],
    start: datetime,
    end: datetime,
) -> None:
    client = BinanceUMClient()
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    for symbol in symbols:
        for window in WINDOWS:
            interval = INTERVALS[window.label]
            cached = cache.load("klines", symbol, interval)
            if cached.empty:
                cached = market_store.load_klines(symbol, interval)
            for miss_start, miss_end in compute_missing_ranges(cached, start_ms, end_ms, "open_time"):
                rows = client.get_klines(symbol, interval, miss_start, miss_end)
                cached = cache.upsert("klines", symbol, interval, rows, time_col="open_time")
                market_store.upsert_klines(rows)
            mark_cached = cache.load("mark_klines", symbol, interval)
            if mark_cached.empty:
                mark_cached = market_store.load_mark_klines(symbol, interval)
            for miss_start, miss_end in compute_missing_ranges(mark_cached, start_ms, end_ms, "open_time"):
                rows = client.get_mark_klines(symbol, interval, miss_start, miss_end)
                mark_cached = cache.upsert("mark_klines", symbol, interval, rows, time_col="open_time")
                market_store.upsert_mark_klines(rows)
        funding_cached = cache.load("funding", symbol, None)
        if funding_cached.empty:
            funding_cached = market_store.load_funding(symbol)
        for miss_start, miss_end in compute_missing_ranges(funding_cached, start_ms, end_ms, "funding_time"):
            rows = client.get_funding_rates(symbol, miss_start, miss_end)
            funding_cached = cache.upsert("funding", symbol, None, rows, time_col="funding_time")
            market_store.upsert_funding(rows)
        if settings.ENABLE_OI_FETCH:
            oi_cached = cache.load("open_interest_hist", symbol, "5m")
            if oi_cached.empty:
                oi_cached = market_store.load_open_interest(symbol, "5m")
            for miss_start, miss_end in compute_missing_ranges(oi_cached, start_ms, end_ms, "timestamp"):
                rows = client.get_open_interest_hist(symbol, "5m", miss_start, miss_end)
                oi_cached = cache.upsert("open_interest_hist", symbol, "5m", rows, time_col="timestamp")
                market_store.upsert_open_interest(rows)


def resolve_market_sync_range() -> tuple[datetime | None, datetime | None]:
    payload = ReportRequest(preset=settings.MARKET_SYNC_PRESET)
    return resolve_range(payload)


def parse_market_sync_symbols() -> list[str]:
    raw = settings.MARKET_SYNC_SYMBOLS.strip()
    if not raw:
        return []
    return [item.strip().upper() for item in raw.split(",") if item.strip()]
