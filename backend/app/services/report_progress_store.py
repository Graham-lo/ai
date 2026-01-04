from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock


@dataclass
class ProgressState:
    status: str
    stage: str
    percent: int
    message: str
    error: str | None
    updated_at: str


_LOCK = Lock()
_STORE: dict[str, ProgressState] = {}


def set_progress(
    report_id: str,
    *,
    status: str,
    stage: str,
    percent: int,
    message: str = "",
    error: str | None = None,
) -> None:
    with _LOCK:
        _STORE[report_id] = ProgressState(
            status=status,
            stage=stage,
            percent=int(max(0, min(percent, 100))),
            message=message,
            error=error,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )


def get_progress(report_id: str) -> ProgressState | None:
    with _LOCK:
        return _STORE.get(report_id)


def clear_progress(report_id: str) -> None:
    with _LOCK:
        _STORE.pop(report_id, None)
