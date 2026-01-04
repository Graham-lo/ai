from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.plugins.base import Adapter, AuthField, HealthStatus
from app.plugins.okx.client import OKXClient
from app.schemas.ledger import Cashflow, Fill


class AdapterImpl(Adapter):
    exchange_id = "okx"

    def capabilities(self) -> dict[str, Any]:
        return {"maker_taker": True, "funding": True, "realized_pnl": True}

    def auth_schema(self) -> list[AuthField]:
        return [
            AuthField(name="api_key", label="API Key", required=True, secret=False),
            AuthField(name="api_secret", label="API Secret", required=True, secret=True),
            AuthField(name="passphrase", label="Passphrase", required=True, secret=True),
        ]

    def health_check(self, credentials: dict[str, Any], options: dict[str, Any]) -> HealthStatus:
        client = _client(credentials, options)
        try:
            data = client.fetch_balance()
        except Exception as exc:  # noqa: BLE001
            return HealthStatus(ok=False, message=str(exc))
        balances = data.get("data") or []
        return HealthStatus(ok=True, message=f"OKX connected, balances={len(balances)}")

    def fetch_fills(
        self,
        credentials: dict[str, Any],
        options: dict[str, Any],
        start: Optional[int],
        end: Optional[int],
        cursor: Optional[str],
    ) -> tuple[list[Fill], Optional[str]]:
        client = _client(credentials, options)
        inst_type = options.get("inst_type") or _inst_type(options)
        data = client.fetch_fills(start, end, cursor, inst_type=inst_type)
        items = data.get("data") or []
        fills: list[Fill] = []
        for item in items:
            ts = _to_dt(item.get("fillTime"))
            price = float(item.get("fillPx", 0) or 0)
            qty = float(item.get("fillSz", 0) or 0)
            fee = float(item.get("fee", 0) or 0)
            fills.append(
                Fill(
                    ts_utc=ts,
                    exchange_id=self.exchange_id,
                    account_id=options["account_id"],
                    account_type=options.get("account_type", "swap"),
                    symbol=self.normalize_symbol(item.get("instId", "")),
                    side=item.get("side", "buy"),
                    price=price,
                    qty=qty,
                    notional=price * qty,
                    fee=abs(fee),
                    fee_asset=item.get("feeCcy") or "USDT",
                    maker_taker=_maker_taker(item.get("liquidity") or item.get("execType")),
                    order_id=item.get("ordId"),
                    trade_id=item.get("tradeId"),
                )
            )
        next_cursor = items[-1].get("tradeId") if len(items) >= 100 else None
        return fills, next_cursor

    def fetch_cashflows(
        self,
        credentials: dict[str, Any],
        options: dict[str, Any],
        start: Optional[int],
        end: Optional[int],
        cursor: Optional[str],
    ) -> tuple[list[Cashflow], Optional[str]]:
        client = _client(credentials, options)
        data = client.fetch_cashflows(start, end, cursor)
        items = data.get("data") or []
        flows: list[Cashflow] = []
        for item in items:
            ts = _to_dt(item.get("ts"))
            amount = float(item.get("balChg", 0) or 0)
            flow_type = _map_cashflow_type(item.get("type"), item.get("subType"))
            flows.append(
                Cashflow(
                    ts_utc=ts,
                    exchange_id=self.exchange_id,
                    account_id=options["account_id"],
                    account_type=options.get("account_type", "swap"),
                    type=flow_type,
                    amount=amount,
                    asset=item.get("ccy") or "USDT",
                    symbol=self.normalize_symbol(item.get("instId", "")) or None,
                    flow_id=item.get("billId"),
                )
            )
        next_cursor = items[-1].get("billId") if len(items) >= 100 else None
        return flows, next_cursor

    def normalize_symbol(self, raw_symbol: str) -> str:
        return raw_symbol.replace("-", "").upper()

    def rate_limit_policy(self) -> dict[str, Any]:
        return {"min_interval_ms": 500, "max_retries": 3, "max_window_days": 7}


def _client(credentials: dict[str, Any], options: dict[str, Any]) -> OKXClient:
    return OKXClient(
        api_key=credentials["api_key"],
        api_secret=credentials["api_secret"],
        passphrase=credentials["passphrase"],
        base_url=options.get("base_url", "https://www.okx.com"),
    )


def _to_dt(value: str | int | None) -> datetime:
    if value is None:
        return datetime.now(tz=timezone.utc)
    try:
        ts_ms = int(value)
        return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    except Exception:  # noqa: BLE001
        return datetime.now(tz=timezone.utc)


def _maker_taker(value: str | None) -> str | None:
    if not value:
        return None
    normalized = str(value).lower()
    if normalized in {"m", "maker"}:
        return "maker"
    if normalized in {"t", "taker"}:
        return "taker"
    return None


def _inst_type(options: dict[str, Any]) -> str:
    account_type = (options.get("account_type") or "").lower()
    if account_type in {"spot"}:
        return "SPOT"
    if account_type in {"futures"}:
        return "FUTURES"
    return "SWAP"


def _map_cashflow_type(raw_type: str | None, raw_subtype: str | None) -> str:
    combined = f"{raw_type or ''} {raw_subtype or ''}".lower()
    if "fund" in combined:
        return "funding"
    if "fee" in combined or "commission" in combined:
        return "commission"
    if "pnl" in combined or "realized" in combined:
        return "realized_pnl"
    if "interest" in combined or "borrow" in combined:
        return "borrow_interest"
    if "rebate" in combined:
        return "rebate"
    return "other"
