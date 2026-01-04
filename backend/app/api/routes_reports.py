from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_token
from app.db.models import ReportRun
from app.schemas.report import ReportOut, ReportRequest, ReportStatusOut
from app.services.report_progress_store import get_progress, set_progress
from app.services.report_service import run_report, run_report_task

router = APIRouter()


@router.post("/run", dependencies=[Depends(require_token)])
async def run_report_endpoint(payload: ReportRequest, db: Session = Depends(get_db)):
    try:
        report = run_report(db, payload)
    except RuntimeError as exc:
        message = str(exc)
        if message.startswith("SYNC_RUNNING:"):
            raise HTTPException(status_code=409, detail=message.replace("SYNC_RUNNING: ", "")) from exc
        raise HTTPException(status_code=400, detail=message) from exc
    return ReportOut(
        id=str(report.id),
        summary=report.summary_json,
        anomalies=report.anomalies_json,
        report_md=report.report_md,
        report_md_llm=report.report_md_llm,
        chart_spec_json=report.chart_spec_json,
        facts_path=report.facts_path,
        evidence_path=report.evidence_path,
        evidence_json=report.evidence_json,
        schema_version=report.schema_version,
        llm_model=report.llm_model,
        llm_generated_at=report.llm_generated_at,
        llm_status=report.llm_status,
        llm_error=report.llm_error,
        created_at=report.created_at,
    ).model_dump()


@router.post("/run-async", dependencies=[Depends(require_token)])
async def run_report_async_endpoint(
    payload: ReportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    report = ReportRun(
        account_scope={"account_ids": payload.account_ids or [], "exchange_id": payload.exchange_id},
        start=payload.start,
        end=payload.end,
        preset=payload.preset,
        net_mode=payload.net_mode or "fees_only",
        summary_json={},
        anomalies_json=[],
        report_md="",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    set_progress(str(report.id), status="queued", stage="queued", percent=1, message="queued")
    background_tasks.add_task(run_report_task, str(report.id), payload)
    return ReportStatusOut(
        report_id=str(report.id),
        status="queued",
        stage="queued",
        percent=1,
        message="queued",
        error=None,
        updated_at=report.created_at.isoformat(),
    ).model_dump()


@router.get("/{report_id}", dependencies=[Depends(require_token)])
async def get_report(report_id: str, db: Session = Depends(get_db)):
    report = db.get(ReportRun, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportOut(
        id=str(report.id),
        summary=report.summary_json,
        anomalies=report.anomalies_json,
        report_md=report.report_md,
        report_md_llm=report.report_md_llm,
        chart_spec_json=report.chart_spec_json,
        facts_path=report.facts_path,
        evidence_path=report.evidence_path,
        evidence_json=report.evidence_json,
        schema_version=report.schema_version,
        llm_model=report.llm_model,
        llm_generated_at=report.llm_generated_at,
        llm_status=report.llm_status,
        llm_error=report.llm_error,
        created_at=report.created_at,
    ).model_dump()


@router.get("/{report_id}/status", dependencies=[Depends(require_token)])
async def get_report_status(report_id: str, db: Session = Depends(get_db)):
    report = db.get(ReportRun, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    progress = get_progress(report_id)
    if not progress:
        return ReportStatusOut(
            report_id=report_id,
            status="unknown",
            stage="unknown",
            percent=0,
            message="no progress",
            error=None,
            updated_at=report.created_at.isoformat(),
        ).model_dump()
    return ReportStatusOut(
        report_id=report_id,
        status=progress.status,
        stage=progress.stage,
        percent=progress.percent,
        message=progress.message,
        error=progress.error,
        updated_at=progress.updated_at,
    ).model_dump()
