from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_token
from app.core.crypto import encrypt_dict
from app.core.logging import redact_dict
from app.db.models import Account
from app.schemas.account import AccountCreate, AccountOut, AccountRotate, AccountUpdate

router = APIRouter()


@router.get("", dependencies=[Depends(require_token)])
async def list_accounts(db: Session = Depends(get_db)):
    accounts = db.query(Account).all()
    return [AccountOut.model_validate(account).model_dump() for account in accounts]


@router.post("", dependencies=[Depends(require_token)])
async def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    encrypted = encrypt_dict(payload.credentials)
    account = Account(
        exchange_id=payload.exchange_id,
        label=payload.label,
        account_types=payload.account_types,
        credentials_encrypted=encrypted,
        options=payload.options or {},
        is_enabled=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return AccountOut.model_validate(account).model_dump()


@router.patch("/{account_id}", dependencies=[Depends(require_token)])
async def update_account(account_id: str, payload: AccountUpdate, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if payload.label is not None:
        account.label = payload.label
    if payload.is_enabled is not None:
        account.is_enabled = payload.is_enabled
    if payload.options is not None:
        account.options = payload.options
    db.commit()
    db.refresh(account)
    return AccountOut.model_validate(account).model_dump()


@router.post("/{account_id}/rotate-credentials", dependencies=[Depends(require_token)])
async def rotate_credentials(account_id: str, payload: AccountRotate, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    account.credentials_encrypted = encrypt_dict(payload.credentials)
    db.commit()
    return {"status": "ok", "credentials": redact_dict(payload.credentials)}


@router.delete("/{account_id}", dependencies=[Depends(require_token)])
async def delete_account(account_id: str, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
    return {"status": "deleted"}
