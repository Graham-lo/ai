from datetime import datetime, timezone
from decimal import Decimal

from app.schemas.ledger import Cashflow, Fill
from app.services.anomalies import detect_anomalies


def test_fee_eats_profit():
    fills = [
        Fill(
            ts_utc=datetime.now(timezone.utc),
            exchange_id="bybit",
            account_id="1",
            account_type="linear",
            symbol="BTCUSDT",
            side="buy",
            price=Decimal("100"),
            qty=Decimal("1"),
            notional=Decimal("100"),
            fee=Decimal("1"),
            fee_asset="USDT",
        )
    ]
    cashflows = [
        Cashflow(
            ts_utc=datetime.now(timezone.utc),
            exchange_id="bybit",
            account_id="1",
            account_type="linear",
            type="realized_pnl",
            amount=Decimal("2"),
            asset="USDT",
        )
    ]
    anomalies = detect_anomalies(fills, cashflows)
    assert any(a["code"] == "FEE_EATS_PROFIT" for a in anomalies)
