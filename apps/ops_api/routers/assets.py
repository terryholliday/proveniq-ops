import uuid

from fastapi import APIRouter, HTTPException

from apps.ops_api.domain import storage
from apps.ops_api.domain.db import async_session_maker
from apps.ops_api.domain.event_crypto import genesis_prev_hash

router = APIRouter()


@router.post("/assets", status_code=501)
def post_asset():
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/assets/{asset_id}/tip")
async def get_asset_tip(asset_id: str):
    entity_id = "dev-entity"

    try:
        uuid.UUID(asset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="asset_id")

    async with async_session_maker() as session:
        res = await storage.read_asset_tip(session, asset_id, entity_id)
        row = res.first()
        if row is None:
            return {"asset_id": asset_id, "aggregate_version": 0, "event_hash": genesis_prev_hash()}

        return {"asset_id": asset_id, "aggregate_version": int(row[0]), "event_hash": str(row[1])}
