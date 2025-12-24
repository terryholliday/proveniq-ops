"""
PROVENIQ Ops - Bids Mock Interface
Auction marketplace for verified assets and excess inventory liquidation

This is a MOCK implementation.
In production, this would connect to the PROVENIQ Bids system.

Contract:
    - Ops publishes ops.excess.flagged events
    - Bids creates auction listings for excess inventory
    - Ops consumes auction.settled events
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
# ENUMS
# =============================================================================

class AuctionType(str, Enum):
    """Types of auctions."""
    TIMED = "timed"           # Fixed end time
    BUY_NOW = "buy_now"       # Immediate purchase
    RESERVE = "reserve"       # Minimum price required
    DUTCH = "dutch"           # Price decreases over time


class ListingStatus(str, Enum):
    """Status of auction listing."""
    DRAFT = "draft"
    ACTIVE = "active"
    ENDED = "ended"
    SOLD = "sold"
    UNSOLD = "unsold"
    CANCELLED = "cancelled"


class ExcessReason(str, Enum):
    """Reasons for excess inventory."""
    OVERSTOCK = "overstock"
    MENU_CHANGE = "menu_change"
    SEASONAL = "seasonal"
    NEAR_EXPIRY = "near_expiry"
    DAMAGED = "damaged"
    OBSOLETE = "obsolete"


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ExcessItem(BaseModel):
    """An excess inventory item to list."""
    item_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    quantity: int
    unit: str
    estimated_value: Decimal
    condition: str = "good"  # "excellent", "good", "fair", "poor"
    expiry_date: Optional[datetime] = None


class ExcessFlagRequest(BaseModel):
    """Request to flag excess inventory for liquidation."""
    business_id: uuid.UUID
    location_id: uuid.UUID
    items: list[ExcessItem]
    reason: ExcessReason
    urgency: str = "medium"  # "low", "medium", "high", "critical"


class ExcessFlagResponse(BaseModel):
    """Response from flagging excess inventory."""
    excess_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    status: str = "FLAGGED"
    bids_listing_created: bool = False
    listing_ids: list[uuid.UUID] = []
    estimated_liquidation_value: Decimal = Decimal("0")
    flagged_at: datetime = Field(default_factory=datetime.utcnow)


class CreateListingRequest(BaseModel):
    """Request to create auction listing."""
    item_id: uuid.UUID
    product_name: str
    description: Optional[str] = None
    quantity: int
    unit: str
    starting_price: Decimal
    reserve_price: Optional[Decimal] = None
    buy_now_price: Optional[Decimal] = None
    auction_type: AuctionType = AuctionType.TIMED
    duration_days: int = 7
    photos: list[str] = []  # Base64 or URLs


class Listing(BaseModel):
    """An auction listing."""
    listing_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    item_id: uuid.UUID
    product_name: str
    description: Optional[str] = None
    quantity: int
    unit: str
    starting_price: Decimal
    current_bid: Optional[Decimal] = None
    reserve_price: Optional[Decimal] = None
    buy_now_price: Optional[Decimal] = None
    auction_type: AuctionType
    status: ListingStatus = ListingStatus.DRAFT
    bid_count: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CreateListingResponse(BaseModel):
    """Response from creating listing."""
    listing: Listing
    success: bool = True
    message: Optional[str] = None


class AuctionSettledEvent(BaseModel):
    """Event when auction settles."""
    listing_id: uuid.UUID
    item_id: uuid.UUID
    status: str  # "sold", "unsold"
    final_price: Optional[Decimal] = None
    buyer_id: Optional[uuid.UUID] = None
    settled_at: datetime = Field(default_factory=datetime.utcnow)


class ProvenanceSummaryRequest(BaseModel):
    """Request for item provenance summary."""
    item_id: uuid.UUID


class ProvenanceSummaryResponse(BaseModel):
    """Provenance summary for listing display."""
    item_id: uuid.UUID
    provenance_score: int = 0
    trust_badges: list[str] = []
    ownership_history: int = 0
    last_verified: Optional[datetime] = None
    fraud_flags: list[str] = []


# =============================================================================
# BIDS MOCK IMPLEMENTATION
# =============================================================================

class BidsMock:
    """
    Mock Proveniq Bids System Interface
    
    Simulates the auction marketplace:
    - Listing creation for excess inventory
    - Auction management
    - Settlement events
    """
    
    def __init__(self) -> None:
        self._listings: dict[uuid.UUID, Listing] = {}
        self._excess_flags: dict[uuid.UUID, ExcessFlagResponse] = {}
        self._event_log: list[dict] = []
    
    # =========================================================================
    # EXCESS INVENTORY LIQUIDATION
    # =========================================================================
    
    async def flag_excess(self, request: ExcessFlagRequest) -> ExcessFlagResponse:
        """
        Flag excess inventory for liquidation on Bids.
        
        This is the primary Ops → Bids integration point.
        Ops calls this when excess inventory is detected.
        """
        listing_ids = []
        total_estimated = Decimal("0")
        
        # Create listings for each excess item
        for item in request.items:
            # Calculate liquidation discount based on urgency and condition
            discount = self._calculate_discount(request.urgency, item.condition)
            liquidation_price = item.estimated_value * (1 - discount)
            total_estimated += liquidation_price
            
            # Create listing
            listing = Listing(
                item_id=item.item_id,
                product_name=item.product_name,
                description=f"Excess inventory - {request.reason.value}",
                quantity=item.quantity,
                unit=item.unit,
                starting_price=liquidation_price * Decimal("0.5"),  # Start at 50%
                buy_now_price=liquidation_price,
                reserve_price=liquidation_price * Decimal("0.7"),  # Reserve at 70%
                auction_type=AuctionType.TIMED,
                status=ListingStatus.ACTIVE,
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow() + timedelta(days=7),
            )
            
            self._listings[listing.listing_id] = listing
            listing_ids.append(listing.listing_id)
            
            # Log event
            self._log_event("auction.listed", {
                "listing_id": str(listing.listing_id),
                "item_id": str(item.item_id),
                "product_name": item.product_name,
                "starting_price": str(listing.starting_price),
                "source": "ops_excess",
            })
        
        response = ExcessFlagResponse(
            status="FLAGGED",
            bids_listing_created=len(listing_ids) > 0,
            listing_ids=listing_ids,
            estimated_liquidation_value=total_estimated.quantize(Decimal("0.01")),
        )
        
        self._excess_flags[response.excess_id] = response
        
        # Log ops.excess.flagged event
        self._log_event("ops.excess.flagged", {
            "excess_id": str(response.excess_id),
            "business_id": str(request.business_id),
            "item_count": len(request.items),
            "total_value": str(total_estimated),
            "reason": request.reason.value,
        })
        
        return response
    
    def _calculate_discount(self, urgency: str, condition: str) -> Decimal:
        """Calculate liquidation discount based on urgency and condition."""
        urgency_discounts = {
            "low": Decimal("0.10"),
            "medium": Decimal("0.20"),
            "high": Decimal("0.35"),
            "critical": Decimal("0.50"),
        }
        
        condition_discounts = {
            "excellent": Decimal("0.00"),
            "good": Decimal("0.05"),
            "fair": Decimal("0.15"),
            "poor": Decimal("0.30"),
        }
        
        base = urgency_discounts.get(urgency, Decimal("0.20"))
        cond = condition_discounts.get(condition, Decimal("0.10"))
        
        return min(base + cond, Decimal("0.70"))  # Max 70% discount
    
    # =========================================================================
    # LISTING MANAGEMENT
    # =========================================================================
    
    async def create_listing(self, request: CreateListingRequest) -> CreateListingResponse:
        """Create a new auction listing."""
        listing = Listing(
            item_id=request.item_id,
            product_name=request.product_name,
            description=request.description,
            quantity=request.quantity,
            unit=request.unit,
            starting_price=request.starting_price,
            reserve_price=request.reserve_price,
            buy_now_price=request.buy_now_price,
            auction_type=request.auction_type,
            status=ListingStatus.ACTIVE,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(days=request.duration_days),
        )
        
        self._listings[listing.listing_id] = listing
        
        self._log_event("auction.listed", {
            "listing_id": str(listing.listing_id),
            "item_id": str(request.item_id),
            "product_name": request.product_name,
        })
        
        return CreateListingResponse(listing=listing)
    
    async def get_listing(self, listing_id: uuid.UUID) -> Optional[Listing]:
        """Get listing by ID."""
        return self._listings.get(listing_id)
    
    async def get_listing_status(self, listing_id: uuid.UUID) -> Optional[dict]:
        """Get listing status."""
        listing = self._listings.get(listing_id)
        if not listing:
            return None
        
        return {
            "listing_id": str(listing.listing_id),
            "status": listing.status.value,
            "current_bid": str(listing.current_bid) if listing.current_bid else None,
            "bid_count": listing.bid_count,
            "end_time": listing.end_time.isoformat() if listing.end_time else None,
        }
    
    # =========================================================================
    # AUCTION SETTLEMENT
    # =========================================================================
    
    async def settle_auction(self, listing_id: uuid.UUID, sold: bool = True, final_price: Optional[Decimal] = None) -> AuctionSettledEvent:
        """
        Settle an auction (for testing).
        
        In production, this would be triggered by the auction engine.
        """
        listing = self._listings.get(listing_id)
        if not listing:
            raise ValueError(f"Listing {listing_id} not found")
        
        if sold:
            listing.status = ListingStatus.SOLD
            listing.current_bid = final_price or listing.buy_now_price or listing.starting_price
        else:
            listing.status = ListingStatus.UNSOLD
        
        event = AuctionSettledEvent(
            listing_id=listing_id,
            item_id=listing.item_id,
            status="sold" if sold else "unsold",
            final_price=listing.current_bid if sold else None,
            buyer_id=uuid.uuid4() if sold else None,
        )
        
        self._log_event("auction.settled", {
            "listing_id": str(listing_id),
            "item_id": str(listing.item_id),
            "status": event.status,
            "final_price": str(event.final_price) if event.final_price else None,
        })
        
        return event
    
    # =========================================================================
    # PROVENANCE INTEGRATION
    # =========================================================================
    
    async def get_provenance_summary(self, request: ProvenanceSummaryRequest) -> ProvenanceSummaryResponse:
        """
        Get provenance summary for listing display.
        
        In production, this calls Core for provenance data.
        """
        # Mock provenance data
        return ProvenanceSummaryResponse(
            item_id=request.item_id,
            provenance_score=75,
            trust_badges=["INVENTORY_TRACKED", "ORIGIN_VERIFIED"],
            ownership_history=1,
            last_verified=datetime.utcnow(),
        )
    
    # =========================================================================
    # UTILITIES
    # =========================================================================
    
    def _log_event(self, event_type: str, payload: dict) -> None:
        """Log an event for the event bus."""
        self._event_log.append({
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload,
        })
    
    def get_event_log(self) -> list[dict]:
        """Return event log."""
        return self._event_log.copy()
    
    def get_active_listings(self) -> list[Listing]:
        """Get all active listings."""
        return [l for l in self._listings.values() if l.status == ListingStatus.ACTIVE]
    
    def reset(self) -> None:
        """Reset mock state."""
        self._listings.clear()
        self._excess_flags.clear()
        self._event_log.clear()


# Singleton instance
bids_mock_instance = BidsMock()
