from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_token
from app.db.models import SyncRun
from app.schemas.report import ReportRequest
from app.schemas.sync import SyncRunOut
from app.services.sync_service import run_sync

router = APIRouter()


@router.post("/run", dependencies=[Depends(require_token)])
async def run_sync_endpoint(payload: ReportRequest, db: Session = Depends(get_db)):
    result = run_sync(db, payload)
    return result


@router.get("/runs", dependencies=[Depends(require_token)])
async def list_sync_runs(db: Session = Depends(get_db)):
    runs = db.query(SyncRun).order_by(SyncRun.created_at.desc()).limit(50).all()
    return [SyncRunOut.model_validate(run).model_dump() for run in runs]


@router.get("/runs/{run_id}", dependencies=[Depends(require_token)])
async def get_sync_run(run_id: str, db: Session = Depends(get_db)):
    run = db.get(SyncRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Sync run not found")
    return SyncRunOut.model_validate(run).model_dump()
