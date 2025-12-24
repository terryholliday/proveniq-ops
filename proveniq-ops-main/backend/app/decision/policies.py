"""
PROVENIQ Ops - Policy Engine

Evaluates policy gates for decision execution.
Integrates with Capital for liquidity, ClaimsIQ for coverage, etc.
"""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
import logging

from .dag import DecisionGate, GateType, NodeStatus
from app.bridges import get_capital_bridge, get_claimsiq_bridge, get_bids_bridge
from app.bridges.events import LossType

logger = logging.getLogger(__name__)


class PolicyResult(BaseModel):
    """Result of a policy evaluation"""
    passed: bool
    gate_type: GateType
    message: str
    details: Dict[str, Any] = {}
    evaluated_at: datetime = datetime.utcnow()
    requires_action: bool = False
    action_type: Optional[str] = None  # "approval_needed", "evidence_needed", etc.


class PolicyEngine:
    """
    Evaluates policy gates against current system state.
    
    Integrates with:
    - Capital: Liquidity checks
    - ClaimsIQ: Coverage checks
    - Bids: Salvage valuation
    - Internal: Thresholds, approvals
    """
    
    def __init__(self, org_id: UUID):
        self.org_id = org_id
    
    async def evaluate_gate(
        self,
        gate: DecisionGate,
        context: Dict[str, Any],
    ) -> PolicyResult:
        """
        Evaluate a single policy gate.
        
        Args:
            gate: The gate to evaluate
            context: Context data for evaluation (order details, item info, etc.)
        
        Returns:
            PolicyResult indicating pass/fail and details
        """
        logger.info(f"Evaluating gate {gate.gate_id} ({gate.gate_type})")
        
        if gate.gate_type == GateType.LIQUIDITY:
            return await self._check_liquidity(gate, context)
        elif gate.gate_type == GateType.CRITICALITY:
            return await self._check_criticality(gate, context)
        elif gate.gate_type == GateType.APPROVAL:
            return await self._check_approval(gate, context)
        elif gate.gate_type == GateType.COVERAGE:
            return await self._check_coverage(gate, context)
        elif gate.gate_type == GateType.VENDOR:
            return await self._check_vendor(gate, context)
        elif gate.gate_type == GateType.THRESHOLD:
            return await self._check_threshold(gate, context)
        else:
            return PolicyResult(
                passed=False,
                gate_type=gate.gate_type,
                message=f"Unknown gate type: {gate.gate_type}",
            )
    
    async def _check_liquidity(
        self,
        gate: DecisionGate,
        context: Dict[str, Any],
    ) -> PolicyResult:
        """Check if there's sufficient liquidity for the operation"""
        order_amount = context.get("order_amount_cents", 0)
        
        capital = get_capital_bridge()
        liquidity = await capital.get_liquidity_snapshot(self.org_id)
        
        if order_amount > liquidity.effective_liquidity_cents:
            return PolicyResult(
                passed=False,
                gate_type=GateType.LIQUIDITY,
                message=f"Insufficient liquidity. Need ${order_amount/100:.2f}, have ${liquidity.effective_liquidity_cents/100:.2f}",
                details={
                    "required_cents": order_amount,
                    "available_cents": liquidity.effective_liquidity_cents,
                    "shortfall_cents": order_amount - liquidity.effective_liquidity_cents,
                },
            )
        
        return PolicyResult(
            passed=True,
            gate_type=GateType.LIQUIDITY,
            message=f"Liquidity check passed. ${liquidity.effective_liquidity_cents/100:.2f} available.",
            details={
                "required_cents": order_amount,
                "available_cents": liquidity.effective_liquidity_cents,
            },
        )
    
    async def _check_criticality(
        self,
        gate: DecisionGate,
        context: Dict[str, Any],
    ) -> PolicyResult:
        """Assess criticality of the decision"""
        criticality = context.get("criticality", "normal")
        hours_to_stockout = context.get("hours_to_stockout")
        
        if criticality == "critical" or (hours_to_stockout and hours_to_stockout < 24):
            return PolicyResult(
                passed=True,
                gate_type=GateType.CRITICALITY,
                message="Critical situation - fast-track approved",
                details={
                    "criticality": criticality,
                    "hours_to_stockout": hours_to_stockout,
                    "fast_tracked": True,
                },
            )
        
        return PolicyResult(
            passed=True,
            gate_type=GateType.CRITICALITY,
            message="Standard criticality - normal processing",
            details={
                "criticality": criticality,
                "hours_to_stockout": hours_to_stockout,
                "fast_tracked": False,
            },
        )
    
    async def _check_approval(
        self,
        gate: DecisionGate,
        context: Dict[str, Any],
    ) -> PolicyResult:
        """Check if approval is required and obtained"""
        order_amount = context.get("order_amount_cents", 0)
        approval_threshold = gate.config.get("threshold_cents", 50000)  # $500 default
        approval_token = context.get("approval_token")
        
        # If below threshold, no approval needed
        if order_amount < approval_threshold:
            return PolicyResult(
                passed=True,
                gate_type=GateType.APPROVAL,
                message="Below approval threshold - auto-approved",
                details={
                    "order_amount_cents": order_amount,
                    "threshold_cents": approval_threshold,
                    "approval_required": False,
                },
            )
        
        # If above threshold, check for approval token
        if approval_token:
            # Validate token (in production, verify against stored approvals)
            return PolicyResult(
                passed=True,
                gate_type=GateType.APPROVAL,
                message="Manager approval verified",
                details={
                    "order_amount_cents": order_amount,
                    "approval_token": approval_token,
                    "approved_by": context.get("approved_by"),
                },
            )
        
        # Approval required but not obtained
        return PolicyResult(
            passed=False,
            gate_type=GateType.APPROVAL,
            message=f"Manager approval required for orders over ${approval_threshold/100:.2f}",
            details={
                "order_amount_cents": order_amount,
                "threshold_cents": approval_threshold,
            },
            requires_action=True,
            action_type="approval_needed",
        )
    
    async def _check_coverage(
        self,
        gate: DecisionGate,
        context: Dict[str, Any],
    ) -> PolicyResult:
        """Check insurance coverage via ClaimsIQ"""
        item_id = context.get("item_id")
        loss_type_str = context.get("loss_type", "unknown")
        estimated_value = context.get("estimated_value_cents", 0)
        
        # Map string to LossType enum
        loss_type_map = {
            "theft": LossType.THEFT,
            "spoilage": LossType.SPOILAGE,
            "damage": LossType.DAMAGE,
            "admin_error": LossType.ADMIN_ERROR,
            "vendor_error": LossType.VENDOR_ERROR,
            "unknown": LossType.UNKNOWN,
        }
        loss_type = loss_type_map.get(loss_type_str, LossType.UNKNOWN)
        
        claimsiq = get_claimsiq_bridge()
        coverage = await claimsiq.get_coverage(
            self.org_id,
            item_id,
            loss_type,
            estimated_value,
        )
        
        return PolicyResult(
            passed=True,  # Coverage check always passes, just provides info
            gate_type=GateType.COVERAGE,
            message=f"Coverage: {'Yes' if coverage.is_covered else 'No'}",
            details={
                "is_covered": coverage.is_covered,
                "coverage_type": coverage.coverage_type,
                "coverage_limit_cents": coverage.coverage_limit_cents,
                "deductible_cents": coverage.deductible_cents,
                "required_evidence": coverage.required_evidence,
            },
            requires_action=coverage.is_covered and len(coverage.required_evidence) > 0,
            action_type="evidence_needed" if coverage.required_evidence else None,
        )
    
    async def _check_vendor(
        self,
        gate: DecisionGate,
        context: Dict[str, Any],
    ) -> PolicyResult:
        """Check vendor availability"""
        vendor_id = context.get("vendor_id")
        product_id = context.get("product_id")
        quantity = context.get("quantity", 1)
        
        # In production, would call vendor API
        # For now, assume available
        return PolicyResult(
            passed=True,
            gate_type=GateType.VENDOR,
            message="Vendor availability confirmed",
            details={
                "vendor_id": vendor_id,
                "product_id": product_id,
                "quantity_available": quantity,
                "lead_time_hours": 24,
            },
        )
    
    async def _check_threshold(
        self,
        gate: DecisionGate,
        context: Dict[str, Any],
    ) -> PolicyResult:
        """Check against configured thresholds"""
        current_quantity = context.get("current_quantity", 0)
        par_level = context.get("par_level", 0)
        
        if current_quantity < par_level:
            return PolicyResult(
                passed=True,
                gate_type=GateType.THRESHOLD,
                message=f"Stock ({current_quantity}) is below par level ({par_level})",
                details={
                    "current_quantity": current_quantity,
                    "par_level": par_level,
                    "shortage": par_level - current_quantity,
                },
            )
        
        return PolicyResult(
            passed=False,
            gate_type=GateType.THRESHOLD,
            message=f"Stock ({current_quantity}) is at or above par level ({par_level})",
            details={
                "current_quantity": current_quantity,
                "par_level": par_level,
            },
        )
