from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import ReportRun


def build_deepseek_payload(db: Session, report: ReportRun) -> dict:
    if report.evidence_json:
        return report.evidence_json
    if report.evidence_path:
        return json.loads(Path(report.evidence_path).read_text(encoding="utf-8"))
    raise RuntimeError("evidence_json missing")
