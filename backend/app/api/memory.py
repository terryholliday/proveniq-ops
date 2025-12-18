"""
PROVENIQ Ops - Decision Memory API Routes
Bishop decision recording and outcome tracking endpoints

GUARDRAILS:
- Memory INFORMS recommendations but NEVER overrides policy
- All records are immutable once created
- Outcomes are linked after resolution window
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any

from fastapi import APIRouter, Query

from app.models.memory import (
    DecisionMemoryStats,
    DecisionRecord,
    DecisionType,
    InputsSnapshot,
    MemoryConfig,
    MemoryLookupResult,
    OutcomeMetrics,
    OutcomeQuality,
    OutcomeRecord,
)
from app.services.bishop.memory_engine import memory_engine

router = APIRouter(prefix="/memory", tags=["Decision Memory"])


# =============================================================================
# DECISION RECORDING
# =============================================================================

@router.post("/decision", response_model=DecisionRecord)
async def record_decision(
    decision_type: DecisionType,
    decision_description: str,
    decision_trace_id: uuid.UUID,
    action_taken: str,
    confidence: Decimal,
    dag_node_id: Optional[str] = None,
    # Snapshot data
    inventory_levels: Optional[dict[str, Decimal]] = None,
    demand_forecast: Optional[dict[str, Decimal]] = None,
    stockout_risk_items: int = 0,
    waste_risk_items: int = 0,
    day_of_week: int = 0,
    hour_of_day: int = 0,
) -> DecisionRecord:
    """
    Record an immutable decision.
    
    Once recorded, decisions cannot be modified.
    Link outcomes after resolution window.
    """
    snapshot = InputsSnapshot(
        inventory_levels=inventory_levels or {},
        demand_forecast=demand_forecast or {},
        stockout_risk_items=stockout_risk_items,
        waste_risk_items=waste_risk_items,
        day_of_week=day_of_week,
        hour_of_day=hour_of_day,
    )
    
    return memory_engine.record_decision(
        decision_type=decision_type,
        decision_description=decision_description,
        decision_trace_id=decision_trace_id,
        inputs_snapshot=snapshot,
        action_taken=action_taken,
        action_parameters={},
        confidence=confidence,
        dag_node_id=dag_node_id,
    )


# =============================================================================
# OUTCOME RECORDING
# =============================================================================

@router.post("/outcome/{decision_id}", response_model=OutcomeRecord)
async def record_outcome(
    decision_id: uuid.UUID,
    outcome_quality: OutcomeQuality,
    outcome_description: str,
    # Metrics
    waste_actual_pct: Optional[Decimal] = None,
    waste_expected_pct: Optional[Decimal] = None,
    margin_actual_pct: Optional[Decimal] = None,
    margin_expected_pct: Optional[Decimal] = None,
    stockout_occurred: bool = False,
    stockout_duration_hours: Optional[int] = None,
    delivery_delay_hours: Optional[int] = None,
    # Feedback
    human_feedback: Optional[str] = None,
    human_override_applied: bool = False,
    lessons_learned: list[str] = Query(default=[]),
) -> dict:
    """
    Link an outcome to a decision after resolution.
    
    Call this once the decision's impact is known.
    """
    metrics = OutcomeMetrics(
        waste_actual_pct=waste_actual_pct,
        waste_expected_pct=waste_expected_pct,
        waste_delta_pct=(waste_actual_pct - waste_expected_pct) if waste_actual_pct and waste_expected_pct else None,
        margin_actual_pct=margin_actual_pct,
        margin_expected_pct=margin_expected_pct,
        margin_delta_pct=(margin_actual_pct - margin_expected_pct) if margin_actual_pct and margin_expected_pct else None,
        stockout_occurred=stockout_occurred,
        stockout_duration_hours=stockout_duration_hours,
        delivery_delay_hours=delivery_delay_hours,
    )
    
    outcome = memory_engine.record_outcome(
        decision_id=decision_id,
        outcome_quality=outcome_quality,
        outcome_description=outcome_description,
        metrics=metrics,
        human_feedback=human_feedback,
        human_override_applied=human_override_applied,
        lessons_learned=lessons_learned,
    )
    
    if not outcome:
        return {"error": "Decision not found", "decision_id": str(decision_id)}
    
    return outcome.model_dump()


# =============================================================================
# SIMILARITY LOOKUP
# =============================================================================

@router.post("/lookup", response_model=MemoryLookupResult)
async def find_similar_decisions(
    decision_type: Optional[DecisionType] = None,
    max_results: int = Query(10, ge=1, le=50),
    # Current context
    inventory_levels: Optional[dict[str, Decimal]] = None,
    demand_forecast: Optional[dict[str, Decimal]] = None,
    stockout_risk_items: int = 0,
    waste_risk_items: int = 0,
    day_of_week: Optional[int] = None,
    hour_of_day: Optional[int] = None,
) -> MemoryLookupResult:
    """
    Surface historical analogs for current context.
    
    GUARDRAIL: Results inform recommendations but NEVER override policy.
    
    Returns similar past decisions with their outcomes.
    """
    now = datetime.utcnow()
    
    snapshot = InputsSnapshot(
        inventory_levels=inventory_levels or {},
        demand_forecast=demand_forecast or {},
        stockout_risk_items=stockout_risk_items,
        waste_risk_items=waste_risk_items,
        day_of_week=day_of_week if day_of_week is not None else now.weekday(),
        hour_of_day=hour_of_day if hour_of_day is not None else now.hour,
    )
    
    return memory_engine.find_similar_decisions(
        current_inputs=snapshot,
        decision_type=decision_type,
        max_results=max_results,
    )


# =============================================================================
# QUERY
# =============================================================================

@router.get("/decision/{decision_id}")
async def get_decision(decision_id: uuid.UUID) -> dict:
    """Get a specific decision and its outcome."""
    decision = memory_engine.get_decision(decision_id)
    if not decision:
        return {"error": "Decision not found"}
    
    outcome = memory_engine.get_outcome(decision_id)
    
    return {
        "decision": decision.model_dump(),
        "outcome": outcome.model_dump() if outcome else None,
    }


@router.get("/trace/{trace_id}")
async def get_decision_by_trace(trace_id: uuid.UUID) -> dict:
    """Get decision by trace ID."""
    decision = memory_engine.get_decision_by_trace(trace_id)
    if not decision:
        return {"error": "No decision for trace", "trace_id": str(trace_id)}
    
    outcome = memory_engine.get_outcome(decision.decision_id)
    
    return {
        "decision": decision.model_dump(),
        "outcome": outcome.model_dump() if outcome else None,
    }


@router.get("/pending")
async def get_pending_resolutions() -> dict:
    """Get decisions awaiting outcome recording."""
    pending = memory_engine.get_pending_resolutions()
    return {
        "count": len(pending),
        "decisions": [d.model_dump() for d in pending],
    }


# =============================================================================
# STATISTICS
# =============================================================================

@router.get("/stats", response_model=DecisionMemoryStats)
async def get_stats() -> DecisionMemoryStats:
    """Get memory statistics."""
    return memory_engine.get_stats()


# =============================================================================
# CONFIGURATION
# =============================================================================

@router.get("/config", response_model=MemoryConfig)
async def get_config() -> MemoryConfig:
    """Get memory configuration."""
    return memory_engine.get_config()


@router.put("/config")
async def update_config(
    similarity_threshold: Optional[Decimal] = Query(None, ge=0, le=1),
    max_similar_results: Optional[int] = Query(None, ge=1),
    default_resolution_hours: Optional[int] = Query(None, ge=1),
) -> MemoryConfig:
    """Update memory configuration."""
    config = memory_engine.get_config()
    
    if similarity_threshold is not None:
        config.similarity_threshold = similarity_threshold
    if max_similar_results is not None:
        config.max_similar_results = max_similar_results
    if default_resolution_hours is not None:
        config.default_resolution_hours = default_resolution_hours
    
    memory_engine.configure(config)
    return config


@router.delete("/data/clear")
async def clear_data() -> dict:
    """Clear all memory data (for testing)."""
    memory_engine.clear_data()
    return {"status": "cleared"}


# =============================================================================
# DEMO
# =============================================================================

@router.post("/demo/setup")
async def setup_demo() -> dict:
    """
    Set up demo data for decision memory testing.
    
    Creates sample decisions with outcomes.
    """
    memory_engine.clear_data()
    
    now = datetime.utcnow()
    
    # Decision 1: Order placement - GOOD outcome
    snapshot1 = InputsSnapshot(
        inventory_levels={"chicken": Decimal("50"), "beef": Decimal("30")},
        demand_forecast={"chicken": Decimal("20"), "beef": Decimal("15")},
        stockout_risk_items=1,
        waste_risk_items=0,
        day_of_week=1,  # Tuesday
        hour_of_day=9,
    )
    
    decision1 = memory_engine.record_decision(
        decision_type=DecisionType.ORDER_PLACEMENT,
        decision_description="Place order for chicken restock",
        decision_trace_id=uuid.uuid4(),
        inputs_snapshot=snapshot1,
        action_taken="Order 100 lbs chicken from Sysco",
        action_parameters={"vendor": "Sysco", "quantity": 100, "product": "chicken"},
        confidence=Decimal("0.85"),
        dag_node_id="N40_order_execution",
    )
    
    outcome1 = memory_engine.record_outcome(
        decision_id=decision1.decision_id,
        outcome_quality=OutcomeQuality.GOOD,
        outcome_description="Order delivered on time, no stockout",
        metrics=OutcomeMetrics(
            stockout_occurred=False,
            delivery_delay_hours=0,
            waste_actual_pct=Decimal("2"),
            waste_expected_pct=Decimal("3"),
        ),
    )
    
    # Decision 2: Order delay - POOR outcome
    snapshot2 = InputsSnapshot(
        inventory_levels={"chicken": Decimal("25"), "beef": Decimal("40")},
        demand_forecast={"chicken": Decimal("22"), "beef": Decimal("12")},
        stockout_risk_items=1,
        waste_risk_items=0,
        day_of_week=3,  # Thursday
        hour_of_day=14,
    )
    
    decision2 = memory_engine.record_decision(
        decision_type=DecisionType.ORDER_DELAY,
        decision_description="Delay chicken order due to cash constraints",
        decision_trace_id=uuid.uuid4(),
        inputs_snapshot=snapshot2,
        action_taken="Delay order 48 hours",
        action_parameters={"delay_hours": 48, "reason": "liquidity"},
        confidence=Decimal("0.70"),
        dag_node_id="N20_liquidity_gate",
    )
    
    outcome2 = memory_engine.record_outcome(
        decision_id=decision2.decision_id,
        outcome_quality=OutcomeQuality.POOR,
        outcome_description="Stockout occurred during delay period",
        metrics=OutcomeMetrics(
            stockout_occurred=True,
            stockout_duration_hours=6,
            delivery_delay_hours=48,
        ),
        lessons_learned=["Consider buffer stock for high-demand items", "48h delay too long for low inventory"],
    )
    
    # Decision 3: Vendor selection - EXCELLENT outcome
    snapshot3 = InputsSnapshot(
        inventory_levels={"flour": Decimal("100"), "sugar": Decimal("80")},
        demand_forecast={"flour": Decimal("15"), "sugar": Decimal("10")},
        stockout_risk_items=0,
        waste_risk_items=0,
        day_of_week=1,  # Tuesday
        hour_of_day=10,
    )
    
    decision3 = memory_engine.record_decision(
        decision_type=DecisionType.VENDOR_SELECTION,
        decision_description="Switch flour vendor for better price",
        decision_trace_id=uuid.uuid4(),
        inputs_snapshot=snapshot3,
        action_taken="Switch from Sysco to US Foods for flour",
        action_parameters={"from_vendor": "Sysco", "to_vendor": "US Foods", "savings_pct": 8},
        confidence=Decimal("0.90"),
        dag_node_id="N34_vendor_arbitrage",
    )
    
    outcome3 = memory_engine.record_outcome(
        decision_id=decision3.decision_id,
        outcome_quality=OutcomeQuality.EXCELLENT,
        outcome_description="8% cost savings, quality maintained",
        metrics=OutcomeMetrics(
            margin_actual_pct=Decimal("58"),
            margin_expected_pct=Decimal("55"),
            stockout_occurred=False,
        ),
    )
    
    # Decision 4: Pending (no outcome yet)
    snapshot4 = InputsSnapshot(
        inventory_levels={"chicken": Decimal("45"), "beef": Decimal("35")},
        demand_forecast={"chicken": Decimal("18"), "beef": Decimal("14")},
        stockout_risk_items=0,
        waste_risk_items=1,
        day_of_week=now.weekday(),
        hour_of_day=now.hour,
    )
    
    decision4 = memory_engine.record_decision(
        decision_type=DecisionType.WASTE_DISPOSITION,
        decision_description="Discount near-expiry items",
        decision_trace_id=uuid.uuid4(),
        inputs_snapshot=snapshot4,
        action_taken="Apply 30% discount to expiring produce",
        action_parameters={"discount_pct": 30, "category": "produce"},
        confidence=Decimal("0.80"),
        dag_node_id="N33_expiration_action",
    )
    
    # Test similarity lookup
    current_context = InputsSnapshot(
        inventory_levels={"chicken": Decimal("48"), "beef": Decimal("32")},
        demand_forecast={"chicken": Decimal("21"), "beef": Decimal("14")},
        stockout_risk_items=1,
        waste_risk_items=0,
        day_of_week=1,
        hour_of_day=10,
    )
    
    lookup_result = memory_engine.find_similar_decisions(current_context)
    
    return {
        "status": "demo_data_created",
        "decisions_created": 4,
        "outcomes_recorded": 3,
        "pending_resolutions": 1,
        "sample_lookup": {
            "similar_found": lookup_result.total_similar_found,
            "avg_outcome_score": str(lookup_result.avg_outcome_score) if lookup_result.avg_outcome_score else None,
            "historical_success_rate": str(lookup_result.historical_success_rate) if lookup_result.historical_success_rate else None,
            "suggestions": lookup_result.suggested_adjustments,
        },
        "guardrail_reminder": "Memory informs recommendations but NEVER overrides policy.",
    }
