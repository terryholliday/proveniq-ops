"""
PROVENIQ Ops - Operational Integrity Framework
Phase 3-4: Ops as De Facto Standard

GOAL: "We prefer Ops-based documentation" — not "We require Proveniq"

This module:
- Publishes the Proveniq Operational Integrity Framework
- Maps Ops events to industry-standard concepts (insurance, audit, compliance)
- Provides framework documentation for third parties
- Enables downstream systems to understand Ops data without Proveniq mediation
"""

import uuid
import json
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
import logging

from app.db.session import async_session_maker

logger = logging.getLogger(__name__)


class EvidenceStrength(str, Enum):
    """Strength of evidence for claims/compliance purposes."""
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"
    DEFINITIVE = "definitive"


class IndustryMapping(BaseModel):
    """Maps an Ops event to industry-standard concepts."""
    ops_event_type: str
    
    # Insurance mappings
    insurance_category: Optional[str] = None
    insurance_subcategory: Optional[str] = None
    insurance_description: Optional[str] = None
    
    # Audit mappings
    audit_classification: Optional[str] = None
    audit_description: Optional[str] = None
    
    # Compliance mappings
    compliance_domain: Optional[str] = None
    regulatory_relevance: List[str] = []
    
    # ISO/Standard mappings
    iso_category: Optional[str] = None
    haccp_relevance: bool = False
    food_safety_category: Optional[str] = None
    
    # Claims relevance
    claims_weight: Decimal = Decimal("0.5")
    evidence_strength: EvidenceStrength = EvidenceStrength.MEDIUM
    
    # Plain language
    plain_language_description: str


class FrameworkVersion(BaseModel):
    """Published version of the Operational Integrity Framework."""
    version: str
    name: str
    status: str
    
    # Schema
    schema_definition: Dict[str, Any]
    event_types: Dict[str, Any]
    trust_tier_requirements: Dict[str, Any]
    attestation_rules: Dict[str, Any]
    
    # Compatibility
    backward_compatible_with: List[str] = []
    breaking_changes: Optional[Dict[str, Any]] = None
    
    published_at: Optional[datetime] = None


class IntegrityFrameworkService:
    """
    Service for the Proveniq Operational Integrity Framework.
    
    MOAT PRINCIPLE:
    - Framework becomes the reference standard for operational truth
    - Third parties adopt terminology and concepts
    - "Ops-based documentation" becomes industry preference
    - Competitors must adopt standard or be incompatible
    """
    
    async def get_current_framework(self) -> FrameworkVersion:
        """Get the current published framework version."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("""
                    SELECT * FROM framework_versions
                    WHERE status = 'published'
                    ORDER BY published_at DESC
                    LIMIT 1
                """)
            )
            row = result.fetchone()
            
            if not row:
                # Return default framework
                return self._get_default_framework()
            
            return FrameworkVersion(
                version=row.version,
                name=row.name,
                status=row.status,
                schema_definition=row.schema_definition,
                event_types=row.event_types,
                trust_tier_requirements=row.trust_tier_requirements,
                attestation_rules=row.attestation_rules,
                backward_compatible_with=row.backward_compatible_with or [],
                breaking_changes=row.breaking_changes,
                published_at=row.published_at,
            )
    
    def _get_default_framework(self) -> FrameworkVersion:
        """Return default framework definition."""
        return FrameworkVersion(
            version="1.0.0",
            name="PROVENIQ Operational Integrity Framework",
            status="published",
            schema_definition={
                "version": "1.0.0",
                "standard": "proveniq-oif",
                "description": "Operational truth infrastructure standard",
                "core_principles": [
                    "Observation is not Evidence",
                    "Evidence-Gated State",
                    "Append-Only History",
                    "Clear Authority Boundaries",
                    "Continuity Over Snapshots",
                    "Neutrality",
                ],
            },
            event_types={
                "categories": [
                    "telemetry",
                    "bishop",
                    "shrinkage",
                    "inventory",
                    "vendor",
                    "anomaly",
                ],
                "naming_convention": "ops.<category>.<action>",
            },
            trust_tier_requirements={
                "bronze": {"min_score": 0.0, "min_days": 0, "meaning": "Observed"},
                "silver": {"min_score": 0.3, "min_days": 7, "meaning": "Corroborated"},
                "gold": {"min_score": 0.6, "min_days": 30, "meaning": "Verified"},
                "platinum": {"min_score": 0.85, "min_days": 90, "meaning": "Attestable"},
            },
            attestation_rules={
                "types": [
                    "OPERATION_WITHIN_SPEC",
                    "CONDITION_AT_TIME",
                    "CONTINUITY_CONFIRMED",
                ],
                "platinum_required": True,
                "expiration_required": True,
                "no_perpetual_attestations": True,
            },
            published_at=datetime.now(timezone.utc),
        )
    
    async def get_event_taxonomy(self) -> List[IndustryMapping]:
        """Get all event-to-industry mappings."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("SELECT * FROM event_taxonomy ORDER BY ops_event_type")
            )
            
            mappings = []
            for row in result.fetchall():
                mappings.append(IndustryMapping(
                    ops_event_type=row.ops_event_type,
                    insurance_category=row.insurance_category,
                    insurance_subcategory=row.insurance_subcategory,
                    insurance_description=row.insurance_description,
                    audit_classification=row.audit_classification,
                    audit_description=row.audit_description,
                    compliance_domain=row.compliance_domain,
                    regulatory_relevance=row.regulatory_relevance or [],
                    iso_category=row.iso_category,
                    haccp_relevance=row.haccp_relevance or False,
                    food_safety_category=row.food_safety_category,
                    claims_weight=row.claims_weight,
                    evidence_strength=EvidenceStrength(row.evidence_strength),
                    plain_language_description=row.plain_language_description,
                ))
            
            return mappings
    
    async def get_event_mapping(self, event_type: str) -> Optional[IndustryMapping]:
        """Get industry mapping for a specific event type."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("SELECT * FROM event_taxonomy WHERE ops_event_type = :event_type"),
                {"event_type": event_type}
            )
            row = result.fetchone()
            
            if not row:
                return None
            
            return IndustryMapping(
                ops_event_type=row.ops_event_type,
                insurance_category=row.insurance_category,
                insurance_subcategory=row.insurance_subcategory,
                insurance_description=row.insurance_description,
                audit_classification=row.audit_classification,
                audit_description=row.audit_description,
                compliance_domain=row.compliance_domain,
                regulatory_relevance=row.regulatory_relevance or [],
                iso_category=row.iso_category,
                haccp_relevance=row.haccp_relevance or False,
                food_safety_category=row.food_safety_category,
                claims_weight=row.claims_weight,
                evidence_strength=EvidenceStrength(row.evidence_strength),
                plain_language_description=row.plain_language_description,
            )
    
    async def get_insurance_mappings(self) -> Dict[str, List[IndustryMapping]]:
        """Get events grouped by insurance category."""
        mappings = await self.get_event_taxonomy()
        
        grouped = {}
        for m in mappings:
            if m.insurance_category:
                if m.insurance_category not in grouped:
                    grouped[m.insurance_category] = []
                grouped[m.insurance_category].append(m)
        
        return grouped
    
    async def get_audit_mappings(self) -> Dict[str, List[IndustryMapping]]:
        """Get events grouped by audit classification."""
        mappings = await self.get_event_taxonomy()
        
        grouped = {}
        for m in mappings:
            if m.audit_classification:
                if m.audit_classification not in grouped:
                    grouped[m.audit_classification] = []
                grouped[m.audit_classification].append(m)
        
        return grouped
    
    async def get_compliance_mappings(self) -> Dict[str, List[IndustryMapping]]:
        """Get events grouped by compliance domain."""
        mappings = await self.get_event_taxonomy()
        
        grouped = {}
        for m in mappings:
            if m.compliance_domain:
                if m.compliance_domain not in grouped:
                    grouped[m.compliance_domain] = []
                grouped[m.compliance_domain].append(m)
        
        return grouped
    
    def get_framework_documentation(self) -> Dict[str, Any]:
        """
        Get complete framework documentation for third parties.
        
        This is the publishable standard that downstream systems reference.
        """
        return {
            "title": "PROVENIQ Operational Integrity Framework",
            "version": "1.0.0",
            "status": "published",
            "description": (
                "A standard for operational truth infrastructure. "
                "This framework defines how operational evidence is captured, "
                "classified, and attested for third-party reliance."
            ),
            "core_principles": {
                "observation_vs_evidence": {
                    "observation": "What did we see?",
                    "evidence": "What can survive challenge?",
                    "principle": "A standard must privilege the latter.",
                },
                "evidence_gated_state": "No material state change occurs without verifiable proof.",
                "append_only_history": "History is recorded, not rewritten.",
                "authority_boundaries": {
                    "ops_vs_finance": "Operations are distinct from finance.",
                    "observation_vs_decision": "Observation is distinct from decision.",
                    "ai_role": "AI is advisory, never authoritative.",
                },
                "continuity": "Truth is accumulated over time, not inferred from moments.",
                "neutrality": "The system records what happened. It does not advocate for outcomes.",
            },
            "trust_tiers": {
                "purpose": "Measure how confidently external parties can rely on Ops data.",
                "tiers": {
                    "BRONZE": {
                        "level": 1,
                        "name": "Observed",
                        "meaning": "Verification relies heavily on humans.",
                        "requirements": ["Human-submitted evidence", "Third-party sensors allowed"],
                    },
                    "SILVER": {
                        "level": 2,
                        "name": "Corroborated",
                        "meaning": "Multiple signals agree, but not all are controlled.",
                        "requirements": ["Mixed evidence", "≥1 continuous sensor", "Bishop active"],
                    },
                    "GOLD": {
                        "level": 3,
                        "name": "Verified",
                        "meaning": "Evidence quality and discipline are consistently high.",
                        "requirements": ["Continuous telemetry", "Certified sensors", "No recent waivers"],
                    },
                    "PLATINUM": {
                        "level": 4,
                        "name": "Attestable",
                        "meaning": "History can be relied upon by third parties.",
                        "requirements": ["Long-term continuity", "Crypto-verifiable chains", "Attestation eligible"],
                    },
                },
                "rules": [
                    "Tiers are per asset, NOT per account.",
                    "Tiers are earned from behavior over time.",
                    "Tiers CANNOT be manually set.",
                    "Tiers CANNOT be tied to price.",
                    "Tiers degrade automatically when inputs degrade.",
                ],
            },
            "attestations": {
                "definition": (
                    "A cryptographically signed, time-bound, evidence-backed statement "
                    "asserting operational condition during a specific interval."
                ),
                "types": {
                    "OPERATION_WITHIN_SPEC": "Operated within declared parameters.",
                    "CONDITION_AT_TIME": "Condition observed at a specific time.",
                    "CONTINUITY_CONFIRMED": "No detected gaps in declared telemetry.",
                },
                "rules": [
                    "Only PLATINUM tier assets are eligible.",
                    "All attestations expire (no perpetual attestations).",
                    "Verifiable without Proveniq authentication.",
                    "Never imply guarantee, coverage, or prediction.",
                ],
                "disclaimers": [
                    "Attestations reflect observed operation during the time window.",
                    "Attestations do not predict future performance.",
                    "Attestations do not constitute insurance, approval, or guarantee.",
                ],
            },
            "event_categories": [
                {"category": "telemetry", "description": "Sensor readings and measurements"},
                {"category": "bishop", "description": "AI recommendations and human decisions"},
                {"category": "shrinkage", "description": "Inventory loss detection and classification"},
                {"category": "inventory", "description": "Stock levels and movements"},
                {"category": "vendor", "description": "Supplier interactions and orders"},
                {"category": "anomaly", "description": "Deviations from established baselines"},
            ],
            "integration_guidance": {
                "for_insurers": (
                    "Ops evidence can supplement or replace traditional loss documentation. "
                    "Higher trust tiers indicate greater reliability without additional verification."
                ),
                "for_lenders": (
                    "Trust tier and operational history inform asset-backed lending decisions. "
                    "Continuous telemetry reduces risk of undisclosed operational issues."
                ),
                "for_auditors": (
                    "Ops provides append-only, hash-verified event history. "
                    "Events are mapped to standard audit classifications."
                ),
                "for_regulators": (
                    "Compliance-relevant events are tagged by domain (FDA, SOX, etc.). "
                    "Reports can be generated for regulatory filings."
                ),
            },
            "adoption": {
                "principle": "This standard spreads when institutions independently conclude: 'This is what serious operational truth looks like.'",
                "goal": "'We prefer Ops-based documentation' — not 'We require Proveniq'",
            },
        }


# Singleton instance
integrity_framework = IntegrityFrameworkService()
