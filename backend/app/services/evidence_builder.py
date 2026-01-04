from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
from sqlalchemy.orm import Session

from app.attribution.joiner import build_trade_attribution_table
from app.connectors.binance_um import BinanceUMClient
from app.services.attribution_report import _build_bybit_df_from_db
from app.storage.cache import MarketDataCache
from app.storage.market_store import MarketDataStore


SCHEMA_VERSION = "1.2"
MARKET_STATE_MACHINE_VERSION = "1.1"


@dataclass
class FactsEvidenceResult:
    facts_path: str
    evidence_path: str
    evidence_json: dict


def build_facts_and_evidence(
    db: Session,
    account_ids: list[str],
    exchange_id: str | None,
    start: datetime | None,
    end: datetime | None,
    preset: str | None,
    symbols: list[str] | None = None,
    cache_dir: Path | None = None,
    output_dir: Path | None = None,
    report_id: str | None = None,
    anomalies: list[dict] | None = None,
    fetch_market: bool = True,
    include_market: bool = True,
) -> FactsEvidenceResult:
    if not start or not end:
        raise RuntimeError("start/end required for evidence generation")

    bybit_df, realized_present = _build_bybit_df_from_db(db, account_ids, exchange_id, start, end, symbols or [])
    symbols = symbols or sorted(set(bybit_df["symbol"].dropna().astype(str)))

    client = BinanceUMClient()
    cache = MarketDataCache(cache_dir or Path("outputs/market_cache"))
    market_store = MarketDataStore(db)

    facts = build_trade_attribution_table(
        bybit_df=bybit_df,
        client=client,
        cache=cache,
        start_ms=int(start.timestamp() * 1000),
        end_ms=int(end.timestamp() * 1000),
        symbols=symbols,
        market_store=market_store,
        fetch_market=fetch_market,
    )

    facts = _add_market_state(facts)
    facts = _normalize_facts(facts)

    output_root = output_dir or Path("outputs")
    output_root.mkdir(parents=True, exist_ok=True)
    tag = report_id or start.strftime("%Y%m%d%H%M%S")
    facts_path = output_root / f"facts_{tag}.parquet"
    facts.to_parquet(facts_path, index=False)

    evidence = build_evidence_from_facts(
        facts,
        start=start,
        end=end,
        preset=preset,
        realized_present=realized_present,
        anomalies=anomalies or [],
        include_market=include_market,
    )
    evidence_path = output_root / f"evidence_{tag}.json"
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    return FactsEvidenceResult(
        facts_path=str(facts_path),
        evidence_path=str(evidence_path),
        evidence_json=evidence,
    )


def build_evidence_from_facts(
    facts: pd.DataFrame,
    start: datetime,
    end: datetime,
    preset: str | None,
    realized_present: bool,
    anomalies: list[dict],
    include_market: bool,
) -> dict:
    facts = facts.copy()
    trades = int(len(facts))
    net_change = float(facts["pnl_net"].sum()) if trades else 0.0
    fees = float(facts["fee"].sum()) if trades else 0.0
    funding = float(facts.get("funding", pd.Series([0])).sum()) if trades else 0.0
    turnover = float(facts["turnover"].sum()) if trades else 0.0
    fee_bps = float((fees / turnover * 1e4) if turnover > 0 else 0.0)

    if include_market:
        market_regime_stats = {
            "trend_bucket": _ratio_map(facts, "trend_bucket"),
            "vol_bucket": _ratio_map(facts, "vol_bucket"),
            "oi_quadrant": _ratio_map(facts, "oi_quadrant"),
            "market_state": _ratio_map(facts, "market_state"),
        }
        perf = _performance_by_regime(facts)
    else:
        market_regime_stats = {}
        perf = {"top": [], "bottom": []}
    behavior_flags = {
        "after_big_loss_acceleration": {
            "trigger_ratio": float(facts.get("after_big_loss_flag", pd.Series([0])).mean() if trades else 0.0),
            "avg_accel_ratio": float(facts.get("trade_acceleration_score", pd.Series([0])).mean() if trades else 0.0),
        },
        "trade_clustering": {
            "cluster_score_avg": float(facts.get("trade_clustering", pd.Series([0])).mean() if trades else 0.0),
        },
        "taker_share_spike": {
            "spike_ratio": float(facts.get("taker_share_spike", pd.Series([0])).mean() if trades else 0.0),
        },
    }

    anomalies_summary = _anomaly_counts(anomalies)
    counterfactual = _counterfactual_stats(facts) if include_market else {}
    market_state_machine = _market_state_machine_summary(facts) if include_market else {
        "version": MARKET_STATE_MACHINE_VERSION,
        "constraints_by_state": {},
    }

    notes = []
    if not realized_present:
        notes.append("realized_pnl_missing")
    if not include_market:
        notes.append("market_data_missing")
    if facts.get("open_time").isna().any():
        notes.append("open_time_inferred")
    if "oi_proxy_24h" in facts.columns:
        notes.append("oi_sampled")

    return {
        "schema_version": SCHEMA_VERSION,
        "meta": {
            "range": {"start": start.isoformat(), "end": end.isoformat(), "preset": preset},
        },
        "account_summary": {
            "net_change": net_change,
            "fees": fees,
            "funding": funding,
            "turnover": turnover,
            "trades": trades,
            "fee_bps": fee_bps,
        },
        "market_regime_stats": market_regime_stats,
        "performance_by_regime": perf,
        "behavior_flags": behavior_flags,
        "anomalies": anomalies_summary,
        "counterfactual": counterfactual,
        "market_state_machine": market_state_machine,
        "notes": notes,
    }


def _performance_by_regime(facts: pd.DataFrame) -> dict:
    if facts.empty:
        return {"top": [], "bottom": []}
    grouped = facts.groupby("market_state").agg(
        expectancy_net=("pnl_net", "mean"),
        win_rate_net=("pnl_net", lambda x: float((x > 0).mean())),
        pf_net=("pnl_net", _profit_factor),
        tail_loss=("pnl_net", lambda x: float(x.quantile(0.05))),
        fee_bps=("fee_bps", "mean"),
        trades=("pnl_net", "count"),
    )
    ranked = grouped.sort_values("expectancy_net", ascending=False)
    top = _rows_from_group(ranked.head(3))
    bottom = _rows_from_group(ranked.tail(3).sort_values("expectancy_net"))
    return {"top": top, "bottom": bottom}


def _rows_from_group(df: pd.DataFrame) -> list[dict]:
    output = []
    for idx, row in df.iterrows():
        output.append(
            {
                "market_state": idx,
                "expectancy_net": float(row["expectancy_net"]),
                "win_rate_net": float(row["win_rate_net"]),
                "pf_net": float(row["pf_net"]),
                "tail_loss": float(row["tail_loss"]),
                "fee_bps": float(row["fee_bps"]),
                "trades": int(row["trades"]),
            }
        )
    return output


def _counterfactual_stats(facts: pd.DataFrame) -> dict:
    if facts.empty:
        return {
            "net_change_all": 0.0,
            "net_change_exclude_bottom": 0.0,
            "net_change_only_top": 0.0,
            "mdd_all": 0.0,
            "mdd_exclude_bottom": 0.0,
            "mdd_only_top": 0.0,
        }
    perf = _performance_by_regime(facts)
    top_states = {row["market_state"] for row in perf["top"]}
    bottom_states = {row["market_state"] for row in perf["bottom"]}
    net_all = float(facts["pnl_net"].sum())
    net_exclude_bottom = float(facts[~facts["market_state"].isin(bottom_states)]["pnl_net"].sum())
    net_only_top = float(facts[facts["market_state"].isin(top_states)]["pnl_net"].sum())
    mdd_all = _max_drawdown(facts)
    mdd_exclude_bottom = _max_drawdown(facts[~facts["market_state"].isin(bottom_states)])
    mdd_only_top = _max_drawdown(facts[facts["market_state"].isin(top_states)])
    return {
        "net_change_all": net_all,
        "net_change_exclude_bottom": net_exclude_bottom,
        "net_change_only_top": net_only_top,
        "mdd_all": mdd_all,
        "mdd_exclude_bottom": mdd_exclude_bottom,
        "mdd_only_top": mdd_only_top,
    }


def _ratio_map(facts: pd.DataFrame, col: str) -> dict:
    if col not in facts.columns or facts.empty:
        return {}
    ratios = facts[col].value_counts(normalize=True)
    return {str(key): float(value) for key, value in ratios.items()}


def _profit_factor(series: Iterable[float]) -> float:
    series = pd.Series(series)
    gains = series[series > 0].sum()
    losses = -series[series < 0].sum()
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)


def _anomaly_counts(anomalies: list[dict]) -> dict:
    if not anomalies:
        return {"total": 0, "by_code": {}}
    codes = [item.get("code", "UNKNOWN") for item in anomalies]
    counter = Counter(codes)
    return {"total": int(sum(counter.values())), "by_code": dict(counter)}


def _add_market_state(facts: pd.DataFrame) -> pd.DataFrame:
    if facts.empty:
        return facts
    def _get(col, default="na"):
        return facts[col] if col in facts.columns else default
    facts["market_state"] = (
        _get("trend_bucket", "na").astype(str)
        + "|"
        + _get("vol_bucket", "na").astype(str)
        + "|"
        + _get("oi_quadrant", "na").astype(str)
    )
    constraints = facts.apply(_market_state_constraints, axis=1)
    facts["state_constraints"] = [
        json.dumps(item, ensure_ascii=True, separators=(",", ":")) for item in constraints
    ]
    facts["state_machine_version"] = MARKET_STATE_MACHINE_VERSION
    return facts


def _normalize_facts(facts: pd.DataFrame) -> pd.DataFrame:
    if facts.empty:
        return facts
    facts = facts.copy()
    facts["open_time"] = facts["open_time"].fillna(0).astype("int64")
    facts["holding_seconds"] = facts["holding_seconds"].fillna(0).astype("int64")
    return facts


def _market_state_machine_summary(facts: pd.DataFrame) -> dict:
    if facts.empty:
        return {"version": MARKET_STATE_MACHINE_VERSION, "constraints_by_state": {}}
    unique = facts.drop_duplicates("market_state")
    constraints_by_state = {}
    for _, row in unique.iterrows():
        state = row["market_state"]
        constraints_by_state[state] = _market_state_constraints(row)
    return {"version": MARKET_STATE_MACHINE_VERSION, "constraints_by_state": constraints_by_state}


def _market_state_constraints(row: pd.Series) -> dict:
    trend_bucket = str(row.get("trend_bucket", "na"))
    vol_bucket = str(row.get("vol_bucket", "na"))
    oi_quadrant = str(row.get("oi_quadrant", "na"))

    if vol_bucket == "high":
        max_leverage = 1
        max_trades_2h = 3
        allow_aggressive_taker = 0
    elif vol_bucket == "mid":
        max_leverage = 2
        max_trades_2h = 6
        allow_aggressive_taker = 1
    elif vol_bucket == "low":
        max_leverage = 3
        max_trades_2h = 10
        allow_aggressive_taker = 1
    else:
        max_leverage = 2
        max_trades_2h = 5
        allow_aggressive_taker = 0

    if "oi_down" in oi_quadrant:
        max_leverage = max(1, max_leverage - 1)

    if trend_bucket == "trend":
        max_holding_seconds = 4 * 60 * 60
        max_position_adds = 3
    elif trend_bucket == "range":
        max_holding_seconds = 60 * 60
        max_position_adds = 1
    else:
        max_holding_seconds = 2 * 60 * 60
        max_position_adds = 2

    return {
        "max_leverage": max_leverage,
        "max_trades_2h": max_trades_2h,
        "max_holding_seconds": max_holding_seconds,
        "max_position_adds": max_position_adds,
        "allow_aggressive_taker": allow_aggressive_taker,
    }


def _max_drawdown(facts: pd.DataFrame) -> float:
    if facts.empty:
        return 0.0
    pnl = facts.sort_values("close_time")["pnl_net"].fillna(0)
    equity = pnl.cumsum()
    peak = equity.cummax()
    drawdown = equity - peak
    return float(abs(drawdown.min()))
