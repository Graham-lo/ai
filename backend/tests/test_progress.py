from datetime import datetime, timezone
from decimal import Decimal

from app.schemas.ledger import Cashflow, Fill
from app.services.progress import monthly_aggregate


def test_monthly_aggregate_groups():
    fills = [
        Fill(
            ts_utc=datetime(2024, 1, 10, tzinfo=timezone.utc),
            exchange_id="bybit",
            account_id="1",
            account_type="linear",
            symbol="BTCUSDT",
            side="buy",
            price=Decimal("100"),
            qty=Decimal("1"),
            notional=Decimal("100"),
            fee=Decimal("0.1"),
            fee_asset="USDT",
        )
    ]
    cashflows = [
        Cashflow(
            ts_utc=datetime(2024, 1, 10, tzinfo=timezone.utc),
            exchange_id="bybit",
            account_id="1",
            account_type="linear",
            type="realized_pnl",
            amount=Decimal("1.0"),
            asset="USDT",
        )
    ]
    result = monthly_aggregate(fills, cashflows)
    assert result[0].month == "2024-01"
