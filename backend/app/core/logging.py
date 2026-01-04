import logging
from typing import Any


SENSITIVE_KEYS = {"api_secret", "secret", "passphrase", "password"}


def _redact(value: Any) -> Any:
    if value is None:
        return None
    return "***" if isinstance(value, str) else value


def redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    return {k: (_redact(v) if k in SENSITIVE_KEYS else v) for k, v in data.items()}


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
