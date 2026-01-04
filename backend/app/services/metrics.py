from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from app.core.config import settings
from app.schemas.ledger import Cashflow, Fill


EPS = Decimal("1e-9")


@dataclass
class DailyNet:
    net_after_fees: Decimal = Decimal("0")
    net_after_fees_and_funding: Decimal = Decimal("0")
    turnover: Decimal = Decimal("0")
    trades: int = 0


def _to_decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def sum_decimal(values: Iterable[Decimal]) -> Decimal:
    total = Decimal("0")
    for value in values:
        total += _to_decimal(value)
    return total


def compute_metrics(fills: list[Fill], cashflows: list[Cashflow]) -> dict:
    base = settings.BASE_CURRENCY
    turnover = sum_decimal([fill.notional for fill in fills])
    trades = len(fills)

    commission_flows = [cf for cf in cashflows if cf.type == "commission"]
    if commission_flows:
        trading_fees = sum_decimal([abs(cf.amount) for cf in commission_flows])
    else:
        trading_fees = sum_decimal([abs(fill.fee) for fill in fills])

    funding_pnl = sum_decimal([cf.amount for cf in cashflows if cf.type == "funding"])
    borrow_interest = sum_decimal([abs(cf.amount) for cf in cashflows if cf.type == "borrow_interest"])
    rebates = sum_decimal([cf.amount for cf in cashflows if cf.type == "rebate"])
    realized_pnl = sum_decimal([cf.amount for cf in cashflows if cf.type == "realized_pnl"])

    net_after_fees = realized_pnl + rebates - trading_fees - borrow_interest
    net_after_fees_and_funding = net_after_fees + funding_pnl

    fee_rate_bps = (trading_fees / turnover * Decimal("10000")) if turnover > 0 else Decimal("0")
    funding_intensity_bps = (abs(funding_pnl) / turnover * Decimal("10000")) if turnover > 0 else Decimal("0")

    gross_profit = realized_pnl if realized_pnl > 0 else Decimal("0")
    denom = max(abs(realized_pnl), gross_profit, EPS)
    cost_share_fee = trading_fees / denom

    unconverted_fee_assets = sorted({fill.fee_asset for fill in fills if fill.fee_asset and fill.fee_asset != base})
    unconverted_cashflow_assets = sorted({cf.asset for cf in cashflows if cf.asset and cf.asset != base})

    return {
        "turnover": float(turnover),
        "trades": trades,
        "trading_fees": float(trading_fees),
        "funding_pnl": float(funding_pnl),
        "borrow_interest": float(borrow_interest),
        "rebates": float(rebates),
        "realized_pnl": float(realized_pnl),
        "net_after_fees": float(net_after_fees),
        "net_after_fees_and_funding": float(net_after_fees_and_funding),
        "fee_rate_bps": float(fee_rate_bps),
        "funding_intensity_bps": float(funding_intensity_bps),
        "cost_share_fee": float(cost_share_fee),
        "unconverted_fee_assets": unconverted_fee_assets,
        "unconverted_cashflow_assets": unconverted_cashflow_assets,
    }


def compute_daily_series(fills: list[Fill], cashflows: list[Cashflow]) -> dict[date, DailyNet]:
    daily: dict[date, DailyNet] = defaultdict(DailyNet)

    for fill in fills:
        d = fill.ts_utc.date()
        daily[d].turnover += _to_decimal(fill.notional)
        daily[d].trades += 1
        daily[d].net_after_fees -= abs(_to_decimal(fill.fee))
        daily[d].net_after_fees_and_funding -= abs(_to_decimal(fill.fee))

    for cf in cashflows:
        d = cf.ts_utc.date()
        amount = _to_decimal(cf.amount)
        if cf.type == "funding":
            daily[d].net_after_fees_and_funding += amount
        elif cf.type == "commission":
            daily[d].net_after_fees -= abs(amount)
            daily[d].net_after_fees_and_funding -= abs(amount)
        elif cf.type == "borrow_interest":
            daily[d].net_after_fees -= abs(amount)
            daily[d].net_after_fees_and_funding -= abs(amount)
        elif cf.type == "rebate":
            daily[d].net_after_fees += amount
            daily[d].net_after_fees_and_funding += amount
        elif cf.type == "realized_pnl":
            daily[d].net_after_fees += amount
            daily[d].net_after_fees_and_funding += amount
        else:
            daily[d].net_after_fees += amount
            daily[d].net_after_fees_and_funding += amount

    return daily


def max_drawdown(net_curve: list[Decimal]) -> Decimal:
    peak = Decimal("0")
    max_dd = Decimal("0")
    cumulative = Decimal("0")
    for value in net_curve:
        cumulative += value
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
    return max_dd
