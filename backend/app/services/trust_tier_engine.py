"""
PROVENIQ Ops - Trust Tier Engine
Phase 1-2: Credibility Stack

GOVERNANCE RULES (ABSOLUTE):
- Trust Tiers are per asset, NOT per account
- Trust Tiers are derived from behavior over time
- Trust Tiers CANNOT be manually set
- Trust Tiers CANNOT be overridden by sales/support
- Trust Tiers CANNOT be tied to price
- Trust Tiers MUST degrade automatically when inputs degrade
- Trust Tiers MUST be explainable in plain language

TIER DEFINITIONS:
- BRONZE (1): Observed - Human-submitted evidence, unverified sensors
- SILVER (2): Corroborated - Mixed evidence, ≥1 continuous sensor, Bishop active
- GOLD (3): Verified - Continuous telemetry, certified sensors, no recent waivers
- PLATINUM (4): Attestable - Long-term continuity, crypto-verifiable chains

DRIVERS (ALL must be considered):
1. Evidence Quality
2. Telemetry Continuity
3. Human Discipline
4. Time-in-System
5. Integrity Events
"""

import uuid
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
import logging

from app.db.session import async_session_maker
from app.services.events.store import event_store

logger = logging.getLogger(__name__)


class TrustTier(int, Enum):
    """Trust Tier levels - EARNED, not purchased."""
    BRONZE = 1    # Observed
    SILVER = 2    # Corroborated
    GOLD = 3      # Verified
    PLATINUM = 4  # Attestable


TIER_NAMES = {
    TrustTier.BRONZE: "BRONZE",
    TrustTier.SILVER: "SILVER",
    TrustTier.GOLD: "GOLD",
    TrustTier.PLATINUM: "PLATINUM",
}

TIER_MEANINGS = {
    TrustTier.BRONZE: "Observed - verification relies heavily on humans",
    TrustTier.SILVER: "Corroborated - multiple signals agree, but not all are controlled",
    TrustTier.GOLD: "Verified - evidence quality and operational discipline are consistently high",
    TrustTier.PLATINUM: "Attestable - operational history can be relied upon by third parties",
}


class TrustTierThresholds(BaseModel):
    """Configurable thresholds for tier calculation."""
    version: str = "1.0.0"
    
    # Composite score thresholds
    bronze_min: Decimal = Decimal("0.0")
    silver_min: Decimal = Decimal("0.30")
    gold_min: Decimal = Decimal("0.60")
    platinum_min: Decimal = Decimal("0.85")
    
    # Driver weights (must sum to 1.0)
    evidence_weight: Decimal = Decimal("0.25")
    telemetry_weight: Decimal = Decimal("0.25")
    discipline_weight: Decimal = Decimal("0.20")
    time_weight: Decimal = Decimal("0.15")
    integrity_weight: Decimal = Decimal("0.15")
    
    # Minimum days in system
    silver_min_days: int = 7
    gold_min_days: int = 30
    platinum_min_days: int = 90


class DriverScores(BaseModel):
    """Calculated scores for each trust tier driver."""
    evidence_quality: Decimal = Decimal("0")
    telemetry_continuity: Decimal = Decimal("0")
    human_discipline: Decimal = Decimal("0")
    time_in_system: Decimal = Decimal("0")
    integrity: Decimal = Decimal("0")
    
    # Composite weighted score
    composite: Decimal = Decimal("0")


class TrustTierResult(BaseModel):
    """Result of trust tier calculation."""
    asset_id: uuid.UUID
    tier: TrustTier
    tier_name: str
    tier_meaning: str
    
    # Driver scores
    scores: DriverScores
    
    # Explanation in plain language
    explanation: str
    upgrade_path: str
    risk_factors: List[str]
    
    # Caps
    tier_cap: Optional[TrustTier] = None
    tier_cap_reason: Optional[str] = None
    
    # Time metrics
    first_event_at: Optional[datetime] = None
    last_event_at: Optional[datetime] = None
    days_in_system: int = 0
    
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TrustTierEngine:
    """
    Engine for calculating Trust Tiers.
    
    MOAT PRINCIPLE:
    - Trust is earned from operational behavior over time
    - Trust cannot be purchased or imported
    - Higher trust reduces downstream friction (ClaimsIQ, Capital, Bids)
    - Competitors cannot copy earned credibility
    """
    
    def __init__(self):
        self._thresholds: Optional[TrustTierThresholds] = None
    
    async def get_thresholds(self) -> TrustTierThresholds:
        """Get current trust tier thresholds from database."""
        if self._thresholds:
            return self._thresholds
        
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("""
                    SELECT * FROM trust_tier_thresholds
                    WHERE effective_until IS NULL
                    OR effective_until > NOW()
                    ORDER BY effective_from DESC
                    LIMIT 1
                """)
            )
            row = result.fetchone()
            
            if row:
                self._thresholds = TrustTierThresholds(
                    version=row.version,
                    bronze_min=row.bronze_min,
                    silver_min=row.silver_min,
                    gold_min=row.gold_min,
                    platinum_min=row.platinum_min,
                    evidence_weight=row.evidence_weight,
                    telemetry_weight=row.telemetry_weight,
                    discipline_weight=row.discipline_weight,
                    time_weight=row.time_weight,
                    integrity_weight=row.integrity_weight,
                    silver_min_days=row.silver_min_days,
                    gold_min_days=row.gold_min_days,
                    platinum_min_days=row.platinum_min_days,
                )
            else:
                self._thresholds = TrustTierThresholds()
        
        return self._thresholds
    
    async def calculate_tier(
        self,
        asset_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> TrustTierResult:
        """
        Calculate the trust tier for an asset.
        
        This is the core credibility calculation. It considers:
        1. Evidence Quality - Types, hashes, waivers
        2. Telemetry Continuity - Gaps, coverage
        3. Human Discipline - Bishop acceptance rates
        4. Time-in-System - Duration of history
        5. Integrity - Unresolved flags/anomalies
        """
        thresholds = await self.get_thresholds()
        
        # Calculate each driver score
        evidence_score = await self._calculate_evidence_quality(asset_id)
        telemetry_score = await self._calculate_telemetry_continuity(asset_id)
        discipline_score = await self._calculate_human_discipline(asset_id, org_id)
        time_score, first_event, last_event, days = await self._calculate_time_in_system(asset_id)
        integrity_score = await self._calculate_integrity(asset_id, org_id)
        
        # Calculate composite score
        composite = (
            evidence_score * thresholds.evidence_weight +
            telemetry_score * thresholds.telemetry_weight +
            discipline_score * thresholds.discipline_weight +
            time_score * thresholds.time_weight +
            integrity_score * thresholds.integrity_weight
        )
        
        scores = DriverScores(
            evidence_quality=evidence_score,
            telemetry_continuity=telemetry_score,
            human_discipline=discipline_score,
            time_in_system=time_score,
            integrity=integrity_score,
            composite=composite,
        )
        
        # Determine tier from composite score
        tier = self._score_to_tier(composite, days, thresholds)
        
        # Check for tier caps (waivers, flags)
        tier_cap, cap_reason = await self._get_tier_cap(asset_id)
        if tier_cap and tier.value > tier_cap.value:
            tier = tier_cap
        
        # Generate explanations
        explanation = self._generate_explanation(tier, scores, days)
        upgrade_path = self._generate_upgrade_path(tier, scores, days, thresholds)
        risk_factors = self._identify_risk_factors(scores)
        
        result = TrustTierResult(
            asset_id=asset_id,
            tier=tier,
            tier_name=TIER_NAMES[tier],
            tier_meaning=TIER_MEANINGS[tier],
            scores=scores,
            explanation=explanation,
            upgrade_path=upgrade_path,
            risk_factors=risk_factors,
            tier_cap=tier_cap,
            tier_cap_reason=cap_reason,
            first_event_at=first_event,
            last_event_at=last_event,
            days_in_system=days,
        )
        
        # Persist the result
        await self._save_tier(result, org_id)
        
        logger.info(f"Trust tier calculated for asset {asset_id}: {tier.name} (composite={composite})")
        
        return result
    
    async def _calculate_evidence_quality(self, asset_id: uuid.UUID) -> Decimal:
        """
        Calculate evidence quality score.
        
        Considers:
        - Evidence types (human-submitted vs sensor)
        - Hash continuity
        - Presence of waivers
        """
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Count events by type for this asset
            result = await session.execute(
                text("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE payload->>'evidence_type' = 'sensor') as sensor_events,
                        COUNT(*) FILTER (WHERE payload->>'evidence_type' = 'certified') as certified_events,
                        COUNT(*) FILTER (WHERE payload_hash IS NOT NULL) as hashed_events
                    FROM ops_events
                    WHERE payload->>'asset_id' = :asset_id
                    AND timestamp > NOW() - INTERVAL '90 days'
                """),
                {"asset_id": str(asset_id)}
            )
            row = result.fetchone()
            
            if not row or row.total == 0:
                return Decimal("0.1")
            
            # Score components
            sensor_ratio = Decimal(str(row.sensor_events / row.total)) if row.total > 0 else Decimal("0")
            certified_ratio = Decimal(str(row.certified_events / row.total)) if row.total > 0 else Decimal("0")
            hash_ratio = Decimal(str(row.hashed_events / row.total)) if row.total > 0 else Decimal("0")
            
            # Weighted score
            score = (
                sensor_ratio * Decimal("0.3") +
                certified_ratio * Decimal("0.4") +
                hash_ratio * Decimal("0.3")
            )
            
            # Boost for high volume
            if row.total > 100:
                score = min(score + Decimal("0.1"), Decimal("1.0"))
            
            return min(max(score, Decimal("0")), Decimal("1"))
    
    async def _calculate_telemetry_continuity(self, asset_id: uuid.UUID) -> Decimal:
        """
        Calculate telemetry continuity score.
        
        Considers:
        - Gap frequency
        - Gap duration
        - Coverage of critical variables
        """
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Get events ordered by time to detect gaps
            result = await session.execute(
                text("""
                    WITH event_gaps AS (
                        SELECT 
                            timestamp,
                            LAG(timestamp) OVER (ORDER BY timestamp) as prev_timestamp,
                            EXTRACT(EPOCH FROM (timestamp - LAG(timestamp) OVER (ORDER BY timestamp))) / 3600 as gap_hours
                        FROM ops_events
                        WHERE payload->>'asset_id' = :asset_id
                        AND timestamp > NOW() - INTERVAL '30 days'
                    )
                    SELECT 
                        COUNT(*) as total_events,
                        COUNT(*) FILTER (WHERE gap_hours > 24) as gaps_over_24h,
                        COUNT(*) FILTER (WHERE gap_hours > 72) as gaps_over_72h,
                        AVG(gap_hours) as avg_gap_hours
                    FROM event_gaps
                    WHERE prev_timestamp IS NOT NULL
                """),
                {"asset_id": str(asset_id)}
            )
            row = result.fetchone()
            
            if not row or row.total_events == 0:
                return Decimal("0.1")
            
            # Penalize gaps
            gap_penalty = Decimal("0")
            if row.gaps_over_72h and row.gaps_over_72h > 0:
                gap_penalty += Decimal("0.3")
            if row.gaps_over_24h and row.gaps_over_24h > 2:
                gap_penalty += Decimal("0.2")
            
            # Base score from event frequency
            base_score = Decimal("0.8") if row.total_events > 50 else Decimal(str(min(row.total_events / 50, 0.8)))
            
            score = max(base_score - gap_penalty, Decimal("0"))
            
            return min(max(score, Decimal("0")), Decimal("1"))
    
    async def _calculate_human_discipline(
        self,
        asset_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> Decimal:
        """
        Calculate human discipline score.
        
        Considers:
        - Bishop recommendation acceptance rate
        - Review timeliness
        - Override vs evidence usage
        """
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Get Bishop recommendation acceptance stats
            result = await session.execute(
                text("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE event_type = 'ops.bishop.recommendation_accepted') as accepted,
                        COUNT(*) FILTER (WHERE event_type = 'ops.bishop.recommendation_rejected') as rejected
                    FROM ops_events
                    WHERE event_type LIKE 'ops.bishop.recommendation_%'
                    AND (payload->>'asset_id' = :asset_id OR payload->>'org_id' = :org_id)
                    AND timestamp > NOW() - INTERVAL '90 days'
                """),
                {"asset_id": str(asset_id), "org_id": str(org_id)}
            )
            row = result.fetchone()
            
            if not row or row.total == 0:
                return Decimal("0.5")  # Neutral if no recommendations
            
            # Acceptance rate
            acceptance_rate = Decimal(str(row.accepted / row.total)) if row.total > 0 else Decimal("0")
            
            # Very low acceptance might indicate ignored recommendations
            # Very high might be fine, but some rejections show engagement
            if acceptance_rate > Decimal("0.95"):
                score = Decimal("0.9")
            elif acceptance_rate > Decimal("0.7"):
                score = Decimal("0.8") + (acceptance_rate - Decimal("0.7")) * Decimal("0.5")
            elif acceptance_rate > Decimal("0.4"):
                score = Decimal("0.5") + (acceptance_rate - Decimal("0.4")) * Decimal("1.0")
            else:
                score = acceptance_rate * Decimal("1.25")
            
            return min(max(score, Decimal("0")), Decimal("1"))
    
    async def _calculate_time_in_system(
        self,
        asset_id: uuid.UUID,
    ) -> Tuple[Decimal, Optional[datetime], Optional[datetime], int]:
        """
        Calculate time-in-system score.
        
        Trust increases with uninterrupted history.
        """
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("""
                    SELECT 
                        MIN(timestamp) as first_event,
                        MAX(timestamp) as last_event
                    FROM ops_events
                    WHERE payload->>'asset_id' = :asset_id
                """),
                {"asset_id": str(asset_id)}
            )
            row = result.fetchone()
            
            if not row or not row.first_event:
                return Decimal("0"), None, None, 0
            
            first_event = row.first_event
            last_event = row.last_event
            days = (datetime.now(timezone.utc) - first_event.replace(tzinfo=timezone.utc)).days
            
            # Score based on days
            if days >= 180:
                score = Decimal("1.0")
            elif days >= 90:
                score = Decimal("0.8") + Decimal(str((days - 90) / 90)) * Decimal("0.2")
            elif days >= 30:
                score = Decimal("0.5") + Decimal(str((days - 30) / 60)) * Decimal("0.3")
            elif days >= 7:
                score = Decimal("0.2") + Decimal(str((days - 7) / 23)) * Decimal("0.3")
            else:
                score = Decimal(str(days / 7)) * Decimal("0.2")
            
            return score, first_event, last_event, days
    
    async def _calculate_integrity(
        self,
        asset_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> Decimal:
        """
        Calculate integrity score.
        
        Unresolved anomalies/flags reduce integrity.
        """
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Count unresolved anomalies
            result = await session.execute(
                text("""
                    SELECT 
                        COUNT(*) as total_anomalies,
                        COUNT(*) FILTER (WHERE status NOT IN ('resolved', 'false_positive')) as unresolved,
                        COUNT(*) FILTER (WHERE anomaly_severity IN ('high', 'critical')) as severe
                    FROM anomaly_contexts
                    WHERE (product_id = :asset_id OR org_id = :org_id)
                    AND detected_at > NOW() - INTERVAL '90 days'
                """),
                {"asset_id": asset_id, "org_id": org_id}
            )
            row = result.fetchone()
            
            if not row:
                return Decimal("1.0")
            
            # Start with perfect integrity
            score = Decimal("1.0")
            
            # Penalize unresolved anomalies
            if row.unresolved:
                score -= Decimal(str(min(row.unresolved * 0.1, 0.4)))
            
            # Extra penalty for severe unresolved
            if row.severe:
                score -= Decimal(str(min(row.severe * 0.15, 0.3)))
            
            return max(score, Decimal("0"))
    
    async def _get_tier_cap(
        self,
        asset_id: uuid.UUID,
    ) -> Tuple[Optional[TrustTier], Optional[str]]:
        """Check for active waivers that cap the tier."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("""
                    SELECT tier_cap, waiver_type, waiver_reason
                    FROM security_waivers
                    WHERE asset_id = :asset_id
                    AND status = 'active'
                    AND (expires_at IS NULL OR expires_at > NOW())
                    ORDER BY tier_cap ASC
                    LIMIT 1
                """),
                {"asset_id": asset_id}
            )
            row = result.fetchone()
            
            if row:
                tier_cap = TrustTier(row.tier_cap)
                reason = f"{row.waiver_type}: {row.waiver_reason}"
                return tier_cap, reason
            
            return None, None
    
    def _score_to_tier(
        self,
        composite: Decimal,
        days: int,
        thresholds: TrustTierThresholds,
    ) -> TrustTier:
        """Convert composite score to tier, respecting time requirements."""
        if composite >= thresholds.platinum_min and days >= thresholds.platinum_min_days:
            return TrustTier.PLATINUM
        elif composite >= thresholds.gold_min and days >= thresholds.gold_min_days:
            return TrustTier.GOLD
        elif composite >= thresholds.silver_min and days >= thresholds.silver_min_days:
            return TrustTier.SILVER
        else:
            return TrustTier.BRONZE
    
    def _generate_explanation(
        self,
        tier: TrustTier,
        scores: DriverScores,
        days: int,
    ) -> str:
        """Generate plain language explanation of the tier."""
        explanations = {
            TrustTier.BRONZE: f"This asset has been observed for {days} days. Evidence relies primarily on human submissions. To increase credibility, add sensor-based telemetry and maintain consistent operational records.",
            TrustTier.SILVER: f"This asset has {days} days of corroborated history. Multiple evidence sources agree, but not all are independently verified. Continue building consistent records to advance.",
            TrustTier.GOLD: f"This asset has {days} days of verified operational history. Evidence quality and operational discipline are consistently high. Maintain current practices to preserve this status.",
            TrustTier.PLATINUM: f"This asset has {days} days of attestable history. Operational records can be relied upon by third parties without additional verification. This is the highest level of operational credibility.",
        }
        return explanations[tier]
    
    def _generate_upgrade_path(
        self,
        tier: TrustTier,
        scores: DriverScores,
        days: int,
        thresholds: TrustTierThresholds,
    ) -> str:
        """Generate guidance on how to advance to the next tier."""
        if tier == TrustTier.PLATINUM:
            return "This asset has achieved the highest trust tier. Maintain current operational discipline to preserve this status."
        
        next_tier = TrustTier(tier.value + 1)
        improvements = []
        
        if scores.evidence_quality < Decimal("0.7"):
            improvements.append("Add certified sensor evidence")
        if scores.telemetry_continuity < Decimal("0.7"):
            improvements.append("Reduce gaps in telemetry coverage")
        if scores.human_discipline < Decimal("0.7"):
            improvements.append("Respond consistently to Bishop recommendations")
        if scores.integrity < Decimal("0.9"):
            improvements.append("Resolve outstanding anomaly flags")
        
        if tier == TrustTier.BRONZE and days < thresholds.silver_min_days:
            improvements.append(f"Continue operations for {thresholds.silver_min_days - days} more days")
        elif tier == TrustTier.SILVER and days < thresholds.gold_min_days:
            improvements.append(f"Continue operations for {thresholds.gold_min_days - days} more days")
        elif tier == TrustTier.GOLD and days < thresholds.platinum_min_days:
            improvements.append(f"Continue operations for {thresholds.platinum_min_days - days} more days")
        
        if improvements:
            return f"To advance to {TIER_NAMES[next_tier]}: " + "; ".join(improvements)
        else:
            return f"Continue current practices to advance to {TIER_NAMES[next_tier]}"
    
    def _identify_risk_factors(self, scores: DriverScores) -> List[str]:
        """Identify factors that could decrease the tier."""
        risks = []
        
        if scores.evidence_quality < Decimal("0.4"):
            risks.append("Low evidence quality may trigger tier downgrade")
        if scores.telemetry_continuity < Decimal("0.4"):
            risks.append("Telemetry gaps detected - could impact tier")
        if scores.human_discipline < Decimal("0.4"):
            risks.append("Low response rate to recommendations")
        if scores.integrity < Decimal("0.7"):
            risks.append("Unresolved integrity flags present")
        
        return risks
    
    async def _save_tier(
        self,
        result: TrustTierResult,
        org_id: uuid.UUID,
    ) -> None:
        """Persist tier calculation to database."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Check if record exists
            existing = await session.execute(
                text("SELECT id, tier FROM asset_trust_tiers WHERE asset_id = :asset_id"),
                {"asset_id": result.asset_id}
            )
            existing_row = existing.fetchone()
            
            if existing_row:
                previous_tier = existing_row.tier
                
                # Update existing record
                await session.execute(
                    text("""
                        UPDATE asset_trust_tiers SET
                            tier = :tier,
                            tier_name = :tier_name,
                            evidence_quality_score = :evidence,
                            telemetry_continuity_score = :telemetry,
                            human_discipline_score = :discipline,
                            time_in_system_score = :time,
                            integrity_score = :integrity,
                            composite_score = :composite,
                            explanation = :explanation,
                            upgrade_path = :upgrade_path,
                            risk_factors = :risk_factors,
                            tier_cap = :tier_cap,
                            tier_cap_reason = :tier_cap_reason,
                            first_event_at = :first_event,
                            last_event_at = :last_event,
                            days_in_system = :days,
                            last_calculated_at = :calculated_at,
                            updated_at = NOW()
                        WHERE asset_id = :asset_id
                    """),
                    {
                        "asset_id": result.asset_id,
                        "tier": result.tier.value,
                        "tier_name": result.tier_name,
                        "evidence": result.scores.evidence_quality,
                        "telemetry": result.scores.telemetry_continuity,
                        "discipline": result.scores.human_discipline,
                        "time": result.scores.time_in_system,
                        "integrity": result.scores.integrity,
                        "composite": result.scores.composite,
                        "explanation": result.explanation,
                        "upgrade_path": result.upgrade_path,
                        "risk_factors": json.dumps(result.risk_factors),
                        "tier_cap": result.tier_cap.value if result.tier_cap else None,
                        "tier_cap_reason": result.tier_cap_reason,
                        "first_event": result.first_event_at,
                        "last_event": result.last_event_at,
                        "days": result.days_in_system,
                        "calculated_at": result.calculated_at,
                    }
                )
                
                # Log tier change if changed
                if previous_tier != result.tier.value:
                    change_type = "upgrade" if result.tier.value > previous_tier else "downgrade"
                    await self._log_tier_change(
                        session, result, org_id, previous_tier, change_type
                    )
            else:
                # Insert new record
                await session.execute(
                    text("""
                        INSERT INTO asset_trust_tiers (
                            id, asset_id, org_id,
                            tier, tier_name,
                            evidence_quality_score, telemetry_continuity_score,
                            human_discipline_score, time_in_system_score, integrity_score,
                            composite_score, explanation, upgrade_path, risk_factors,
                            tier_cap, tier_cap_reason,
                            first_event_at, last_event_at, days_in_system,
                            last_calculated_at, calculation_version,
                            created_at, updated_at
                        ) VALUES (
                            gen_random_uuid(), :asset_id, :org_id,
                            :tier, :tier_name,
                            :evidence, :telemetry, :discipline, :time, :integrity,
                            :composite, :explanation, :upgrade_path, :risk_factors,
                            :tier_cap, :tier_cap_reason,
                            :first_event, :last_event, :days,
                            :calculated_at, '1.0.0',
                            NOW(), NOW()
                        )
                    """),
                    {
                        "asset_id": result.asset_id,
                        "org_id": org_id,
                        "tier": result.tier.value,
                        "tier_name": result.tier_name,
                        "evidence": result.scores.evidence_quality,
                        "telemetry": result.scores.telemetry_continuity,
                        "discipline": result.scores.human_discipline,
                        "time": result.scores.time_in_system,
                        "integrity": result.scores.integrity,
                        "composite": result.scores.composite,
                        "explanation": result.explanation,
                        "upgrade_path": result.upgrade_path,
                        "risk_factors": json.dumps(result.risk_factors),
                        "tier_cap": result.tier_cap.value if result.tier_cap else None,
                        "tier_cap_reason": result.tier_cap_reason,
                        "first_event": result.first_event_at,
                        "last_event": result.last_event_at,
                        "days": result.days_in_system,
                        "calculated_at": result.calculated_at,
                    }
                )
                
                # Log initial tier
                await self._log_tier_change(
                    session, result, org_id, None, "initial"
                )
            
            await session.commit()
    
    async def _log_tier_change(
        self,
        session,
        result: TrustTierResult,
        org_id: uuid.UUID,
        previous_tier: Optional[int],
        change_type: str,
    ) -> None:
        """Log tier change to history table."""
        from sqlalchemy import text
        
        previous_name = TIER_NAMES[TrustTier(previous_tier)] if previous_tier else None
        
        change_reason = f"Tier calculated: composite score {result.scores.composite}"
        if change_type == "upgrade":
            change_reason = f"Upgraded from {previous_name} to {result.tier_name}"
        elif change_type == "downgrade":
            change_reason = f"Downgraded from {previous_name} to {result.tier_name}"
        elif change_type == "initial":
            change_reason = f"Initial tier assignment: {result.tier_name}"
        
        await session.execute(
            text("""
                INSERT INTO trust_tier_history (
                    id, asset_id, org_id,
                    previous_tier, new_tier, previous_tier_name, new_tier_name,
                    change_type, change_reason,
                    evidence_quality_score, telemetry_continuity_score,
                    human_discipline_score, time_in_system_score, integrity_score,
                    composite_score, recorded_at
                ) VALUES (
                    gen_random_uuid(), :asset_id, :org_id,
                    :prev_tier, :new_tier, :prev_name, :new_name,
                    :change_type, :change_reason,
                    :evidence, :telemetry, :discipline, :time, :integrity,
                    :composite, NOW()
                )
            """),
            {
                "asset_id": result.asset_id,
                "org_id": org_id,
                "prev_tier": previous_tier,
                "new_tier": result.tier.value,
                "prev_name": previous_name,
                "new_name": result.tier_name,
                "change_type": change_type,
                "change_reason": change_reason,
                "evidence": result.scores.evidence_quality,
                "telemetry": result.scores.telemetry_continuity,
                "discipline": result.scores.human_discipline,
                "time": result.scores.time_in_system,
                "integrity": result.scores.integrity,
                "composite": result.scores.composite,
            }
        )
    
    async def get_tier(self, asset_id: uuid.UUID) -> Optional[TrustTierResult]:
        """Get current trust tier for an asset."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("SELECT * FROM asset_trust_tiers WHERE asset_id = :asset_id"),
                {"asset_id": asset_id}
            )
            row = result.fetchone()
            
            if not row:
                return None
            
            return TrustTierResult(
                asset_id=row.asset_id,
                tier=TrustTier(row.tier),
                tier_name=row.tier_name,
                tier_meaning=TIER_MEANINGS[TrustTier(row.tier)],
                scores=DriverScores(
                    evidence_quality=row.evidence_quality_score,
                    telemetry_continuity=row.telemetry_continuity_score,
                    human_discipline=row.human_discipline_score,
                    time_in_system=row.time_in_system_score,
                    integrity=row.integrity_score,
                    composite=row.composite_score,
                ),
                explanation=row.explanation,
                upgrade_path=row.upgrade_path,
                risk_factors=json.loads(row.risk_factors) if row.risk_factors else [],
                tier_cap=TrustTier(row.tier_cap) if row.tier_cap else None,
                tier_cap_reason=row.tier_cap_reason,
                first_event_at=row.first_event_at,
                last_event_at=row.last_event_at,
                days_in_system=row.days_in_system,
                calculated_at=row.last_calculated_at,
            )
    
    async def get_tier_distribution(self, org_id: uuid.UUID) -> Dict[str, int]:
        """Get distribution of assets by tier for an org."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("""
                    SELECT tier_name, COUNT(*) as count
                    FROM asset_trust_tiers
                    WHERE org_id = :org_id
                    GROUP BY tier_name
                """),
                {"org_id": org_id}
            )
            
            distribution = {"BRONZE": 0, "SILVER": 0, "GOLD": 0, "PLATINUM": 0}
            for row in result.fetchall():
                distribution[row.tier_name] = row.count
            
            return distribution


# Singleton instance
trust_tier_engine = TrustTierEngine()
