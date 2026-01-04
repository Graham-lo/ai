from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Fill(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ts_utc: datetime
    exchange_id: str
    account_id: UUID
    account_type: str
    symbol: str
    side: str
    price: Decimal
    qty: Decimal
    notional: Decimal
    fee: Decimal
    fee_asset: str
    maker_taker: Optional[str] = None
    order_id: Optional[str] = None
    trade_id: Optional[str] = None


class Cashflow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ts_utc: datetime
    exchange_id: str
    account_id: UUID
    account_type: str
    type: str
    amount: Decimal
    asset: str
    symbol: Optional[str] = None
    flow_id: Optional[str] = None
