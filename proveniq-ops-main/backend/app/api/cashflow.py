"""
PROVENIQ Ops - Cash Flow Aware Ordering API Routes
Bishop liquidity-gated ordering endpoints

DAG Nodes: N20, N40

Gates inventory orders through liquidity reality via the Ledger.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query

from app.core.types import Money
from app.models.cashflow import (
    CashFlowConfig,
    CashFlowForecast,
    LedgerBalance,
    LiquidityWarningAlert,
    ObligationType,
    OrderDecision,
    OrderDelayAlert,
    OrderPriority,
    OrderQueueAnalysis,
    PendingOrder,
    UpcomingObligation,
)
from app.services.bishop.cashflow_engine import cashflow_engine

router = APIRouter(prefix="/cashflow", tags=["Cash Flow Ordering"])


# =============================================================================
# ORDER SUBMISSION
# =============================================================================

@router.post("/order/submit", response_model=OrderDecision)
async def submit_order(
    vendor_id: uuid.UUID,
    vendor_name: str,
    total_amount_dollars: str,
    priority: OrderPriority = OrderPriority.NORMAL,
    priority_reason: Optional[str] = None,
) -> OrderDecision:
    """
    Submit an order for cash flow approval.
    
    Bishop Logic (N20/N40):
        1. Classify orders as CRITICAL or DEFERRABLE
        2. Delay non-critical orders when liquidity constrained
    
    Returns:
        OrderDecision with approved/delayed/blocked status
    """
    order = PendingOrder(
        vendor_id=vendor_id,
        vendor_name=vendor_name,
        total_amount_micros=Money.from_dollars(total_amount_dollars),
        priority=priority,
        priority_reason=priority_reason,
    )
    
    return cashflow_engine.submit_order(order)


@router.get("/order/{order_id}")
async def get_order(order_id: uuid.UUID) -> dict:
    """Get a specific order and its decision."""
    order = cashflow_engine.get_order(order_id)
    if not order:
        return {"error": "Order not found"}
    
    decision = cashflow_engine.get_decision(order_id)
    
    return {
        "order": order.model_dump(),
        "decision": decision.model_dump() if decision else None,
    }


@router.get("/orders/delayed")
async def get_delayed_orders() -> dict:
    """Get orders currently delayed due to liquidity constraints."""
    orders = cashflow_engine.get_delayed_orders()
    total_value = sum(o.total_amount_micros for o in orders)
    
    return {
        "count": len(orders),
        "total_value_micros": total_value,
        "total_value_display": Money.to_dollars_str(total_value),
        "orders": [o.model_dump() for o in orders],
    }


# =============================================================================
# CASH FLOW ANALYSIS
# =============================================================================

@router.get("/forecast", response_model=CashFlowForecast)
async def get_forecast() -> CashFlowForecast:
    """
    Get cash flow forecast.
    
    Shows current balance, upcoming obligations, and liquidity risk.
    """
    return cashflow_engine.get_cash_flow_forecast()


@router.get("/queue", response_model=OrderQueueAnalysis)
async def analyze_order_queue() -> OrderQueueAnalysis:
    """
    Analyze pending order queue against cash flow.
    
    Shows which orders can be funded and which are at risk.
    """
    return cashflow_engine.analyze_order_queue()


@router.get("/warning")
async def get_liquidity_warning() -> dict:
    """
    Check for liquidity warning.
    
    Returns warning if cash flow is constrained.
    """
    warning = cashflow_engine.get_liquidity_warning()
    if warning:
        return {
            "has_warning": True,
            "warning": warning.model_dump(),
        }
    return {
        "has_warning": False,
        "status": "Liquidity healthy",
    }


# =============================================================================
# ALERTS
# =============================================================================

@router.get("/alerts", response_model=list[OrderDelayAlert])
async def get_alerts(limit: int = Query(100, ge=1, le=1000)) -> list[OrderDelayAlert]:
    """Get order delay alerts."""
    return cashflow_engine.get_alerts(limit=limit)


# =============================================================================
# CONFIGURATION
# =============================================================================

@router.get("/config", response_model=CashFlowConfig)
async def get_config() -> CashFlowConfig:
    """Get current cash flow configuration."""
    return cashflow_engine.get_config()


@router.put("/config")
async def update_config(
    minimum_reserve_dollars: Optional[str] = None,
    reserve_days_coverage: Optional[int] = Query(None, ge=1),
    default_delay_hours: Optional[int] = Query(None, ge=1),
    auto_approve_critical: Optional[bool] = None,
) -> CashFlowConfig:
    """Update cash flow configuration."""
    config = cashflow_engine.get_config()
    
    if minimum_reserve_dollars is not None:
        config.minimum_reserve_micros = Money.from_dollars(minimum_reserve_dollars)
    if reserve_days_coverage is not None:
        config.reserve_days_coverage = reserve_days_coverage
    if default_delay_hours is not None:
        config.default_delay_hours = default_delay_hours
    if auto_approve_critical is not None:
        config.auto_approve_critical = auto_approve_critical
    
    cashflow_engine.configure(config)
    return config


# =============================================================================
# DATA REGISTRATION
# =============================================================================

@router.post("/data/ledger")
async def update_ledger_balance(
    cash_balance_dollars: str,
    available_balance_dollars: Optional[str] = None,
    minimum_reserve_dollars: str = "0",
) -> dict:
    """Update ledger balance from external Ledger system."""
    cash = Money.from_dollars(cash_balance_dollars)
    available = Money.from_dollars(available_balance_dollars) if available_balance_dollars else cash
    
    balance = LedgerBalance(
        cash_balance_micros=cash,
        available_balance_micros=available,
        minimum_reserve_micros=Money.from_dollars(minimum_reserve_dollars),
    )
    cashflow_engine.update_ledger_balance(balance)
    
    return {
        "status": "updated",
        "cash_balance_micros": cash,
        "available_balance_micros": available,
    }


@router.post("/data/obligation")
async def register_obligation(
    obligation_type: ObligationType,
    description: str,
    amount_dollars: str,
    due_date: datetime,
    is_mandatory: bool = True,
) -> dict:
    """Register an upcoming financial obligation."""
    obligation = UpcomingObligation(
        obligation_type=obligation_type,
        description=description,
        amount_micros=Money.from_dollars(amount_dollars),
        due_date=due_date,
        days_until_due=(due_date - datetime.utcnow()).days,
        is_mandatory=is_mandatory,
    )
    cashflow_engine.register_obligation(obligation)
    
    return {
        "status": "registered",
        "obligation_id": str(obligation.obligation_id),
        "description": description,
        "due_date": due_date.isoformat(),
    }


@router.delete("/data/clear")
async def clear_data() -> dict:
    """Clear all cash flow data (for testing)."""
    cashflow_engine.clear_data()
    return {"status": "cleared"}


# =============================================================================
# DEMO DATA
# =============================================================================

@router.post("/demo/setup")
async def setup_demo_data() -> dict:
    """
    Set up demo data for cash flow ordering testing.
    
    Creates ledger balance and upcoming obligations.
    """
    cashflow_engine.clear_data()
    
    now = datetime.utcnow()
    
    # Set ledger balance - tight liquidity scenario
    balance = LedgerBalance(
        cash_balance_micros=Money.from_dollars("75000"),  # $75k
        available_balance_micros=Money.from_dollars("72000"),  # $72k available
        minimum_reserve_micros=Money.from_dollars("25000"),  # $25k reserve
    )
    cashflow_engine.update_ledger_balance(balance)
    
    # Upcoming obligations
    obligations = [
        # Payroll in 2 days - high priority
        (ObligationType.PAYROLL, "Bi-weekly Payroll", "35000", now + timedelta(days=2)),
        # Vendor payment in 5 days
        (ObligationType.VENDOR_PAYMENT, "Sysco Invoice #4521", "12000", now + timedelta(days=5)),
        # Rent in 10 days
        (ObligationType.RENT, "Monthly Rent", "8500", now + timedelta(days=10)),
        # Utilities in 12 days
        (ObligationType.UTILITIES, "Electric + Gas", "2500", now + timedelta(days=12)),
    ]
    
    for ob_type, desc, amount, due in obligations:
        ob = UpcomingObligation(
            obligation_type=ob_type,
            description=desc,
            amount_micros=Money.from_dollars(amount),
            due_date=due,
            days_until_due=(due - now).days,
        )
        cashflow_engine.register_obligation(ob)
    
    # Test orders
    test_orders = [
        # Critical order - should approve despite tight cash
        {
            "vendor_id": uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            "vendor_name": "Sysco",
            "amount": "5000",
            "priority": OrderPriority.CRITICAL,
            "reason": "Chicken stockout imminent",
        },
        # Normal order - should delay (payroll in 2 days)
        {
            "vendor_id": uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            "vendor_name": "US Foods",
            "amount": "15000",
            "priority": OrderPriority.NORMAL,
            "reason": "Weekly restock",
        },
        # Deferrable order - should definitely delay
        {
            "vendor_id": uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            "vendor_name": "Restaurant Depot",
            "amount": "8000",
            "priority": OrderPriority.DEFERRABLE,
            "reason": "Stock up on supplies",
        },
    ]
    
    results = []
    for order_data in test_orders:
        order = PendingOrder(
            vendor_id=order_data["vendor_id"],
            vendor_name=order_data["vendor_name"],
            total_amount_micros=Money.from_dollars(order_data["amount"]),
            priority=order_data["priority"],
            priority_reason=order_data["reason"],
        )
        decision = cashflow_engine.submit_order(order)
        results.append({
            "vendor": order_data["vendor_name"],
            "amount": order_data["amount"],
            "priority": order_data["priority"].value,
            "decision": "APPROVED" if decision.approved else ("DELAYED" if decision.delayed else "BLOCKED"),
            "delay_hours": decision.delay_hours,
            "reason": decision.reason_codes,
        })
    
    return {
        "status": "demo_data_created",
        "ledger_balance": "$72,000 available",
        "obligations_7d": "$47,000 (Payroll $35k + Vendor $12k)",
        "liquidity_status": "TIGHT - Payroll in 2 days",
        "order_decisions": results,
        "expected_behavior": [
            "CRITICAL orders: Approved (stockout prevention)",
            "NORMAL orders: Delayed (payroll protection)",
            "DEFERRABLE orders: Delayed (liquidity constraint)",
        ],
    }
