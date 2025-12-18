"""
PROVENIQ Ops - FastAPI Application Entry Point
B2B Inventory & Operations Management Platform

Bishop: Operational intelligence interface (deterministic FSM)
Vendor Bridge: Multi-vendor aggregation with failover
Ecosystem: Ledger, ClaimsIQ, Capital (mocked)
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import bishop, inventory, mocks, receiving, stockout, vendors
from app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    print("PROVENIQ Ops initializing...")
    print(f"Environment: {settings.app_env}")
    print("Bishop FSM: IDLE")
    print("Bishop Stockout Engine: Ready")
    print("Bishop Receiving Engine: Ready")
    print("Vendor Bridge: Ready")
    print("Mock systems: Ledger, ClaimsIQ, Capital")
    yield
    # Shutdown
    print("PROVENIQ Ops shutting down...")


app = FastAPI(
    title="PROVENIQ Ops",
    description="""
## B2B Inventory & Operations Management Platform

**Synthetic Precision** — faster than human perception, anticipatory rather than reactive.

### Core Systems

- **Bishop FSM** — Deterministic operational intelligence interface
- **Bishop Stockout Engine** — Predictive stockout alerts with burn rate analysis
- **Bishop Receiving Engine** — Smart scan-to-PO reconciliation
- **Vendor Bridge** — Multi-vendor aggregation with automatic failover
- **Synthetic Eye** — AR inventory scanning (mobile integration)
- **Smart Par Engine** — Intelligent reorder recommendations

### External System Mocks

| System | Purpose | Status |
|--------|---------|--------|
| Ledger | Cash & liquidity verification | Mocked |
| ClaimsIQ | Risk & liability assessment | Mocked |
| Capital | Inventory financing | Future hook |

### Bishop States

- `IDLE` — Awaiting directive
- `SCANNING` — Inventory capture in progress
- `ANALYZING_RISK` — ClaimsIQ risk evaluation
- `CHECKING_FUNDS` — Ledger balance verification
- `ORDER_QUEUED` — Order dispatched to vendor
    """,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware for mobile app integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(bishop.router, prefix="/api/v1")
app.include_router(stockout.router, prefix="/api/v1")
app.include_router(receiving.router, prefix="/api/v1")
app.include_router(vendors.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
app.include_router(mocks.router, prefix="/api/v1")


@app.get("/", tags=["Health"])
async def root() -> dict:
    """Root endpoint - system status."""
    return {
        "system": "PROVENIQ Ops",
        "status": "operational",
        "version": "0.1.0",
        "bishop": "IDLE",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "environment": settings.app_env,
        "debug": settings.debug,
    }
