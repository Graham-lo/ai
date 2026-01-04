from fastapi import APIRouter, Depends

from app.api.deps import require_token
from app.plugins.registry import list_manifests

router = APIRouter()


@router.get("", dependencies=[Depends(require_token)])
async def get_plugins():
    return [manifest.model_dump() for manifest in list_manifests()]
