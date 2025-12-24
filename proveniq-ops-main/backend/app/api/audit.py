"""
PROVENIQ Ops - Audit Trail API Routes
Immutable audit log access for training data and compliance.

This data is APPEND-ONLY. Never delete.
Future ML models train on this data.
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from app.models.audit import (
    AuditEventType,
    OverrideType,
    ReasonCode,
)
from app.services.audit import audit_service

router = APIRouter(prefix="/audit", tags=["Audit Trail"])


# =============================================================================
# STATE TRANSITION LOGS
# =============================================================================

@router.get("/state-transitions")
async def get_state_transitions(
    limit: int = Query(100, ge=1, le=1000),
    state_filter: Optional[str] = None,
) -> dict:
    """
    Get Bishop FSM state transition logs.
    
    Every state change is recorded for ML training.
    """
    logs = audit_service.get_state_logs(limit=limit, state_filter=state_filter)
    return {
        "total": len(logs),
        "logs": [log.model_dump() for log in logs],
    }


# =============================================================================
# PROPOSAL LOGS
# =============================================================================

@router.get("/proposals")
async def get_proposal_logs(
    limit: int = Query(100, ge=1, le=1000),
    event_type: Optional[AuditEventType] = None,
) -> dict:
    """
    Get proposal audit logs.
    
    Shows what Bishop recommended and what humans decided.
    """
    logs = audit_service.get_proposal_logs(limit=limit, event_type=event_type)
    return {
        "total": len(logs),
        "logs": [log.model_dump() for log in logs],
    }


@router.get("/proposals/approved")
async def get_approved_proposals(limit: int = Query(100, ge=1, le=1000)) -> dict:
    """Get proposals that were approved by humans."""
    logs = audit_service.get_proposal_logs(
        limit=limit, 
        event_type=AuditEventType.PROPOSAL_APPROVED
    )
    return {
        "total": len(logs),
        "logs": [log.model_dump() for log in logs],
    }


@router.get("/proposals/rejected")
async def get_rejected_proposals(limit: int = Query(100, ge=1, le=1000)) -> dict:
    """Get proposals that were rejected by humans."""
    logs = audit_service.get_proposal_logs(
        limit=limit,
        event_type=AuditEventType.PROPOSAL_REJECTED
    )
    return {
        "total": len(logs),
        "logs": [log.model_dump() for log in logs],
    }


@router.get("/proposals/modified")
async def get_modified_proposals(limit: int = Query(100, ge=1, le=1000)) -> dict:
    """
    Get proposals that were modified by humans.
    
    CRITICAL for ML: Shows where Bishop's recommendations needed adjustment.
    """
    logs = audit_service.get_proposal_logs(
        limit=limit,
        event_type=AuditEventType.PROPOSAL_MODIFIED
    )
    return {
        "total": len(logs),
        "logs": [log.model_dump() for log in logs],
    }


# =============================================================================
# OVERRIDE LOGS
# =============================================================================

@router.get("/overrides")
async def get_override_logs(
    limit: int = Query(100, ge=1, le=1000),
    override_type: Optional[OverrideType] = None,
) -> dict:
    """
    Get human override logs.
    
    MOST VALUABLE for ML:
    - What Bishop said
    - What human chose instead
    - Why (reason codes)
    - Was human correct? (when tracked)
    """
    logs = audit_service.get_override_logs(limit=limit, override_type=override_type)
    return {
        "total": len(logs),
        "logs": [log.model_dump() for log in logs],
    }


@router.get("/overrides/by-type/{override_type}")
async def get_overrides_by_type(
    override_type: OverrideType,
    limit: int = Query(100, ge=1, le=1000),
) -> dict:
    """Get overrides filtered by type."""
    logs = audit_service.get_override_logs(limit=limit, override_type=override_type)
    return {
        "total": len(logs),
        "override_type": override_type.value,
        "logs": [log.model_dump() for log in logs],
    }


@router.post("/overrides/{log_id}/outcome")
async def record_override_outcome(
    log_id: uuid.UUID,
    was_correct: bool,
    notes: Optional[str] = None,
) -> dict:
    """
    Record whether a human override was correct.
    
    Called later when outcome is known.
    Essential for training ML on when to trust Bishop vs human.
    """
    log = audit_service.update_override_outcome(
        log_id=log_id,
        was_correct=was_correct,
        notes=notes,
    )
    if not log:
        return {"success": False, "error": "Override log not found"}
    
    return {
        "success": True,
        "log_id": str(log_id),
        "was_correct": was_correct,
    }


# =============================================================================
# BLOCK LOGS
# =============================================================================

@router.get("/blocks")
async def get_block_logs(
    limit: int = Query(100, ge=1, le=1000),
    resolved: Optional[bool] = None,
) -> dict:
    """
    Get action block logs.
    
    Shows when Bishop or policy gates blocked actions.
    """
    logs = audit_service.get_block_logs(limit=limit, resolved=resolved)
    return {
        "total": len(logs),
        "logs": [log.model_dump() for log in logs],
    }


@router.get("/blocks/unresolved")
async def get_unresolved_blocks(limit: int = Query(100, ge=1, le=1000)) -> dict:
    """Get blocks that haven't been resolved yet."""
    logs = audit_service.get_block_logs(limit=limit, resolved=False)
    return {
        "total": len(logs),
        "logs": [log.model_dump() for log in logs],
    }


@router.post("/blocks/{log_id}/resolve")
async def resolve_block(
    log_id: uuid.UUID,
    resolution_type: str,
    resolved_by: uuid.UUID,
) -> dict:
    """Mark a block as resolved."""
    log = audit_service.resolve_block(
        log_id=log_id,
        resolution_type=resolution_type,
        resolved_by=resolved_by,
    )
    if not log:
        return {"success": False, "error": "Block log not found"}
    
    return {
        "success": True,
        "log_id": str(log_id),
        "resolution_type": resolution_type,
    }


# =============================================================================
# TRACE
# =============================================================================

@router.get("/trace/{trace_id}")
async def get_trace(trace_id: uuid.UUID) -> dict:
    """
    Get all logs for a decision trace.
    
    Links together the full chain:
    state transitions → proposals → overrides → blocks → executions
    """
    return audit_service.get_trace(trace_id)


# =============================================================================
# METRICS
# =============================================================================

@router.get("/metrics")
async def get_audit_metrics() -> dict:
    """
    Get aggregated audit metrics.
    
    Overview of Bishop vs Human decisions.
    """
    return audit_service.get_metrics()


@router.get("/metrics/override-accuracy")
async def get_override_accuracy() -> dict:
    """
    Get human override accuracy rate.
    
    When humans overrode Bishop, how often were they right?
    """
    metrics = audit_service.get_metrics()
    return {
        "override_accuracy": metrics.get("override_accuracy"),
        "total_overrides": metrics.get("total_overrides"),
        "note": "Accuracy only calculated for overrides with tracked outcomes",
    }


# =============================================================================
# REASON CODES (Reference)
# =============================================================================

@router.get("/reason-codes")
async def list_reason_codes() -> dict:
    """
    List all standardized reason codes.
    
    Use these codes for consistent logging.
    """
    return {
        "block_reasons": [
            {"code": rc.value, "name": rc.name}
            for rc in ReasonCode
            if rc.value.startswith(("insufficient", "risk", "low", "vendor", "policy", "approval", "budget"))
        ],
        "override_reasons": [
            {"code": rc.value, "name": rc.name}
            for rc in ReasonCode
            if rc.value.startswith(("manager", "customer", "vendor_rel", "seasonal", "event", "quality", "cost", "emergency"))
        ],
        "system_reasons": [
            {"code": rc.value, "name": rc.name}
            for rc in ReasonCode
            if rc.value.startswith(("system", "data", "timeout"))
        ],
    }


@router.get("/override-types")
async def list_override_types() -> dict:
    """List all override types."""
    return {
        "override_types": [
            {"type": ot.value, "name": ot.name}
            for ot in OverrideType
        ]
    }
