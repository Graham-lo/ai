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

    def _sign(self, params: dict[str, Any]) -> str:
        sorted_items = sorted(params.items())
        query = "&".join(f"{k}={v}" for k, v in sorted_items)
        return hmac.new(self.api_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()

    def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        params = dict(params)
        params["api_key"] = self.api_key
        params["timestamp"] = int(time.time() * 1000)
        params["recv_window"] = 5000
        params["sign"] = self._sign(params)
        response = requests.get(f"{self.base_url}{path}", params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        if data.get("retCode") not in (0, None):
            raise RuntimeError(f"Bybit error: {data}")
        return data

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
