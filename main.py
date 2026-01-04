from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.attribution.joiner import (
    build_trade_attribution_table,
    load_bybit_trade_log,
    save_trade_attribution,
    to_month_tag,
    to_utc_ms,
)
from app.connectors.binance_um import BinanceUMClient
from app.reports.monthly_report import ReportMeta, build_monthly_report
from app.storage.cache import MarketDataCache


def main() -> None:
    parser = argparse.ArgumentParser(description="Bybit x Binance attribution report")
    parser.add_argument("--bybit_csv", required=True, help="Bybit UM transaction log CSV path")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--symbols", default="", help="Comma-separated symbols")
    parser.add_argument("--report", default="monthly", choices=["monthly"], help="Report type")
    args = parser.parse_args()

    start_dt = _parse_date(args.start)
    end_dt = _parse_date(args.end, end_of_day=True)
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    output_dir = Path("outputs")
    cache_dir = output_dir / "market_cache"

    bybit_df = load_bybit_trade_log(args.bybit_csv)
    client = BinanceUMClient()
    cache = MarketDataCache(cache_dir)

    for month_start, month_end in _iter_months(start_dt, end_dt):
        month_tag = to_month_tag(month_start)
        attribution = build_trade_attribution_table(
            bybit_df=bybit_df,
            client=client,
            cache=cache,
            start_ms=to_utc_ms(month_start),
            end_ms=to_utc_ms(month_end),
            symbols=symbols,
        )
        save_trade_attribution(attribution, output_dir, month_tag)
        report = build_monthly_report(
            attribution,
            ReportMeta(month_tag=month_tag, start=month_start, end=month_end),
        )
        report_path = output_dir / f"report_{month_tag}.md"
        report_path.write_text(report, encoding="utf-8")
        print(f"Saved {report_path}")


def _parse_date(value: str, end_of_day: bool = False) -> datetime:
    dt = datetime.fromisoformat(value)
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59)
    return dt.replace(tzinfo=timezone.utc)


def _iter_months(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    months: list[tuple[datetime, datetime]] = []
    cursor = datetime(start.year, start.month, 1, tzinfo=timezone.utc)
    while cursor <= end:
        next_month = _next_month(cursor)
        month_start = max(start, cursor)
        month_end = min(end, next_month - _one_second())
        months.append((month_start, month_end))
        cursor = next_month
    return months


def _next_month(dt: datetime) -> datetime:
    year = dt.year + (1 if dt.month == 12 else 0)
    month = 1 if dt.month == 12 else dt.month + 1
    return datetime(year, month, 1, tzinfo=timezone.utc)


def _one_second() -> timedelta:
    return timedelta(seconds=1)


if __name__ == "__main__":
    main()
