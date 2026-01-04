from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps import require_token

router = APIRouter()


@router.post("/monthly-attribution", dependencies=[Depends(require_token)])
async def run_monthly_attribution(
    file: UploadFile = File(...),
    start: str | None = Form(None),
    end: str | None = Form(None),
    preset: str | None = Form(None),
    symbols: str | None = Form(None),
) -> dict:
    raise HTTPException(status_code=410, detail="该接口已弃用，请导入数据后使用 /reports/run 生成事实与证据。")


class AttributionDbRequest(BaseModel):
    account_ids: list[str] | None = None
    exchange_id: str | None = None
    start: str | None = None
    end: str | None = None
    preset: str | None = None
    symbols: str | None = None


@router.post("/monthly-attribution-db", dependencies=[Depends(require_token)])
def run_monthly_attribution_db(payload: AttributionDbRequest, db: Session = Depends(get_db)) -> dict:
    raise HTTPException(status_code=410, detail="该接口已弃用，请使用 /reports/run 生成事实与证据。")
