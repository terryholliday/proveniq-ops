"""
PROVENIQ Ops - ClaimsIQ Bridge

OPS ⇄ CLAIMSIQ (Loss → Recovery)

This bridge enables:
1. Loss-to-Claim auto-packaging
2. Coverage-aware Ops alerts
3. Required evidence prompts before disposal
4. Claim outcome feedback into Ops handling rules
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List
from uuid import UUID
import logging

from pydantic import BaseModel

from .events import (
    LossDetectedEvent,
    EvidenceCapturedEvent,
    DisposalPendingEvent,
    CoverageInfo,
    LossType,
)

logger = logging.getLogger(__name__)


# ============================================
# Data Models
# ============================================

class ClaimPacket(BaseModel):
    """Packaged claim ready for submission"""
    claim_id: UUID
    org_id: UUID
    item_id: UUID
    item_name: str
    loss_type: LossType
    quantity_lost: float
    unit: str
    claimed_value_cents: int
    evidence_urls: List[str]
    evidence_hashes: List[str]
    created_at: datetime
    status: str = "draft"  # draft, submitted, under_review, approved, denied


class ClaimOutcome(BaseModel):
    """Result of a claim"""
    claim_id: UUID
    status: str  # approved, denied, partial
    approved_amount_cents: int
    denial_reason: Optional[str] = None
    payout_date: Optional[datetime] = None
    lessons: List[str] = []  # Feedback for Ops handling rules


# ============================================
# Bridge Interface
# ============================================

class ClaimsIQBridge(ABC):
    """
    Abstract interface for ClaimsIQ integration.
    
    Ops uses this bridge to:
    - Check coverage before disposal
    - Package loss events into claims
    - Submit evidence
    - Receive claim outcomes
    """
    
    @abstractmethod
    async def get_coverage(
        self, 
        org_id: UUID, 
        item_id: UUID,
        loss_type: LossType,
        estimated_value_cents: int,
    ) -> CoverageInfo:
        """
        Check if a loss is covered and what evidence is required.
        
        Called BEFORE disposal to determine if claim is possible.
        """
        pass
    
    @abstractmethod
    async def package_claim(
        self,
        loss_event: LossDetectedEvent,
        evidence_events: List[EvidenceCapturedEvent],
    ) -> ClaimPacket:
        """
        Package a loss event and evidence into a claim packet.
        
        Does NOT submit - creates a draft for review.
        """
        pass
    
    @abstractmethod
    async def submit_claim(
        self,
        claim_id: UUID,
        submitted_by: UUID,
    ) -> bool:
        """
        Submit a packaged claim for processing.
        
        Returns True if submission accepted.
        """
        pass
    
    @abstractmethod
    async def get_claim_status(
        self,
        claim_id: UUID,
    ) -> ClaimOutcome:
        """
        Get current status of a claim.
        """
        pass
    
    @abstractmethod
    async def get_required_evidence(
        self,
        disposal_event: DisposalPendingEvent,
    ) -> List[str]:
        """
        Get list of required evidence types before disposal.
        
        Called when DisposalPendingEvent is emitted.
        Returns list like ["photo", "receipt", "temperature_log"]
        """
        pass
    
    @abstractmethod
    async def record_disposal(
        self,
        item_id: UUID,
        quantity: float,
        reason: str,
        evidence_captured: bool,
        claim_filed: bool,
    ) -> None:
        """
        Record that disposal occurred (for audit trail).
        """
        pass


# ============================================
# Mock Implementation (for development)
# ============================================

class MockClaimsIQBridge(ClaimsIQBridge):
    """
    Mock implementation for development and testing.
    
    In production, this would call the ClaimsIQ API.
    """
    
    def __init__(self):
        self._claims: dict[UUID, ClaimPacket] = {}
        self._outcomes: dict[UUID, ClaimOutcome] = {}
    
    async def get_coverage(
        self,
        org_id: UUID,
        item_id: UUID,
        loss_type: LossType,
        estimated_value_cents: int,
    ) -> CoverageInfo:
        logger.info(f"[MOCK] Checking coverage for {loss_type} loss, value ${estimated_value_cents/100:.2f}")
        
        # Mock: Most losses are covered with standard requirements
        if loss_type == LossType.THEFT:
            return CoverageInfo(
                is_covered=True,
                coverage_type="theft",
                coverage_limit_cents=500000,  # $5000
                deductible_cents=25000,  # $250
                required_evidence=["photo", "police_report", "inventory_log"],
                claim_deadline_days=30,
            )
        elif loss_type == LossType.SPOILAGE:
            return CoverageInfo(
                is_covered=True,
                coverage_type="spoilage",
                coverage_limit_cents=1000000,  # $10000
                deductible_cents=10000,  # $100
                required_evidence=["photo", "temperature_log"],
                claim_deadline_days=7,
            )
        elif loss_type == LossType.DAMAGE:
            return CoverageInfo(
                is_covered=True,
                coverage_type="damage",
                coverage_limit_cents=500000,
                deductible_cents=25000,
                required_evidence=["photo", "incident_report"],
                claim_deadline_days=14,
            )
        else:
            return CoverageInfo(
                is_covered=False,
                notes="Loss type not covered under current policy",
            )
    
    async def package_claim(
        self,
        loss_event: LossDetectedEvent,
        evidence_events: List[EvidenceCapturedEvent],
    ) -> ClaimPacket:
        from uuid import uuid4
        
        claim = ClaimPacket(
            claim_id=uuid4(),
            org_id=loss_event.org_id,
            item_id=loss_event.item_id,
            item_name=loss_event.item_name,
            loss_type=loss_event.loss_type,
            quantity_lost=loss_event.quantity_lost,
            unit=loss_event.unit,
            claimed_value_cents=loss_event.estimated_value_cents,
            evidence_urls=[e.evidence_url for e in evidence_events],
            evidence_hashes=[e.evidence_hash for e in evidence_events],
            created_at=datetime.utcnow(),
            status="draft",
        )
        
        self._claims[claim.claim_id] = claim
        logger.info(f"[MOCK] Packaged claim {claim.claim_id} for ${claim.claimed_value_cents/100:.2f}")
        
        return claim
    
    async def submit_claim(
        self,
        claim_id: UUID,
        submitted_by: UUID,
    ) -> bool:
        if claim_id in self._claims:
            self._claims[claim_id].status = "submitted"
            logger.info(f"[MOCK] Claim {claim_id} submitted by {submitted_by}")
            return True
        return False
    
    async def get_claim_status(
        self,
        claim_id: UUID,
    ) -> ClaimOutcome:
        if claim_id in self._outcomes:
            return self._outcomes[claim_id]
        
        # Mock: Return pending status
        return ClaimOutcome(
            claim_id=claim_id,
            status="under_review",
            approved_amount_cents=0,
        )
    
    async def get_required_evidence(
        self,
        disposal_event: DisposalPendingEvent,
    ) -> List[str]:
        # Standard evidence requirements based on disposal reason
        if disposal_event.disposal_reason == "expiration":
            return ["photo", "expiration_label"]
        elif disposal_event.disposal_reason == "damage":
            return ["photo", "incident_report"]
        elif disposal_event.disposal_reason == "contamination":
            return ["photo", "health_inspection_report"]
        else:
            return ["photo"]
    
    async def record_disposal(
        self,
        item_id: UUID,
        quantity: float,
        reason: str,
        evidence_captured: bool,
        claim_filed: bool,
    ) -> None:
        logger.info(
            f"[MOCK] Recorded disposal: item={item_id}, qty={quantity}, "
            f"reason={reason}, evidence={evidence_captured}, claim={claim_filed}"
        )


# ============================================
# Bridge Factory
# ============================================

_bridge_instance: Optional[ClaimsIQBridge] = None


def get_claimsiq_bridge() -> ClaimsIQBridge:
    """
    Get the ClaimsIQ bridge instance.
    
    In production, this would return a real API client.
    For now, returns mock implementation.
    """
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = MockClaimsIQBridge()
    return _bridge_instance
