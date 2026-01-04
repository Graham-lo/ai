from __future__ import annotations

import pandas as pd

from app.features.market_features import build_kline_features


def test_kline_bucket_extreme():
    df = pd.DataFrame(
        {
            "open_time": [0, 60_000, 120_000, 180_000],
            "open": [1, 1, 1, 1],
            "high": [1, 1, 1, 1],
            "low": [1, 1, 1, 1],
            "close": [1, 1, 1, 1],
        }
    )
    out = build_kline_features(df, window=3, prefix="30m")
    assert set(out["vol_bucket_30m"]).issubset({"low", "mid", "high"})
