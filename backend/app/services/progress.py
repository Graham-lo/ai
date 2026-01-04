from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from app.db.models import BybitTradeLog
from app.schemas.ledger import Cashflow, Fill
from app.services.metrics import (
    compute_daily_series,
    compute_daily_series_from_trade_logs,
    compute_metrics,
    compute_metrics_from_trade_logs,
    max_drawdown,
)


@dataclass
class MonthlySummary:
    month: str
    metrics: dict


def monthly_aggregate(fills: list[Fill], cashflows: list[Cashflow]) -> list[MonthlySummary]:
    grouped_fills: dict[str, list[Fill]] = defaultdict(list)
    grouped_cash: dict[str, list[Cashflow]] = defaultdict(list)

    for fill in fills:
        key = fill.ts_utc.strftime("%Y-%m")
        grouped_fills[key].append(fill)
    for cf in cashflows:
        key = cf.ts_utc.strftime("%Y-%m")
        grouped_cash[key].append(cf)

    summaries = []
    for key in sorted(grouped_fills.keys() | grouped_cash.keys()):
        metrics = compute_metrics(grouped_fills.get(key, []), grouped_cash.get(key, []))
        daily_series = compute_daily_series(grouped_fills.get(key, []), grouped_cash.get(key, []))
        mdd = max_drawdown([v.net_after_fees_and_funding for v in daily_series.values()])
        metrics["max_drawdown"] = float(mdd)
        summaries.append(MonthlySummary(month=key, metrics=metrics))
    return summaries


def monthly_aggregate_from_trade_logs(trade_logs: list[BybitTradeLog]) -> list[MonthlySummary]:
    grouped: dict[str, list[BybitTradeLog]] = defaultdict(list)

    for row in trade_logs:
        key = row.ts_utc.strftime("%Y-%m")
        grouped[key].append(row)

    summaries = []
    for key in sorted(grouped.keys()):
        metrics = compute_metrics_from_trade_logs(grouped.get(key, []))
        daily_series = compute_daily_series_from_trade_logs(grouped.get(key, []))
        mdd = max_drawdown([v.net_after_fees_and_funding for v in daily_series.values()])
        metrics["max_drawdown"] = float(mdd)
        summaries.append(MonthlySummary(month=key, metrics=metrics))
    return summaries


def detect_progress(monthly: list[MonthlySummary]) -> dict:
    if len(monthly) < 2:
        return {"status": "insufficient_data"}

    last = monthly[-1].metrics
    prev = monthly[-2].metrics

    trades_ok = last.get("trades", 0) >= 200

    improvements = []
    deteriorations = []

    if trades_ok and last.get("fee_rate_bps", 0) < prev.get("fee_rate_bps", 0):
        improvements.append("fee_bps_down")
    if trades_ok and last.get("max_drawdown", 0) < prev.get("max_drawdown", 0):
        improvements.append("mdd_down")
    if trades_ok and last.get("net_after_fees", 0) > prev.get("net_after_fees", 0):
        improvements.append("expectancy_up")

    if trades_ok and last.get("max_drawdown", 0) > prev.get("max_drawdown", 0) and last.get("fee_rate_bps", 0) > prev.get("fee_rate_bps", 0):
        deteriorations.append("mdd_up_fee_bps_up")
    if trades_ok and last.get("funding_intensity_bps", 0) > prev.get("funding_intensity_bps", 0):
        deteriorations.append("funding_intensity_up")

    status = "flat"
    if improvements:
        status = "improved"
    if len(deteriorations) >= 2:
        status = "deteriorated"

    return {
        "status": status,
        "improvements": improvements,
        "deteriorations": deteriorations,
        "last_month": monthly[-1].month,
        "prev_month": monthly[-2].month,
    }


def rolling_compare(fills: list[Fill], cashflows: list[Cashflow], window_days: int) -> dict:
    daily = compute_daily_series(fills, cashflows)
    dates = sorted(daily.keys())
    if len(dates) < window_days * 2:
        return {"status": "insufficient_data"}

    def sum_window(start: int, end: int) -> Decimal:
        total = Decimal("0")
        for d in dates[start:end]:
            total += daily[d].net_after_fees
        return total

    recent = sum_window(-window_days, None)
    prev = sum_window(-window_days * 2, -window_days)

    status = "flat"
    if recent > prev:
        status = "improved"
    elif recent < prev:
        status = "deteriorated"

    return {"status": status, "recent": float(recent), "previous": float(prev)}


def rolling_compare_from_trade_logs(trade_logs: list[BybitTradeLog], window_days: int) -> dict:
    daily = compute_daily_series_from_trade_logs(trade_logs)
    dates = sorted(daily.keys())
    if len(dates) < window_days * 2:
        return {"status": "insufficient_data"}

    def sum_window(start: int, end: int) -> Decimal:
        total = Decimal("0")
        for d in dates[start:end]:
            total += daily[d].net_after_fees
        return total

    recent = sum_window(-window_days, None)
    prev = sum_window(-window_days * 2, -window_days)

    status = "flat"
    if recent > prev:
        status = "improved"
    elif recent < prev:
        status = "deteriorated"

    return {"status": status, "recent": float(recent), "previous": float(prev)}
