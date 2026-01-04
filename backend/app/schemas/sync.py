from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SyncRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_scope: dict
    start: Optional[datetime]
    end: Optional[datetime]
    preset: Optional[str]
    status: str
    counts: dict
    error: Optional[str]
    created_at: datetime
