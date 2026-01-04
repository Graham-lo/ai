from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.db.session import SessionLocal
from app.schemas.report import ReportRequest
from app.services.market_sync import parse_market_sync_symbols, resolve_market_sync_range, sync_market_data
from app.storage.cache import MarketDataCache
from app.storage.market_store import MarketDataStore
from app.services.report_service import run_report
from app.services.sync_service import run_sync


_scheduler: BackgroundScheduler | None = None


def start_monthly_scheduler() -> None:
    global _scheduler
    if _scheduler:
        return
    _scheduler = BackgroundScheduler(timezone=settings.APP_TIMEZONE)
    _scheduler.add_job(_run_monthly_report, CronTrigger(day=1, hour=0, minute=10))
    if settings.SYNC_INTERVAL_MINUTES > 0:
        _scheduler.add_job(
            _run_periodic_sync,
            IntervalTrigger(minutes=settings.SYNC_INTERVAL_MINUTES),
            id="periodic_sync",
            replace_existing=True,
        )
    if settings.MARKET_SYNC_INTERVAL_MINUTES > 0 and parse_market_sync_symbols():
        _scheduler.add_job(
            _run_market_sync,
            IntervalTrigger(minutes=settings.MARKET_SYNC_INTERVAL_MINUTES),
            id="periodic_market_sync",
            replace_existing=True,
        )
    _scheduler.start()


def _run_monthly_report() -> None:
    db = SessionLocal()
    try:
        payload = ReportRequest(preset="last_month", net_mode="fees_only")
        run_report(db, payload)
    finally:
        db.close()


def _run_periodic_sync() -> None:
    db = SessionLocal()
    try:
        payload = ReportRequest(preset=settings.SYNC_PRESET)
        run_sync(db, payload)
    finally:
        db.close()


def _run_market_sync() -> None:
    db = SessionLocal()
    try:
        symbols = parse_market_sync_symbols()
        if not symbols:
            return
        start, end = resolve_market_sync_range()
        if not start or not end:
            return
        cache = MarketDataCache("outputs/market_cache")
        store = MarketDataStore(db)
        sync_market_data(store, cache, symbols, start, end)
    finally:
        db.close()
