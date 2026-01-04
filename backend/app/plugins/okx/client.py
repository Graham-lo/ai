from typing import Any


class OKXClient:
    def __init__(self, api_key: str, api_secret: str, passphrase: str, base_url: str = "https://www.okx.com") -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.base_url = base_url.rstrip("/")

    def fetch_fills(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("TODO: Implement OKX REST calls")

    def fetch_cashflows(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("TODO: Implement OKX REST calls")
