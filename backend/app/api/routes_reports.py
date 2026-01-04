from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_token
from app.db.models import ReportRun
from app.schemas.report import ReportOut, ReportRequest
from app.services.report_service import run_report

router = APIRouter()


@router.post("/run", dependencies=[Depends(require_token)])
async def run_report_endpoint(payload: ReportRequest, db: Session = Depends(get_db)):
    report = run_report(db, payload)
    return ReportOut(
        id=str(report.id),
        summary=report.summary_json,
        anomalies=report.anomalies_json,
        report_md=report.report_md,
        report_md_llm=report.report_md_llm,
        chart_spec_json=report.chart_spec_json,
        llm_model=report.llm_model,
        llm_generated_at=report.llm_generated_at,
        llm_status=report.llm_status,
        llm_error=report.llm_error,
        created_at=report.created_at,
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
        llm_model=report.llm_model,
        llm_generated_at=report.llm_generated_at,
        llm_status=report.llm_status,
        llm_error=report.llm_error,
        created_at=report.created_at,
    ).model_dump()
