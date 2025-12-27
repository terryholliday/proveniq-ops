from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.ops_api.routers import assets, events, lineage

app = FastAPI(title="PROVENIQ Ops API", version="1.3.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assets.router, prefix="/v1/ops", tags=["assets"])
app.include_router(events.router, prefix="/v1/ops", tags=["events"])
app.include_router(lineage.router, prefix="/v1/ops", tags=["lineage"])
