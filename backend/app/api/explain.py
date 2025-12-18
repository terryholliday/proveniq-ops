"""
PROVENIQ Ops - Explain Engine API Routes
Bishop decision explanation endpoints

Explain any Bishop recommendation in plain language.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query

from app.models.explain import (
    AlternativeConsidered,
    AlternativeStatus,
    DecisionTrace,
    DecisionType,
    DetailedExplanation,
    ExplainConfig,
    Explanation,
    InputUsed,
    PolicyApplied,
    QuickExplanation,
)
from app.services.bishop.explain_engine import explain_engine

router = APIRouter(prefix="/explain", tags=["Explain Engine"])


# =============================================================================
# EXPLANATIONS
# =============================================================================

@router.get("/{trace_id}")
async def explain_decision(trace_id: uuid.UUID) -> dict:
    """
    Explain a Bishop decision in plain language.
    
    Returns:
    - summary: Plain language explanation
    - inputs_used: List of inputs that influenced decision
    - confidence: 0-1 confidence score
    - alternatives_rejected: List of alternatives not chosen
    """
    result = explain_engine.explain(trace_id)
    
    if not result:
        return {"error": "Decision trace not found", "trace_id": str(trace_id)}
    
    return {
        "summary": result.summary,
        "inputs_used": result.inputs_used,
        "confidence": float(result.confidence),
        "alternatives_rejected": result.alternatives_rejected,
    }


@router.get("/{trace_id}/full", response_model=Explanation)
async def explain_decision_full(trace_id: uuid.UUID) -> dict:
    """Get full explanation with all details."""
    result = explain_engine.explain(trace_id)
    
    if not result:
        return {"error": "Decision trace not found", "trace_id": str(trace_id)}
    
    return result.model_dump()


@router.get("/{trace_id}/quick")
async def explain_decision_quick(trace_id: uuid.UUID) -> dict:
    """Get quick one-liner explanation for UI display."""
    result = explain_engine.explain_quick(trace_id)
    
    if not result:
        return {"error": "Decision trace not found", "trace_id": str(trace_id)}
    
    return result.model_dump()


@router.get("/{trace_id}/detailed")
async def explain_decision_detailed(trace_id: uuid.UUID) -> dict:
    """Get detailed explanation with full context and similar decisions."""
    result = explain_engine.explain_detailed(trace_id)
    
    if not result:
        return {"error": "Decision trace not found", "trace_id": str(trace_id)}
    
    return result.model_dump()


# =============================================================================
# TRACE REGISTRATION
# =============================================================================

@router.post("/trace")
async def register_trace(
    decision_type: DecisionType,
    recommendation: str,
    confidence_score: Decimal = Decimal("0.80"),
    inputs: Optional[list[dict]] = None,
    policies: Optional[list[dict]] = None,
    alternatives: Optional[list[dict]] = None,
) -> dict:
    """
    Register a decision trace for explanation.
    
    inputs format: [{"input_name": str, "input_type": str, "value": str, "source": str, "weight": float}]
    policies format: [{"policy_name": str, "policy_type": str, "description": str, "was_satisfied": bool}]
    alternatives format: [{"alternative_name": str, "description": str, "rejection_reason": str, "score": float}]
    """
    # Build inputs
    inputs_used = []
    if inputs:
        for inp in inputs:
            inputs_used.append(InputUsed(
                input_name=inp.get("input_name", "Unknown"),
                input_type=inp.get("input_type", "data"),
                value=inp.get("value", ""),
                source=inp.get("source", "system"),
                weight=Decimal(str(inp.get("weight", 0.5))) if inp.get("weight") else None,
            ))
    
    # Build policies
    policies_applied = []
    if policies:
        for pol in policies:
            policies_applied.append(PolicyApplied(
                policy_name=pol.get("policy_name", "Unknown"),
                policy_type=pol.get("policy_type", "rule"),
                description=pol.get("description", ""),
                was_satisfied=pol.get("was_satisfied", True),
                impact=pol.get("impact", "allowed"),
            ))
    
    # Build alternatives
    alternatives_considered = []
    if alternatives:
        for alt in alternatives:
            reason = alt.get("rejection_reason", "lower_score")
            try:
                rejection_reason = AlternativeStatus(reason)
            except ValueError:
                rejection_reason = AlternativeStatus.LOWER_SCORE
            
            alternatives_considered.append(AlternativeConsidered(
                alternative_name=alt.get("alternative_name", "Unknown"),
                description=alt.get("description", ""),
                rejection_reason=rejection_reason,
                rejection_detail=alt.get("rejection_detail", "Not selected"),
                score=Decimal(str(alt.get("score", 0))) if alt.get("score") else None,
            ))
    
    trace = DecisionTrace(
        decision_type=decision_type,
        recommendation=recommendation,
        confidence_score=confidence_score,
        inputs_used=inputs_used,
        policies_applied=policies_applied,
        alternatives_considered=alternatives_considered,
    )
    
    explain_engine.register_trace(trace)
    
    return {
        "status": "registered",
        "trace_id": str(trace.trace_id),
        "decision_type": decision_type.value,
        "recommendation": recommendation,
    }


@router.get("/trace/{trace_id}")
async def get_trace(trace_id: uuid.UUID) -> dict:
    """Get a decision trace."""
    trace = explain_engine.get_trace(trace_id)
    
    if not trace:
        return {"error": "Trace not found", "trace_id": str(trace_id)}
    
    return trace.model_dump()


# =============================================================================
# CONFIGURATION
# =============================================================================

@router.get("/config", response_model=ExplainConfig)
async def get_config() -> ExplainConfig:
    """Get explain engine configuration."""
    return explain_engine.get_config()


@router.put("/config")
async def update_config(
    max_inputs_to_show: Optional[int] = Query(None, ge=1, le=20),
    max_alternatives_to_show: Optional[int] = Query(None, ge=1, le=10),
    use_technical_terms: Optional[bool] = None,
) -> ExplainConfig:
    """Update explain engine configuration."""
    config = explain_engine.get_config()
    
    if max_inputs_to_show is not None:
        config.max_inputs_to_show = max_inputs_to_show
    if max_alternatives_to_show is not None:
        config.max_alternatives_to_show = max_alternatives_to_show
    if use_technical_terms is not None:
        config.use_technical_terms = use_technical_terms
    
    explain_engine.configure(config)
    return config


@router.delete("/data/clear")
async def clear_data() -> dict:
    """Clear all data (for testing)."""
    explain_engine.clear_data()
    return {"status": "cleared"}


# =============================================================================
# DEMO
# =============================================================================

@router.post("/demo/setup")
async def setup_demo() -> dict:
    """
    Set up demo data for explain engine testing.
    
    Creates sample decision traces with explanations.
    """
    explain_engine.clear_data()
    
    # Decision 1: Order recommendation
    order_trace = DecisionTrace(
        decision_type=DecisionType.ORDER_RECOMMENDATION,
        recommendation="Order 100 lb chicken breast from Sysco",
        confidence_score=Decimal("0.87"),
        inputs_used=[
            InputUsed(
                input_name="Current Inventory",
                input_type="inventory",
                value="45 lb",
                source="inventory_system",
                weight=Decimal("0.35"),
            ),
            InputUsed(
                input_name="7-Day Demand Forecast",
                input_type="forecast",
                value="120 lb",
                source="forecast_engine",
                weight=Decimal("0.30"),
            ),
            InputUsed(
                input_name="Par Level",
                input_type="policy",
                value="80 lb",
                source="par_settings",
                weight=Decimal("0.20"),
            ),
            InputUsed(
                input_name="Vendor Price",
                input_type="price",
                value="$5.50/lb",
                source="vendor_catalog",
                weight=Decimal("0.15"),
            ),
        ],
        policies_applied=[
            PolicyApplied(
                policy_name="Minimum Order Quantity",
                policy_type="hard_rule",
                description="Orders must be at least 50 lb",
                was_satisfied=True,
                impact="allowed",
            ),
            PolicyApplied(
                policy_name="Cash Flow Check",
                policy_type="threshold",
                description="Verify liquidity before ordering",
                was_satisfied=True,
                impact="allowed",
            ),
        ],
        alternatives_considered=[
            AlternativeConsidered(
                alternative_name="Order from US Foods",
                description="Same product at $5.75/lb",
                rejection_reason=AlternativeStatus.COST_TOO_HIGH,
                rejection_detail="4.5% higher cost",
                score=Decimal("0.72"),
            ),
            AlternativeConsidered(
                alternative_name="Delay Order 24h",
                description="Wait for potential price drop",
                rejection_reason=AlternativeStatus.RISK_TOO_HIGH,
                rejection_detail="Stockout risk increases to 35%",
                score=Decimal("0.45"),
            ),
        ],
    )
    explain_engine.register_trace(order_trace)
    
    # Decision 2: Salvage recommendation
    salvage_trace = DecisionTrace(
        decision_type=DecisionType.SALVAGE_RECOMMENDATION,
        recommendation="Transfer 30 lb to Branch B",
        confidence_score=Decimal("0.92"),
        inputs_used=[
            InputUsed(
                input_name="Excess Inventory",
                input_type="inventory",
                value="50 lb overstock",
                source="inventory_system",
                weight=Decimal("0.40"),
            ),
            InputUsed(
                input_name="Branch B Demand",
                input_type="network",
                value="2.5 days supply",
                source="network_inventory",
                weight=Decimal("0.35"),
            ),
            InputUsed(
                input_name="Transfer Cost",
                input_type="cost",
                value="$25",
                source="logistics",
                weight=Decimal("0.15"),
            ),
        ],
        policies_applied=[
            PolicyApplied(
                policy_name="Transfer Recovery Threshold",
                policy_type="threshold",
                description="Transfers must recover >70% value",
                was_satisfied=True,
                impact="allowed",
            ),
        ],
        alternatives_considered=[
            AlternativeConsidered(
                alternative_name="Donate to Food Bank",
                description="Tax benefit ~$75",
                rejection_reason=AlternativeStatus.LOWER_SCORE,
                rejection_detail="Recovery only 25% vs 85%",
                score=Decimal("0.65"),
            ),
            AlternativeConsidered(
                alternative_name="Employee Discount Sale",
                description="Sell at 40% off",
                rejection_reason=AlternativeStatus.LOWER_SCORE,
                rejection_detail="Recovery only 60%",
                score=Decimal("0.78"),
            ),
        ],
    )
    explain_engine.register_trace(salvage_trace)
    
    # Decision 3: Delay recommendation
    delay_trace = DecisionTrace(
        decision_type=DecisionType.DELAY_RECOMMENDATION,
        recommendation="Proceed with order now",
        confidence_score=Decimal("0.78"),
        inputs_used=[
            InputUsed(
                input_name="Cash Position",
                input_type="financial",
                value="$60,000 available",
                source="ledger",
                weight=Decimal("0.30"),
            ),
            InputUsed(
                input_name="Days of Supply",
                input_type="inventory",
                value="3.2 days",
                source="inventory_system",
                weight=Decimal("0.35"),
            ),
            InputUsed(
                input_name="Stockout Risk",
                input_type="risk",
                value="28%",
                source="risk_engine",
                weight=Decimal("0.35"),
            ),
        ],
        policies_applied=[
            PolicyApplied(
                policy_name="Minimum Reserve",
                policy_type="hard_rule",
                description="Maintain $50k minimum",
                was_satisfied=True,
                impact="allowed",
            ),
        ],
        alternatives_considered=[
            AlternativeConsidered(
                alternative_name="Delay 48 hours",
                description="Save $5,175 cash flow",
                rejection_reason=AlternativeStatus.RISK_TOO_HIGH,
                rejection_detail="Stockout probability rises to 52%",
                score=Decimal("0.42"),
            ),
        ],
    )
    explain_engine.register_trace(delay_trace)
    
    # Generate explanations
    order_explain = explain_engine.explain(order_trace.trace_id)
    salvage_explain = explain_engine.explain(salvage_trace.trace_id)
    delay_explain = explain_engine.explain(delay_trace.trace_id)
    
    return {
        "status": "demo_data_created",
        "traces_created": 3,
        "decisions": [
            {
                "trace_id": str(order_trace.trace_id),
                "type": "order_recommendation",
                "recommendation": order_trace.recommendation,
                "summary": order_explain.summary if order_explain else None,
                "confidence": "87%",
            },
            {
                "trace_id": str(salvage_trace.trace_id),
                "type": "salvage_recommendation",
                "recommendation": salvage_trace.recommendation,
                "summary": salvage_explain.summary if salvage_explain else None,
                "confidence": "92%",
            },
            {
                "trace_id": str(delay_trace.trace_id),
                "type": "delay_recommendation",
                "recommendation": delay_trace.recommendation,
                "summary": delay_explain.summary if delay_explain else None,
                "confidence": "78%",
            },
        ],
        "test_endpoints": [
            f"GET /explain/{order_trace.trace_id}",
            f"GET /explain/{salvage_trace.trace_id}/quick",
            f"GET /explain/{delay_trace.trace_id}/detailed",
        ],
    }
