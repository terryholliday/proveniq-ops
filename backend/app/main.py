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
from app.api import attestations
from app.api import framework
from app.api import downstream
from app.api import food
from app.api import telemetry

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
app.include_router(attestations.router)  # Attestations API (Phase 2-3)
app.include_router(framework.router)  # Integrity Framework API (Phase 3-4)
app.include_router(downstream.router)  # Downstream Integration API (Phase 4-5)
app.include_router(food.router)  # Food Management API (Migration 008)
app.include_router(telemetry.router)  # Telemetry & Events API (P1: Data Gravity)


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
