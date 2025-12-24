"""
PROVENIQ Ops - Decision API

API endpoints for decision execution and traces.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.decision import (
    DecisionDAG,
    DecisionExecutor,
    DecisionTrace,
    TraceStore,
    create_reorder_dag,
    create_disposal_dag,
)
from app.decision.dag import NodeStatus

router = APIRouter(prefix="/decisions", tags=["Decisions"])

# Global instances
_trace_store = TraceStore()


# ============================================
# Request/Response Models
# ============================================

class ReorderRequest(BaseModel):
    """Request to create and execute a reorder decision"""
    product_id: UUID
    product_name: str
    quantity: int
    vendor_id: str
    order_amount_cents: int
    current_quantity: int
    par_level: int
    approval_token: Optional[str] = None
    approved_by: Optional[UUID] = None


class DisposalRequest(BaseModel):
    """Request to create and execute a disposal decision"""
    item_id: UUID
    item_name: str
    quantity: int
    reason: str  # expiration, damage, contamination, etc.
    estimated_value_cents: int
    loss_type: str = "unknown"


class TraceResponse(BaseModel):
    """Response with decision trace"""
    trace_id: UUID
    dag_name: str
    status: str
    duration_ms: Optional[int]
    events_count: int
    explanation: str


class PendingApproval(BaseModel):
    """A decision waiting for approval"""
    trace_id: UUID
    dag_name: str
    node_id: str
    node_name: str
    description: str
    order_amount_cents: Optional[int] = None
    created_at: datetime


# ============================================
# Endpoints
# ============================================

@router.post("/reorder", response_model=TraceResponse)
async def execute_reorder_decision(
    request: ReorderRequest,
    org_id: UUID = UUID("00000000-0000-0000-0000-000000000001"),  # TODO: Get from auth
) -> TraceResponse:
    """
    Execute a reorder decision through the DAG.
    
    The decision will:
    1. Verify stock is below par
    2. Check vendor availability
    3. Check liquidity via Capital bridge
    4. Require approval if over threshold
    5. Submit order if all gates pass
    """
    # Create DAG
    dag = create_reorder_dag(
        product_id=request.product_id,
        quantity=request.quantity,
        vendor_id=request.vendor_id,
    )
    
    # Build context
    context = {
        "product_id": str(request.product_id),
        "product_name": request.product_name,
        "quantity": request.quantity,
        "vendor_id": request.vendor_id,
        "order_amount_cents": request.order_amount_cents,
        "current_quantity": request.current_quantity,
        "par_level": request.par_level,
    }
    
    if request.approval_token:
        context["approval_token"] = request.approval_token
        context["approved_by"] = str(request.approved_by)
    
    # Execute
    executor = DecisionExecutor(org_id, _trace_store)
    
    # Register executors
    async def submit_order(ctx: Dict[str, Any]) -> Dict[str, Any]:
        # In production, would call vendor API
        return {
            "order_id": "ORD-12345",
            "vendor_order_id": f"{ctx['vendor_id']}-ORD-001",
            "status": "submitted",
        }
    
    executor.register_executor("submit_order_to_vendor", submit_order)
    
    trace = await executor.execute(dag, context)
    
    return TraceResponse(
        trace_id=trace.trace_id,
        dag_name=trace.dag_name,
        status=trace.status,
        duration_ms=trace.duration_ms,
        events_count=len(trace.events),
        explanation=trace.explain(),
    )


@router.post("/disposal", response_model=TraceResponse)
async def execute_disposal_decision(
    request: DisposalRequest,
    org_id: UUID = UUID("00000000-0000-0000-0000-000000000001"),
) -> TraceResponse:
    """
    Execute a disposal decision through the DAG.
    
    The decision will:
    1. Check insurance coverage via ClaimsIQ
    2. Capture required evidence
    3. Require manager approval
    4. Execute disposal
    5. File claim if covered
    """
    dag = create_disposal_dag(
        item_id=request.item_id,
        quantity=request.quantity,
        reason=request.reason,
    )
    
    context = {
        "item_id": str(request.item_id),
        "item_name": request.item_name,
        "quantity": request.quantity,
        "reason": request.reason,
        "estimated_value_cents": request.estimated_value_cents,
        "loss_type": request.loss_type,
    }
    
    executor = DecisionExecutor(org_id, _trace_store)
    
    # Register executors
    async def execute_disposal(ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {"disposal_id": "DSP-12345", "status": "completed"}
    
    async def file_insurance_claim(ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {"claim_id": "CLM-12345", "status": "submitted"}
    
    executor.register_executor("execute_disposal", execute_disposal)
    executor.register_executor("file_insurance_claim", file_insurance_claim)
    
    trace = await executor.execute(dag, context)
    
    return TraceResponse(
        trace_id=trace.trace_id,
        dag_name=trace.dag_name,
        status=trace.status,
        duration_ms=trace.duration_ms,
        events_count=len(trace.events),
        explanation=trace.explain(),
    )


@router.get("/trace/{trace_id}")
async def get_trace(trace_id: UUID) -> Dict[str, Any]:
    """Get a decision trace by ID"""
    trace = await _trace_store.get(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    
    return {
        "trace_id": str(trace.trace_id),
        "dag_id": str(trace.dag_id),
        "dag_name": trace.dag_name,
        "status": trace.status,
        "started_at": trace.started_at.isoformat() if trace.started_at else None,
        "completed_at": trace.completed_at.isoformat() if trace.completed_at else None,
        "duration_ms": trace.duration_ms,
        "events": [
            {
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type,
                "node_id": e.node_id,
                "gate_id": e.gate_id,
                "message": e.message,
            }
            for e in trace.events
        ],
        "explanation": trace.explain(),
    }


@router.get("/trace/{trace_id}/explain")
async def explain_trace(trace_id: UUID) -> Dict[str, str]:
    """Get human-readable explanation of a decision"""
    trace = await _trace_store.get(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    
    return {"explanation": trace.explain()}


@router.get("/traces")
async def list_traces(
    org_id: UUID = UUID("00000000-0000-0000-0000-000000000001"),
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List decision traces for an organization"""
    traces = await _trace_store.get_by_org(org_id, limit=limit, status=status)
    
    return [
        {
            "trace_id": str(t.trace_id),
            "dag_name": t.dag_name,
            "status": t.status,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "duration_ms": t.duration_ms,
        }
        for t in traces
    ]


@router.get("/search")
async def search_traces(
    query: str,
    org_id: UUID = UUID("00000000-0000-0000-0000-000000000001"),
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Search decision traces.
    
    Used for "What happened last time we ordered chicken?"
    """
    traces = await _trace_store.search(org_id, query, limit=limit)
    
    return [
        {
            "trace_id": str(t.trace_id),
            "dag_name": t.dag_name,
            "status": t.status,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "context_preview": str(t.initial_context)[:200],
        }
        for t in traces
    ]
