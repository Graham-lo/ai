from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timezone import LOCAL_TZ, now_utc
from app.db.models import Account, Cashflow, Fill, ReportRun
from app.schemas.ledger import Cashflow as CashflowSchema
from app.schemas.ledger import Fill as FillSchema
from app.schemas.report import ReportRequest
from app.services.anomalies import detect_anomalies
from app.services.metrics import compute_daily_series, compute_metrics, max_drawdown
from app.services.progress import detect_progress, monthly_aggregate, rolling_compare


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
    start, end = resolve_range(payload)

    accounts_query = db.query(Account).filter(Account.is_enabled.is_(True))
    if payload.account_ids:
        accounts_query = accounts_query.filter(Account.id.in_(payload.account_ids))
    if payload.exchange_id:
        accounts_query = accounts_query.filter(Account.exchange_id == payload.exchange_id)
    accounts = accounts_query.all()
    account_ids = [str(acc.id) for acc in accounts]

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

    all_fills = [FillSchema.model_validate(row) for row in db.query(Fill).filter(Fill.account_id.in_(account_ids)).all()]
    all_cash = [CashflowSchema.model_validate(row) for row in db.query(Cashflow).filter(Cashflow.account_id.in_(account_ids)).all()]
    baseline_metrics = compute_metrics(all_fills, all_cash)

    monthly = monthly_aggregate(all_fills, all_cash)
    progress = detect_progress(monthly)
    rolling_30d = rolling_compare(all_fills, all_cash, 30)
    rolling_14d = rolling_compare(all_fills, all_cash, 14)

    anomalies = detect_anomalies(fills, cashflows)

    daily_series = compute_daily_series(fills, cashflows)
    mdd_fees = max_drawdown([v.net_after_fees for v in daily_series.values()])
    mdd_funding = max_drawdown([v.net_after_fees_and_funding for v in daily_series.values()])

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

    report_md = render_report(summary, anomalies, payload.net_mode or "fees_only")

    report = ReportRun(
        account_scope={"account_ids": account_ids, "exchange_id": payload.exchange_id},
        start=start,
        end=end,
        preset=payload.preset,
        net_mode=payload.net_mode or "fees_only",
        summary_json=summary,
        anomalies_json=anomalies,
        report_md=report_md,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def _top_symbol_contribution(cashflows: list[CashflowSchema]) -> list[dict]:
    totals = defaultdict(float)
    for cf in cashflows:
        if cf.symbol:
            totals[cf.symbol] += float(cf.amount)
    ranked = sorted(totals.items(), key=lambda kv: abs(kv[1]), reverse=True)
    return [{"symbol": sym, "amount": amt} for sym, amt in ranked[:5]]


def render_report(summary: dict, anomalies: list[dict], net_mode: str) -> str:
    period = summary["period"]
    baseline = summary["baseline"]
    mdd = summary["max_drawdown"]
    net_label = "仅费用" if net_mode == "fees_only" else "费用+资金费率"
    mode_value = period["net_after_fees"] if net_mode == "fees_only" else period["net_after_fees_and_funding"]
    lines = []
    lines.append("# 交易体检报告")
    lines.append("")
    lines.append("## 概览")
    lines.append(f"区间：{summary['scope']['start']} -> {summary['scope']['end']}")
    lines.append(f"账户：{', '.join(summary['scope']['accounts']) if summary['scope']['accounts'] else '全部'}")
    lines.append(f"基准币：{summary['scope']['base_currency']}")
    if period["realized_pnl"] == 0:
        lines.append("提示：缺失已实现盈亏数据，报告以成本与行为分析为主。")
    if period["unconverted_fee_assets"] or period["unconverted_cashflow_assets"]:
        lines.append("提示：部分费用/流水未折算为基准币。")
    lines.append("")
    lines.append("## 客观结论")
    lines.append(f"净值（{net_label}）：{mode_value:.4f}")
    lines.append(f"撮合手续费：{period['trading_fees']:.4f}")
    lines.append(f"资金费率：{period['funding_pnl']:.4f}")
    lines.append("")
    lines.append("## 成本拆解")
    lines.append(f"- 撮合手续费：{period['trading_fees']:.4f}")
    lines.append(f"- 资金费率：{period['funding_pnl']:.4f}")
    lines.append(f"- 利息：{period['borrow_interest']:.4f}")
    lines.append(f"- 返佣：{period['rebates']:.4f}")
    lines.append("")
    lines.append("## 绩效与风险")
    lines.append(f"净值（仅费用）：{period['net_after_fees']:.4f}")
    lines.append(f"净值（费用+资金费率）：{period['net_after_fees_and_funding']:.4f}")
    lines.append(f"最大回撤（仅费用）：{mdd['net_after_fees']:.4f}")
    lines.append(f"最大回撤（费用+资金费率）：{mdd['net_after_fees_and_funding']:.4f}")
    lines.append("")
    lines.append("## 进步检测")
    lines.append(_format_progress(summary["progress"]))
    lines.append("")
    lines.append("## 明显错误标注")
    if not anomalies:
        lines.append("未发现明显异常。")
    else:
        severity_map = {"high": "高", "medium": "中", "low": "低"}
        for item in anomalies:
            severity = severity_map.get(item["severity"], item["severity"])
            lines.append(f"- [{severity}] {item['code']}: {item['title']}")
    lines.append("")
    lines.append("## 标的贡献")
    if summary.get("top_symbols"):
        for item in summary["top_symbols"]:
            lines.append(f"- {item['symbol']}: {item['amount']:.4f}")
    else:
        lines.append("暂无标的贡献数据。")
    lines.append("")
    lines.append("## 全历史基准")
    lines.append(f"净值（仅费用）：{baseline['net_after_fees']:.4f}")
    lines.append(f"净值（费用+资金费率）：{baseline['net_after_fees_and_funding']:.4f}")
    return "\n".join(lines)


def _format_progress(progress: dict) -> str:
    status_map = {
        "insufficient_data": "数据不足",
        "improved": "显著改善",
        "deteriorated": "显著恶化",
        "flat": "变化不明显",
    }
    status = status_map.get(progress.get("status"), progress.get("status", "未知"))
    last_month = progress.get("last_month", "-")
    prev_month = progress.get("prev_month", "-")
    improvements = ", ".join(progress.get("improvements", [])) or "无"
    deteriorations = ", ".join(progress.get("deteriorations", [])) or "无"
    return f"状态：{status}（本期 {last_month} vs 上期 {prev_month}），改善项：{improvements}，恶化项：{deteriorations}"
