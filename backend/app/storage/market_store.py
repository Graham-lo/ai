from __future__ import annotations

from typing import Iterable

import pandas as pd
from sqlalchemy import insert as sa_insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import MarketFundingRate, MarketKline, MarketMarkKline, MarketOpenInterest


class MarketDataStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def load_klines(self, symbol: str, interval: str) -> pd.DataFrame:
        rows = self.db.execute(
            select(MarketKline).where(
                MarketKline.symbol == symbol,
                MarketKline.interval == interval,
            )
        ).scalars()
        return _to_df(rows, time_col="open_time")

    def load_mark_klines(self, symbol: str, interval: str) -> pd.DataFrame:
        rows = self.db.execute(
            select(MarketMarkKline).where(
                MarketMarkKline.symbol == symbol,
                MarketMarkKline.interval == interval,
            )
        ).scalars()
        return _to_df(rows, time_col="open_time")

    def load_funding(self, symbol: str) -> pd.DataFrame:
        rows = self.db.execute(
            select(MarketFundingRate).where(MarketFundingRate.symbol == symbol)
        ).scalars()
        return _to_df(rows, time_col="funding_time")

    def load_open_interest(self, symbol: str, period: str) -> pd.DataFrame:
        rows = self.db.execute(
            select(MarketOpenInterest).where(
                MarketOpenInterest.symbol == symbol,
                MarketOpenInterest.period == period,
            )
        ).scalars()
        return _to_df(rows, time_col="timestamp")

    def upsert_klines(self, rows: Iterable[dict]) -> None:
        self._bulk_insert(MarketKline, rows, conflict_cols=["symbol", "interval", "open_time"])

    def upsert_mark_klines(self, rows: Iterable[dict]) -> None:
        self._bulk_insert(MarketMarkKline, rows, conflict_cols=["symbol", "interval", "open_time"])

    def upsert_funding(self, rows: Iterable[dict]) -> None:
        self._bulk_insert(MarketFundingRate, rows, conflict_cols=["symbol", "funding_time"])

    def upsert_open_interest(self, rows: Iterable[dict]) -> None:
        self._bulk_insert(MarketOpenInterest, rows, conflict_cols=["symbol", "period", "timestamp"])

    def _bulk_insert(self, model, rows: Iterable[dict], conflict_cols: list[str]) -> None:
        data = list(rows)
        if not data:
            return
        col_count = max(len(data[0].keys()), 1)
        max_params = 60000
        chunk_size = max(1, min(1000, max_params // col_count))
        dialect = self.db.get_bind().dialect.name
        for start in range(0, len(data), chunk_size):
            chunk = data[start : start + chunk_size]
            if dialect == "postgresql":
                stmt = pg_insert(model).values(chunk).on_conflict_do_nothing(index_elements=conflict_cols)
            elif dialect == "sqlite":
                stmt = sa_insert(model).values(chunk).prefix_with("OR IGNORE")
            else:
                stmt = sa_insert(model).values(chunk)
            self.db.execute(stmt)
            self.db.commit()


def _to_df(rows, *, time_col: str) -> pd.DataFrame:
    items = []
    for row in rows:
        data = row.__dict__.copy()
        data.pop("_sa_instance_state", None)
        items.append(data)
    if not items:
        return pd.DataFrame()
    df = pd.DataFrame(items)
    if time_col in df.columns:
        df = df.sort_values(time_col)
    return df
