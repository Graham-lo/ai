from __future__ import annotations

import numpy as np
import pandas as pd


def add_behavior_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    data = df.sort_values("close_time").copy()
    times = data["close_time"].values
    big_loss_flag = []
    accel_score = []
    recent_taker = []
    cluster_score = []
    taker_spike = []
    window_2h = 2 * 60 * 60 * 1000
    window_24h = 24 * 60 * 60 * 1000
    window_10m = 10 * 60 * 1000
    loss_threshold = -100.0
    for idx, ts in enumerate(times):
        start_2h = ts - window_2h
        start_24h = ts - window_24h
        start_10m = ts - window_10m
        recent_mask_2h = (times >= start_2h) & (times < ts)
        recent_mask_24h = (times >= start_24h) & (times < ts)
        recent_mask_10m = (times >= start_10m) & (times < ts)
        recent_losses = data.loc[recent_mask_2h, "pnl_net"]
        big_loss_flag.append(int((recent_losses < loss_threshold).any()))
        count_2h = int(recent_mask_2h.sum())
        count_24h = int(recent_mask_24h.sum())
        count_10m = int(recent_mask_10m.sum())
        baseline = max(count_24h / 12.0, 1.0)
        accel_score.append(round(count_2h / baseline, 4))
        cluster_baseline = max(count_24h / 144.0, 1.0)
        cluster_score.append(round(count_10m / cluster_baseline, 4))
        start_idx = max(0, idx - 20)
        taker_slice = data["taker_proxy"].iloc[start_idx:idx]
        if taker_slice.empty:
            recent_taker.append(0.0)
        else:
            recent_taker.append(float(taker_slice.mean()))
        baseline_slice = data["taker_proxy"].iloc[max(0, idx - 100) : idx]
        baseline_taker = float(baseline_slice.mean()) if not baseline_slice.empty else 0.0
        taker_spike.append(int(recent_taker[-1] - baseline_taker > 0.2))
    data["after_big_loss_flag"] = big_loss_flag
    data["trade_acceleration_score"] = accel_score
    data["recent_taker_share"] = recent_taker
    data["trade_clustering"] = cluster_score
    data["taker_share_spike"] = taker_spike
    return data
