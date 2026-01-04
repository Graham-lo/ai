from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass
class WindowConfig:
    label: str
    window_ms: int
    kline_window: int


def build_kline_features(df: pd.DataFrame, window: int, prefix: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["open_time", f"trend_score_{prefix}", f"vol_bucket_{prefix}"])
    data = df.sort_values("open_time").copy()
    close = data["close"]
    ma = close.rolling(window=window, min_periods=max(3, window // 3)).mean()
    slope = ma.diff().rolling(window=window, min_periods=1).mean()
    dev = (close - ma) / ma.replace(0, np.nan)
    rolling_max = close.rolling(window=window, min_periods=1).max()
    breakout = (close - rolling_max) / rolling_max.replace(0, np.nan)
    score = (0.6 * dev.fillna(0) + 0.3 * slope.fillna(0) + 0.1 * breakout.fillna(0)).clip(-1, 1)
    data[f"trend_score_{prefix}"] = score
    vol = (data["high"] - data["low"]) / close.replace(0, np.nan)
    data[f"vol_bucket_{prefix}"] = _bucket_from_quantiles(vol.fillna(0))
    return data[["open_time", f"trend_score_{prefix}", f"vol_bucket_{prefix}"]]


def funding_bucket_for_times(
    funding_df: pd.DataFrame, times_ms: Iterable[int], window_ms: int, prefix: str
) -> pd.Series:
    if funding_df.empty:
        return pd.Series(["na"] * len(list(times_ms)), name=f"funding_bucket_{prefix}")
    funding = funding_df.sort_values("funding_time").copy()
    rates = []
    for ts in times_ms:
        start = ts - window_ms
        window_rates = funding[(funding["funding_time"] >= start) & (funding["funding_time"] <= ts)]
        if window_rates.empty:
            rates.append(np.nan)
        else:
            rates.append(window_rates["funding_rate"].mean())
    rates_arr = np.array(rates, dtype=float)
    abs_rates = np.abs(funding["funding_rate"].values)
    extreme_thr = np.quantile(abs_rates, 0.9) if abs_rates.size else 0.0
    buckets = []
    for rate in rates_arr:
        if np.isnan(rate):
            buckets.append("na")
        elif rate > 0 and abs(rate) >= extreme_thr:
            buckets.append("pos_extreme")
        elif rate < 0 and abs(rate) >= extreme_thr:
            buckets.append("neg_extreme")
        elif rate > 0:
            buckets.append("pos")
        elif rate < 0:
            buckets.append("neg")
        else:
            buckets.append("flat")
    return pd.Series(buckets, name=f"funding_bucket_{prefix}")


def oi_proxy_for_times(
    oi_df: pd.DataFrame, times_ms: Iterable[int], window_ms: int, prefix: str
) -> pd.Series:
    if oi_df.empty:
        return pd.Series(["na"] * len(list(times_ms)), name=f"oi_proxy_{prefix}")
    oi = oi_df.sort_values("timestamp").copy()
    buckets = []
    values = oi["sum_open_interest"].values
    if values.size:
        abs_change = np.abs(np.diff(values))
        change_thr = np.quantile(abs_change, 0.7) if abs_change.size else 0.0
    else:
        change_thr = 0.0
    for ts in times_ms:
        start = ts - window_ms
        window = oi[(oi["timestamp"] >= start) & (oi["timestamp"] <= ts)]
        if len(window) < 2:
            buckets.append("na")
            continue
        delta = float(window["sum_open_interest"].iloc[-1] - window["sum_open_interest"].iloc[0])
        if delta > change_thr:
            buckets.append("up")
        elif delta < -change_thr:
            buckets.append("down")
        else:
            buckets.append("flat")
    return pd.Series(buckets, name=f"oi_proxy_{prefix}")


def _bucket_from_quantiles(series: pd.Series) -> pd.Series:
    q1 = series.quantile(0.33)
    q2 = series.quantile(0.66)
    def to_bucket(value: float) -> str:
        if value <= q1:
            return "low"
        if value <= q2:
            return "mid"
        return "high"
    return series.fillna(0).apply(to_bucket)
