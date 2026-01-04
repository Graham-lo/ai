from __future__ import annotations

from typing import Any, Optional

from app.plugins.base import Adapter, AuthField, HealthStatus
from app.schemas.ledger import Cashflow, Fill


class AdapterImpl(Adapter):
    exchange_id = "template"

    def capabilities(self) -> dict[str, Any]:
        return {"maker_taker": True, "funding": False, "realized_pnl": False}

    def auth_schema(self) -> list[AuthField]:
        return [
            AuthField(name="api_key", label="API Key", required=True, secret=False),
            AuthField(name="api_secret", label="API Secret", required=True, secret=True),
        ]

    def health_check(self, credentials: dict[str, Any], options: dict[str, Any]) -> HealthStatus:
        return HealthStatus(ok=False, message="TODO: Implement health check")

    def fetch_fills(
        self,
        credentials: dict[str, Any],
        options: dict[str, Any],
        start: Optional[int],
        end: Optional[int],
        cursor: Optional[str],
    ) -> tuple[list[Fill], Optional[str]]:
        raise NotImplementedError("TODO: Implement fetch_fills")

    def fetch_cashflows(
        self,
        credentials: dict[str, Any],
        options: dict[str, Any],
        start: Optional[int],
        end: Optional[int],
        cursor: Optional[str],
    ) -> tuple[list[Cashflow], Optional[str]]:
        raise NotImplementedError("TODO: Implement fetch_cashflows")

    def normalize_symbol(self, raw_symbol: str) -> str:
        return raw_symbol.replace("-", "").upper()

    def rate_limit_policy(self) -> dict[str, Any]:
        return {"min_interval_ms": 500, "max_retries": 3}
