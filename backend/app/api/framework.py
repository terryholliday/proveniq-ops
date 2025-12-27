"""
PROVENIQ Ops - Operational Integrity Framework API
Phase 3-4: Ops as De Facto Standard

This API publishes the PROVENIQ Operational Integrity Framework
for third-party consumption.

GOAL: "We prefer Ops-based documentation" — not "We require Proveniq"
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from uuid import UUID

from app.services.integrity_framework import (
    integrity_framework,
    IndustryMapping,
    FrameworkVersion,
)

router = APIRouter(prefix="/framework", tags=["framework"])


class TaxonomyMappingResponse(BaseModel):
    """Response for event taxonomy mapping."""
    ops_event_type: str
    insurance_category: Optional[str]
    insurance_subcategory: Optional[str]
    insurance_description: Optional[str]
    audit_classification: Optional[str]
    compliance_domain: Optional[str]
    regulatory_relevance: List[str]
    claims_weight: str
    evidence_strength: str
    plain_language_description: str


@router.get("/")
async def get_framework():
    """
    Get the complete Operational Integrity Framework documentation.
    
    This is the publishable standard that downstream systems,
    insurers, lenders, auditors, and regulators can reference.
    """
    return integrity_framework.get_framework_documentation()


@router.get("/version")
async def get_framework_version():
    """
    Get the current published framework version.
    """
    framework = await integrity_framework.get_current_framework()
    
    return {
        "version": framework.version,
        "name": framework.name,
        "status": framework.status,
        "published_at": framework.published_at.isoformat() if framework.published_at else None,
        "backward_compatible_with": framework.backward_compatible_with,
    }


@router.get("/schema")
async def get_framework_schema():
    """
    Get the framework schema definition.
    
    Used by downstream systems for integration.
    """
    framework = await integrity_framework.get_current_framework()
    
    return {
        "version": framework.version,
        "schema": framework.schema_definition,
        "event_types": framework.event_types,
        "trust_tier_requirements": framework.trust_tier_requirements,
        "attestation_rules": framework.attestation_rules,
    }


@router.get("/taxonomy", response_model=List[TaxonomyMappingResponse])
async def get_event_taxonomy():
    """
    Get the complete event-to-industry taxonomy.
    
    Maps Ops events to:
    - Insurance categories
    - Audit classifications
    - Compliance domains
    - Regulatory relevance
    """
    mappings = await integrity_framework.get_event_taxonomy()
    
    return [
        TaxonomyMappingResponse(
            ops_event_type=m.ops_event_type,
            insurance_category=m.insurance_category,
            insurance_subcategory=m.insurance_subcategory,
            insurance_description=m.insurance_description,
            audit_classification=m.audit_classification,
            compliance_domain=m.compliance_domain,
            regulatory_relevance=m.regulatory_relevance,
            claims_weight=str(m.claims_weight),
            evidence_strength=m.evidence_strength.value,
            plain_language_description=m.plain_language_description,
        )
        for m in mappings
    ]


@router.get("/taxonomy/{event_type}", response_model=TaxonomyMappingResponse)
async def get_event_mapping(event_type: str):
    """
    Get industry mapping for a specific event type.
    """
    mapping = await integrity_framework.get_event_mapping(event_type)
    
    if not mapping:
        raise HTTPException(status_code=404, detail=f"No mapping found for event type: {event_type}")
    
    return TaxonomyMappingResponse(
        ops_event_type=mapping.ops_event_type,
        insurance_category=mapping.insurance_category,
        insurance_subcategory=mapping.insurance_subcategory,
        insurance_description=mapping.insurance_description,
        audit_classification=mapping.audit_classification,
        compliance_domain=mapping.compliance_domain,
        regulatory_relevance=mapping.regulatory_relevance,
        claims_weight=str(mapping.claims_weight),
        evidence_strength=mapping.evidence_strength.value,
        plain_language_description=mapping.plain_language_description,
    )


@router.get("/taxonomy/by-insurance")
async def get_taxonomy_by_insurance():
    """
    Get events grouped by insurance category.
    
    For insurers evaluating Ops evidence.
    """
    grouped = await integrity_framework.get_insurance_mappings()
    
    return {
        category: [
            {
                "event_type": m.ops_event_type,
                "subcategory": m.insurance_subcategory,
                "claims_weight": str(m.claims_weight),
                "evidence_strength": m.evidence_strength.value,
                "description": m.insurance_description or m.plain_language_description,
            }
            for m in mappings
        ]
        for category, mappings in grouped.items()
    }


@router.get("/taxonomy/by-audit")
async def get_taxonomy_by_audit():
    """
    Get events grouped by audit classification.
    
    For auditors evaluating operational controls.
    """
    grouped = await integrity_framework.get_audit_mappings()
    
    return {
        classification: [
            {
                "event_type": m.ops_event_type,
                "evidence_strength": m.evidence_strength.value,
                "description": m.audit_description or m.plain_language_description,
            }
            for m in mappings
        ]
        for classification, mappings in grouped.items()
    }


@router.get("/taxonomy/by-compliance")
async def get_taxonomy_by_compliance():
    """
    Get events grouped by compliance domain.
    
    For compliance teams and regulators.
    """
    grouped = await integrity_framework.get_compliance_mappings()
    
    return {
        domain: [
            {
                "event_type": m.ops_event_type,
                "regulatory_relevance": m.regulatory_relevance,
                "iso_category": m.iso_category,
                "haccp_relevance": m.haccp_relevance,
                "description": m.plain_language_description,
            }
            for m in mappings
        ]
        for domain, mappings in grouped.items()
    }


@router.get("/principles")
async def get_core_principles():
    """
    Get the core principles of the Operational Integrity Framework.
    
    These principles define what "operational truth" means.
    """
    return {
        "title": "Core Principles of Operational Truth",
        "principles": [
            {
                "name": "Observation vs Evidence",
                "observation": "What did we see?",
                "evidence": "What can survive challenge?",
                "implication": "A standard must privilege evidence over observation.",
            },
            {
                "name": "Evidence-Gated State",
                "definition": "No material state change occurs without verifiable proof.",
                "implication": "State changes without evidence are not trustworthy.",
            },
            {
                "name": "Append-Only History",
                "definition": "History is recorded, not rewritten.",
                "implication": "Immutable audit trail is required.",
            },
            {
                "name": "Clear Authority Boundaries",
                "definition": "Operations ≠ finance. Observation ≠ decision. AI = advisory only.",
                "implication": "Separation of concerns prevents conflicts of interest.",
            },
            {
                "name": "Continuity Over Snapshots",
                "definition": "Truth is accumulated over time, not inferred from moments.",
                "implication": "Point-in-time data is less reliable than continuous history.",
            },
            {
                "name": "Neutrality",
                "definition": "The system records what happened. It does not advocate for outcomes.",
                "implication": "Evidence must be impartial to be trustworthy.",
            },
        ],
    }


@router.get("/adoption-guide")
async def get_adoption_guide():
    """
    Get guidance for adopting the Operational Integrity Framework.
    
    For institutions considering Ops-based documentation.
    """
    return {
        "title": "Adopting the Operational Integrity Framework",
        "for_insurers": {
            "value_proposition": "Reduce claims friction with verified operational history.",
            "integration_path": [
                "Review event taxonomy for insurance-relevant events",
                "Request evidence packs via API for claims",
                "Use trust tiers to inform documentation requirements",
                "Accept attestations as supplementary evidence",
            ],
            "benefits": [
                "Faster claims resolution",
                "Better fraud detection",
                "Reduced disputes",
                "Differentiated underwriting",
            ],
        },
        "for_lenders": {
            "value_proposition": "Asset-backed lending with operational confidence.",
            "integration_path": [
                "Check trust tier for loan eligibility",
                "Request operational history for underwriting",
                "Monitor ongoing trust tier for portfolio risk",
                "Use attestations for collateral verification",
            ],
            "benefits": [
                "Reduced operational risk",
                "Better collateral confidence",
                "Differentiated terms",
                "Continuous monitoring",
            ],
        },
        "for_auditors": {
            "value_proposition": "Append-only, hash-verified audit trails.",
            "integration_path": [
                "Export audit trails via API",
                "Map events to audit classifications",
                "Verify event hashes for integrity",
                "Generate compliance reports",
            ],
            "benefits": [
                "Immutable evidence",
                "Industry-standard mapping",
                "Efficient audits",
                "Verifiable controls",
            ],
        },
        "for_regulators": {
            "value_proposition": "Compliance-relevant event capture and reporting.",
            "integration_path": [
                "Review compliance domain mappings",
                "Request regulatory filing reports",
                "Verify attestations for compliance claims",
                "Access forensic timelines for investigations",
            ],
            "benefits": [
                "Standardized reporting",
                "Verifiable compliance",
                "Forensic capability",
                "Industry adoption",
            ],
        },
        "adoption_principle": (
            "This standard spreads when institutions independently conclude: "
            "'This is what serious operational truth looks like.'"
        ),
    }
