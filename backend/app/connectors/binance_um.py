from __future__ import annotations

from dataclasses import dataclass
from time import sleep, time
from typing import Optional
from typing import Any
from urllib.parse import urljoin

import requests


@dataclass
class BinanceUMConfig:
    base_url: str = "https://fapi.binance.com"
    timeout_sec: int = 20
    max_retries: int = 5
    backoff_base: float = 0.5
    backoff_max: float = 8.0
    min_interval_sec: float = 0.1


class BinanceUMClient:
    def __init__(self, config: BinanceUMConfig | None = None) -> None:
        self.config = config or BinanceUMConfig()
        self.session = requests.Session()

    def get_klines(
        self, symbol: str, interval: str, start_ms: int, end_ms: int, limit: int = 1000
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        cursor = start_ms
        while cursor <= end_ms:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": cursor,
                "endTime": end_ms,
                "limit": min(limit, 1500),
            }
            data = self._get("/fapi/v1/klines", params)
            if not data:
                break
            for item in data:
                rows.append(
                    {
                        "symbol": symbol,
                        "interval": interval,
                        "open_time": int(item[0]),
                        "open": float(item[1]),
                        "high": float(item[2]),
                        "low": float(item[3]),
                        "close": float(item[4]),
                        "volume": float(item[5]),
                        "close_time": int(item[6]),
                        "quote_volume": float(item[7]),
                        "trades": int(item[8]),
                        "taker_buy_base": float(item[9]),
                        "taker_buy_quote": float(item[10]),
                    }
                )
            last_close = int(data[-1][6])
            cursor = last_close + 1
            if last_close >= end_ms:
                break
            sleep(self.config.min_interval_sec)
        return rows

    def get_mark_klines(
        self, symbol: str, interval: str, start_ms: int, end_ms: int, limit: int = 1000
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        cursor = start_ms
        while cursor <= end_ms:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": cursor,
                "endTime": end_ms,
                "limit": min(limit, 1500),
            }
            data = self._get("/fapi/v1/markPriceKlines", params)
            if not data:
                break
            for item in data:
                rows.append(
                    {
                        "symbol": symbol,
                        "interval": interval,
                        "open_time": int(item[0]),
                        "open": float(item[1]),
                        "high": float(item[2]),
                        "low": float(item[3]),
                        "close": float(item[4]),
                        "close_time": int(item[6]),
                    }
                )
            last_close = int(data[-1][6])
            cursor = last_close + 1
            if last_close >= end_ms:
                break
            sleep(self.config.min_interval_sec)
        return rows

    def get_funding_rates(
        self, symbol: str, start_ms: int, end_ms: int, limit: int = 1000
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        cursor = start_ms
        while cursor <= end_ms:
            params = {
                "symbol": symbol,
                "startTime": cursor,
                "endTime": end_ms,
                "limit": min(limit, 1000),
            }
            data = self._get("/fapi/v1/fundingRate", params)
            if not data:
                break
            for item in data:
                rows.append(
                    {
                        "symbol": symbol,
                        "funding_time": int(item["fundingTime"]),
                        "funding_rate": float(item["fundingRate"]),
                        "mark_price": float(item.get("markPrice") or 0.0),
                    }
                )
            last_time = int(data[-1]["fundingTime"])
            cursor = last_time + 1
            if last_time >= end_ms:
                break
        return rows

    def get_open_interest_hist(
        self,
        symbol: str,
        period: str,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        end_ms = end_ms or int(time() * 1000)
        max_window_ms = 30 * 24 * 60 * 60 * 1000
        min_start = end_ms - max_window_ms
        if start_ms is None or start_ms < min_start:
            start_ms = min_start
        cursor = start_ms
        while True:
            params = {
                "symbol": symbol,
                "period": period,
                "limit": min(limit, 500),
            }
            if cursor is not None:
                params["startTime"] = cursor
            if end_ms is not None:
                params["endTime"] = end_ms
            try:
                data = self._get("/futures/data/openInterestHist", params)
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    data = self._get("/fapi/v1/openInterestHist", params)
                else:
                    raise
            if not data:
                break
            for item in data:
                rows.append(
                    {
                        "symbol": symbol,
                        "period": period,
                        "timestamp": int(item["timestamp"]),
                        "sum_open_interest": float(item["sumOpenInterest"]),
                        "sum_open_interest_value": float(item["sumOpenInterestValue"]),
                    }
                )
            last_time = int(data[-1]["timestamp"])
            if end_ms is None or last_time >= end_ms:
                break
            cursor = last_time + 1
        return rows

    def get_open_interest_current(self, symbol: str) -> dict[str, Any]:
        data = self._get("/fapi/v1/openInterest", {"symbol": symbol})
        return {
            "symbol": data["symbol"],
            "open_interest": float(data["openInterest"]),
            "time": int(data["time"]),
        }

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        url = urljoin(self.config.base_url, path)
        last_error: Optional[Exception] = None
        for attempt in range(self.config.max_retries):
            resp = self.session.get(url, params=params, timeout=self.config.timeout_sec)
            if resp.status_code in (418, 429, 500, 502, 503, 504):
                last_error = requests.HTTPError(resp.text, response=resp)
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait_sec = min(float(retry_after), self.config.backoff_max)
                else:
                    wait_sec = min(self.config.backoff_base * (2**attempt), self.config.backoff_max)
                sleep(wait_sec)
                continue
            resp.raise_for_status()
            return resp.json()
        if last_error:
            raise last_error
        resp.raise_for_status()
        return resp.json()
