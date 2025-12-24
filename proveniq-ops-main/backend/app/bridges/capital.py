"""
PROVENIQ Ops - Capital Bridge

OPS ⇄ CAPITAL (Inventory → Cash)

This bridge enables:
1. Inventory-backed liquidity signals
2. Asset-quality scoring for lending
3. Credit constraint feedback into ordering
4. Liquidation → Ledger auto-settlement
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List
from uuid import UUID
import logging

from pydantic import BaseModel

from .events import (
    LiquiditySnapshotEvent,
    CreditConstraintEvent,
    SettlementCompleteEvent,
)

logger = logging.getLogger(__name__)


# ============================================
# Data Models
# ============================================

class LiquiditySnapshot(BaseModel):
    """Current liquidity status from Capital"""
    org_id: UUID
    timestamp: datetime
    
    # Cash position
    available_cash_cents: int
    committed_orders_cents: int
    pending_receivables_cents: int
    
    # Credit position
    credit_limit_cents: int
    credit_used_cents: int
    credit_available_cents: int
    
    # Derived metrics
    effective_liquidity_cents: int
    days_runway: float  # Based on burn rate
    
    # Constraints
    is_constrained: bool
    constraint_reason: Optional[str] = None


class CreditConstraints(BaseModel):
    """Credit constraints affecting ordering"""
    org_id: UUID
    
    # Global constraints
    can_place_orders: bool
    max_order_amount_cents: int
    requires_approval_above_cents: int
    
    # Vendor-specific
    blocked_vendors: List[str] = []
    preferred_vendors: List[str] = []
    
    # Payment terms
    net_terms_days: int = 30
    early_pay_discount_bps: int = 0  # basis points
    
    # Warnings
    warnings: List[str] = []


class AssetQuality(BaseModel):
    """Inventory asset quality score for lending"""
    org_id: UUID
    location_id: Optional[UUID] = None
    
    # Overall score
    score: float  # 0.0 - 1.0
    grade: str  # "A", "B", "C", "D", "F"
    
    # Components
    freshness_score: float  # % not near expiration
    turnover_score: float  # Inventory turnover rate
    shrinkage_score: float  # Inverse of shrinkage rate
    diversity_score: float  # SKU diversity
    
    # Lending implications
    collateral_value_cents: int
    lendable_percentage: float  # % of inventory that can back loans
    max_loan_cents: int


class Settlement(BaseModel):
    """Settlement record for liquidation proceeds"""
    settlement_id: UUID
    auction_id: Optional[UUID] = None
    item_id: UUID
    org_id: UUID
    
    # Amounts
    gross_amount_cents: int
    fees_cents: int
    net_amount_cents: int
    
    # Status
    status: str  # "pending", "processing", "completed", "failed"
    settlement_date: Optional[datetime] = None
    ledger_entry_id: Optional[UUID] = None


# ============================================
# Bridge Interface
# ============================================

class CapitalBridge(ABC):
    """
    Abstract interface for Capital integration.
    
    Ops uses this bridge to:
    - Get liquidity snapshots for ordering decisions
    - Check credit constraints before placing orders
    - Get inventory asset quality scores
    - Settle liquidation proceeds
    """
    
    @abstractmethod
    async def get_liquidity_snapshot(
        self,
        org_id: UUID,
    ) -> LiquiditySnapshot:
        """
        Get current liquidity status.
        
        Used by Bishop to gate ordering decisions.
        """
        pass
    
    @abstractmethod
    async def get_credit_constraints(
        self,
        org_id: UUID,
    ) -> CreditConstraints:
        """
        Get credit constraints affecting ordering.
        
        Used to determine max order amounts and blocked vendors.
        """
        pass
    
    @abstractmethod
    async def check_order_allowed(
        self,
        org_id: UUID,
        order_amount_cents: int,
        vendor_id: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if an order can be placed.
        
        Returns (allowed, reason_if_blocked).
        """
        pass
    
    @abstractmethod
    async def get_asset_quality(
        self,
        org_id: UUID,
        location_id: Optional[UUID] = None,
    ) -> AssetQuality:
        """
        Get inventory asset quality score.
        
        Used for inventory-backed lending decisions.
        """
        pass
    
    @abstractmethod
    async def initiate_settlement(
        self,
        org_id: UUID,
        item_id: UUID,
        gross_amount_cents: int,
        fees_cents: int,
        auction_id: Optional[UUID] = None,
    ) -> Settlement:
        """
        Initiate settlement of liquidation proceeds.
        
        Creates a pending settlement record.
        """
        pass
    
    @abstractmethod
    async def get_settlement_status(
        self,
        settlement_id: UUID,
    ) -> Settlement:
        """
        Get status of a settlement.
        """
        pass
    
    @abstractmethod
    async def subscribe_to_constraints(
        self,
        org_id: UUID,
        callback_url: str,
    ) -> bool:
        """
        Subscribe to credit constraint updates.
        
        Capital will POST to callback_url when constraints change.
        """
        pass


# ============================================
# Mock Implementation (for development)
# ============================================

class MockCapitalBridge(CapitalBridge):
    """
    Mock implementation for development and testing.
    
    In production, this would call the Capital/Ledger API.
    """
    
    def __init__(self):
        self._settlements: dict[UUID, Settlement] = {}
        self._subscriptions: dict[UUID, str] = {}
    
    async def get_liquidity_snapshot(
        self,
        org_id: UUID,
    ) -> LiquiditySnapshot:
        logger.info(f"[MOCK] Getting liquidity snapshot for org {org_id}")
        
        # Mock: Return healthy liquidity
        available = 5000000  # $50,000
        committed = 1200000  # $12,000
        credit_limit = 2500000  # $25,000
        credit_used = 500000  # $5,000
        
        return LiquiditySnapshot(
            org_id=org_id,
            timestamp=datetime.utcnow(),
            available_cash_cents=available,
            committed_orders_cents=committed,
            pending_receivables_cents=800000,  # $8,000
            credit_limit_cents=credit_limit,
            credit_used_cents=credit_used,
            credit_available_cents=credit_limit - credit_used,
            effective_liquidity_cents=available + (credit_limit - credit_used) - committed,
            days_runway=45.0,
            is_constrained=False,
        )
    
    async def get_credit_constraints(
        self,
        org_id: UUID,
    ) -> CreditConstraints:
        logger.info(f"[MOCK] Getting credit constraints for org {org_id}")
        
        return CreditConstraints(
            org_id=org_id,
            can_place_orders=True,
            max_order_amount_cents=1000000,  # $10,000
            requires_approval_above_cents=500000,  # $5,000
            blocked_vendors=[],
            preferred_vendors=["SYSCO", "US Foods"],
            net_terms_days=30,
            early_pay_discount_bps=200,  # 2%
            warnings=[],
        )
    
    async def check_order_allowed(
        self,
        org_id: UUID,
        order_amount_cents: int,
        vendor_id: str,
    ) -> tuple[bool, Optional[str]]:
        logger.info(f"[MOCK] Checking order: ${order_amount_cents/100:.2f} from {vendor_id}")
        
        constraints = await self.get_credit_constraints(org_id)
        
        if vendor_id in constraints.blocked_vendors:
            return False, f"Vendor {vendor_id} is blocked due to payment issues"
        
        if order_amount_cents > constraints.max_order_amount_cents:
            return False, f"Order exceeds maximum of ${constraints.max_order_amount_cents/100:.2f}"
        
        liquidity = await self.get_liquidity_snapshot(org_id)
        if order_amount_cents > liquidity.effective_liquidity_cents:
            return False, "Insufficient liquidity for this order"
        
        return True, None
    
    async def get_asset_quality(
        self,
        org_id: UUID,
        location_id: Optional[UUID] = None,
    ) -> AssetQuality:
        logger.info(f"[MOCK] Getting asset quality for org {org_id}")
        
        # Mock: Return B-grade quality
        return AssetQuality(
            org_id=org_id,
            location_id=location_id,
            score=0.72,
            grade="B",
            freshness_score=0.85,
            turnover_score=0.65,
            shrinkage_score=0.78,
            diversity_score=0.60,
            collateral_value_cents=3500000,  # $35,000
            lendable_percentage=0.60,
            max_loan_cents=2100000,  # $21,000
        )
    
    async def initiate_settlement(
        self,
        org_id: UUID,
        item_id: UUID,
        gross_amount_cents: int,
        fees_cents: int,
        auction_id: Optional[UUID] = None,
    ) -> Settlement:
        from uuid import uuid4
        
        settlement = Settlement(
            settlement_id=uuid4(),
            auction_id=auction_id,
            item_id=item_id,
            org_id=org_id,
            gross_amount_cents=gross_amount_cents,
            fees_cents=fees_cents,
            net_amount_cents=gross_amount_cents - fees_cents,
            status="pending",
        )
        
        self._settlements[settlement.settlement_id] = settlement
        logger.info(f"[MOCK] Initiated settlement {settlement.settlement_id} for ${settlement.net_amount_cents/100:.2f}")
        
        return settlement
    
    async def get_settlement_status(
        self,
        settlement_id: UUID,
    ) -> Settlement:
        if settlement_id in self._settlements:
            return self._settlements[settlement_id]
        raise ValueError(f"Settlement {settlement_id} not found")
    
    async def subscribe_to_constraints(
        self,
        org_id: UUID,
        callback_url: str,
    ) -> bool:
        self._subscriptions[org_id] = callback_url
        logger.info(f"[MOCK] Subscribed org {org_id} to constraint updates at {callback_url}")
        return True


# ============================================
# Bridge Factory
# ============================================

_bridge_instance: Optional[CapitalBridge] = None


def get_capital_bridge() -> CapitalBridge:
    """
    Get the Capital bridge instance.
    
    In production, this would return a real API client.
    For now, returns mock implementation.
    """
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = MockCapitalBridge()
    return _bridge_instance
