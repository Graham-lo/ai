from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


@dataclass
class CachePaths:
    root: Path

    def subdir(self, name: str) -> Path:
        path = self.root / name
        path.mkdir(parents=True, exist_ok=True)
        return path


class MarketDataCache:
    def __init__(self, root: str | Path) -> None:
        self.paths = CachePaths(Path(root))
        self.paths.root.mkdir(parents=True, exist_ok=True)

    def load(self, data_type: str, symbol: str, interval: str | None = None) -> pd.DataFrame:
        path = self._path(data_type, symbol, interval)
        if not path.exists():
            return pd.DataFrame()
        return pd.read_parquet(path)

    def save(self, data_type: str, symbol: str, interval: str | None, df: pd.DataFrame) -> None:
        path = self._path(data_type, symbol, interval)
        df.to_parquet(path, index=False)

    def upsert(
        self,
        data_type: str,
        symbol: str,
        interval: str | None,
        rows: Iterable[dict],
        time_col: str,
        dedupe_cols: list[str] | None = None,
    ) -> pd.DataFrame:
        incoming = pd.DataFrame(list(rows))
        if incoming.empty:
            return self.load(data_type, symbol, interval)
        existing = self.load(data_type, symbol, interval)
        if existing.empty:
            combined = incoming
        else:
            combined = pd.concat([existing, incoming], ignore_index=True)
        dedupe = dedupe_cols or [time_col, "symbol"]
        combined = combined.drop_duplicates(subset=dedupe, keep="last")
        combined = combined.sort_values(time_col)
        self.save(data_type, symbol, interval, combined)
        return combined

    def _path(self, data_type: str, symbol: str, interval: str | None) -> Path:
        safe_symbol = symbol.upper()
        suffix = f"_{interval}" if interval else ""
        file_name = f"{safe_symbol}{suffix}.parquet"
        return self.paths.subdir(data_type) / file_name


def compute_missing_ranges(
    df: pd.DataFrame, start_ms: int, end_ms: int, time_col: str
) -> list[tuple[int, int]]:
    if df.empty:
        return [(start_ms, end_ms)]
    min_ts = int(df[time_col].min())
    max_ts = int(df[time_col].max())
    ranges: list[tuple[int, int]] = []
    if start_ms < min_ts:
        ranges.append((start_ms, min(end_ms, min_ts - 1)))
    if end_ms > max_ts:
        ranges.append((max_ts + 1, end_ms))
    return ranges
