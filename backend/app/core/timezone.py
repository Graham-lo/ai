from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings


UTC = timezone.utc
LOCAL_TZ = ZoneInfo(settings.APP_TIMEZONE)


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(UTC)


def to_local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(LOCAL_TZ)


def now_utc() -> datetime:
    return datetime.now(tz=UTC)
