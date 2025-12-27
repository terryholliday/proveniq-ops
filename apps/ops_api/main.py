from fastapi import FastAPI
from apps.ops_api.routers import assets, events, lineage

app = FastAPI(title="PROVENIQ Ops API", version="1.3.1")

app.include_router(assets.router, prefix="/v1/ops", tags=["assets"])
app.include_router(events.router, prefix="/v1/ops", tags=["events"])
app.include_router(lineage.router, prefix="/v1/ops", tags=["lineage"])
