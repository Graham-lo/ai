from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timezone import LOCAL_TZ, now_utc
from app.db.models import Account, BybitTradeLog, Cashflow, Fill, ReportRun, SyncRun
from app.db.session import SessionLocal
from app.schemas.ledger import Cashflow as CashflowSchema
from app.schemas.ledger import Fill as FillSchema
from app.schemas.report import ReportRequest
from app.services.anomalies import detect_anomalies, detect_anomalies_from_trade_logs
from app.services.evidence_builder import build_facts_and_evidence
from app.services.metrics import (
    compute_daily_series,
    compute_daily_series_from_trade_logs,
    compute_metrics,
    compute_metrics_from_trade_logs,
    max_drawdown,
)
from app.services.progress import (
    detect_progress,
    monthly_aggregate,
    monthly_aggregate_from_trade_logs,
    rolling_compare,
    rolling_compare_from_trade_logs,
)
from app.services.report_progress_store import set_progress

PRESETS = {
    "last_7d": timedelta(days=7),
    "last_30d": timedelta(days=30),
    "this_month": "this_month",
    "last_month": "last_month",
    "ytd": "ytd",
    "all_time": None,
}


def resolve_range(payload: ReportRequest) -> tuple[datetime | None, datetime | None]:
    if payload.start and payload.end:
        return payload.start, payload.end
    if payload.preset in ("last_7d", "last_30d"):
        end = now_utc()
        start = end - PRESETS[payload.preset]
        return start, end
    if payload.preset == "this_month":
        now_local = now_utc().astimezone(LOCAL_TZ)
        start_local = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start_local.astimezone(timezone.utc), now_utc()
    if payload.preset == "last_month":
        now_local = now_utc().astimezone(LOCAL_TZ)
        first = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_end = first - timedelta(seconds=1)
        last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return last_month_start.astimezone(timezone.utc), last_month_end.astimezone(timezone.utc)
    if payload.preset == "ytd":
        now_local = now_utc().astimezone(LOCAL_TZ)
        start_local = now_local.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return start_local.astimezone(timezone.utc), now_utc()
    return None, None


def run_report(db: Session, payload: ReportRequest) -> ReportRun:
    account_ids, start, end = _resolve_scope(db, payload)

    report = ReportRun(
        account_scope={"account_ids": account_ids, "exchange_id": payload.exchange_id},
        start=start,
        end=end,
        preset=payload.preset,
        net_mode=payload.net_mode or "fees_only",
        summary_json={},
        anomalies_json=[],
        report_md="",
    )
    db.add(report)
    db.flush()

    _fill_report(db, report, payload, account_ids, start, end, progress_cb=None)
    db.commit()
    db.refresh(report)
    return report


def run_report_task(report_id: str, payload: ReportRequest) -> None:
    db = SessionLocal()
    try:
        report = db.get(ReportRun, report_id)
        if not report:
            return
        set_progress(report_id, status="running", stage="prepare", percent=5, message="prepare scope")
        account_ids, start, end = _resolve_scope(db, payload)
        report.account_scope = {"account_ids": account_ids, "exchange_id": payload.exchange_id}
        report.start = start
        report.end = end
        report.preset = payload.preset
        report.net_mode = payload.net_mode or "fees_only"
        db.commit()

        def progress_cb(stage: str, percent: int, message: str) -> None:
            set_progress(report_id, status="running", stage=stage, percent=percent, message=message)

        _fill_report(db, report, payload, account_ids, start, end, progress_cb=progress_cb)
        db.commit()
        set_progress(report_id, status="completed", stage="done", percent=100, message="completed")
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        set_progress(report_id, status="failed", stage="error", percent=100, message="failed", error=str(exc))
        raise
    finally:
        db.close()


def _resolve_scope(db: Session, payload: ReportRequest) -> tuple[list[str], datetime | None, datetime | None]:
    start, end = resolve_range(payload)

    accounts_query = db.query(Account).filter(Account.is_enabled.is_(True))
    if payload.account_ids:
        accounts_query = accounts_query.filter(Account.id.in_(payload.account_ids))
    if payload.exchange_id:
        accounts_query = accounts_query.filter(Account.exchange_id == payload.exchange_id)
    accounts = accounts_query.all()
    account_ids = [str(acc.id) for acc in accounts]
    _ensure_sync_ready(db, account_ids)

    start, end = _resolve_data_range(
        db=db,
        account_ids=account_ids,
        exchange_id=payload.exchange_id,
        start=start,
        end=end,
    )
    return account_ids, start, end


def _fill_report(
    db: Session,
    report: ReportRun,
    payload: ReportRequest,
    account_ids: list[str],
    start: datetime | None,
    end: datetime | None,
    progress_cb: callable | None,
) -> None:
    if progress_cb:
        progress_cb("load_ledger", 20, "load fills/cashflows")

    use_trade_logs = _should_use_trade_logs(db, account_ids, payload.exchange_id)
    if use_trade_logs:
        logs_query = db.query(BybitTradeLog).filter(BybitTradeLog.account_id.in_(account_ids))
        if payload.exchange_id:
            logs_query = logs_query.filter(BybitTradeLog.exchange_id == payload.exchange_id)
        if start:
            logs_query = logs_query.filter(BybitTradeLog.ts_utc >= start)
        if end:
            logs_query = logs_query.filter(BybitTradeLog.ts_utc <= end)
        trade_logs = logs_query.all()
        period_metrics = compute_metrics_from_trade_logs(trade_logs)
    else:
        fills_query = db.query(Fill).filter(Fill.account_id.in_(account_ids))
        cash_query = db.query(Cashflow).filter(Cashflow.account_id.in_(account_ids))

        if start:
            fills_query = fills_query.filter(Fill.ts_utc >= start)
            cash_query = cash_query.filter(Cashflow.ts_utc >= start)
        if end:
            fills_query = fills_query.filter(Fill.ts_utc <= end)
            cash_query = cash_query.filter(Cashflow.ts_utc <= end)

        fills = [FillSchema.model_validate(row) for row in fills_query.all()]
        cashflows = [CashflowSchema.model_validate(row) for row in cash_query.all()]
        period_metrics = compute_metrics(fills, cashflows)

    if progress_cb:
        progress_cb("metrics", 40, "compute metrics")

    if use_trade_logs:
        all_logs_query = db.query(BybitTradeLog).filter(BybitTradeLog.account_id.in_(account_ids))
        if payload.exchange_id:
            all_logs_query = all_logs_query.filter(BybitTradeLog.exchange_id == payload.exchange_id)
        all_trade_logs = all_logs_query.all()
        baseline_metrics = compute_metrics_from_trade_logs(all_trade_logs)
        monthly = monthly_aggregate_from_trade_logs(all_trade_logs)
        progress = detect_progress(monthly)
        rolling_30d = rolling_compare_from_trade_logs(all_trade_logs, 30)
        rolling_14d = rolling_compare_from_trade_logs(all_trade_logs, 14)
        anomalies = detect_anomalies_from_trade_logs(trade_logs)
    else:
        all_fills = [
            FillSchema.model_validate(row)
            for row in db.query(Fill).filter(Fill.account_id.in_(account_ids)).all()
        ]
        all_cash = [
            CashflowSchema.model_validate(row)
            for row in db.query(Cashflow).filter(Cashflow.account_id.in_(account_ids)).all()
        ]
        baseline_metrics = compute_metrics(all_fills, all_cash)
        monthly = monthly_aggregate(all_fills, all_cash)
        progress = detect_progress(monthly)
        rolling_30d = rolling_compare(all_fills, all_cash, 30)
        rolling_14d = rolling_compare(all_fills, all_cash, 14)
        anomalies = detect_anomalies(fills, cashflows)

    if progress_cb:
        progress_cb("anomalies", 55, "detect anomalies")

    if use_trade_logs:
        daily_series = compute_daily_series_from_trade_logs(trade_logs)
    else:
        daily_series = compute_daily_series(fills, cashflows)
    mdd_fees = max_drawdown([v.net_after_fees for v in daily_series.values()])
    mdd_funding = max_drawdown([v.net_after_fees_and_funding for v in daily_series.values()])

    if use_trade_logs:
        top_symbols = _top_symbol_contribution_from_trade_logs(trade_logs)
    else:
        top_symbols = _top_symbol_contribution(cashflows)

    summary = {
        "scope": {
            "accounts": account_ids,
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "preset": payload.preset,
            "base_currency": settings.BASE_CURRENCY,
        },
        "baseline": baseline_metrics,
        "period": period_metrics,
        "max_drawdown": {
            "net_after_fees": float(mdd_fees),
            "net_after_fees_and_funding": float(mdd_funding),
        },
        "progress": progress,
        "rolling": {"rolling_30d": rolling_30d, "rolling_14d": rolling_14d},
        "top_symbols": top_symbols,
    }

    report.summary_json = summary
    report.anomalies_json = anomalies
    report.report_md = ""

    try:
        if progress_cb:
            if payload.include_market:
                progress_cb("facts_evidence", 80, "build facts/evidence")
            else:
                progress_cb("facts_evidence", 80, "build cost-only facts/evidence")
        facts_result = build_facts_and_evidence(
            db=db,
            account_ids=account_ids,
            exchange_id=payload.exchange_id,
            start=start,
            end=end,
            preset=payload.preset,
            report_id=str(report.id),
            anomalies=anomalies,
            fetch_market=False,
            include_market=bool(payload.include_market),
        )
    except Exception:  # noqa: BLE001
        db.rollback()
        raise

    report.facts_path = facts_result.facts_path
    report.evidence_path = facts_result.evidence_path
    report.evidence_json = facts_result.evidence_json
    report.schema_version = facts_result.evidence_json.get("schema_version")

    if progress_cb:
        progress_cb("finalize", 95, "finalize report")


def _ensure_sync_ready(db: Session, account_ids: list[str]) -> None:
    if not account_ids:
        return
    running = db.query(SyncRun).filter(SyncRun.status == "running").all()
    if not running:
        return
    target = set(account_ids)
    for run in running:
        scope = run.account_scope or {}
        run_ids = set(scope.get("account_ids") or [])
        if target & run_ids:
            raise RuntimeError("SYNC_RUNNING: 账户正在同步，请稍后再生成报告。")


def _resolve_data_range(
    db: Session,
    account_ids: list[str],
    exchange_id: str | None,
    start: datetime | None,
    end: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    if start and end:
        return start, end
    if not account_ids:
        return start, end
    fills_query = db.query(func.min(Fill.ts_utc), func.max(Fill.ts_utc)).filter(
        Fill.account_id.in_(account_ids)
    )
    cash_query = db.query(func.min(Cashflow.ts_utc), func.max(Cashflow.ts_utc)).filter(
        Cashflow.account_id.in_(account_ids)
    )
    logs_query = db.query(func.min(BybitTradeLog.ts_utc), func.max(BybitTradeLog.ts_utc)).filter(
        BybitTradeLog.account_id.in_(account_ids)
    )
    if exchange_id:
        fills_query = fills_query.filter(Fill.exchange_id == exchange_id)
        cash_query = cash_query.filter(Cashflow.exchange_id == exchange_id)
        logs_query = logs_query.filter(BybitTradeLog.exchange_id == exchange_id)
    fills_min, fills_max = fills_query.one()
    cash_min, cash_max = cash_query.one()
    logs_min, logs_max = logs_query.one()
    min_ts = min([ts for ts in (fills_min, cash_min, logs_min) if ts is not None], default=None)
    max_ts = max([ts for ts in (fills_max, cash_max, logs_max) if ts is not None], default=None)
    return start or min_ts, end or max_ts


def _top_symbol_contribution(cashflows: list[CashflowSchema]) -> list[dict]:
    totals = defaultdict(float)
    for cf in cashflows:
        if cf.symbol:
            totals[cf.symbol] += float(cf.amount)
    ranked = sorted(totals.items(), key=lambda kv: abs(kv[1]), reverse=True)
    return [{"symbol": sym, "amount": amt} for sym, amt in ranked[:5]]


def _top_symbol_contribution_from_trade_logs(trade_logs: list[BybitTradeLog]) -> list[dict]:
    totals = defaultdict(float)
    for row in trade_logs:
        if not row.contract:
            continue
        if "TRADE" not in (row.type or "").upper():
            continue
        amount = 0.0
        try:
            amount = float(row.change or 0)
        except (TypeError, ValueError):
            amount = 0.0
        totals[row.contract] += amount
    ranked = sorted(totals.items(), key=lambda kv: abs(kv[1]), reverse=True)
    return [{"symbol": sym, "amount": amt} for sym, amt in ranked[:5]]


def _should_use_trade_logs(db: Session, account_ids: list[str], exchange_id: str | None) -> bool:
    if exchange_id and exchange_id != "bybit":
        return False
    accounts = db.query(Account.exchange_id).filter(Account.id.in_(account_ids)).all()
    if not accounts:
        return False
    if not all(row[0] == "bybit" for row in accounts):
        return False
    logs_query = db.query(func.count(BybitTradeLog.id)).filter(BybitTradeLog.account_id.in_(account_ids))
    if exchange_id:
        logs_query = logs_query.filter(BybitTradeLog.exchange_id == exchange_id)
    return (logs_query.scalar() or 0) > 0
