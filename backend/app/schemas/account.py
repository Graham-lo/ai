from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AccountCreate(BaseModel):
    exchange_id: str
    label: str
    account_types: list[str]
    credentials: dict[str, Any]
    options: dict[str, Any] = {}


class AccountUpdate(BaseModel):
    label: Optional[str] = None
    is_enabled: Optional[bool] = None
    options: Optional[dict[str, Any]] = None


class AccountRotate(BaseModel):
    credentials: dict[str, Any]


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    exchange_id: str
    label: str
    account_types: list[str]
    options: dict[str, Any]
    is_enabled: bool
