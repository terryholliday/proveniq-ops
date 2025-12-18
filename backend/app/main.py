"""
PROVENIQ Ops - FastAPI Application Entry Point
B2B Inventory & Operations Management Platform

Bishop: Operational intelligence interface (deterministic FSM)
Vendor Bridge: Multi-vendor aggregation with failover
Ecosystem: Ledger, ClaimsIQ, Capital (mocked)

RULE: OpenAPI is the single source of truth.
      If it's not in /openapi.json, it doesn't exist.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.api import audit, auditready, benchmark, bishop, bulk, cashflow, costdelay, custody, dag, expiration, ghost, inventory, memory, menucost, mocks, pricewatch, rebalance, receiving, scananomaly, stockout, vendors, vendorscore, vision, whatif
from app.core.config import get_settings

settings = get_settings()


# =============================================================================
# OPENAPI CONFIGURATION - SINGLE SOURCE OF TRUTH
# =============================================================================

API_VERSION = "1.0.0"
API_TITLE = "PROVENIQ Ops"

OPENAPI_TAGS = [
    {
        "name": "Health",
        "description": "System health and status endpoints",
    },
    {
        "name": "Bishop FSM",
        "description": "Bishop Finite State Machine control. Deterministic operational intelligence.",
        "externalDocs": {
            "description": "Bishop DAG Specification",
            "url": "/api/v1/dag/mermaid",
        },
    },
    {
        "name": "DAG Governance",
        "description": "Bishop Decision DAG inspection and validation. The DAG is the single source of truth for Bishop logic.",
    },
    {
        "name": "Bulk Normalization",
        "description": "N5: Canonical Unit Model. Base/Handling/Measurement layers with confidence scoring.",
    },
    {
        "name": "Vision Estimation",
        "description": "Photo-assisted bulk inventory. Container library, confidence math, force-weigh rules.",
    },
    {
        "name": "What-If Simulator",
        "description": "Scenario simulation. ADVISORY ONLY - never executes actions.",
    },
    {
        "name": "Decision Memory",
        "description": "Record decisions and outcomes. Memory informs but never overrides policy.",
    },
    {
        "name": "Chain of Custody",
        "description": "Track high-risk item movement. Traceability, not surveillance.",
    },
    {
        "name": "Audit Readiness",
        "description": "Detect compliance gaps before audits. Evidence tracking and remediation.",
    },
    {
        "name": "Cost of Delay",
        "description": "Quantify financial impact of inaction. Savings vs. downstream risk costs.",
    },
    {
        "name": "Vendor Reliability",
        "description": "Score vendors on execution. Timeliness, fill accuracy, substitutions, price stability.",
    },
    {
        "name": "Peer Benchmark",
        "description": "Anonymous opt-in performance comparison. No peer identities exposed.",
    },
    {
        "name": "Audit Trail",
        "description": "Immutable audit logs for Bishop decisions and human overrides. Training data for future ML.",
    },
    {
        "name": "Cash Flow Ordering",
        "description": "N20/N40: Gate orders through Ledger liquidity. Delay non-critical when constrained.",
    },
    {
        "name": "Predictive Stockout",
        "description": "N11: Stockout risk detection with burn rate analysis and reorder recommendations.",
    },
    {
        "name": "Ghost Inventory",
        "description": "N12: Detect unscanned inventory indicating shrinkage. Loss-signal, not disciplinary tool.",
    },
    {
        "name": "Scan Anomaly Detector",
        "description": "N15: Detect unusual scan patterns. Signal for review, not accusation.",
    },
    {
        "name": "Expiration Cascade",
        "description": "N13/N33: Surface expirations and convert waste into decisions. Donation respects compliance.",
    },
    {
        "name": "Cost Per Serving",
        "description": "N17/N37: Menu profitability from inventory costs. Price suggestions disabled by default.",
    },
    {
        "name": "Multi-Location Rebalancer",
        "description": "N18/N35: Network inventory optimization. Respects location autonomy by default.",
    },
    {
        "name": "Smart Receiving",
        "description": "N16/N32: Scan-to-PO reconciliation with discrepancy detection.",
    },
    {
        "name": "Vendor Price Watch",
        "description": "N14/N34: Monitor vendor pricing and surface arbitrage opportunities. Never auto-switch without approval.",
    },
    {
        "name": "Vendor Bridge",
        "description": "Multi-vendor aggregation with priority failover and price arbitrage.",
    },
    {
        "name": "Inventory",
        "description": "Product catalog and inventory snapshot management.",
    },
    {
        "name": "Mock Systems",
        "description": "Development mocks for Ledger, ClaimsIQ, and Capital integrations.",
    },
]

OPENAPI_DESCRIPTION = """
## B2B Inventory & Operations Management Platform

**Synthetic Precision** — faster than human perception, anticipatory rather than reactive.

---

### 🔒 API Contract

> **OpenAPI is the single source of truth.**
> If it's not in `/openapi.json`, it doesn't exist.

All clients (mobile, web, integrations) MUST use this spec for code generation.

---

### Core Systems

| System | DAG Nodes | Purpose |
|--------|-----------|---------|
| **Bishop FSM** | N40 | Deterministic state machine |
| **Stockout Engine** | N10, N11, N30, N31 | Predictive stockout alerts |
| **Receiving Engine** | N16, N32, N44 | Scan-to-PO reconciliation |
| **Vendor Bridge** | N3, N14, N23, N34 | Multi-vendor aggregation |
| **Priority Scoring** | N25 | Bishop triage worklist |

### Bishop DAG Layers

```
Layer 0: Canonical Data Contracts (N0-N4)
Layer 1: Signals - Pure Detection (N10-N18)
Layer 2: Policy Gates (N20-N25)
Layer 3: Proposals - Ready to Approve (N30-N37)
Layer 4: Execution - Approval Required (N40-N46)
Layer 5: Telemetry - Audit & Metrics (N50-N52)
```

### The One Rule

> **Signals detect. Policy decides. Proposals package. Approvals authorize. Execution commits. Telemetry proves.**

---

### External System Mocks

| System | Purpose | Status |
|--------|---------|--------|
| Ledger | Cash & liquidity verification (N4, N20) | Mocked |
| ClaimsIQ | Risk & liability assessment (N21) | Mocked |
| Capital | Inventory financing | Future hook |

### Authentication

Currently open for development. Production will require:
- API Key header: `X-API-Key`
- JWT Bearer token for user context (N0)

### Rate Limits

| Environment | Limit |
|-------------|-------|
| Development | Unlimited |
| Production | 1000 req/min per API key |

### Versioning

API version is in the path: `/api/v1/...`

Breaking changes will increment the version. Old versions deprecated with 90-day notice.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    print("PROVENIQ Ops initializing...")
    print(f"Environment: {settings.app_env}")
    print("Bishop FSM: IDLE")
    print("Bishop DAG Orchestrator: Loading...")
    print("Bishop Stockout Engine: Ready")
    print("Bishop Receiving Engine: Ready")
    print("Vendor Bridge: Ready")
    print("Mock systems: Ledger, ClaimsIQ, Capital")
    yield
    # Shutdown
    print("PROVENIQ Ops shutting down...")


app = FastAPI(
    title=API_TITLE,
    description=OPENAPI_DESCRIPTION,
    version=API_VERSION,
    openapi_tags=OPENAPI_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    contact={
        "name": "PROVENIQ Engineering",
        "url": "https://proveniq.com",
        "email": "api@proveniq.com",
    },
    license_info={
        "name": "Proprietary",
        "url": "https://proveniq.com/terms",
    },
    servers=[
        {"url": "http://localhost:8000", "description": "Development"},
        {"url": "https://api.proveniq.com", "description": "Production"},
    ],
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
app.include_router(dag.router, prefix="/api/v1")
app.include_router(bulk.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(cashflow.router, prefix="/api/v1")
app.include_router(stockout.router, prefix="/api/v1")
app.include_router(receiving.router, prefix="/api/v1")
app.include_router(ghost.router, prefix="/api/v1")
app.include_router(expiration.router, prefix="/api/v1")
app.include_router(menucost.router, prefix="/api/v1")
app.include_router(rebalance.router, prefix="/api/v1")
app.include_router(scananomaly.router, prefix="/api/v1")
app.include_router(pricewatch.router, prefix="/api/v1")
app.include_router(vendors.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
app.include_router(vision.router, prefix="/api/v1")
app.include_router(whatif.router, prefix="/api/v1")
app.include_router(memory.router, prefix="/api/v1")
app.include_router(custody.router, prefix="/api/v1")
app.include_router(auditready.router, prefix="/api/v1")
app.include_router(costdelay.router, prefix="/api/v1")
app.include_router(vendorscore.router, prefix="/api/v1")
app.include_router(benchmark.router, prefix="/api/v1")
app.include_router(mocks.router, prefix="/api/v1")


@app.get("/", tags=["Health"])
async def root() -> dict:
    """
    Root endpoint - system status.
    
    Returns basic system information and links to documentation.
    """
    return {
        "system": API_TITLE,
        "status": "operational",
        "version": API_VERSION,
        "bishop": "IDLE",
        "openapi": "/openapi.json",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    Health check endpoint for monitoring.
    
    Used by load balancers and monitoring systems.
    """
    return {
        "status": "healthy",
        "version": API_VERSION,
        "environment": settings.app_env,
        "debug": settings.debug,
    }


# =============================================================================
# OPENAPI UTILITIES
# =============================================================================

@app.get("/api/v1/openapi/export", tags=["Health"])
async def export_openapi() -> dict:
    """
    Export OpenAPI specification.
    
    **This is the single source of truth for the API.**
    
    Use this endpoint to:
    - Generate client SDKs
    - Validate API contracts
    - Document integrations
    
    Returns:
        Complete OpenAPI 3.1 specification
    """
    return app.openapi()


@app.get("/api/v1/openapi/endpoints", tags=["Health"])
async def list_endpoints() -> dict:
    """
    List all registered API endpoints.
    
    Useful for debugging and documentation verification.
    """
    endpoints = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            for method in route.methods:
                if method != "HEAD":
                    endpoints.append({
                        "method": method,
                        "path": route.path,
                        "name": route.name,
                        "tags": getattr(route, "tags", []),
                    })
    
    return {
        "total": len(endpoints),
        "endpoints": sorted(endpoints, key=lambda x: (x["path"], x["method"])),
    }
