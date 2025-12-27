from typing import Optional

from fastapi import APIRouter

router = APIRouter()


@router.get("/assets/{asset_id}/lineage")
def get_lineage(asset_id: str, cursor: Optional[str] = None, limit: Optional[int] = None):
    return {"asset_id": asset_id, "cursor": cursor, "limit": limit, "events": []}
