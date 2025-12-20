"""
PROVENIQ Ops - Ecosystem Bridges

Cross-system integration layer for:
- OPS ⇄ CLAIMSIQ (Loss → Recovery)
- OPS ⇄ BIDS (Excess → Liquidity)
- OPS ⇄ CAPITAL (Inventory → Cash)

These bridges enable the PROVENIQ flywheel:
> Ops creates truth. Bishop creates intelligence. 
> ClaimsIQ recovers losses. Bids unlocks dead capital. 
> Capital controls the bloodstream.
"""

from .claimsiq import ClaimsIQBridge, get_claimsiq_bridge
from .bids import BidsBridge, get_bids_bridge
from .capital import CapitalBridge, get_capital_bridge
from .events import (
    # Loss Events (Ops → ClaimsIQ)
    LossDetectedEvent,
    EvidenceCapturedEvent,
    DisposalPendingEvent,
    # Excess Events (Ops → Bids)
    ExcessInventoryEvent,
    SalvageReadyEvent,
    AuctionListedEvent,
    # Financial Events (Ops ⇄ Capital)
    LiquiditySnapshotEvent,
    CreditConstraintEvent,
    SettlementCompleteEvent,
)

__all__ = [
    # Bridges
    "ClaimsIQBridge",
    "BidsBridge", 
    "CapitalBridge",
    "get_claimsiq_bridge",
    "get_bids_bridge",
    "get_capital_bridge",
    # Events
    "LossDetectedEvent",
    "EvidenceCapturedEvent",
    "DisposalPendingEvent",
    "ExcessInventoryEvent",
    "SalvageReadyEvent",
    "AuctionListedEvent",
    "LiquiditySnapshotEvent",
    "CreditConstraintEvent",
    "SettlementCompleteEvent",
]
