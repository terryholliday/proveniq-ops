from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/assets", status_code=501)
def post_asset():
    raise HTTPException(status_code=501, detail="Not implemented")
