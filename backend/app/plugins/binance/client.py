from typing import Any


class BinanceClient:
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://api.binance.com") -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")

    def fetch_trades(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("TODO: Implement Binance REST calls")

    def fetch_cashflows(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("TODO: Implement Binance REST calls")
