from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel

from app.schemas.ledger import Cashflow, Fill


class AuthField(BaseModel):
    name: str
    label: str
    type: str = "string"
    required: bool = True
    secret: bool = False


class Manifest(BaseModel):
    exchange_id: str
    display_name: str
    auth_fields: list[AuthField]
    account_types: list[str]
    capabilities: dict[str, Any]
    notes: list[str] = []


class HealthStatus(BaseModel):
    ok: bool
    message: str = ""


class Adapter(ABC):
    exchange_id: str

    @abstractmethod
    def capabilities(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def auth_schema(self) -> list[AuthField]:
        raise NotImplementedError

    @abstractmethod
    def health_check(self, credentials: dict[str, Any], options: dict[str, Any]) -> HealthStatus:
        raise NotImplementedError

    @abstractmethod
    def fetch_fills(
        self,
        credentials: dict[str, Any],
        options: dict[str, Any],
        start: Optional[int],
        end: Optional[int],
        cursor: Optional[str],
    ) -> tuple[list[Fill], Optional[str]]:
        raise NotImplementedError

    @abstractmethod
    def fetch_cashflows(
        self,
        credentials: dict[str, Any],
        options: dict[str, Any],
        start: Optional[int],
        end: Optional[int],
        cursor: Optional[str],
    ) -> tuple[list[Cashflow], Optional[str]]:
        raise NotImplementedError

    @abstractmethod
    def normalize_symbol(self, raw_symbol: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def rate_limit_policy(self) -> dict[str, Any]:
        raise NotImplementedError
