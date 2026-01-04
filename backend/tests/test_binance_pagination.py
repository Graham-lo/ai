from __future__ import annotations

from app.connectors.binance_um import BinanceUMClient


def test_klines_pagination(monkeypatch):
    client = BinanceUMClient()
    all_items = []
    start = 0
    for i in range(3):
        open_time = start + i * 60_000
        close_time = open_time + 59_000
        all_items.append(
            [
                open_time,
                "1.0",
                "1.0",
                "1.0",
                "1.0",
                "1.0",
                close_time,
                "1.0",
                1,
                "0.5",
                "0.5",
            ]
        )

    def fake_get(_path, params):
        start_time = params["startTime"]
        end_time = params["endTime"]
        limit = params["limit"]
        candidates = [item for item in all_items if item[0] >= start_time and item[0] <= end_time]
        return candidates[:limit]

    monkeypatch.setattr(client, "_get", fake_get)
    rows = client.get_klines("ETHUSDT", "1m", 0, 180_000, limit=2)
    times = sorted({row["open_time"] for row in rows})
    assert times == [0, 60_000, 120_000]
