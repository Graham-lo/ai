from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.plugins.base import Adapter, AuthField, HealthStatus
from app.plugins.bybit.client import BybitClient
from app.schemas.ledger import Cashflow, Fill


class AdapterImpl(Adapter):
    exchange_id = "bybit"

    def capabilities(self) -> dict[str, Any]:
        return {"maker_taker": True, "funding": True, "realized_pnl": True}

    def auth_schema(self) -> list[AuthField]:
        return [
            AuthField(name="api_key", label="API Key", required=True, secret=False),
            AuthField(name="api_secret", label="API Secret", required=True, secret=True),
        ]

    def health_check(self, credentials: dict[str, Any], options: dict[str, Any]) -> HealthStatus:
        try:
            client = BybitClient(credentials["api_key"], credentials["api_secret"])
            client.fetch_executions("linear", None, None, None)
            return HealthStatus(ok=True)
        except Exception as exc:  # noqa: BLE001
            return HealthStatus(ok=False, message=str(exc))

    def fetch_fills(
        self,
        credentials: dict[str, Any],
        options: dict[str, Any],
        start: Optional[int],
        end: Optional[int],
        cursor: Optional[str],
    ) -> tuple[list[Fill], Optional[str]]:
        category = options.get("category", "linear")
        client = BybitClient(credentials["api_key"], credentials["api_secret"])
        data = client.fetch_executions(category, start, end, cursor)
        result = data.get("result", {})
        items = []
        for raw in result.get("list", []):
            ts = datetime.fromtimestamp(int(raw["execTime"]) / 1000, tz=timezone.utc)
            items.append(
                Fill(
                    ts_utc=ts,
                    exchange_id=self.exchange_id,
                    account_id=options["account_id"],
                    account_type=category,
                    symbol=self.normalize_symbol(raw.get("symbol", "")),
                    side=raw.get("side", "").lower(),
                    price=raw.get("execPrice"),
                    qty=raw.get("execQty"),
                    notional=raw.get("execValue"),
                    fee=raw.get("execFee"),
                    fee_asset=raw.get("feeCurrency", ""),
                    maker_taker="maker" if raw.get("isMaker") else "taker",
                    order_id=raw.get("orderId"),
                    trade_id=raw.get("execId"),
                )
            )
        return items, result.get("nextPageCursor")

    def fetch_cashflows(
        self,
        credentials: dict[str, Any],
        options: dict[str, Any],
        start: Optional[int],
        end: Optional[int],
        cursor: Optional[str],
    ) -> tuple[list[Cashflow], Optional[str]]:
        account_type = options.get("account_type", "UNIFIED")
        client = BybitClient(credentials["api_key"], credentials["api_secret"])
        data = client.fetch_transactions(account_type, start, end, cursor)
        result = data.get("result", {})
        items = []
        for raw in result.get("list", []):
            ts = datetime.fromtimestamp(int(raw["transactionTime"]) / 1000, tz=timezone.utc)
            flow_type = _map_transaction_type(raw.get("type"))
            items.append(
                Cashflow(
                    ts_utc=ts,
                    exchange_id=self.exchange_id,
                    account_id=options["account_id"],
                    account_type=account_type,
                    type=flow_type,
                    amount=raw.get("change", 0),
                    asset=raw.get("currency", ""),
                    symbol=raw.get("symbol"),
                    flow_id=str(raw.get("id")),
                )
            )
        return items, result.get("nextPageCursor")

    def normalize_symbol(self, raw_symbol: str) -> str:
        return raw_symbol.replace("-", "").upper()

    def rate_limit_policy(self) -> dict[str, Any]:
        return {"min_interval_ms": 250, "max_retries": 5, "max_window_days": 7}


def _map_transaction_type(raw_type: str | None) -> str:
    mapping = {
        "FUNDING": "funding",
        "REALIZED_PNL": "realized_pnl",
        "COMMISSION": "commission",
        "INTEREST": "borrow_interest",
        "REBATE": "rebate",
        "LIQUIDATION_FEE": "liquidation_fee",
    }
    return mapping.get(raw_type or "", "other")
