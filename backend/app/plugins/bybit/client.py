import hashlib
import hmac
import time
from typing import Any

import requests


class BybitClient:
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://api.bybit.com") -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.time_offset_ms = 0
        self._sync_time()

    def _sign(self, params: dict[str, Any]) -> str:
        sorted_items = sorted(params.items())
        query = "&".join(f"{k}={v}" for k, v in sorted_items)
        return hmac.new(self.api_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()

    def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        params = dict(params)
        params["api_key"] = self.api_key
        params["recv_window"] = 10000
        for attempt in range(2):
            params["timestamp"] = int(time.time() * 1000) + self.time_offset_ms
            params["sign"] = self._sign(params)
            response = requests.get(f"{self.base_url}{path}", params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            if data.get("retCode") in (0, None):
                return data
            if data.get("retCode") == 10002 and attempt == 0:
                self._sync_time()
                continue
            raise RuntimeError(f"Bybit error: {data}")
        raise RuntimeError("Bybit error: failed after timestamp resync")

    def _sync_time(self) -> None:
        server_ms = self._fetch_server_time_ms()
        if server_ms is None:
            return
        local_ms = int(time.time() * 1000)
        self.time_offset_ms = server_ms - local_ms

    def _fetch_server_time_ms(self) -> int | None:
        try:
            response = requests.get(f"{self.base_url}/v5/market/time", timeout=10)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException:
            return None
        if payload.get("retCode") not in (0, None):
            return None
        result = payload.get("result", {})
        time_second = result.get("timeSecond")
        if time_second is not None:
            return int(time_second) * 1000
        time_nano = result.get("timeNano")
        if time_nano is not None:
            return int(int(time_nano) / 1_000_000)
        return None

    def fetch_executions(self, category: str, start: int | None, end: int | None, cursor: str | None) -> dict[str, Any]:
        params: dict[str, Any] = {"category": category, "limit": 200}
        if start:
            params["startTime"] = start
        if end:
            params["endTime"] = end
        if cursor:
            params["cursor"] = cursor
        return self._request("/v5/execution/list", params)

    def fetch_transactions(self, account_type: str, start: int | None, end: int | None, cursor: str | None) -> dict[str, Any]:
        params: dict[str, Any] = {"accountType": account_type, "limit": 200}
        if start:
            params["startTime"] = start
        if end:
            params["endTime"] = end
        if cursor:
            params["cursor"] = cursor
        return self._request("/v5/account/transaction-log", params)
