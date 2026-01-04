from __future__ import annotations

import json
from datetime import datetime, timezone

from openai import OpenAI

from app.core.config import settings
from app.db.models import ReportRun
from app.services.deepseek_prompts import (
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_ANALYZE,
    USER_PROMPT_ANALYZE_TEMPLATE,
    USER_PROMPT_TEMPLATE,
)


def build_report_payload(report: ReportRun) -> dict:
    summary = report.summary_json or {}
    period = summary.get("period", {})
    scope = summary.get("scope", {})
    max_drawdown = summary.get("max_drawdown", {})

    data_quality = []
    if period.get("realized_pnl", 0) == 0:
        data_quality.append("缺失已实现盈亏（realized_pnl=0），净值仅成本口径。")
    if period.get("unconverted_fee_assets"):
        data_quality.append(f"手续费未折算币种: {', '.join(period.get('unconverted_fee_assets', []))}")
    if period.get("unconverted_cashflow_assets"):
        data_quality.append(f"资金流水未折算币种: {', '.join(period.get('unconverted_cashflow_assets', []))}")
    if not data_quality:
        data_quality.append("无明显缺失项。")

    report_md_raw = report.report_md or ""
    if len(report_md_raw) > 4000:
        report_md_raw = report_md_raw[:4000] + "..."

    return {
        "meta": {
            "range": {"start": scope.get("start"), "end": scope.get("end"), "preset": scope.get("preset")},
            "base_currency": scope.get("base_currency"),
            "net_mode": report.net_mode,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_quality": data_quality,
        },
        "headline_cards": {
            "net_after_fees": period.get("net_after_fees"),
            "net_after_fees_and_funding": period.get("net_after_fees_and_funding"),
            "trading_fees": period.get("trading_fees"),
            "funding_pnl": period.get("funding_pnl"),
            "trades": period.get("trades"),
            "turnover": period.get("turnover"),
        },
        "cost_breakdown": {
            "trading_fees": period.get("trading_fees"),
            "funding_pnl": period.get("funding_pnl"),
            "borrow_interest": period.get("borrow_interest"),
            "rebates": period.get("rebates"),
        },
        "efficiency": {
            "fee_rate_bps": period.get("fee_rate_bps"),
            "funding_intensity_bps": period.get("funding_intensity_bps"),
            "cost_share_fee": period.get("cost_share_fee"),
            "max_drawdown": max_drawdown,
        },
        "anomalies": report.anomalies_json or [],
        "report_md_raw": report_md_raw,
    }


def generate_deepseek_markdown(
    payload: dict,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 3000,
) -> tuple[str, str]:
    resolved_key = (api_key or settings.DEEPSEEK_API_KEY).strip()
    if not resolved_key:
        raise RuntimeError("DEEPSEEK_API_KEY not configured")

    resolved_base_url = base_url or settings.DEEPSEEK_BASE_URL
    resolved_model = model or settings.DEEPSEEK_MODEL

    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
    prompt = USER_PROMPT_TEMPLATE.format(payload_json_pretty=payload_json)

    client = OpenAI(api_key=resolved_key, base_url=resolved_base_url)
    response = client.chat.completions.create(
        model=resolved_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content or ""
    return content.strip(), resolved_model


def generate_deepseek_analysis(
    payload: dict,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 3500,
) -> tuple[str, dict, str]:
    resolved_key = (api_key or settings.DEEPSEEK_API_KEY).strip()
    if not resolved_key:
        raise RuntimeError("DEEPSEEK_API_KEY not configured")

    resolved_base_url = base_url or settings.DEEPSEEK_BASE_URL
    resolved_model = model or settings.DEEPSEEK_MODEL

    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
    prompt = USER_PROMPT_ANALYZE_TEMPLATE.format(payload_json_pretty=payload_json)

    client = OpenAI(api_key=resolved_key, base_url=resolved_base_url)
    response = client.chat.completions.create(
        model=resolved_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_ANALYZE},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content or ""
    try:
        report_md, chart_spec = _parse_analysis_output(content)
    except Exception:
        report_md = content.strip()
        chart_spec = {"charts": []}
    if not isinstance(chart_spec, dict) or "charts" not in chart_spec:
        chart_spec = {"charts": []}
    return report_md, chart_spec, resolved_model


def _parse_analysis_output(content: str) -> tuple[str, dict]:
    def _extract(tag_start: str, tag_end: str) -> str | None:
        if tag_start not in content or tag_end not in content:
            return None
        start = content.index(tag_start) + len(tag_start)
        end = content.index(tag_end, start)
        return content[start:end].strip()

    report_md = _extract("<<<REPORT_MD>>>", "<<<END_REPORT_MD>>>")
    chart_json = _extract("<<<CHART_SPEC_JSON>>>", "<<<END_CHART_SPEC_JSON>>>")

    if chart_json:
        try:
            chart_spec = json.loads(chart_json)
        except json.JSONDecodeError:
            chart_spec = {"charts": []}
    else:
        chart_spec = _try_extract_chart_spec(content)
    if not isinstance(chart_spec, dict) or "charts" not in chart_spec:
        chart_spec = {"charts": []}

    if not report_md:
        report_md = content.strip()

    return report_md, chart_spec


def _try_extract_chart_spec(content: str) -> dict:
    marker = "\"charts\""
    idx = content.find(marker)
    if idx == -1:
        return {"charts": []}
    start = content.rfind("{", 0, idx)
    if start == -1:
        return {"charts": []}
    brace = 0
    end = None
    for i in range(start, len(content)):
        if content[i] == "{":
            brace += 1
        elif content[i] == "}":
            brace -= 1
            if brace == 0:
                end = i + 1
                break
    if end is None:
        return {"charts": []}
    try:
        return json.loads(content[start:end])
    except json.JSONDecodeError:
        return {"charts": []}
