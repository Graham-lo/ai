from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MarketCoverageRequest(BaseModel):
    account_ids: Optional[list[str]] = None
    exchange_id: Optional[str] = None
    preset: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    symbols: Optional[list[str]] = None


class MarketCoverageResponse(BaseModel):
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    symbols: list[str]
    has_market: bool
    coverage: dict
    missing: dict
    notes: list[str]
