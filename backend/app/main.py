"""PROVENIQ OPS - FastAPI Application.

Restaurant & Retail Inventory Operations (Bishop FSM)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth, admin
from app.modules.bishop import bishop_router
from app.api import inventory, vendors, decisions, predictions
from app.api import trust_tiers

app = FastAPI(
    title=settings.APP_NAME,
    description="PROVENIQ OPS - Restaurant & Retail Inventory Operations (Bishop FSM)",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
if settings.DEBUG:
    app.include_router(admin.router)
app.include_router(bishop_router)  # BISHOP module (restaurant/retail inventory)
app.include_router(inventory.router)  # Inventory API
app.include_router(vendors.router)  # Vendors API
app.include_router(decisions.router)  # Decision DAG API
app.include_router(predictions.router)  # ML Predictions API
app.include_router(trust_tiers.router)  # Trust Tiers API (Phase 1-2)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "PROVENIQ OPS",
        "version": "2.0.0",
        "spec": "Restaurant & Retail Inventory",
        "status": "operational",
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",  # TODO: Actually check DB connection
    }
