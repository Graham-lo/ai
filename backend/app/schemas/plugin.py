from pydantic import BaseModel


class PluginOut(BaseModel):
    exchange_id: str
    display_name: str
    auth_fields: list[dict]
    account_types: list[str]
    capabilities: dict
    notes: list[str]
