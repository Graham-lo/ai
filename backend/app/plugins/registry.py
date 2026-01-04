import importlib
import json
from pathlib import Path

from app.plugins.base import Adapter, Manifest


PLUGIN_DIR = Path(__file__).resolve().parent


def list_manifests() -> list[Manifest]:
    manifests: list[Manifest] = []
    for manifest_path in PLUGIN_DIR.glob("*/manifest.json"):
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifests.append(Manifest(**data))
    return manifests


def get_adapter(exchange_id: str) -> Adapter:
    module = importlib.import_module(f"app.plugins.{exchange_id}.adapter")
    return module.AdapterImpl()
