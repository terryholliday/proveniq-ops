"""
PROVENIQ Ops - Trust Tier API
Phase 1-2: Credibility Stack Endpoints

GOVERNANCE COMPLIANCE:
- Trust Tiers are READ-ONLY via API (no manual setting)
- Explanations in plain language
- Full audit trail accessible
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.services.trust_tier_engine import (
    trust_tier_engine,
    TrustTier,
    TrustTierResult,
    TIER_NAMES,
    TIER_MEANINGS,
)

router = APIRouter(prefix="/trust-tiers", tags=["trust-tiers"])


class TierSummary(BaseModel):
    """Summary response for trust tier."""
    asset_id: str
    tier: int
    tier_name: str
    tier_meaning: str
    composite_score: str
    days_in_system: int
    explanation: str


class TierDetailResponse(BaseModel):
    """Detailed trust tier response."""
    asset_id: str
    tier: int
    tier_name: str
    tier_meaning: str
    
    # Driver scores
    evidence_quality_score: str
    telemetry_continuity_score: str
    human_discipline_score: str
    time_in_system_score: str
    integrity_score: str
    composite_score: str
    
    # Plain language explanations
    explanation: str
    upgrade_path: str
    risk_factors: List[str]
    
    # Caps
    tier_cap: Optional[int]
    tier_cap_reason: Optional[str]
    
    # Time metrics
    first_event_at: Optional[str]
    last_event_at: Optional[str]
    days_in_system: int
    
    calculated_at: str


class TierHistoryEntry(BaseModel):
    """Single entry in tier history."""
    previous_tier: Optional[int]
    new_tier: int
    previous_tier_name: Optional[str]
    new_tier_name: str
    change_type: str
    change_reason: str
    composite_score: str
    recorded_at: str


class TierDistributionResponse(BaseModel):
    """Distribution of assets by tier."""
    bronze: int
    silver: int
    gold: int
    platinum: int
    total: int


@router.get("/assets/{asset_id}", response_model=TierDetailResponse)
async def get_asset_trust_tier(asset_id: UUID):
    """
    Get the current trust tier for an asset.
    
    Returns full tier details including:
    - Current tier and meaning
    - All driver scores
    - Plain language explanation
    - Upgrade path guidance
    - Risk factors
    """
    result = await trust_tier_engine.get_tier(asset_id)
    
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No trust tier found for asset {asset_id}. Run /calculate first."
        )
    
    return TierDetailResponse(
        asset_id=str(result.asset_id),
        tier=result.tier.value,
        tier_name=result.tier_name,
        tier_meaning=result.tier_meaning,
        evidence_quality_score=str(result.scores.evidence_quality),
        telemetry_continuity_score=str(result.scores.telemetry_continuity),
        human_discipline_score=str(result.scores.human_discipline),
        time_in_system_score=str(result.scores.time_in_system),
        integrity_score=str(result.scores.integrity),
        composite_score=str(result.scores.composite),
        explanation=result.explanation,
        upgrade_path=result.upgrade_path,
        risk_factors=result.risk_factors,
        tier_cap=result.tier_cap.value if result.tier_cap else None,
        tier_cap_reason=result.tier_cap_reason,
        first_event_at=result.first_event_at.isoformat() if result.first_event_at else None,
        last_event_at=result.last_event_at.isoformat() if result.last_event_at else None,
        days_in_system=result.days_in_system,
        calculated_at=result.calculated_at.isoformat(),
    )


@router.post("/assets/{asset_id}/calculate", response_model=TierDetailResponse)
async def calculate_asset_trust_tier(asset_id: UUID, org_id: UUID):
    """
    Calculate (or recalculate) the trust tier for an asset.
    
    This evaluates all 5 drivers:
    1. Evidence Quality
    2. Telemetry Continuity
    3. Human Discipline
    4. Time-in-System
    5. Integrity
    
    The tier is determined by the composite score and time requirements.
    Trust is EARNED, not set manually.
    """
    result = await trust_tier_engine.calculate_tier(asset_id, org_id)
    
    return TierDetailResponse(
        asset_id=str(result.asset_id),
        tier=result.tier.value,
        tier_name=result.tier_name,
        tier_meaning=result.tier_meaning,
        evidence_quality_score=str(result.scores.evidence_quality),
        telemetry_continuity_score=str(result.scores.telemetry_continuity),
        human_discipline_score=str(result.scores.human_discipline),
        time_in_system_score=str(result.scores.time_in_system),
        integrity_score=str(result.scores.integrity),
        composite_score=str(result.scores.composite),
        explanation=result.explanation,
        upgrade_path=result.upgrade_path,
        risk_factors=result.risk_factors,
        tier_cap=result.tier_cap.value if result.tier_cap else None,
        tier_cap_reason=result.tier_cap_reason,
        first_event_at=result.first_event_at.isoformat() if result.first_event_at else None,
        last_event_at=result.last_event_at.isoformat() if result.last_event_at else None,
        days_in_system=result.days_in_system,
        calculated_at=result.calculated_at.isoformat(),
    )


@router.get("/assets/{asset_id}/history", response_model=List[TierHistoryEntry])
async def get_asset_tier_history(
    asset_id: UUID,
    limit: int = Query(default=50, le=200),
):
    """
    Get the trust tier history for an asset.
    
    Shows all tier changes with:
    - Previous and new tier
    - Change type (upgrade/downgrade/initial)
    - Reason for change
    - Scores at time of change
    """
    from app.db.session import async_session_maker
    from sqlalchemy import text
    
    async with async_session_maker() as session:
        result = await session.execute(
            text("""
                SELECT * FROM trust_tier_history
                WHERE asset_id = :asset_id
                ORDER BY recorded_at DESC
                LIMIT :limit
            """),
            {"asset_id": asset_id, "limit": limit}
        )
        
        history = []
        for row in result.fetchall():
            history.append(TierHistoryEntry(
                previous_tier=row.previous_tier,
                new_tier=row.new_tier,
                previous_tier_name=row.previous_tier_name,
                new_tier_name=row.new_tier_name,
                change_type=row.change_type,
                change_reason=row.change_reason,
                composite_score=str(row.composite_score),
                recorded_at=row.recorded_at.isoformat(),
            ))
        
        return history


@router.get("/organizations/{org_id}/distribution", response_model=TierDistributionResponse)
async def get_org_tier_distribution(org_id: UUID):
    """
    Get the distribution of assets by trust tier for an organization.
    
    Shows count of assets at each tier level.
    """
    distribution = await trust_tier_engine.get_tier_distribution(org_id)
    
    return TierDistributionResponse(
        bronze=distribution["BRONZE"],
        silver=distribution["SILVER"],
        gold=distribution["GOLD"],
        platinum=distribution["PLATINUM"],
        total=sum(distribution.values()),
    )


@router.get("/organizations/{org_id}/assets", response_model=List[TierSummary])
async def get_org_assets_by_tier(
    org_id: UUID,
    tier: Optional[int] = Query(default=None, ge=1, le=4),
    limit: int = Query(default=100, le=500),
):
    """
    Get all assets for an organization, optionally filtered by tier.
    """
    from app.db.session import async_session_maker
    from sqlalchemy import text
    
    async with async_session_maker() as session:
        query = """
            SELECT asset_id, tier, tier_name, composite_score, days_in_system, explanation
            FROM asset_trust_tiers
            WHERE org_id = :org_id
        """
        params = {"org_id": org_id, "limit": limit}
        
        if tier:
            query += " AND tier = :tier"
            params["tier"] = tier
        
        query += " ORDER BY composite_score DESC LIMIT :limit"
        
        result = await session.execute(text(query), params)
        
        assets = []
        for row in result.fetchall():
            assets.append(TierSummary(
                asset_id=str(row.asset_id),
                tier=row.tier,
                tier_name=row.tier_name,
                tier_meaning=TIER_MEANINGS[TrustTier(row.tier)],
                composite_score=str(row.composite_score),
                days_in_system=row.days_in_system,
                explanation=row.explanation or "",
            ))
        
        return assets


@router.get("/definitions")
async def get_tier_definitions():
    """
    Get the definitions and requirements for each trust tier.
    
    Use this to understand what each tier means and requires.
    """
    thresholds = await trust_tier_engine.get_thresholds()
    
    return {
        "tiers": [
            {
                "tier": 1,
                "name": "BRONZE",
                "meaning": TIER_MEANINGS[TrustTier.BRONZE],
                "min_composite_score": str(thresholds.bronze_min),
                "min_days": 0,
                "requirements": [
                    "Human-submitted evidence",
                    "Third-party or unverified sensors allowed",
                    "Minimal telemetry continuity",
                ],
            },
            {
                "tier": 2,
                "name": "SILVER",
                "meaning": TIER_MEANINGS[TrustTier.SILVER],
                "min_composite_score": str(thresholds.silver_min),
                "min_days": thresholds.silver_min_days,
                "requirements": [
                    "Mixed evidence (human + telemetry)",
                    "At least one continuous sensor feed",
                    "Bishop anomaly checks active",
                    "No unresolved integrity flags",
                ],
            },
            {
                "tier": 3,
                "name": "GOLD",
                "meaning": TIER_MEANINGS[TrustTier.GOLD],
                "min_composite_score": str(thresholds.gold_min),
                "min_days": thresholds.gold_min_days,
                "requirements": [
                    "Continuous telemetry on critical variables",
                    "Proveniq-certified OR attested sensor sources",
                    "No SECURITY_WAIVER in last N days",
                    "Consistent human acceptance discipline",
                ],
            },
            {
                "tier": 4,
                "name": "PLATINUM",
                "meaning": TIER_MEANINGS[TrustTier.PLATINUM],
                "min_composite_score": str(thresholds.platinum_min),
                "min_days": thresholds.platinum_min_days,
                "requirements": [
                    "Long-term continuity (time-in-system)",
                    "Cryptographically verifiable evidence chains",
                    "No unresolved ledger, integrity, or forensic flags",
                    "Eligible for Ops Attestations",
                ],
            },
        ],
        "driver_weights": {
            "evidence_quality": str(thresholds.evidence_weight),
            "telemetry_continuity": str(thresholds.telemetry_weight),
            "human_discipline": str(thresholds.discipline_weight),
            "time_in_system": str(thresholds.time_weight),
            "integrity": str(thresholds.integrity_weight),
        },
        "version": thresholds.version,
    }


@router.get("/downstream-effects")
async def get_downstream_effects():
    """
    Get information about how trust tiers affect downstream systems.
    
    Trust tiers directly influence:
    - ClaimsIQ documentation requirements
    - Capital eligibility and terms
    - Bids listing eligibility
    """
    return {
        "claimsiq": {
            "description": "Higher tiers reduce documentation friction in claims",
            "effects": {
                "BRONZE": "Full documentation required, additional verification needed",
                "SILVER": "Standard documentation, some verification may be waived",
                "GOLD": "Reduced documentation, preferential handling",
                "PLATINUM": "Minimal documentation, highest trust level",
            },
        },
        "capital": {
            "description": "Trust tier influences loan eligibility and terms",
            "effects": {
                "BRONZE": "May be excluded from certain loan products",
                "SILVER": "Standard eligibility with normal terms",
                "GOLD": "Improved terms, faster processing",
                "PLATINUM": "Best terms, priority processing",
            },
        },
        "bids": {
            "description": "Minimum trust tier required for marketplace listing",
            "effects": {
                "BRONZE": "Limited listing options",
                "SILVER": "Standard listing with provenance indicator",
                "GOLD": "Enhanced listing with verification badge",
                "PLATINUM": "Premium listing with full attestation",
            },
        },
    }
