"""
PROVENIQ Ops - Bishop Cash Flow Aware Ordering Engine
Gate inventory orders through liquidity reality via the Ledger.

DAG Nodes: N20, N40

LOGIC:
1. Classify orders as CRITICAL or DEFERRABLE
2. Delay non-critical orders when liquidity constrained
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.core.types import Money
from app.models.cashflow import (
    CashFlowConfig,
    CashFlowForecast,
    DelayReason,
    LedgerBalance,
    LiquidityWarningAlert,
    ObligationType,
    OrderAlertType,
    OrderDecision,
    OrderDelayAlert,
    OrderPriority,
    OrderQueueAnalysis,
    PendingOrder,
    UpcomingObligation,
)
from app.services.audit import audit_service
from app.models.audit import ReasonCode


class CashFlowOrderingEngine:
    """
    Bishop Cash Flow Aware Ordering Engine
    
    Gates inventory orders through liquidity checks.
    
    Maps to DAG nodes: N20 (liquidity gate), N40 (order execution)
    """
    
    def __init__(self) -> None:
        self._config = CashFlowConfig()
        
        # Data stores
        self._ledger_balance: Optional[LedgerBalance] = None
        self._obligations: list[UpcomingObligation] = []
        self._pending_orders: dict[uuid.UUID, PendingOrder] = {}
        self._decisions: list[OrderDecision] = []
        
        # Alerts
        self._alerts: list[OrderDelayAlert] = []
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure(self, config: CashFlowConfig) -> None:
        """Update engine configuration."""
        self._config = config
    
    def get_config(self) -> CashFlowConfig:
        """Get current configuration."""
        return self._config
    
    # =========================================================================
    # DATA REGISTRATION
    # =========================================================================
    
    def update_ledger_balance(self, balance: LedgerBalance) -> None:
        """Update current ledger balance from Ledger system."""
        self._ledger_balance = balance
    
    def register_obligation(self, obligation: UpcomingObligation) -> None:
        """Register an upcoming financial obligation."""
        # Calculate days until due
        obligation.days_until_due = (obligation.due_date - datetime.utcnow()).days
        self._obligations.append(obligation)
        
        # Sort by due date
        self._obligations.sort(key=lambda o: o.due_date)
    
    def submit_order(self, order: PendingOrder) -> OrderDecision:
        """
        Submit an order for cash flow approval.
        
        Returns decision: approved, delayed, or blocked.
        """
        self._pending_orders[order.order_id] = order
        
        # Make decision
        decision = self._evaluate_order(order)
        self._decisions.append(decision)
        
        # Update order status
        if decision.approved:
            order.status = "approved"
        elif decision.delayed:
            order.status = "delayed"
        else:
            order.status = "blocked"
        
        # Generate alert if delayed
        if decision.delayed:
            alert = self._create_delay_alert(order, decision)
            self._alerts.append(alert)
            
            # Log to audit service
            audit_service.log_block(
                blocked_action="order_submission",
                entity_id=order.order_id,
                entity_type="purchase_order",
                blocker="liquidity_gate",
                dag_node_id="N20_liquidity_gate",
                reason_codes=[ReasonCode.INSUFFICIENT_FUNDS],
                reason_details={
                    "delay_hours": decision.delay_hours,
                    "reason": decision.delay_reason.value if decision.delay_reason else None,
                },
                blocked_value_micros=order.total_amount_micros,
                threshold_value_micros=self._ledger_balance.available_balance_micros if self._ledger_balance else 0,
            )
        
        return decision
    
    # =========================================================================
    # ORDER EVALUATION (N20)
    # =========================================================================
    
    def _evaluate_order(self, order: PendingOrder) -> OrderDecision:
        """
        Evaluate an order against cash flow constraints.
        
        Logic:
        1. Check if we have enough cash
        2. Check upcoming obligations
        3. Apply priority rules
        """
        if not self._ledger_balance:
            return self._create_decision(
                order,
                approved=False,
                blocked=True,
                reason_codes=["no_ledger_data"],
            )
        
        available = self._ledger_balance.available_balance_micros
        order_amount = order.total_amount_micros
        
        # Get upcoming obligations
        obligations_7d = self._get_obligations_within_days(7)
        total_obligations = sum(o.amount_micros for o in obligations_7d)
        
        # Calculate required reserve
        required_reserve = max(
            self._config.minimum_reserve_micros,
            total_obligations
        )
        
        # Calculate what we'd have left after order
        remaining_after = available - order_amount
        
        # Check 1: Can we even afford it?
        if order_amount > available:
            return self._create_decision(
                order,
                approved=False,
                blocked=True,
                reason_codes=["insufficient_funds"],
                remaining_after=remaining_after,
            )
        
        # Check 2: Would it breach minimum reserve?
        if remaining_after < self._config.minimum_reserve_micros:
            # Critical orders can breach reserve
            if order.priority == OrderPriority.CRITICAL and self._config.auto_approve_critical:
                return self._create_decision(
                    order,
                    approved=True,
                    reason_codes=["critical_override", "reserve_breach_warning"],
                    remaining_after=remaining_after,
                )
            
            # Delay non-critical
            delay_hours = self._calculate_delay(order, remaining_after, required_reserve)
            return self._create_decision(
                order,
                approved=False,
                delayed=True,
                delay_hours=delay_hours,
                delay_reason=DelayReason.CASH_RESERVE_PROTECTION,
                reason_codes=["reserve_protection"],
                remaining_after=remaining_after,
            )
        
        # Check 3: Are we in a payroll protection window?
        payroll_due = self._get_next_obligation_of_type(ObligationType.PAYROLL)
        if payroll_due and payroll_due.days_until_due <= self._config.payroll_protection_days:
            # Check if order would impact payroll
            if remaining_after < payroll_due.amount_micros + self._config.minimum_reserve_micros:
                if order.priority in (OrderPriority.DEFERRABLE, OrderPriority.OPTIONAL):
                    delay_hours = (payroll_due.days_until_due + 1) * 24
                    return self._create_decision(
                        order,
                        approved=False,
                        delayed=True,
                        delay_hours=min(delay_hours, self._config.max_delay_hours),
                        delay_reason=DelayReason.PAYROLL_WINDOW,
                        reason_codes=["payroll_protection", f"payroll_in_{payroll_due.days_until_due}_days"],
                        remaining_after=remaining_after,
                    )
        
        # Check 4: Would remaining be less than upcoming obligations?
        if remaining_after < total_obligations:
            if order.priority in (OrderPriority.DEFERRABLE, OrderPriority.OPTIONAL):
                delay_hours = self._calculate_delay(order, remaining_after, total_obligations)
                return self._create_decision(
                    order,
                    approved=False,
                    delayed=True,
                    delay_hours=delay_hours,
                    delay_reason=DelayReason.UPCOMING_OBLIGATIONS,
                    reason_codes=["obligation_coverage"],
                    remaining_after=remaining_after,
                )
        
        # Check 5: Liquidity is tight but order is high priority
        liquidity_ratio = Decimal(remaining_after) / Decimal(required_reserve) * 100 if required_reserve > 0 else Decimal("100")
        if liquidity_ratio < self._config.tight_liquidity_threshold_pct:
            if order.priority == OrderPriority.OPTIONAL and self._config.defer_optional_when_tight:
                return self._create_decision(
                    order,
                    approved=False,
                    delayed=True,
                    delay_hours=self._config.default_delay_hours,
                    delay_reason=DelayReason.LIQUIDITY_CONSTRAINT,
                    reason_codes=["tight_liquidity", "optional_deferred"],
                    remaining_after=remaining_after,
                )
        
        # All checks passed - approve
        return self._create_decision(
            order,
            approved=True,
            reason_codes=["sufficient_funds", "obligations_covered"],
            remaining_after=remaining_after,
        )
    
    def _create_decision(
        self,
        order: PendingOrder,
        approved: bool,
        delayed: bool = False,
        blocked: bool = False,
        delay_hours: Optional[int] = None,
        delay_reason: Optional[DelayReason] = None,
        reason_codes: Optional[list[str]] = None,
        remaining_after: Optional[int] = None,
    ) -> OrderDecision:
        """Create an order decision."""
        review_at = None
        if delayed and delay_hours:
            review_at = datetime.utcnow() + timedelta(hours=delay_hours)
        
        return OrderDecision(
            order_id=order.order_id,
            approved=approved,
            delayed=delayed,
            blocked=blocked,
            delay_hours=delay_hours,
            delay_reason=delay_reason,
            review_at=review_at,
            available_balance_micros=self._ledger_balance.available_balance_micros if self._ledger_balance else 0,
            order_amount_micros=order.total_amount_micros,
            remaining_after_micros=remaining_after,
            reason_codes=reason_codes or [],
        )
    
    def _calculate_delay(
        self,
        order: PendingOrder,
        remaining: int,
        required: int,
    ) -> int:
        """Calculate appropriate delay hours."""
        shortfall = required - remaining
        
        # Base delay on priority
        if order.priority == OrderPriority.HIGH:
            base_delay = 12
        elif order.priority == OrderPriority.NORMAL:
            base_delay = 24
        elif order.priority == OrderPriority.DEFERRABLE:
            base_delay = 48
        else:  # OPTIONAL
            base_delay = 72
        
        # Adjust based on shortfall severity
        if shortfall > order.total_amount_micros:
            base_delay = min(base_delay * 2, self._config.max_delay_hours)
        
        return min(base_delay, self._config.max_delay_hours)
    
    def _create_delay_alert(
        self,
        order: PendingOrder,
        decision: OrderDecision,
    ) -> OrderDelayAlert:
        """Create a delay alert."""
        obligations = self._get_obligations_within_days(7)
        total_obligations = sum(o.amount_micros for o in obligations)
        
        # Find blocking obligation if any
        blocking = None
        for ob in obligations:
            if ob.obligation_type == ObligationType.PAYROLL:
                blocking = f"Payroll due in {ob.days_until_due} days"
                break
        
        shortfall = None
        if decision.remaining_after_micros and decision.remaining_after_micros < 0:
            shortfall = abs(decision.remaining_after_micros)
        
        return OrderDelayAlert(
            alert_type=OrderAlertType.ORDER_DELAYED,
            order_id=order.order_id,
            vendor_name=order.vendor_name,
            order_amount_micros=order.total_amount_micros,
            order_priority=order.priority,
            delay_hours=decision.delay_hours or self._config.default_delay_hours,
            reason=decision.delay_reason or DelayReason.LIQUIDITY_CONSTRAINT,
            review_at=decision.review_at or datetime.utcnow() + timedelta(hours=24),
            current_balance_micros=self._ledger_balance.available_balance_micros if self._ledger_balance else 0,
            upcoming_obligations_micros=total_obligations,
            shortfall_micros=shortfall,
            blocking_obligation=blocking,
        )
    
    # =========================================================================
    # CASH FLOW ANALYSIS
    # =========================================================================
    
    def get_cash_flow_forecast(self) -> CashFlowForecast:
        """Get cash flow forecast for decision making."""
        if not self._ledger_balance:
            return CashFlowForecast(
                current_balance_micros=0,
                total_obligations_7d_micros=0,
                total_obligations_14d_micros=0,
                projected_balance_7d_micros=0,
                projected_balance_14d_micros=0,
                liquidity_risk_level="unknown",
            )
        
        current = self._ledger_balance.available_balance_micros
        
        obligations_7d = sum(o.amount_micros for o in self._get_obligations_within_days(7))
        obligations_14d = sum(o.amount_micros for o in self._get_obligations_within_days(14))
        
        projected_7d = current - obligations_7d
        projected_14d = current - obligations_14d
        
        # Determine risk level
        if projected_7d < 0:
            risk = "critical"
        elif projected_7d < self._config.minimum_reserve_micros:
            risk = "high"
        elif projected_14d < self._config.minimum_reserve_micros:
            risk = "medium"
        else:
            risk = "low"
        
        return CashFlowForecast(
            current_balance_micros=current,
            total_obligations_7d_micros=obligations_7d,
            total_obligations_14d_micros=obligations_14d,
            projected_balance_7d_micros=projected_7d,
            projected_balance_14d_micros=projected_14d,
            liquidity_risk_level=risk,
        )
    
    def analyze_order_queue(self) -> OrderQueueAnalysis:
        """Analyze the pending order queue."""
        pending = [o for o in self._pending_orders.values() if o.status == "pending"]
        
        total_value = sum(o.total_amount_micros for o in pending)
        
        critical = [o for o in pending if o.priority == OrderPriority.CRITICAL]
        critical_value = sum(o.total_amount_micros for o in critical)
        
        deferrable = [o for o in pending if o.priority in (OrderPriority.DEFERRABLE, OrderPriority.OPTIONAL)]
        deferrable_value = sum(o.total_amount_micros for o in deferrable)
        
        available = self._ledger_balance.available_balance_micros if self._ledger_balance else 0
        
        # Count decisions
        approved = len([d for d in self._decisions if d.approved])
        delayed = len([d for d in self._decisions if d.delayed])
        blocked = len([d for d in self._decisions if d.blocked])
        
        return OrderQueueAnalysis(
            total_pending_orders=len(pending),
            total_pending_value_micros=total_value,
            critical_orders=len(critical),
            critical_value_micros=critical_value,
            deferrable_orders=len(deferrable),
            deferrable_value_micros=deferrable_value,
            available_balance_micros=available,
            can_fund_critical=available >= critical_value,
            can_fund_all=available >= total_value,
            orders_approved=approved,
            orders_delayed=delayed,
            orders_blocked=blocked,
            alerts=self._alerts[-10:],
        )
    
    def get_liquidity_warning(self) -> Optional[LiquidityWarningAlert]:
        """Check if liquidity warning should be raised."""
        if not self._ledger_balance:
            return None
        
        forecast = self.get_cash_flow_forecast()
        
        if forecast.liquidity_risk_level in ("high", "critical"):
            pending = [o for o in self._pending_orders.values() if o.status == "pending"]
            orders_at_risk = len(pending)
            value_at_risk = sum(o.total_amount_micros for o in pending)
            
            shortfall = None
            shortfall_date = None
            if forecast.projected_balance_7d_micros < 0:
                shortfall = abs(forecast.projected_balance_7d_micros)
                shortfall_date = datetime.utcnow() + timedelta(days=7)
            
            return LiquidityWarningAlert(
                current_balance_micros=forecast.current_balance_micros,
                minimum_reserve_micros=self._config.minimum_reserve_micros,
                obligations_next_7d=self._get_obligations_within_days(7),
                total_obligations_micros=forecast.total_obligations_7d_micros,
                orders_at_risk=orders_at_risk,
                orders_value_at_risk_micros=value_at_risk,
                projected_shortfall_micros=shortfall,
                shortfall_date=shortfall_date,
            )
        
        return None
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _get_obligations_within_days(self, days: int) -> list[UpcomingObligation]:
        """Get obligations due within N days."""
        cutoff = datetime.utcnow() + timedelta(days=days)
        return [o for o in self._obligations if o.due_date <= cutoff]
    
    def _get_next_obligation_of_type(self, ob_type: ObligationType) -> Optional[UpcomingObligation]:
        """Get the next obligation of a specific type."""
        for ob in self._obligations:
            if ob.obligation_type == ob_type and ob.due_date > datetime.utcnow():
                return ob
        return None
    
    # =========================================================================
    # QUERY
    # =========================================================================
    
    def get_alerts(self, limit: int = 100) -> list[OrderDelayAlert]:
        """Get order delay alerts."""
        return self._alerts[-limit:]
    
    def get_order(self, order_id: uuid.UUID) -> Optional[PendingOrder]:
        """Get a specific order."""
        return self._pending_orders.get(order_id)
    
    def get_decision(self, order_id: uuid.UUID) -> Optional[OrderDecision]:
        """Get decision for an order."""
        for d in reversed(self._decisions):
            if d.order_id == order_id:
                return d
        return None
    
    def get_delayed_orders(self) -> list[PendingOrder]:
        """Get orders currently delayed."""
        return [o for o in self._pending_orders.values() if o.status == "delayed"]
    
    def clear_data(self) -> None:
        """Clear all data (for testing)."""
        self._ledger_balance = None
        self._obligations.clear()
        self._pending_orders.clear()
        self._decisions.clear()
        self._alerts.clear()


# Singleton instance
cashflow_engine = CashFlowOrderingEngine()
