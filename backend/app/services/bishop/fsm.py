"""
PROVENIQ Ops - Bishop Finite State Machine
Deterministic operational intelligence interface

Bishop is NOT a chatbot.
Bishop is a deterministic FSM with strict state transitions.
All outputs are short, declarative, machine-like.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Optional

from app.models.schemas import (
    BishopResponse,
    BishopState,
    BishopStateTransition,
    LedgerCheckResponse,
    RiskCheckResponse,
    VendorQueryResponse,
)


class BishopFSM:
    """
    Bishop Finite State Machine
    
    States:
        IDLE → Awaiting input
        SCANNING → Inventory capture in progress
        ANALYZING_RISK → ClaimsIQ risk evaluation
        CHECKING_FUNDS → Ledger balance verification
        ORDER_QUEUED → Order dispatched to vendor
    
    Rules:
        - Output varies by state
        - State transitions are logged
        - No free-form conversation
        - All outputs are declarative
    """
    
    # State-specific output templates (machine-like, declarative)
    STATE_OUTPUTS: dict[BishopState, str] = {
        BishopState.IDLE: "Awaiting directive.",
        BishopState.SCANNING: "Inventory capture in progress.",
        BishopState.ANALYZING_RISK: "Risk evaluation in progress.",
        BishopState.CHECKING_FUNDS: "Ledger verification in progress.",
        BishopState.ORDER_QUEUED: "Order queued. Awaiting confirmation.",
    }
    
    # Valid state transitions: current_state -> allowed_next_states
    VALID_TRANSITIONS: dict[BishopState, set[BishopState]] = {
        BishopState.IDLE: {BishopState.SCANNING, BishopState.ANALYZING_RISK, BishopState.CHECKING_FUNDS},
        BishopState.SCANNING: {BishopState.IDLE, BishopState.ANALYZING_RISK},
        BishopState.ANALYZING_RISK: {BishopState.IDLE, BishopState.CHECKING_FUNDS},
        BishopState.CHECKING_FUNDS: {BishopState.IDLE, BishopState.ORDER_QUEUED},
        BishopState.ORDER_QUEUED: {BishopState.IDLE},
    }
    
    def __init__(self) -> None:
        self._state: BishopState = BishopState.IDLE
        self._context: dict[str, Any] = {}
        self._transition_log: list[BishopStateTransition] = []
        self._state_handlers: dict[BishopState, Callable] = {}
    
    @property
    def state(self) -> BishopState:
        """Current FSM state."""
        return self._state
    
    @property
    def context(self) -> dict[str, Any]:
        """Current operational context."""
        return self._context.copy()
    
    def _log_transition(
        self,
        previous: Optional[BishopState],
        current: BishopState,
        trigger: str,
        message: str,
        context: Optional[dict] = None,
    ) -> BishopStateTransition:
        """Record state transition for audit trail."""
        transition = BishopStateTransition(
            previous_state=previous,
            current_state=current,
            trigger_event=trigger,
            context_data=context,
            output_message=message,
        )
        self._transition_log.append(transition)
        return transition
    
    def _validate_transition(self, target: BishopState) -> bool:
        """Validate if transition to target state is allowed."""
        return target in self.VALID_TRANSITIONS.get(self._state, set())
    
    def transition_to(
        self,
        target: BishopState,
        trigger: str,
        context: Optional[dict] = None,
    ) -> BishopResponse:
        """
        Execute state transition with validation.
        
        Args:
            target: Target state to transition to
            trigger: Event that triggered the transition
            context: Optional context data for the transition
        
        Returns:
            BishopResponse with new state and output message
        
        Raises:
            ValueError: If transition is not valid
        """
        if not self._validate_transition(target):
            return BishopResponse(
                state=self._state,
                message=f"Invalid transition. Current state: {self._state.value}. Target state {target.value} not reachable.",
                context={"error": "invalid_transition", "attempted_target": target.value},
            )
        
        previous = self._state
        self._state = target
        
        if context:
            self._context.update(context)
        
        message = self.STATE_OUTPUTS[target]
        self._log_transition(previous, target, trigger, message, context)
        
        return BishopResponse(
            state=self._state,
            message=message,
            context=self._context,
        )
    
    def reset(self) -> BishopResponse:
        """Reset FSM to IDLE state."""
        previous = self._state
        self._state = BishopState.IDLE
        self._context = {}
        
        message = "State reset. " + self.STATE_OUTPUTS[BishopState.IDLE]
        self._log_transition(previous, BishopState.IDLE, "RESET", message)
        
        return BishopResponse(
            state=self._state,
            message=message,
        )
    
    # =========================================================================
    # OPERATIONAL COMMANDS
    # =========================================================================
    
    def begin_scan(self, location: Optional[str] = None) -> BishopResponse:
        """Initiate inventory scanning operation."""
        context = {"location": location} if location else {}
        return self.transition_to(BishopState.SCANNING, "SCAN_INITIATED", context)
    
    def complete_scan(
        self,
        items_detected: int,
        products: list[dict],
    ) -> BishopResponse:
        """
        Complete scan and transition to risk analysis or idle.
        
        Args:
            items_detected: Number of unique items detected
            products: List of scanned product data
        """
        if self._state != BishopState.SCANNING:
            return BishopResponse(
                state=self._state,
                message=f"Cannot complete scan. Current state: {self._state.value}.",
                context={"error": "invalid_state"},
            )
        
        self._context["scan_result"] = {
            "items_detected": items_detected,
            "products": products,
            "scanned_at": datetime.utcnow().isoformat(),
        }
        
        # Transition to risk analysis if products detected
        if items_detected > 0:
            return self.transition_to(
                BishopState.ANALYZING_RISK,
                "SCAN_COMPLETE",
                {"items_detected": items_detected},
            )
        
        return self.transition_to(BishopState.IDLE, "SCAN_EMPTY")
    
    def process_risk_check(self, risk_response: RiskCheckResponse) -> BishopResponse:
        """
        Process ClaimsIQ risk assessment result.
        
        Decision Logic:
            - If flagged as high/critical → Block and return to IDLE
            - If flagged with liability → Log and continue with warning
            - Otherwise → Proceed to funds check
        """
        if self._state != BishopState.ANALYZING_RISK:
            return BishopResponse(
                state=self._state,
                message=f"Cannot process risk. Current state: {self._state.value}.",
                context={"error": "invalid_state"},
            )
        
        self._context["risk_check"] = {
            "is_flagged": risk_response.is_flagged,
            "risk_level": risk_response.risk_level,
            "liability_flags": risk_response.liability_flags,
        }
        
        # High/Critical risk → Block operation
        if risk_response.risk_level in ("high", "critical"):
            message = f"Risk level {risk_response.risk_level}. Operation blocked. {risk_response.recommended_action or 'Manual review required.'}"
            self._log_transition(
                self._state,
                BishopState.IDLE,
                "RISK_BLOCKED",
                message,
                {"risk_level": risk_response.risk_level},
            )
            self._state = BishopState.IDLE
            return BishopResponse(
                state=self._state,
                message=message,
                context=self._context,
            )
        
        # Liability flags present → Log warning, continue
        if risk_response.liability_flags:
            self._context["warnings"] = risk_response.liability_flags
            message = f"Liability flag raised: {', '.join(risk_response.liability_flags)}. Proceeding to funds verification."
        else:
            message = "Risk check passed. Proceeding to funds verification."
        
        return self.transition_to(BishopState.CHECKING_FUNDS, "RISK_CLEARED", {"message": message})
    
    def process_ledger_check(
        self,
        ledger_response: LedgerCheckResponse,
        order_total: Decimal,
    ) -> BishopResponse:
        """
        Process Ledger balance verification.
        
        Decision Logic:
            - If sufficient_funds = false → Block order, return to IDLE
            - If sufficient_funds = true → Queue order
        """
        if self._state != BishopState.CHECKING_FUNDS:
            return BishopResponse(
                state=self._state,
                message=f"Cannot process ledger check. Current state: {self._state.value}.",
                context={"error": "invalid_state"},
            )
        
        self._context["ledger_check"] = {
            "order_total": str(order_total),
            "available_balance": str(ledger_response.available_balance),
            "sufficient_funds": ledger_response.sufficient_funds,
        }
        
        # Insufficient funds → Block
        if not ledger_response.sufficient_funds:
            shortfall = order_total - ledger_response.available_balance
            message = f"Ledger balance insufficient. Required: {order_total}. Available: {ledger_response.available_balance}. Shortfall: {shortfall}. Order blocked."
            self._log_transition(
                self._state,
                BishopState.IDLE,
                "FUNDS_INSUFFICIENT",
                message,
                {"shortfall": str(shortfall)},
            )
            self._state = BishopState.IDLE
            return BishopResponse(
                state=self._state,
                message=message,
                context=self._context,
            )
        
        # Sufficient funds → Queue order
        message = f"Ledger verified. Balance: {ledger_response.available_balance}. Order total: {order_total}. Proceeding to queue."
        return self.transition_to(BishopState.ORDER_QUEUED, "FUNDS_VERIFIED", {"message": message})
    
    def queue_order(
        self,
        vendor_response: VendorQueryResponse,
        order_id: uuid.UUID,
    ) -> BishopResponse:
        """
        Finalize order queuing with vendor details.
        
        Args:
            vendor_response: Vendor availability confirmation
            order_id: Generated order ID
        """
        if self._state != BishopState.ORDER_QUEUED:
            return BishopResponse(
                state=self._state,
                message=f"Cannot queue order. Current state: {self._state.value}.",
                context={"error": "invalid_state"},
            )
        
        eta = f"{vendor_response.estimated_delivery_hours} hours" if vendor_response.estimated_delivery_hours else "TBD"
        message = f"Order queued with {vendor_response.vendor_name}. Order ID: {order_id}. ETA: {eta}."
        
        self._context["order"] = {
            "order_id": str(order_id),
            "vendor_name": vendor_response.vendor_name,
            "vendor_id": str(vendor_response.vendor_id),
            "eta_hours": vendor_response.estimated_delivery_hours,
        }
        
        self._log_transition(
            self._state,
            BishopState.ORDER_QUEUED,
            "ORDER_CONFIRMED",
            message,
            self._context["order"],
        )
        
        return BishopResponse(
            state=self._state,
            message=message,
            context=self._context,
        )
    
    def get_transition_log(self) -> list[BishopStateTransition]:
        """Return full transition audit log."""
        return self._transition_log.copy()
    
    def get_status(self) -> BishopResponse:
        """Get current Bishop status."""
        return BishopResponse(
            state=self._state,
            message=self.STATE_OUTPUTS[self._state],
            context=self._context,
        )


# Singleton instance for application-wide use
bishop_instance = BishopFSM()
