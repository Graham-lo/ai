from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ReportRequest(BaseModel):
    account_ids: Optional[list[str]] = None
    exchange_id: Optional[str] = None
    preset: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    net_mode: Optional[str] = "fees_only"


class ReportOut(BaseModel):
    id: str
    summary: dict
    anomalies: list
    report_md: str
    report_md_llm: Optional[str] = None
    chart_spec_json: Optional[str] = None
    llm_model: Optional[str] = None
    llm_generated_at: Optional[datetime] = None
    llm_status: Optional[str] = None
    llm_error: Optional[str] = None
    created_at: datetime
