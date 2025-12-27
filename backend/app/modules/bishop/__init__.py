"""BISHOP Module - Restaurant/Retail Inventory FSM.

State machine: IDLE → SCANNING → ANALYZING_RISK → CHECKING_FUNDS → ORDER_QUEUED

Phase 0-1 Governance:
- Every state transition is persisted
- Every recommendation requires human accept/reject
- All events become forensic history
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from uuid import UUID

from app.modules.bishop.fsm import (
    bishop_fsm,
    BishopFSM,
    BishopState,
    BishopSession,
    BishopRecommendation,
    RecommendationType,
    RecommendationStatus,
)

bishop_router = APIRouter(prefix="/bishop", tags=["bishop"])


class StartSessionRequest(BaseModel):
    org_id: UUID
    location_id: UUID
    initiated_by: Optional[UUID] = None


class AcceptRecommendationRequest(BaseModel):
    accepted_by: UUID
    modified_quantity: Optional[int] = None
    modified_vendor_id: Optional[UUID] = None
    modification_reason: Optional[str] = None


class RejectRecommendationRequest(BaseModel):
    rejected_by: UUID
    rejection_reason: str


@bishop_router.get("/status")
async def get_bishop_status():
    """Get current BISHOP FSM status."""
    active_sessions = bishop_fsm.get_active_sessions()
    return {
        "status": "ready",
        "active_sessions": len(active_sessions),
        "message": "Bishop ready." if not active_sessions else f"Bishop has {len(active_sessions)} active session(s).",
    }


@bishop_router.post("/sessions")
async def start_session(request: StartSessionRequest):
    """Start a new Bishop session."""
    session = await bishop_fsm.start_session(
        org_id=request.org_id,
        location_id=request.location_id,
        initiated_by=request.initiated_by,
    )
    return {
        "session_id": str(session.session_id),
        "state": session.state.value,
        "correlation_id": session.correlation_id,
        "message": "Session started. Ready for scanning.",
    }


@bishop_router.get("/sessions/{session_id}")
async def get_session(session_id: UUID):
    """Get session details."""
    session = bishop_fsm.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": str(session.session_id),
        "state": session.state.value,
        "started_at": session.started_at.isoformat(),
        "transition_count": len(session.transitions),
        "recommendation_count": len(session.recommendations),
        "pending_recommendations": [
            {
                "recommendation_id": str(r.recommendation_id),
                "type": r.recommendation_type.value,
                "product_name": r.product_name,
                "quantity": r.recommended_quantity,
                "confidence": str(r.confidence),
            }
            for r in session.recommendations
            if r.status == RecommendationStatus.PENDING
        ],
    }


@bishop_router.post("/sessions/{session_id}/transition")
async def transition_state(session_id: UUID, new_state: str, trigger_event: str):
    """Manually transition state (for testing)."""
    try:
        state = BishopState(new_state)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid state: {new_state}")
    
    try:
        transition = await bishop_fsm.transition(session_id, state, trigger_event)
        return {
            "transition_id": str(transition.transition_id),
            "previous_state": transition.previous_state.value if transition.previous_state else None,
            "new_state": transition.new_state.value,
            "trigger_event": transition.trigger_event,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@bishop_router.post("/sessions/{session_id}/recommendations/{recommendation_id}/accept")
async def accept_recommendation(
    session_id: UUID,
    recommendation_id: UUID,
    request: AcceptRecommendationRequest,
):
    """Accept a Bishop recommendation."""
    try:
        recommendation = await bishop_fsm.accept_recommendation(
            session_id=session_id,
            recommendation_id=recommendation_id,
            accepted_by=request.accepted_by,
            modified_quantity=request.modified_quantity,
            modified_vendor_id=request.modified_vendor_id,
            modification_reason=request.modification_reason,
        )
        return {
            "recommendation_id": str(recommendation.recommendation_id),
            "status": recommendation.status.value,
            "final_quantity": request.modified_quantity or recommendation.recommended_quantity,
            "message": "Recommendation accepted. Order will be queued.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@bishop_router.post("/sessions/{session_id}/recommendations/{recommendation_id}/reject")
async def reject_recommendation(
    session_id: UUID,
    recommendation_id: UUID,
    request: RejectRecommendationRequest,
):
    """Reject a Bishop recommendation."""
    try:
        recommendation = await bishop_fsm.reject_recommendation(
            session_id=session_id,
            recommendation_id=recommendation_id,
            rejected_by=request.rejected_by,
            rejection_reason=request.rejection_reason,
        )
        return {
            "recommendation_id": str(recommendation.recommendation_id),
            "status": recommendation.status.value,
            "message": "Recommendation rejected. Logged for ML training.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@bishop_router.post("/sessions/{session_id}/complete")
async def complete_session(session_id: UUID):
    """Complete a Bishop session."""
    try:
        session = await bishop_fsm.complete_session(session_id)
        return {
            "session_id": str(session.session_id),
            "duration_seconds": (session.completed_at - session.started_at).total_seconds(),
            "total_transitions": len(session.transitions),
            "total_recommendations": len(session.recommendations),
            "message": "Session completed. All events persisted.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
