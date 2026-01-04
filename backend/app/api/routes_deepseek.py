import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_token
from app.db.models import ReportRun
from app.services.deepseek_client import build_report_payload, generate_deepseek_analysis, generate_deepseek_markdown
from app.services.deepseek_payload_builder import build_deepseek_payload


router = APIRouter()


@router.post("/{report_id}/deepseek", dependencies=[Depends(require_token)])
async def generate_deepseek_report(
    report_id: str,
    refresh: int = Query(0),
    model: str | None = Query(None),
    deepseek_api_key: str | None = Header(None, alias="X-DeepSeek-Api-Key"),
    db: Session = Depends(get_db),
):
    report = db.get(ReportRun, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if report.report_md_llm and not refresh:
        return _format_llm_response(report)

    payload = build_report_payload(report)
    try:
        content, resolved_model = generate_deepseek_markdown(
            payload,
            api_key=deepseek_api_key,
            model=model,
        )
        report.report_md_llm = content
        report.llm_model = resolved_model
        report.llm_generated_at = datetime.now(timezone.utc)
        report.llm_status = "success"
        report.llm_error = None
        db.commit()
        db.refresh(report)
        return _format_llm_response(report)
    except Exception as exc:
        report.llm_status = "failed"
        report.llm_error = _safe_error(exc)
        report.llm_generated_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=502, detail=f"DeepSeek 生成失败：{report.llm_error}") from exc


@router.get("/{report_id}/deepseek-payload", dependencies=[Depends(require_token)])
async def get_deepseek_payload(report_id: str, db: Session = Depends(get_db)):
    report = db.get(ReportRun, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    payload = build_deepseek_payload(db, report)
    return payload


@router.post("/{report_id}/deepseek-analyze", dependencies=[Depends(require_token)])
async def analyze_with_deepseek(
    report_id: str,
    refresh: int = Query(0),
    model: str | None = Query(None),
    deepseek_api_key: str | None = Header(None, alias="X-DeepSeek-Api-Key"),
    db: Session = Depends(get_db),
):
    report = db.get(ReportRun, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if report.report_md_llm and report.chart_spec_json and not refresh:
        return _format_llm_response(report)

    payload = build_deepseek_payload(db, report)
    try:
        report_md, chart_spec, resolved_model = generate_deepseek_analysis(
            payload,
            api_key=deepseek_api_key,
            model=model,
        )
        report.report_md_llm = report_md
        report.chart_spec_json = json.dumps(chart_spec, ensure_ascii=False)
        report.llm_model = resolved_model
        report.llm_generated_at = datetime.now(timezone.utc)
        if chart_spec.get("charts"):
            report.llm_status = "success"
            report.llm_error = None
        else:
            report.llm_status = "partial"
            report.llm_error = "chart_spec_missing_or_invalid"
        db.commit()
        db.refresh(report)
        return _format_llm_response(report)
    except Exception as exc:
        report.llm_status = "failed"
        report.llm_error = _safe_error(exc)
        report.llm_generated_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=502, detail=f"DeepSeek 深度拆解失败：{report.llm_error}") from exc


def _format_llm_response(report: ReportRun) -> dict:
    return {
        "report_id": str(report.id),
        "report_md_llm": report.report_md_llm,
        "chart_spec_json": report.chart_spec_json,
        "llm_model": report.llm_model,
        "llm_generated_at": report.llm_generated_at,
        "llm_status": report.llm_status,
        "llm_error": report.llm_error,
    }


def _safe_error(exc: Exception) -> str:
    message = str(exc)
    if "api_key=" in message:
        message = message.replace("api_key=", "api_key=***")
    if "Authorization" in message:
        message = message.replace("Authorization", "Authorization(omitted)")
    return message[:1000]
