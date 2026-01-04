from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from app.db.models import BybitTradeLog
from app.schemas.ledger import Cashflow, Fill
from app.services.metrics import (
    compute_daily_series,
    compute_daily_series_from_trade_logs,
    compute_metrics,
    compute_metrics_from_trade_logs,
    max_drawdown,
    _trade_rows_from_logs,
)


def detect_anomalies(fills: list[Fill], cashflows: list[Cashflow]) -> list[dict]:
    metrics = compute_metrics(fills, cashflows)
    daily = compute_daily_series(fills, cashflows)
    anomalies: list[dict] = []

    window = _period_window(fills, cashflows)

    gross_profit = max(metrics.get("realized_pnl", 0), 0)
    if gross_profit and metrics.get("trading_fees", 0) > 0.3 * gross_profit:
        anomalies.append(
            {
                "code": "FEE_EATS_PROFIT",
                "severity": "high",
                "window": window,
                "evidence": {"trading_fees": metrics.get("trading_fees"), "gross_profit": gross_profit},
                "impact": {"amount": metrics.get("trading_fees"), "share_of_cost": 0.3},
            }
        )

    if metrics.get("funding_pnl", 0) < 0 and metrics.get("funding_intensity_bps", 0) > 5:
        anomalies.append(
            {
                "code": "FUNDING_DRAG",
                "severity": "medium",
                "window": window,
                "evidence": {
                    "funding_pnl": metrics.get("funding_pnl"),
                    "funding_bps": metrics.get("funding_intensity_bps"),
                },
                "impact": {"amount": metrics.get("funding_pnl"), "share_of_cost": 0.2},
            }
        )

    if daily:
        daily_net = [v.net_after_fees for v in daily.values()]
        mdd = max_drawdown(daily_net)
        loss_days = sorted(daily.items(), key=lambda kv: kv[1].net_after_fees)[:3]
        tail_loss = sum([abs(x[1].net_after_fees) for x in loss_days])
        if mdd > 0 and tail_loss / mdd > Decimal("0.5"):
            anomalies.append(
                {
                    "code": "TAIL_LOSS_DOMINATES",
                    "severity": "medium",
                    "window": window,
                    "evidence": {"top3_loss": float(tail_loss), "mdd": float(mdd)},
                    "impact": {"amount": float(tail_loss), "share_of_drawdown": float(tail_loss / mdd)},
                }
            )

        overtrade = _detect_overtrading(daily)
        if overtrade:
            anomalies.append(overtrade)

        revenge = _detect_revenge_cluster(daily)
        if revenge:
            anomalies.append(revenge)

    symbol_pnl = defaultdict(Decimal)
    for cf in cashflows:
        if cf.symbol:
            symbol_pnl[cf.symbol] += Decimal(str(cf.amount))
    if symbol_pnl:
        top_symbol, top_amount = max(symbol_pnl.items(), key=lambda kv: abs(kv[1]))
        total = sum(abs(v) for v in symbol_pnl.values())
        if total > 0 and abs(top_amount) / total > Decimal("0.7"):
            anomalies.append(
                {
                    "code": "CONCENTRATION_RISK",
                    "severity": "low",
                    "window": window,
                    "evidence": {"symbol": top_symbol, "share": float(abs(top_amount) / total)},
                    "impact": {"amount": float(top_amount), "share_of_drawdown": float(abs(top_amount) / total)},
                }
            )

    return anomalies


def detect_anomalies_from_trade_logs(trade_logs: list[BybitTradeLog]) -> list[dict]:
    metrics = compute_metrics_from_trade_logs(trade_logs)
    daily = compute_daily_series_from_trade_logs(trade_logs)
    anomalies: list[dict] = []

    window = _period_window_logs(trade_logs)

    gross_profit = max(metrics.get("realized_pnl", 0), 0)
    if gross_profit and metrics.get("trading_fees", 0) > 0.3 * gross_profit:
        anomalies.append(
            {
                "code": "FEE_EATS_PROFIT",
                "severity": "high",
                "window": window,
                "evidence": {"trading_fees": metrics.get("trading_fees"), "gross_profit": gross_profit},
                "impact": {"amount": metrics.get("trading_fees"), "share_of_cost": 0.3},
            }
        )

    if metrics.get("funding_pnl", 0) < 0 and metrics.get("funding_intensity_bps", 0) > 5:
        anomalies.append(
            {
                "code": "FUNDING_DRAG",
                "severity": "medium",
                "window": window,
                "evidence": {
                    "funding_pnl": metrics.get("funding_pnl"),
                    "funding_bps": metrics.get("funding_intensity_bps"),
                },
                "impact": {"amount": metrics.get("funding_pnl"), "share_of_cost": 0.2},
            }
        )

    if daily:
        daily_net = [v.net_after_fees for v in daily.values()]
        mdd = max_drawdown(daily_net)
        loss_days = sorted(daily.items(), key=lambda kv: kv[1].net_after_fees)[:3]
        tail_loss = sum([abs(x[1].net_after_fees) for x in loss_days])
        if mdd > 0 and tail_loss / mdd > Decimal("0.5"):
            anomalies.append(
                {
                    "code": "TAIL_LOSS_DOMINATES",
                    "severity": "medium",
                    "window": window,
                    "evidence": {"top3_loss": float(tail_loss), "mdd": float(mdd)},
                    "impact": {"amount": float(tail_loss), "share_of_drawdown": float(tail_loss / mdd)},
                }
            )

        overtrade = _detect_overtrading(daily)
        if overtrade:
            anomalies.append(overtrade)

        revenge = _detect_revenge_cluster(daily)
        if revenge:
            anomalies.append(revenge)

    symbol_pnl = defaultdict(Decimal)
    for row in _trade_rows_from_logs(trade_logs):
        if row.contract:
            symbol_pnl[row.contract] += Decimal(str(row.change or 0))
    if symbol_pnl:
        top_symbol, top_amount = max(symbol_pnl.items(), key=lambda kv: abs(kv[1]))
        total = sum(abs(v) for v in symbol_pnl.values())
        if total > 0 and abs(top_amount) / total > Decimal("0.7"):
            anomalies.append(
                {
                    "code": "CONCENTRATION_RISK",
                    "severity": "low",
                    "window": window,
                    "evidence": {"symbol": top_symbol, "share": float(abs(top_amount) / total)},
                    "impact": {"amount": float(top_amount), "share_of_drawdown": float(abs(top_amount) / total)},
                }
            )

    return anomalies


def _period_window(fills: list[Fill], cashflows: list[Cashflow]) -> dict:
    ts = [item.ts_utc for item in fills] + [item.ts_utc for item in cashflows]
    if not ts:
        return {}
    start = min(ts)
    end = max(ts)
    return {"start": start.isoformat(), "end": end.isoformat()}


def _period_window_logs(trade_logs: list[BybitTradeLog]) -> dict:
    ts = [item.ts_utc for item in trade_logs]
    if not ts:
        return {}
    start = min(ts)
    end = max(ts)
    return {"start": start.isoformat(), "end": end.isoformat()}


def _detect_overtrading(daily) -> dict | None:
    dates = sorted(daily.keys())
    if len(dates) < 8:
        return None
    mid = len(dates) // 2
    first = dates[:mid]
    second = dates[mid:]

    first_turnover = sum(daily[d].turnover for d in first)
    second_turnover = sum(daily[d].turnover for d in second)
    first_net = sum(daily[d].net_after_fees for d in first)
    second_net = sum(daily[d].net_after_fees for d in second)

    if first_turnover > 0 and second_turnover / first_turnover > Decimal("1.5") and second_net < first_net:
        return {
            "code": "OVERTRADING_NO_EDGE",
            "severity": "medium",
            "window": {"start": second[0].isoformat(), "end": second[-1].isoformat()},
            "evidence": {"turnover_up": float(second_turnover), "net_down": float(second_net - first_net)},
            "impact": {"amount": float(second_net - first_net), "share_of_cost": 0.1},
        }
    return None


def _detect_revenge_cluster(daily) -> dict | None:
    dates = sorted(daily.keys())
    if len(dates) < 3:
        return None

    worst_day = min(dates, key=lambda d: daily[d].net_after_fees)
    worst_idx = dates.index(worst_day)
    if worst_idx >= len(dates) - 1:
        return None

    next_day = dates[worst_idx + 1]
    trades = [daily[d].trades for d in dates]
    median_trades = sorted(trades)[len(trades) // 2]
    if daily[worst_day].net_after_fees < 0 and daily[next_day].trades > max(1, median_trades * 2):
        return {
            "code": "REVENGE_CLUSTER",
            "severity": "low",
            "window": {"start": next_day.isoformat(), "end": next_day.isoformat()},
            "evidence": {"next_day_trades": daily[next_day].trades, "median_trades": median_trades},
            "impact": {"amount": float(daily[next_day].net_after_fees), "share_of_cost": 0.05},
        }
    return None
