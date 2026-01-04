from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode, urljoin

import requests


class OKXClient:
    def __init__(self, api_key: str, api_secret: str, passphrase: str, base_url: str = "https://www.okx.com") -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def fetch_fills(
        self,
        start_ms: int | None,
        end_ms: int | None,
        cursor: str | None,
        inst_type: str = "SWAP",
        limit: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"instType": inst_type, "limit": min(limit, 100)}
        if start_ms is not None:
            params["begin"] = start_ms
        if end_ms is not None:
            params["end"] = end_ms
        if cursor:
            params["after"] = cursor
        return self._request("GET", "/api/v5/trade/fills", params=params)

    def fetch_cashflows(
        self,
        start_ms: int | None,
        end_ms: int | None,
        cursor: str | None,
        limit: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": min(limit, 100)}
        if start_ms is not None:
            params["begin"] = start_ms
        if end_ms is not None:
            params["end"] = end_ms
        if cursor:
            params["after"] = cursor
        return self._request("GET", "/api/v5/account/bills", params=params)

    def fetch_balance(self) -> dict[str, Any]:
        return self._request("GET", "/api/v5/account/balance")

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None, body: dict | None = None) -> Any:
        method_upper = method.upper()
        query = f"?{urlencode(params)}" if params else ""
        request_path = f"{path}{query}"
        url = urljoin(self.base_url + "/", request_path.lstrip("/"))
        body_text = json.dumps(body) if body else ""
        timestamp = self._timestamp()
        sign = self._sign(timestamp, method_upper, request_path, body_text)
        headers = {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }
        resp = self.session.request(method_upper, url, headers=headers, data=body_text, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") not in ("0", 0):
            raise RuntimeError(f"OKX error: {data}")
        return data

    def _timestamp(self) -> str:
        now = datetime.now(tz=timezone.utc)
        return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _sign(self, timestamp: str, method: str, path: str, body: str) -> str:
        prehash = f"{timestamp}{method}{path}{body}"
        digest = hmac.new(self.api_secret.encode(), prehash.encode(), hashlib.sha256).digest()
        return base64.b64encode(digest).decode()
