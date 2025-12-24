"""
PROVENIQ Ops - Bids Bridge

OPS ⇄ BIDS (Excess → Liquidity)

This bridge enables:
1. Salvage readiness scoring
2. Condition grading & resale valuation
3. Liquidation path optimization (Transfer → Discount → Donate → Auction)
4. One-tap auction listing from Ops
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID
import logging

from pydantic import BaseModel

from .events import (
    ExcessInventoryEvent,
    SalvageReadyEvent,
    AuctionListedEvent,
    SalvageCondition,
)

logger = logging.getLogger(__name__)


# ============================================
# Data Models
# ============================================

class SalvageScore(BaseModel):
    """Salvage assessment for an item"""
    item_id: UUID
    score: float  # 0.0 - 1.0 (1.0 = highly salvageable)
    condition: SalvageCondition
    estimated_recovery_cents: int
    recovery_percentage: float  # % of original value recoverable
    recommended_path: str  # "transfer", "discount", "donate", "auction"
    reasoning: str


class LiquidationPath(BaseModel):
    """Recommended liquidation strategy"""
    item_id: UUID
    paths: List[dict]  # Ordered list of options
    # Each path: {"action": "transfer", "target": "location_id", "expected_recovery": 0.95}
    best_path: str
    expected_recovery_cents: int
    time_to_liquidate_hours: int


class AuctionListing(BaseModel):
    """Created auction listing"""
    auction_id: UUID
    item_id: UUID
    listing_url: str
    starting_price_cents: int
    reserve_price_cents: Optional[int] = None
    auction_start: datetime
    auction_end: datetime
    status: str = "active"


class AuctionResult(BaseModel):
    """Result of a completed auction"""
    auction_id: UUID
    item_id: UUID
    status: str  # "sold", "no_bids", "reserve_not_met", "cancelled"
    winning_bid_cents: Optional[int] = None
    winner_id: Optional[UUID] = None
    fees_cents: int = 0
    net_proceeds_cents: int = 0


# ============================================
# Bridge Interface
# ============================================

class BidsBridge(ABC):
    """
    Abstract interface for Bids integration.
    
    Ops uses this bridge to:
    - Get salvage scores for excess inventory
    - Determine optimal liquidation paths
    - Create auction listings
    - Track auction outcomes
    """
    
    @abstractmethod
    async def get_salvage_score(
        self,
        item_id: UUID,
        item_name: str,
        quantity: float,
        unit: str,
        original_value_cents: int,
        days_until_expiration: Optional[int] = None,
        condition: Optional[SalvageCondition] = None,
    ) -> SalvageScore:
        """
        Get salvage assessment for an item.
        
        Returns score, recommended path, and expected recovery.
        """
        pass
    
    @abstractmethod
    async def get_liquidation_path(
        self,
        item_id: UUID,
        quantity: float,
        original_value_cents: int,
        urgency: str = "normal",  # "low", "normal", "high", "critical"
    ) -> LiquidationPath:
        """
        Get recommended liquidation path for an item.
        
        Considers transfer, discount, donate, and auction options.
        """
        pass
    
    @abstractmethod
    async def create_auction(
        self,
        salvage_event: SalvageReadyEvent,
        duration_hours: int = 72,
        reserve_price_cents: Optional[int] = None,
    ) -> AuctionListing:
        """
        Create an auction listing for a salvage item.
        
        Returns the created listing with URL.
        """
        pass
    
    @abstractmethod
    async def get_auction_status(
        self,
        auction_id: UUID,
    ) -> AuctionListing:
        """
        Get current status of an auction.
        """
        pass
    
    @abstractmethod
    async def cancel_auction(
        self,
        auction_id: UUID,
        reason: str,
    ) -> bool:
        """
        Cancel an active auction.
        """
        pass
    
    @abstractmethod
    async def get_auction_result(
        self,
        auction_id: UUID,
    ) -> AuctionResult:
        """
        Get final result of a completed auction.
        """
        pass


# ============================================
# Mock Implementation (for development)
# ============================================

class MockBidsBridge(BidsBridge):
    """
    Mock implementation for development and testing.
    
    In production, this would call the Bids API.
    """
    
    def __init__(self):
        self._auctions: dict[UUID, AuctionListing] = {}
        self._results: dict[UUID, AuctionResult] = {}
    
    async def get_salvage_score(
        self,
        item_id: UUID,
        item_name: str,
        quantity: float,
        unit: str,
        original_value_cents: int,
        days_until_expiration: Optional[int] = None,
        condition: Optional[SalvageCondition] = None,
    ) -> SalvageScore:
        logger.info(f"[MOCK] Scoring salvage for {item_name}, value ${original_value_cents/100:.2f}")
        
        # Calculate mock score based on expiration and condition
        base_score = 0.7
        
        if days_until_expiration is not None:
            if days_until_expiration <= 1:
                base_score = 0.2
            elif days_until_expiration <= 3:
                base_score = 0.4
            elif days_until_expiration <= 7:
                base_score = 0.6
        
        if condition:
            condition_multipliers = {
                SalvageCondition.NEW: 1.0,
                SalvageCondition.LIKE_NEW: 0.95,
                SalvageCondition.GOOD: 0.8,
                SalvageCondition.FAIR: 0.6,
                SalvageCondition.POOR: 0.3,
                SalvageCondition.SALVAGE_ONLY: 0.1,
            }
            base_score *= condition_multipliers.get(condition, 0.5)
        
        # Determine recommended path
        if base_score >= 0.8:
            path = "transfer"
            recovery = 0.95
        elif base_score >= 0.5:
            path = "discount"
            recovery = 0.6
        elif base_score >= 0.2:
            path = "auction"
            recovery = 0.3
        else:
            path = "donate"
            recovery = 0.0
        
        return SalvageScore(
            item_id=item_id,
            score=base_score,
            condition=condition or SalvageCondition.GOOD,
            estimated_recovery_cents=int(original_value_cents * recovery),
            recovery_percentage=recovery,
            recommended_path=path,
            reasoning=f"Based on {'expiration in ' + str(days_until_expiration) + ' days' if days_until_expiration else 'condition assessment'}",
        )
    
    async def get_liquidation_path(
        self,
        item_id: UUID,
        quantity: float,
        original_value_cents: int,
        urgency: str = "normal",
    ) -> LiquidationPath:
        logger.info(f"[MOCK] Getting liquidation path for item {item_id}, urgency={urgency}")
        
        paths = [
            {
                "action": "transfer",
                "description": "Transfer to another location",
                "expected_recovery": 0.95,
                "time_hours": 4,
            },
            {
                "action": "discount",
                "description": "Sell at 40% discount",
                "expected_recovery": 0.60,
                "time_hours": 24,
            },
            {
                "action": "auction",
                "description": "List on Bids marketplace",
                "expected_recovery": 0.35,
                "time_hours": 72,
            },
            {
                "action": "donate",
                "description": "Donate to food bank",
                "expected_recovery": 0.0,
                "time_hours": 2,
                "tax_benefit": True,
            },
        ]
        
        # Adjust based on urgency
        if urgency == "critical":
            best = "donate"
            time = 2
        elif urgency == "high":
            best = "discount"
            time = 24
        else:
            best = "transfer"
            time = 4
        
        return LiquidationPath(
            item_id=item_id,
            paths=paths,
            best_path=best,
            expected_recovery_cents=int(original_value_cents * 0.6),
            time_to_liquidate_hours=time,
        )
    
    async def create_auction(
        self,
        salvage_event: SalvageReadyEvent,
        duration_hours: int = 72,
        reserve_price_cents: Optional[int] = None,
    ) -> AuctionListing:
        from uuid import uuid4
        
        auction_id = uuid4()
        now = datetime.utcnow()
        
        listing = AuctionListing(
            auction_id=auction_id,
            item_id=salvage_event.item_id,
            listing_url=f"https://bids.proveniq.io/auction/{auction_id}",
            starting_price_cents=salvage_event.minimum_acceptable_cents,
            reserve_price_cents=reserve_price_cents,
            auction_start=now,
            auction_end=now + timedelta(hours=duration_hours),
            status="active",
        )
        
        self._auctions[auction_id] = listing
        logger.info(f"[MOCK] Created auction {auction_id} for item {salvage_event.item_id}")
        
        return listing
    
    async def get_auction_status(
        self,
        auction_id: UUID,
    ) -> AuctionListing:
        if auction_id in self._auctions:
            return self._auctions[auction_id]
        raise ValueError(f"Auction {auction_id} not found")
    
    async def cancel_auction(
        self,
        auction_id: UUID,
        reason: str,
    ) -> bool:
        if auction_id in self._auctions:
            self._auctions[auction_id].status = "cancelled"
            logger.info(f"[MOCK] Cancelled auction {auction_id}: {reason}")
            return True
        return False
    
    async def get_auction_result(
        self,
        auction_id: UUID,
    ) -> AuctionResult:
        if auction_id in self._results:
            return self._results[auction_id]
        
        # Mock: Return pending result
        return AuctionResult(
            auction_id=auction_id,
            item_id=self._auctions.get(auction_id, AuctionListing).item_id if auction_id in self._auctions else UUID(int=0),
            status="pending",
        )


# ============================================
# Bridge Factory
# ============================================

_bridge_instance: Optional[BidsBridge] = None


def get_bids_bridge() -> BidsBridge:
    """
    Get the Bids bridge instance.
    
    In production, this would return a real API client.
    For now, returns mock implementation.
    """
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = MockBidsBridge()
    return _bridge_instance
