from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Cashflow, Fill, ReportRun
from app.schemas.ledger import Cashflow as CashflowSchema
from app.schemas.ledger import Fill as FillSchema
from app.services.metrics import compute_daily_series, compute_metrics


@dataclass
class SymbolAgg:
    turnover: Decimal = Decimal("0")
    trades: int = 0
    fees: Decimal = Decimal("0")
    funding: Decimal = Decimal("0")
    borrow_interest: Decimal = Decimal("0")
    rebates: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")


def _to_decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _sum(values: Iterable[Decimal]) -> Decimal:
    total = Decimal("0")
    for value in values:
        total += _to_decimal(value)
    return total


def _percentile(sorted_values: list[Decimal], p: float) -> Decimal:
    if not sorted_values:
        return Decimal("0")
    idx = int(round(p * (len(sorted_values) - 1)))
    return sorted_values[max(0, min(idx, len(sorted_values) - 1))]


def _quantiles(values: list[Decimal]) -> dict:
    if not values:
        return {"p50": None, "p75": None, "p90": None, "p95": None, "p99": None, "max": None, "min": None}
    sorted_values = sorted(values)
    return {
        "p50": float(_percentile(sorted_values, 0.50)),
        "p75": float(_percentile(sorted_values, 0.75)),
        "p90": float(_percentile(sorted_values, 0.90)),
        "p95": float(_percentile(sorted_values, 0.95)),
        "p99": float(_percentile(sorted_values, 0.99)),
        "max": float(max(sorted_values)),
        "min": float(min(sorted_values)),
    }


def build_deepseek_payload(db: Session, report: ReportRun, top_n: int = 5, sample_n: int = 20) -> dict:
    account_scope = report.account_scope or {}
    account_ids = account_scope.get("account_ids") or []
    exchange_id = account_scope.get("exchange_id")
    start = report.start
    end = report.end

    fills_query = db.query(Fill)
    cash_query = db.query(Cashflow)
    if account_ids:
        fills_query = fills_query.filter(Fill.account_id.in_(account_ids))
        cash_query = cash_query.filter(Cashflow.account_id.in_(account_ids))
    if exchange_id:
        fills_query = fills_query.filter(Fill.exchange_id == exchange_id)
        cash_query = cash_query.filter(Cashflow.exchange_id == exchange_id)
    if start:
        fills_query = fills_query.filter(Fill.ts_utc >= start)
        cash_query = cash_query.filter(Cashflow.ts_utc >= start)
    if end:
        fills_query = fills_query.filter(Fill.ts_utc <= end)
        cash_query = cash_query.filter(Cashflow.ts_utc <= end)

    fills = [FillSchema.model_validate(row) for row in fills_query.all()]
    cashflows = [CashflowSchema.model_validate(row) for row in cash_query.all()]

    period_metrics = report.summary_json.get("period") if report.summary_json else None
    if not period_metrics:
        period_metrics = compute_metrics(fills, cashflows)

    has_realized_pnl = any(cf.type == "realized_pnl" for cf in cashflows)
    data_quality = {
        "has_realized_pnl": has_realized_pnl,
        "unconverted_assets": sorted(
            set(period_metrics.get("unconverted_fee_assets", []) + period_metrics.get("unconverted_cashflow_assets", []))
        ),
        "notes": [],
    }

    if not has_realized_pnl:
        data_quality["notes"].append("缺失已实现盈亏，无法进行盈利能力与部分风险判断。")

    symbol_aggs: dict[str, SymbolAgg] = defaultdict(SymbolAgg)
    for fill in fills:
        agg = symbol_aggs[fill.symbol]
        agg.turnover += _to_decimal(fill.notional)
        agg.trades += 1
        agg.fees += abs(_to_decimal(fill.fee))

    for cf in cashflows:
        if not cf.symbol:
            continue
        agg = symbol_aggs[cf.symbol]
        if cf.type == "funding":
            agg.funding += _to_decimal(cf.amount)
        elif cf.type == "borrow_interest":
            agg.borrow_interest += abs(_to_decimal(cf.amount))
        elif cf.type == "rebate":
            agg.rebates += _to_decimal(cf.amount)
        elif cf.type == "realized_pnl":
            agg.realized_pnl += _to_decimal(cf.amount)

    symbol_rows = []
    for symbol, agg in symbol_aggs.items():
        turnover = float(agg.turnover)
        net_after_fees = agg.realized_pnl + agg.rebates - agg.fees - agg.borrow_interest
        net_after_fees_and_funding = net_after_fees + agg.funding
        fee_bps = float((agg.fees / agg.turnover * Decimal("10000")) if agg.turnover > 0 else Decimal("0"))
        symbol_rows.append(
            {
                "symbol": symbol,
                "net_fees_only": float(net_after_fees),
                "net_fees_plus_funding": float(net_after_fees_and_funding),
                "turnover": turnover,
                "trades": agg.trades,
                "fee_bps": fee_bps,
            }
        )

    top_profit = sorted(symbol_rows, key=lambda row: row["net_fees_plus_funding"], reverse=True)[:top_n]
    top_loss = sorted(symbol_rows, key=lambda row: row["net_fees_plus_funding"])[:top_n]
    full_top = sorted(symbol_rows, key=lambda row: row["turnover"], reverse=True)[: max(10, top_n)]

    month_aggs: dict[str, SymbolAgg] = defaultdict(SymbolAgg)
    for fill in fills:
        month_key = fill.ts_utc.strftime("%Y-%m")
        agg = month_aggs[month_key]
        agg.turnover += _to_decimal(fill.notional)
        agg.trades += 1
        agg.fees += abs(_to_decimal(fill.fee))

    for cf in cashflows:
        month_key = cf.ts_utc.strftime("%Y-%m")
        agg = month_aggs[month_key]
        if cf.type == "funding":
            agg.funding += _to_decimal(cf.amount)
        elif cf.type == "borrow_interest":
            agg.borrow_interest += abs(_to_decimal(cf.amount))
        elif cf.type == "rebate":
            agg.rebates += _to_decimal(cf.amount)
        elif cf.type == "realized_pnl":
            agg.realized_pnl += _to_decimal(cf.amount)

    by_month = []
    for month_key in sorted(month_aggs.keys()):
        agg = month_aggs[month_key]
        net_after_fees = agg.realized_pnl + agg.rebates - agg.fees - agg.borrow_interest
        net_after_fees_and_funding = net_after_fees + agg.funding
        fee_bps = float((agg.fees / agg.turnover * Decimal("10000")) if agg.turnover > 0 else Decimal("0"))
        funding_bps = float((abs(agg.funding) / agg.turnover * Decimal("10000")) if agg.turnover > 0 else Decimal("0"))
        by_month.append(
            {
                "month": month_key,
                "turnover": float(agg.turnover),
                "trades": agg.trades,
                "trading_fees": float(agg.fees),
                "funding_pnl": float(agg.funding),
                "net_after_fees": float(net_after_fees),
                "net_after_fees_and_funding": float(net_after_fees_and_funding),
                "fee_bps": fee_bps,
                "funding_intensity_bps": funding_bps,
            }
        )

    maker_turnover = Decimal("0")
    taker_turnover = Decimal("0")
    maker_fees = Decimal("0")
    taker_fees = Decimal("0")
    for fill in fills:
        if fill.maker_taker == "maker":
            maker_turnover += _to_decimal(fill.notional)
            maker_fees += abs(_to_decimal(fill.fee))
        elif fill.maker_taker == "taker":
            taker_turnover += _to_decimal(fill.notional)
            taker_fees += abs(_to_decimal(fill.fee))

    total_turnover = maker_turnover + taker_turnover
    taker_share = float(taker_turnover / total_turnover) if total_turnover > 0 else 0.0

    execution = {
        "maker_taker": {
            "taker_turnover": float(taker_turnover),
            "maker_turnover": float(maker_turnover),
            "taker_share": taker_share,
            "taker_fees": float(taker_fees),
            "maker_fees": float(maker_fees),
        },
        "open_vs_close": {
            "open_turnover": 0.0,
            "close_turnover": 0.0,
            "open_fee_bps": 0.0,
            "close_fee_bps": 0.0,
            "open_trades": 0,
            "close_trades": 0,
        },
    }
    data_quality["notes"].append("缺少开平字段，无法区分开仓/平仓结构。")

    realized_values = [_to_decimal(cf.amount) for cf in cashflows if cf.type == "realized_pnl"]
    close_pnl_quantiles = {"gross": _quantiles(realized_values), "net": _quantiles(realized_values)}
    if not realized_values:
        data_quality["notes"].append("缺少逐笔已实现盈亏样本，无法生成平仓分布。")

    daily_series = compute_daily_series(fills, cashflows)
    daily_rows = []
    fees_by_day: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    funding_by_day: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    for fill in fills:
        d = fill.ts_utc.date()
        fees_by_day[d] += abs(_to_decimal(fill.fee))
    for cf in cashflows:
        d = cf.ts_utc.date()
        if cf.type == "funding":
            funding_by_day[d] += _to_decimal(cf.amount)
        elif cf.type == "commission":
            fees_by_day[d] += abs(_to_decimal(cf.amount))

    for day_key in sorted(daily_series.keys()):
        daily = daily_series[day_key]
        daily_rows.append(
            {
                "date": day_key.isoformat(),
                "net_after_fees": float(daily.net_after_fees),
                "net_after_fees_and_funding": float(daily.net_after_fees_and_funding),
                "fees": float(fees_by_day.get(day_key, Decimal("0"))),
                "funding": float(funding_by_day.get(day_key, Decimal("0"))),
            }
        )

    drawdown_windows = _max_drawdown_windows(daily_rows, cashflows)

    worst_closes = _sample_realized(realized_values, cashflows, sample_n, reverse=False)
    best_closes = _sample_realized(realized_values, cashflows, sample_n, reverse=True)

    scores = _score_radar(period_metrics, by_month, drawdown_windows, taker_share, report.anomalies_json, has_realized_pnl)

    return {
        "meta": {
            "range": {"start": report.start.isoformat() if report.start else None, "end": report.end.isoformat() if report.end else None, "preset": report.preset},
            "account_scope": {"account_ids": account_ids, "exchange_id": exchange_id},
            "base_currency": settings.BASE_CURRENCY,
            "net_modes_available": ["fees_only", "fees_plus_funding"],
            "data_quality": data_quality,
        },
        "kpis": {
            "turnover": period_metrics.get("turnover"),
            "trades": period_metrics.get("trades"),
            "trading_fees": period_metrics.get("trading_fees"),
            "funding_pnl": period_metrics.get("funding_pnl"),
            "borrow_interest": period_metrics.get("borrow_interest"),
            "rebates": period_metrics.get("rebates"),
            "realized_pnl": period_metrics.get("realized_pnl"),
            "net_after_fees": period_metrics.get("net_after_fees"),
            "net_after_fees_and_funding": period_metrics.get("net_after_fees_and_funding"),
            "fee_bps": period_metrics.get("fee_rate_bps"),
            "funding_intensity_bps": period_metrics.get("funding_intensity_bps"),
        },
        "breakdowns": {
            "by_symbol": {"top_profit": top_profit, "top_loss": top_loss, "full_topN": full_top},
            "by_month": by_month,
            "execution": execution,
        },
        "distributions": {
            "close_pnl_quantiles": close_pnl_quantiles,
            "daily_net_series": daily_rows,
            "drawdown_windows": drawdown_windows,
        },
        "samples": {"worst_closes": worst_closes, "best_closes": best_closes},
        "rules": {"anomalies": report.anomalies_json or []},
        "scores": scores,
    }


def _max_drawdown_windows(daily_rows: list[dict], cashflows: list[CashflowSchema]) -> list[dict]:
    if not daily_rows:
        return []

    cumulative = 0.0
    peak = 0.0
    peak_date = daily_rows[0]["date"]
    max_dd = 0.0
    dd_start = daily_rows[0]["date"]
    dd_end = daily_rows[0]["date"]

    for row in daily_rows:
        cumulative += row["net_after_fees_and_funding"]
        if cumulative >= peak:
            peak = cumulative
            peak_date = row["date"]
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
            dd_start = peak_date
            dd_end = row["date"]

    contributors = defaultdict(Decimal)
    if max_dd > 0:
        for cf in cashflows:
            date_str = cf.ts_utc.date().isoformat()
            if dd_start <= date_str <= dd_end and cf.symbol:
                contributors[cf.symbol] += _to_decimal(cf.amount)

    top_contributors = sorted(contributors.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
    return [
        {
            "start": dd_start,
            "end": dd_end,
            "mdd": float(max_dd),
            "top_contributors": [{"symbol": sym, "contrib": float(val)} for sym, val in top_contributors],
        }
    ]


def _sample_realized(values: list[Decimal], cashflows: list[CashflowSchema], sample_n: int, reverse: bool) -> list[dict]:
    if not values:
        return []
    realized_rows = [cf for cf in cashflows if cf.type == "realized_pnl"]
    realized_rows.sort(key=lambda row: row.amount, reverse=reverse)
    output = []
    for row in realized_rows[:sample_n]:
        output.append(
            {
                "time": row.ts_utc.isoformat(),
                "symbol": row.symbol or "UNKNOWN",
                "side": "N/A",
                "pnl_gross": float(row.amount),
                "fees": 0.0,
                "pnl_net": float(row.amount),
                "turnover": 0.0,
            }
        )
    return output


def _score_radar(
    period_metrics: dict,
    by_month: list[dict],
    drawdown_windows: list[dict],
    taker_share: float,
    anomalies: list[dict],
    has_realized_pnl: bool,
) -> dict:
    turnover = period_metrics.get("turnover") or 0.0
    net_after_fees = period_metrics.get("net_after_fees") or 0.0
    fee_bps = period_metrics.get("fee_rate_bps") or 0.0
    funding_bps = period_metrics.get("funding_intensity_bps") or 0.0
    mdd = drawdown_windows[0]["mdd"] if drawdown_windows else 0.0

    positive_months = 0
    for row in by_month:
        if row.get("net_after_fees", 0) > 0:
            positive_months += 1
    consistency = (positive_months / max(len(by_month), 1)) * 10

    tail_loss_share = min(1.0, (mdd / max(abs(net_after_fees), 1.0))) if mdd else 0.0

    edge_score = None
    consistency_score = None
    if has_realized_pnl:
        edge_score = _clamp(5 + (net_after_fees / max(turnover, 1.0)) * 100)
        consistency_score = _clamp(consistency)

    execution_score = _clamp(10 - (fee_bps / 5) - (taker_share * 3))
    risk_score = _clamp(10 - (mdd / max(turnover, 1.0)) * 1000 - (tail_loss_share * 3))

    discipline_hits = sum(1 for item in anomalies if item.get("code") in {"OVERTRADING_NO_EDGE", "REVENGE_CLUSTER"})
    discipline_score = _clamp(10 - discipline_hits * 2)

    concentration_score = _clamp(10 - (funding_bps / 50))

    values = [edge_score, execution_score, risk_score, consistency_score, discipline_score, concentration_score]

    return {
        "radar_6d": {
            "axes": ["Edge", "Execution", "Risk", "Consistency", "Discipline", "Concentration"],
            "values": values,
            "explain": {
                "Edge": "由净值与成交额占比估算；缺失已实现盈亏时置空。",
                "Execution": "由 fee_bps 与 taker_share 估算。",
                "Risk": "由最大回撤与尾部损失占比估算。",
                "Consistency": "由正收益月份占比估算；缺失已实现盈亏时置空。",
                "Discipline": "由过度交易/报复性交易等规则触发估算。",
                "Concentration": "由资金费率强度与集中风险近似。",
            },
        }
    }


def _clamp(value: float) -> float:
    return max(0.0, min(10.0, value))
