"""BISHOP Module - Restaurant/Retail Inventory FSM.

State machine: IDLE → SCANNING → ANALYZING_RISK → CHECKING_FUNDS → ORDER_QUEUED
"""

from fastapi import APIRouter

bishop_router = APIRouter(prefix="/bishop", tags=["bishop"])


@bishop_router.get("/status")
async def get_bishop_status():
    """Get current BISHOP FSM status."""
    return {
        "state": "IDLE",
        "message": "Bishop ready. No active scan.",
    }


@bishop_router.post("/scan")
async def trigger_scan():
    """Trigger a shelf scan (stub)."""
    return {
        "state": "SCANNING",
        "message": "Scan initiated. Processing...",
        "scan_id": "stub-scan-001",
    }
