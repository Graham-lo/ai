from datetime import datetime, timezone
from decimal import Decimal

from app.schemas.ledger import Cashflow, Fill
from app.services.metrics import compute_metrics


def test_metrics_fee_and_funding_split():
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
            fee=Decimal("0.1"),
            fee_asset="USDT",
        )
    ]
    cashflows = [
        Cashflow(
            ts_utc=datetime.now(timezone.utc),
            exchange_id="bybit",
            account_id="1",
            account_type="linear",
            type="funding",
            amount=Decimal("-0.2"),
            asset="USDT",
        ),
        Cashflow(
            ts_utc=datetime.now(timezone.utc),
            exchange_id="bybit",
            account_id="1",
            account_type="linear",
            type="realized_pnl",
            amount=Decimal("1.0"),
            asset="USDT",
        ),
    ]
    metrics = compute_metrics(fills, cashflows)
    assert metrics["trading_fees"] == 0.1
    assert metrics["funding_pnl"] == -0.2
    assert metrics["net_after_fees"] == 0.9
    assert metrics["net_after_fees_and_funding"] == 0.7
