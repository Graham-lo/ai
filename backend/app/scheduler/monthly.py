from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.db.session import SessionLocal
from app.schemas.report import ReportRequest
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
