from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_token
from app.db.models import Account
from app.services.imports import (
    parse_bybit_transaction_log,
    parse_bybit_transaction_log_rows,
    upsert_bybit_trade_logs,
    upsert_imported_data,
)

router = APIRouter()


@router.post("/bybit/transaction-log", dependencies=[Depends(require_token)])
async def import_bybit_transaction_log(
    account_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    raw = await file.read()
    content = raw.decode("utf-8", errors="ignore")
    account_type = (account.account_types or ["linear"])[0]
    fills, cashflows = parse_bybit_transaction_log(content, account.id, account.exchange_id, account_type)
    log_rows = parse_bybit_transaction_log_rows(content, account.id, account.exchange_id, account_type)
    result = upsert_imported_data(db, fills, cashflows)
    logs_inserted = upsert_bybit_trade_logs(db, log_rows)
    return {"status": "ok", **result, "bybit_trade_logs": logs_inserted}
