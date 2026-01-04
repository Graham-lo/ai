from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from app.connectors.binance_um import BinanceUMClient
from app.features.behavior_features import add_behavior_features
from app.features.market_features import WindowConfig, build_kline_features, oi_proxy_for_times
from app.core.config import settings
from app.storage.cache import MarketDataCache, compute_missing_ranges
from app.storage.market_store import MarketDataStore


WINDOWS = [
    WindowConfig(label="30m", window_ms=30 * 60 * 1000, kline_window=30),
    WindowConfig(label="2h", window_ms=2 * 60 * 60 * 1000, kline_window=24),
    WindowConfig(label="24h", window_ms=24 * 60 * 60 * 1000, kline_window=24),
]

INTERVALS = {
    "30m": "1m",
    "2h": "5m",
    "24h": "1h",
}


@dataclass
class AttributionConfig:
    cache_dir: Path
    output_dir: Path


def load_bybit_trade_log(csv_source: str | Path | object) -> pd.DataFrame:
    df = pd.read_csv(csv_source)
    df.columns = [col.strip() for col in df.columns]
    df["Time"] = pd.to_datetime(df["Time"], utc=True, errors="coerce")
    df["time_ms"] = (df["Time"].astype("int64") // 1_000_000).astype("int64")
    df.loc[df["Time"].isna(), "time_ms"] = 0
    df["symbol"] = df["Contract"].astype(str).str.strip()
    df["action_norm"] = df["Action"].astype(str).str.upper()
    df["type_norm"] = df["Type"].astype(str).str.upper()
    df["direction_norm"] = df["Direction"].astype(str).str.upper()
    return df


def build_trade_attribution_table(
    bybit_df: pd.DataFrame,
    client: BinanceUMClient,
    cache: MarketDataCache,
    start_ms: int,
    end_ms: int,
    symbols: list[str],
    market_store: MarketDataStore | None = None,
    fetch_market: bool = True,
) -> pd.DataFrame:
    closes = _extract_closes(bybit_df, start_ms, end_ms, symbols)
    if closes.empty:
        return closes
    funding_df = _extract_funding(bybit_df, start_ms, end_ms, symbols)
    market_features = _load_market_features(
        client,
        cache,
        symbols,
        start_ms,
        end_ms,
        market_store,
        fetch_missing=fetch_market,
    )
    closes = _merge_market_features(closes, market_features, funding_df, cache, symbols, start_ms, end_ms)
    closes = add_behavior_features(closes)
    return closes


def save_trade_attribution(df: pd.DataFrame, output_dir: Path, month_tag: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"trade_attribution_{month_tag}.parquet"
    df.to_parquet(path, index=False)
    return path


def _extract_closes(df: pd.DataFrame, start_ms: int, end_ms: int, symbols: list[str]) -> pd.DataFrame:
    data = df.copy()
    if symbols:
        data = data[data["symbol"].isin(symbols)]
    is_close = data["action_norm"].str.contains("CLOSE", na=False)
    closes = data[is_close].copy()
    if closes.empty:
        closes = data[data["type_norm"].str.contains("TRADE", na=False)].copy()
    closes = closes[(closes["time_ms"] >= start_ms) & (closes["time_ms"] <= end_ms)]
    closes["close_time"] = closes["time_ms"]
    closes["qty"] = pd.to_numeric(closes["Quantity"], errors="coerce").fillna(0)
    closes["price"] = pd.to_numeric(closes["Filled Price"], errors="coerce").fillna(0)
    closes["turnover"] = (closes["qty"] * closes["price"]).fillna(0)
    closes["fee"] = pd.to_numeric(closes["Fee Paid"], errors="coerce").fillna(0).abs()
    closes["pnl_net"] = pd.to_numeric(closes["Change"], errors="coerce").fillna(0)
    closes["direction"] = closes["direction_norm"].map({"BUY": "long", "SELL": "short"}).fillna("unknown")
    open_times, holding_seconds = _match_open_times(data, closes)
    closes["open_time"] = open_times
    closes["holding_seconds"] = holding_seconds
    closes["pnl_gross"] = closes["pnl_net"] + closes["fee"]
    closes["taker_proxy"] = (closes["fee"] > 0).astype(int)
    closes["fee_bps"] = closes.apply(_fee_bps, axis=1)
    closes["close_fee_bps"] = closes["fee_bps"]
    return closes[
        [
            "close_time",
            "symbol",
            "direction",
            "open_time",
            "holding_seconds",
            "qty",
            "price",
            "turnover",
            "fee",
            "fee_bps",
            "close_fee_bps",
            "pnl_gross",
            "pnl_net",
            "taker_proxy",
        ]
    ]


def _extract_funding(df: pd.DataFrame, start_ms: int, end_ms: int, symbols: list[str]) -> pd.DataFrame:
    data = df.copy()
    if symbols:
        data = data[data["symbol"].isin(symbols)]
    is_settlement = data["type_norm"].str.contains("SETTLEMENT", na=False)
    funding = data[is_settlement].copy()
    funding = funding[(funding["time_ms"] >= start_ms) & (funding["time_ms"] <= end_ms)]
    funding["funding"] = pd.to_numeric(funding["Funding"], errors="coerce").fillna(0)
    return funding[["time_ms", "symbol", "funding"]]


def _load_market_features(
    client: BinanceUMClient,
    cache: MarketDataCache,
    symbols: list[str],
    start_ms: int,
    end_ms: int,
    market_store: MarketDataStore | None,
    fetch_missing: bool,
) -> dict[str, dict[str, pd.DataFrame]]:
    features: dict[str, dict[str, pd.DataFrame]] = {}
    for symbol in symbols:
        features[symbol] = {}
        for window in WINDOWS:
            interval = INTERVALS[window.label]
            cached = cache.load("klines", symbol, interval)
            if cached.empty and market_store is not None:
                cached = market_store.load_klines(symbol, interval)
            if fetch_missing:
                for miss_start, miss_end in compute_missing_ranges(cached, start_ms, end_ms, "open_time"):
                    rows = client.get_klines(symbol, interval, miss_start, miss_end)
                    cached = cache.upsert("klines", symbol, interval, rows, time_col="open_time")
                    if market_store is not None:
                        market_store.upsert_klines(rows)
            feat = build_kline_features(cached, window.kline_window, window.label)
            features[symbol][window.label] = feat
            mark_cached = cache.load("mark_klines", symbol, interval)
            if mark_cached.empty and market_store is not None:
                mark_cached = market_store.load_mark_klines(symbol, interval)
            if fetch_missing:
                for miss_start, miss_end in compute_missing_ranges(mark_cached, start_ms, end_ms, "open_time"):
                    rows = client.get_mark_klines(symbol, interval, miss_start, miss_end)
                    mark_cached = cache.upsert("mark_klines", symbol, interval, rows, time_col="open_time")
                    if market_store is not None:
                        market_store.upsert_mark_klines(rows)
        features[symbol]["funding"] = pd.DataFrame()
        if settings.ENABLE_OI_FETCH:
            oi_cached = cache.load("open_interest_hist", symbol, "5m")
            if oi_cached.empty and market_store is not None:
                oi_cached = market_store.load_open_interest(symbol, "5m")
            if fetch_missing:
                for miss_start, miss_end in compute_missing_ranges(oi_cached, start_ms, end_ms, "timestamp"):
                    rows = client.get_open_interest_hist(symbol, "5m", miss_start, miss_end)
                    oi_cached = cache.upsert("open_interest_hist", symbol, "5m", rows, time_col="timestamp")
                    if market_store is not None:
                        market_store.upsert_open_interest(rows)
            features[symbol]["oi"] = oi_cached
        else:
            features[symbol]["oi"] = pd.DataFrame()
    return features


def _merge_market_features(
    closes: pd.DataFrame,
    market_features: dict[str, dict[str, pd.DataFrame]],
    funding_df: pd.DataFrame,
    cache: MarketDataCache,
    symbols: list[str],
    start_ms: int,
    end_ms: int,
) -> pd.DataFrame:
    merged_rows = []
    for symbol in symbols:
        symbol_closes = closes[closes["symbol"] == symbol].sort_values("close_time").copy()
        if symbol_closes.empty:
            continue
        for window in WINDOWS:
            feature_df = market_features[symbol][window.label]
            if not feature_df.empty:
                feature_df = feature_df.sort_values("open_time")
                symbol_closes = pd.merge_asof(
                    symbol_closes,
                    feature_df,
                    left_on="close_time",
                    right_on="open_time",
                    direction="backward",
                    suffixes=("", "_market"),
                )
                if "open_time_market" in symbol_closes.columns:
                    symbol_closes = symbol_closes.drop(columns=["open_time_market"])
            else:
                symbol_closes[f"trend_score_{window.label}"] = 0.0
                symbol_closes[f"vol_bucket_{window.label}"] = "na"
        for window in WINDOWS:
            symbol_closes[f"funding_bucket_{window.label}"] = "na"
        oi_local = market_features[symbol]["oi"]
        for window in WINDOWS:
            oi_buckets = oi_proxy_for_times(oi_local, symbol_closes["close_time"], window.window_ms, window.label)
            symbol_closes[oi_buckets.name] = oi_buckets.values
        symbol_closes["trend_bucket"] = symbol_closes["trend_score_24h"].apply(_trend_bucket)
        symbol_closes["vol_bucket"] = symbol_closes["vol_bucket_24h"]
        symbol_closes["funding_bucket"] = "na"
        symbol_closes["oi_quadrant"] = symbol_closes.apply(_oi_quadrant, axis=1)
        symbol_closes["funding"] = 0.0
        if not funding_df.empty:
            funding_symbol = funding_df[funding_df["symbol"] == symbol].sort_values("time_ms")
            prev_time = start_ms
            for idx, row in symbol_closes.iterrows():
                close_time = row["close_time"]
                window_rows = funding_symbol[(funding_symbol["time_ms"] > prev_time) & (funding_symbol["time_ms"] <= close_time)]
                if not window_rows.empty:
                    symbol_closes.at[idx, "funding"] = float(window_rows["funding"].sum())
                prev_time = close_time
        symbol_closes["pnl_gross"] = symbol_closes["pnl_net"] + symbol_closes["fee"] + symbol_closes["funding"]
        merged_rows.append(symbol_closes)
    if not merged_rows:
        return closes
    merged = pd.concat(merged_rows, ignore_index=True)
    return merged


def _fee_bps(row: pd.Series) -> float:
    turnover = row.get("turnover", 0) or 0
    fee = row.get("fee", 0) or 0
    if turnover <= 0:
        return 0.0
    return float(fee / turnover * 1e4)


def _trend_bucket(score: float) -> str:
    if score >= 0.2:
        return "trend"
    if score <= -0.2:
        return "trend"
    return "range"


def _oi_quadrant(row: pd.Series) -> str:
    oi_proxy = row.get("oi_proxy_24h", "na")
    score = row.get("trend_score_24h", 0.0) or 0.0
    if oi_proxy == "na":
        return "na"
    price_dir = "up" if score > 0.05 else "down" if score < -0.05 else "flat"
    return f"oi_{oi_proxy}_price_{price_dir}"


def _match_open_times(data: pd.DataFrame, closes: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    opens = data[data["action_norm"].str.contains("OPEN", na=False)].copy()
    opens = opens.sort_values("time_ms")
    stacks: dict[tuple[str, str], list[int]] = {}
    for _, row in opens.iterrows():
        key = (row["symbol"], row["direction_norm"])
        stacks.setdefault(key, []).append(int(row["time_ms"]))
    open_time_map: dict[int, int | None] = {}
    holding_map: dict[int, int | None] = {}
    for idx, row in closes.sort_values("time_ms").iterrows():
        key = (row["symbol"], row["direction_norm"])
        if stacks.get(key):
            open_time = stacks[key].pop()
            open_time_map[idx] = open_time
            holding_map[idx] = int((row["time_ms"] - open_time) / 1000)
        else:
            open_time_map[idx] = None
            holding_map[idx] = None
    open_series = pd.Series(open_time_map).reindex(closes.index)
    holding_series = pd.Series(holding_map).reindex(closes.index)
    return open_series, holding_series


def to_month_tag(dt: datetime) -> str:
    return dt.strftime("%Y%m")


def to_utc_ms(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)
