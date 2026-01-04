from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timezone import LOCAL_TZ, now_utc
from app.core.crypto import decrypt_dict
from app.db.models import Account, Cashflow, Fill, SyncRun
from app.plugins.registry import get_adapter
from app.schemas.report import ReportRequest


PRESETS = {
    "last_7d": timedelta(days=7),
    "last_30d": timedelta(days=30),
    "this_month": "this_month",
    "last_month": "last_month",
    "ytd": "ytd",
    "all_time": None,
}


def _insert_ignore(session: Session, model, rows: list[dict]) -> int:
    if not rows:
        return 0
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        stmt = pg_insert(model).values(rows).on_conflict_do_nothing()
        result = session.execute(stmt)
        return result.rowcount or 0
    stmt = insert(model).values(rows)
    if dialect == "sqlite":
        stmt = stmt.prefix_with("OR IGNORE")
    result = session.execute(stmt)
    return result.rowcount or 0


def run_sync(db: Session, payload: ReportRequest) -> dict:
    accounts_query = db.query(Account).filter(Account.is_enabled.is_(True))
    if payload.account_ids:
        accounts_query = accounts_query.filter(Account.id.in_(payload.account_ids))
    if payload.exchange_id:
        accounts_query = accounts_query.filter(Account.exchange_id == payload.exchange_id)
    accounts = accounts_query.all()

    start_dt, end_dt = _resolve_sync_range(payload)

    sync_run = SyncRun(
        account_scope={"account_ids": [str(acc.id) for acc in accounts], "exchange_id": payload.exchange_id},
        start=start_dt,
        end=end_dt,
        preset=payload.preset,
        status="running",
        counts={},
    )
    db.add(sync_run)
    db.commit()
    db.refresh(sync_run)

    total_fills = 0
    total_cashflows = 0
    try:
        for account in accounts:
            adapter = get_adapter(account.exchange_id)
            credentials = decrypt_dict(account.credentials_encrypted)
            options = dict(account.options or {})
            options["account_id"] = str(account.id)
            options["exchange_id"] = account.exchange_id
            if account.account_types:
                options["account_type"] = account.account_types[0]
            per_start, per_end = _account_range(start_dt, end_dt, account.created_at)
            if per_start and per_end and per_start >= per_end:
                continue
            total_fills += _sync_kind(db, adapter, adapter.fetch_fills, Fill, credentials, options, per_start, per_end)
            total_cashflows += _sync_kind(
                db, adapter, adapter.fetch_cashflows, Cashflow, credentials, options, per_start, per_end
            )

        sync_run.status = "completed"
        sync_run.counts = {"fills": total_fills, "cashflows": total_cashflows}
        db.commit()
    except Exception as exc:  # noqa: BLE001
        sync_run.status = "failed"
        sync_run.error = str(exc)
        db.commit()
        raise

    return {"fills": total_fills, "cashflows": total_cashflows, "status": sync_run.status}


def _sync_kind(
    db: Session,
    adapter,
    fetch_fn,
    model,
    credentials: dict[str, Any],
    options: dict[str, Any],
    start_dt: datetime | None,
    end_dt: datetime | None,
) -> int:
    policy = adapter.rate_limit_policy()
    min_interval = policy.get("min_interval_ms", 250) / 1000
    max_retries = policy.get("max_retries", 3)
    max_window_days = policy.get("max_window_days")

    total = 0
    windows = _build_windows(start_dt, end_dt, max_window_days)
    for window_start, window_end in windows:
        cursor = None
        while True:
            last_exc: Exception | None = None
            for attempt in range(max_retries):
                try:
                    items, cursor = fetch_fn(
                        credentials,
                        options,
                        _to_ms(window_start),
                        _to_ms(window_end),
                        cursor,
                    )
                    break
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    time.sleep(min_interval * (2**attempt))
            else:
                detail = f"Max retries exceeded. Last error: {last_exc}" if last_exc else "Max retries exceeded"
                raise RuntimeError(detail)

            rows = [item.model_dump() for item in items]
            total += _insert_ignore(db, model, rows)
            db.commit()
            if not cursor:
                break
            time.sleep(min_interval)
    return total


def _resolve_sync_range(payload: ReportRequest) -> tuple[datetime | None, datetime | None]:
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
    if payload.preset == "all_time":
        end = now_utc()
        start = end - timedelta(days=729)
        return start, end
    return payload.start, payload.end


def _build_windows(
    start_dt: datetime | None,
    end_dt: datetime | None,
    max_window_days: int | None,
) -> list[tuple[datetime | None, datetime | None]]:
    if not start_dt or not end_dt or not max_window_days:
        return [(start_dt, end_dt)]
    windows: list[tuple[datetime, datetime]] = []
    cursor = start_dt
    while cursor < end_dt:
        window_end = min(cursor + timedelta(days=max_window_days), end_dt)
        windows.append((cursor, window_end))
        cursor = window_end
    return windows


def _to_ms(dt: datetime | None) -> int | None:
    if not dt:
        return None
    return int(dt.timestamp() * 1000)


def _account_range(
    start_dt: datetime | None,
    end_dt: datetime | None,
    created_at: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    start = _normalize_dt(start_dt)
    end = _normalize_dt(end_dt)
    created = _normalize_dt(created_at)
    if created and start:
        start = max(start, created)
    elif created and not start:
        start = created
    return start, end


def _normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
