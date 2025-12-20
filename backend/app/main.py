"""PROVENIQ OPS - FastAPI Application.

Spec v1.1: Landlord Vector - Zero-CAC tenant acquisition
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import landlord, tenant, auth
from app.modules.bishop import bishop_router

app = FastAPI(
    title=settings.APP_NAME,
    description="PROVENIQ OPS - Landlord Vector & Tenant Management API (Spec v1.1)",
    version="1.1.0",
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
app.include_router(auth.router)  # Auth first (magic link exchange)
app.include_router(landlord.router)
app.include_router(tenant.router)
app.include_router(bishop_router)  # BISHOP module (restaurant/retail inventory)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "PROVENIQ OPS",
        "version": "1.1.0",
        "spec": "v1.1 Landlord Vector",
        "status": "operational",
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",  # TODO: Actually check DB connection
    }
