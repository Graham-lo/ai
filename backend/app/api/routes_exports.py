from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_token
from app.db.models import Cashflow, Fill, ReportRun
from app.services.export import (
    bybit_transaction_log_csv_from_rows,
    bybit_transaction_log_entries,
    cashflows_to_csv,
    fills_to_csv,
)

router = APIRouter()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


@router.get("/fills.csv", response_class=PlainTextResponse, dependencies=[Depends(require_token)])
async def export_fills(account_id: str, start: str | None = None, end: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Fill).filter(Fill.account_id == account_id)
    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)
    if start_dt:
        query = query.filter(Fill.ts_utc >= start_dt)
    if end_dt:
        query = query.filter(Fill.ts_utc <= end_dt)
    return fills_to_csv(query.all())


@router.get("/cashflows.csv", response_class=PlainTextResponse, dependencies=[Depends(require_token)])
async def export_cashflows(account_id: str, start: str | None = None, end: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Cashflow).filter(Cashflow.account_id == account_id)
    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)
    if start_dt:
        query = query.filter(Cashflow.ts_utc >= start_dt)
    if end_dt:
        query = query.filter(Cashflow.ts_utc <= end_dt)
    return cashflows_to_csv(query.all())


@router.get("/summary.json", dependencies=[Depends(require_token)])
async def export_summary(report_run_id: str, db: Session = Depends(get_db)):
    report = db.get(ReportRun, report_run_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report.summary_json


@router.get("/anomalies.json", dependencies=[Depends(require_token)])
async def export_anomalies(report_run_id: str, db: Session = Depends(get_db)):
    report = db.get(ReportRun, report_run_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report.anomalies_json


@router.get("/report.md", response_class=PlainTextResponse, dependencies=[Depends(require_token)])
async def export_report_md(report_run_id: str, db: Session = Depends(get_db)):
    report = db.get(ReportRun, report_run_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report.report_md


@router.get(
    "/bybit_transaction_log.csv",
    response_class=PlainTextResponse,
    dependencies=[Depends(require_token)],
)
async def export_bybit_log(
    account_id: str,
    start: str | None = None,
    end: str | None = None,
    symbol: str | None = None,
    type: str | None = None,
    db: Session = Depends(get_db),
):
    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)
    fills_query = db.query(Fill).filter(Fill.account_id == account_id)
    cash_query = db.query(Cashflow).filter(Cashflow.account_id == account_id)
    if start_dt:
        fills_query = fills_query.filter(Fill.ts_utc >= start_dt)
        cash_query = cash_query.filter(Cashflow.ts_utc >= start_dt)
    if end_dt:
        fills_query = fills_query.filter(Fill.ts_utc <= end_dt)
        cash_query = cash_query.filter(Cashflow.ts_utc <= end_dt)
    if symbol:
        fills_query = fills_query.filter(Fill.symbol == symbol)
        cash_query = cash_query.filter(Cashflow.symbol == symbol)
    rows = bybit_transaction_log_entries(fills_query.all(), cash_query.all())
    if type:
        rows = [row for row in rows if row["Type"] == type.upper()]
    if symbol:
        rows = [row for row in rows if row["Contract"] == symbol]
    return bybit_transaction_log_csv_from_rows(rows)


@router.get(
    "/bybit_transaction_log.json",
    dependencies=[Depends(require_token)],
)
async def export_bybit_log_json(
    account_id: str,
    start: str | None = None,
    end: str | None = None,
    symbol: str | None = None,
    type: str | None = None,
    db: Session = Depends(get_db),
):
    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)
    fills_query = db.query(Fill).filter(Fill.account_id == account_id)
    cash_query = db.query(Cashflow).filter(Cashflow.account_id == account_id)
    if start_dt:
        fills_query = fills_query.filter(Fill.ts_utc >= start_dt)
        cash_query = cash_query.filter(Cashflow.ts_utc >= start_dt)
    if end_dt:
        fills_query = fills_query.filter(Fill.ts_utc <= end_dt)
        cash_query = cash_query.filter(Cashflow.ts_utc <= end_dt)
    if symbol:
        fills_query = fills_query.filter(Fill.symbol == symbol)
        cash_query = cash_query.filter(Cashflow.symbol == symbol)
    rows = bybit_transaction_log_entries(fills_query.all(), cash_query.all())
    if type:
        rows = [row for row in rows if row["Type"] == type.upper()]
    if symbol:
        rows = [row for row in rows if row["Contract"] == symbol]
    return rows
