"""
PROVENIQ Ops - Bishop API Routes
FSM control and status endpoints
"""

import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from app.models.schemas import (
    BishopResponse,
    BishopState,
    BishopStateTransition,
    LedgerCheckRequest,
    RiskCheckRequest,
    VendorQueryResponse,
)
from app.services.bishop import bishop_instance
from app.services.mocks import claimsiq_mock_instance, ledger_mock_instance

router = APIRouter(prefix="/bishop", tags=["Bishop FSM"])


@router.get("/status", response_model=BishopResponse)
async def get_bishop_status() -> BishopResponse:
    """Get current Bishop FSM status and state."""
    return bishop_instance.get_status()


@router.post("/reset", response_model=BishopResponse)
async def reset_bishop() -> BishopResponse:
    """Reset Bishop FSM to IDLE state."""
    return bishop_instance.reset()


@router.post("/scan/begin", response_model=BishopResponse)
async def begin_scan(location: Optional[str] = None) -> BishopResponse:
    """Initiate inventory scanning operation."""
    return bishop_instance.begin_scan(location)


@router.post("/scan/complete", response_model=BishopResponse)
async def complete_scan(
    items_detected: int,
    products: list[dict],
) -> BishopResponse:
    """
    Complete scan operation with detected items.
    
    Transitions to ANALYZING_RISK if items detected, otherwise IDLE.
    """
    return bishop_instance.complete_scan(items_detected, products)


@router.post("/risk/check", response_model=BishopResponse)
async def process_risk_check(request: RiskCheckRequest) -> BishopResponse:
    """
    Execute risk assessment via ClaimsIQ mock.
    
    Decision Logic:
        - High/Critical risk → Block, return to IDLE
        - Liability flags → Log warning, proceed to CHECKING_FUNDS
        - Clean → Proceed to CHECKING_FUNDS
    """
    risk_response = await claimsiq_mock_instance.check_risk(request)
    return bishop_instance.process_risk_check(risk_response)


@router.post("/funds/check", response_model=BishopResponse)
async def process_ledger_check(
    order_total: Decimal,
    currency: str = "USD",
) -> BishopResponse:
    """
    Execute ledger balance verification via Ledger mock.
    
    Decision Logic:
        - Insufficient funds → Block order, return to IDLE
        - Sufficient funds → Proceed to ORDER_QUEUED
    """
    ledger_request = LedgerCheckRequest(order_total=order_total, currency=currency)
    ledger_response = await ledger_mock_instance.check_funds(ledger_request)
    return bishop_instance.process_ledger_check(ledger_response, order_total)


@router.post("/order/queue", response_model=BishopResponse)
async def queue_order(
    vendor_id: uuid.UUID,
    vendor_name: str,
    estimated_delivery_hours: Optional[int] = 4,
) -> BishopResponse:
    """
    Finalize order queuing with vendor details.
    
    Must be in ORDER_QUEUED state (reached via funds verification).
    """
    order_id = uuid.uuid4()
    vendor_response = VendorQueryResponse(
        vendor_id=vendor_id,
        vendor_name=vendor_name,
        in_stock=True,
        available_quantity=999,
        unit_price=Decimal("0.00"),
        estimated_delivery_hours=estimated_delivery_hours,
    )
    return bishop_instance.queue_order(vendor_response, order_id)


@router.get("/log", response_model=list[BishopStateTransition])
async def get_transition_log() -> list[BishopStateTransition]:
    """Get full Bishop state transition audit log."""
    return bishop_instance.get_transition_log()


@router.post("/transition", response_model=BishopResponse)
async def manual_transition(
    target_state: BishopState,
    trigger: str = "MANUAL_TRANSITION",
) -> BishopResponse:
    """
    Manually transition Bishop to a target state.
    
    Only valid transitions are allowed. Invalid transitions return error.
    """
    return bishop_instance.transition_to(target_state, trigger)
