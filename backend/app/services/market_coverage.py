from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Fill, MarketKline, MarketMarkKline, MarketOpenInterest
from app.schemas.market import MarketCoverageRequest
from app.services.report_service import resolve_range, _resolve_data_range


@dataclass
class CoverageItem:
    min_time: int | None
    max_time: int | None
    ok: bool


def compute_market_coverage(db: Session, payload: MarketCoverageRequest) -> dict:
    notes: list[str] = []
    start, end = resolve_range(payload)
    account_ids = payload.account_ids or []
    if account_ids:
        start, end = _resolve_data_range(
            db=db,
            account_ids=account_ids,
            exchange_id=payload.exchange_id,
            start=start,
            end=end,
        )

    symbols = payload.symbols or _resolve_symbols(db, payload, start, end)
    if not start or not end:
        notes.append("range_unresolved")
    if not symbols:
        notes.append("symbols_empty")

    start_ms = int(start.timestamp() * 1000) if start else None
    end_ms = int(end.timestamp() * 1000) if end else None

    coverage = {
        "klines": _coverage_by_interval(db, MarketKline, symbols, ["1m", "5m", "1h"], start_ms, end_ms),
        "mark_klines": _coverage_by_interval(db, MarketMarkKline, symbols, ["1m", "5m", "1h"], start_ms, end_ms),
    }
    if settings.ENABLE_OI_FETCH:
        coverage["open_interest"] = _coverage_single(
            db, MarketOpenInterest, symbols, start_ms, end_ms, time_col="timestamp"
        )
    else:
        notes.append("oi_fetch_disabled")

    missing = _missing_from_coverage(coverage)
    has_market = not missing and (not notes or _only_oi_disabled(notes))

    return {
        "start": start,
        "end": end,
        "symbols": symbols,
        "has_market": has_market,
        "coverage": coverage,
        "missing": missing,
        "notes": notes,
    }


def _resolve_symbols(
    db: Session, payload: MarketCoverageRequest, start, end
) -> list[str]:
    query = db.query(Fill.symbol).distinct()
    if payload.account_ids:
        query = query.filter(Fill.account_id.in_(payload.account_ids))
    if payload.exchange_id:
        query = query.filter(Fill.exchange_id == payload.exchange_id)
    if start:
        query = query.filter(Fill.ts_utc >= start)
    if end:
        query = query.filter(Fill.ts_utc <= end)
    return [row[0] for row in query.all() if row[0]]


def _coverage_by_interval(
    db: Session,
    model,
    symbols: list[str],
    intervals: list[str],
    start_ms: int | None,
    end_ms: int | None,
) -> dict:
    output: dict[str, dict[str, CoverageItem]] = {}
    for interval in intervals:
        output[interval] = {}
        for symbol in symbols:
            min_ts, max_ts = db.query(
                func.min(model.open_time), func.max(model.open_time)
            ).filter(model.symbol == symbol, model.interval == interval).one()
            ok = _range_ok(min_ts, max_ts, start_ms, end_ms)
            output[interval][symbol] = CoverageItem(min_ts, max_ts, ok)
    return _to_dict(output)


def _coverage_single(
    db: Session,
    model,
    symbols: list[str],
    start_ms: int | None,
    end_ms: int | None,
    *,
    time_col: str,
) -> dict:
    output: dict[str, CoverageItem] = {}
    col = getattr(model, time_col)
    for symbol in symbols:
        min_ts, max_ts = db.query(func.min(col), func.max(col)).filter(model.symbol == symbol).one()
        ok = _range_ok(min_ts, max_ts, start_ms, end_ms)
        output[symbol] = CoverageItem(min_ts, max_ts, ok)
    return _to_dict(output)


def _range_ok(min_ts: int | None, max_ts: int | None, start_ms: int | None, end_ms: int | None) -> bool:
    if min_ts is None or max_ts is None or start_ms is None or end_ms is None:
        return False
    tol_ms = int(settings.MARKET_COVERAGE_TOLERANCE_MINUTES) * 60 * 1000
    start_ok = min_ts <= (start_ms + tol_ms)
    end_ok = max_ts >= (end_ms - tol_ms)
    return start_ok and end_ok


def _missing_from_coverage(coverage: dict) -> dict:
    missing: dict = {}
    for key, value in coverage.items():
        if not value:
            missing[key] = "no_data"
            continue
        if _is_symbol_coverage(value):
            miss_symbols = [sym for sym, item in value.items() if not item["ok"]]
            if miss_symbols:
                missing[key] = miss_symbols
            continue
        if _is_interval_coverage(value):
            if key in {"klines", "mark_klines"}:
                miss_symbols = []
                for symbol in _collect_symbols(value):
                    if not _any_interval_ok(value, symbol):
                        miss_symbols.append(symbol)
                if miss_symbols:
                    missing[key] = miss_symbols
            else:
                missing_intervals = {}
                for interval, symbols in value.items():
                    miss_symbols = [sym for sym, item in symbols.items() if not item["ok"]]
                    if miss_symbols:
                        missing_intervals[interval] = miss_symbols
                if missing_intervals:
                    missing[key] = missing_intervals
            continue
        missing[key] = "invalid_shape"
    return missing


def _is_symbol_coverage(value: dict) -> bool:
    if not value:
        return False
    return all(isinstance(item, dict) and "ok" in item for item in value.values())


def _is_interval_coverage(value: dict) -> bool:
    if not value:
        return False
    if not all(isinstance(item, dict) for item in value.values()):
        return False
    for symbols in value.values():
        if not symbols:
            continue
        if not all(isinstance(item, dict) and "ok" in item for item in symbols.values()):
            return False
    return True


def _collect_symbols(value: dict) -> list[str]:
    symbols = set()
    for symbols_map in value.values():
        if isinstance(symbols_map, dict):
            symbols.update(symbols_map.keys())
    return sorted(symbols)


def _any_interval_ok(value: dict, symbol: str) -> bool:
    for symbols_map in value.values():
        if not isinstance(symbols_map, dict):
            continue
        item = symbols_map.get(symbol)
        if isinstance(item, dict) and item.get("ok"):
            return True
    return False


def _only_oi_disabled(notes: list[str]) -> bool:
    if not notes:
        return False
    allowed = {"oi_fetch_disabled"}
    return all(note in allowed for note in notes)


def _to_dict(data: dict) -> dict:
    output = {}
    for key, value in data.items():
        if isinstance(value, dict):
            output[key] = _to_dict(value)
        elif isinstance(value, CoverageItem):
            output[key] = {"min_time": value.min_time, "max_time": value.max_time, "ok": value.ok}
        else:
            output[key] = value
    return output
