"""
PROVENIQ Ops - Downstream Integration API
Phase 4-5: Regulatory & Capital Dependence

APIs for:
- ClaimsIQ claims processing
- Capital loan eligibility
- Bids marketplace listing
- External insurers, lenders, auditors
- Compliance reporting and audit exports

GOAL:
- Capital systems require Ops truth
- Claims systems defer to Ops timelines
- Operating without Ops = riskier, more expensive
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from app.services.downstream_service import (
    downstream_service,
    SystemType,
    ReportType,
    EvidencePack,
    ComplianceReport,
)

router = APIRouter(prefix="/downstream", tags=["downstream"])


class IntegrationRequest(BaseModel):
    """Request to register a downstream integration."""
    system_name: str
    system_type: str
    api_endpoint: Optional[str] = None
    webhook_url: Optional[str] = None
    shared_event_types: List[str] = Field(default_factory=list)
    trust_tier_threshold: Optional[int] = None
    attestation_required: bool = False


class EvidencePackRequest(BaseModel):
    """Request for evidence pack."""
    asset_id: UUID
    org_id: UUID
    time_range_start: datetime
    time_range_end: datetime


class TimelineRequest(BaseModel):
    """Request for claims timeline."""
    asset_id: UUID
    org_id: UUID
    incident_time: datetime


class EligibilityRequest(BaseModel):
    """Request for eligibility check."""
    asset_id: UUID
    org_id: UUID


class ReportRequest(BaseModel):
    """Request for compliance report."""
    org_id: UUID
    report_type: str
    time_range_start: datetime
    time_range_end: datetime
    asset_ids: Optional[List[UUID]] = None


class AuditExportRequest(BaseModel):
    """Request for audit export."""
    org_id: UUID
    time_range_start: datetime
    time_range_end: datetime
    asset_ids: Optional[List[UUID]] = None


# ============================================================================
# Integration Management
# ============================================================================

@router.post("/integrations")
async def register_integration(request: IntegrationRequest):
    """
    Register a new downstream integration.
    
    Supported system types:
    - claimsiq: PROVENIQ ClaimsIQ
    - capital: PROVENIQ Capital
    - bids: PROVENIQ Bids
    - insurer: External insurance company
    - lender: External lender
    - regulator: Regulatory body
    - auditor: External auditor
    """
    try:
        system_type = SystemType(request.system_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid system type. Must be one of: {[t.value for t in SystemType]}"
        )
    
    integration = await downstream_service.register_integration(
        system_name=request.system_name,
        system_type=system_type,
        api_endpoint=request.api_endpoint,
        webhook_url=request.webhook_url,
        shared_event_types=request.shared_event_types,
        trust_tier_threshold=request.trust_tier_threshold,
        attestation_required=request.attestation_required,
    )
    
    return {
        "integration_id": integration.integration_id,
        "system_name": integration.system_name,
        "system_type": integration.system_type.value,
        "status": integration.status,
    }


# ============================================================================
# ClaimsIQ Integration
# ============================================================================

@router.post("/claimsiq/timeline")
async def get_claims_timeline(request: TimelineRequest):
    """
    Get forensic timeline for ClaimsIQ claims processing.
    
    Returns events before and after the incident time for context.
    Used by ClaimsIQ to build claims evidence packages.
    """
    return await downstream_service.get_timeline_for_claims(
        asset_id=request.asset_id,
        org_id=request.org_id,
        incident_time=request.incident_time,
        integration_id="claimsiq",
    )


@router.post("/claimsiq/evidence-pack")
async def get_claimsiq_evidence_pack(request: EvidencePackRequest):
    """
    Get evidence pack for ClaimsIQ claims processing.
    
    Includes:
    - Events in time range
    - Anomalies detected
    - Attestations (if any)
    - Trust tier at time of request
    - Industry-relevant event mappings
    """
    pack = await downstream_service.get_evidence_pack(
        asset_id=request.asset_id,
        org_id=request.org_id,
        time_range_start=request.time_range_start,
        time_range_end=request.time_range_end,
        integration_id="claimsiq",
    )
    
    return {
        "pack_id": pack.pack_id,
        "asset_id": str(pack.asset_id),
        "trust_tier": pack.trust_tier,
        "trust_tier_name": pack.trust_tier_name,
        "time_range": {
            "start": pack.time_range_start.isoformat(),
            "end": pack.time_range_end.isoformat(),
        },
        "evidence": {
            "event_count": pack.event_count,
            "event_types": pack.event_types,
            "anomaly_count": pack.anomaly_count,
            "attestation_count": len(pack.attestations),
        },
        "claims_relevance": {
            "insurance_relevant_events": pack.insurance_relevant_events,
            "compliance_relevant_events": pack.compliance_relevant_events,
        },
        "evidence_digest": pack.evidence_digest,
        "generated_at": pack.generated_at.isoformat(),
    }


# ============================================================================
# Capital Integration
# ============================================================================

@router.post("/capital/eligibility")
async def check_capital_eligibility(request: EligibilityRequest):
    """
    Check asset eligibility for Capital lending.
    
    Returns:
    - Eligibility status
    - Trust tier and driver scores
    - Risk assessment
    - Recommendation
    
    Used by Capital for loan underwriting decisions.
    """
    return await downstream_service.check_capital_eligibility(
        asset_id=request.asset_id,
        org_id=request.org_id,
        integration_id="capital",
    )


@router.post("/capital/evidence-pack")
async def get_capital_evidence_pack(request: EvidencePackRequest):
    """
    Get evidence pack for Capital underwriting.
    """
    pack = await downstream_service.get_evidence_pack(
        asset_id=request.asset_id,
        org_id=request.org_id,
        time_range_start=request.time_range_start,
        time_range_end=request.time_range_end,
        integration_id="capital",
    )
    
    return {
        "pack_id": pack.pack_id,
        "asset_id": str(pack.asset_id),
        "trust_tier": pack.trust_tier,
        "trust_tier_name": pack.trust_tier_name,
        "operational_history": {
            "event_count": pack.event_count,
            "anomaly_count": pack.anomaly_count,
            "attestation_count": len(pack.attestations),
        },
        "evidence_digest": pack.evidence_digest,
    }


# ============================================================================
# Bids Integration
# ============================================================================

@router.post("/bids/eligibility")
async def check_bids_eligibility(request: EligibilityRequest):
    """
    Check asset eligibility for Bids marketplace listing.
    
    Returns:
    - Listing tier (basic/standard/verified/premium)
    - Trust tier and provenance badge
    - Buyer confidence indicators
    
    Used by Bids for listing presentation.
    """
    return await downstream_service.check_bids_eligibility(
        asset_id=request.asset_id,
        org_id=request.org_id,
        integration_id="bids",
    )


# ============================================================================
# External Integrations (Insurers, Lenders, Auditors)
# ============================================================================

@router.post("/external/evidence-pack")
async def get_external_evidence_pack(
    request: EvidencePackRequest,
    integration_id: str = Query(..., description="Integration ID of the requesting system"),
):
    """
    Get evidence pack for external systems (insurers, lenders, auditors).
    
    Requires a registered integration_id.
    """
    pack = await downstream_service.get_evidence_pack(
        asset_id=request.asset_id,
        org_id=request.org_id,
        time_range_start=request.time_range_start,
        time_range_end=request.time_range_end,
        integration_id=integration_id,
    )
    
    return {
        "pack_id": pack.pack_id,
        "asset_id": str(pack.asset_id),
        "org_id": str(pack.org_id),
        "trust_tier": pack.trust_tier,
        "trust_tier_name": pack.trust_tier_name,
        "time_range": {
            "start": pack.time_range_start.isoformat(),
            "end": pack.time_range_end.isoformat(),
        },
        "events": pack.events,
        "event_count": pack.event_count,
        "anomalies": pack.anomalies,
        "anomaly_count": pack.anomaly_count,
        "attestations": pack.attestations,
        "industry_mappings": {
            "insurance_relevant": pack.insurance_relevant_events,
            "compliance_relevant": pack.compliance_relevant_events,
        },
        "evidence_digest": pack.evidence_digest,
        "generated_at": pack.generated_at.isoformat(),
    }


# ============================================================================
# Compliance Reporting
# ============================================================================

@router.post("/reports/generate")
async def generate_compliance_report(request: ReportRequest):
    """
    Generate a compliance/audit report.
    
    Report types:
    - operational_summary: General operational overview
    - compliance_audit: Audit-ready compliance report
    - insurance_evidence: Evidence pack for insurance claims
    - regulatory_filing: Data for regulatory filings
    - loss_prevention: Loss prevention analysis
    - incident_timeline: Forensic incident reconstruction
    """
    try:
        report_type = ReportType(request.report_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report type. Must be one of: {[t.value for t in ReportType]}"
        )
    
    report = await downstream_service.generate_compliance_report(
        org_id=request.org_id,
        report_type=report_type,
        time_range_start=request.time_range_start,
        time_range_end=request.time_range_end,
        asset_ids=request.asset_ids,
    )
    
    return {
        "report_id": report.report_id,
        "report_type": report.report_type.value,
        "org_id": str(report.org_id),
        "time_range": {
            "start": report.time_range_start.isoformat(),
            "end": report.time_range_end.isoformat(),
        },
        "summary": report.summary,
        "metrics": {
            "total_events": report.total_events,
            "anomalies_detected": report.anomalies_detected,
            "attestations_issued": report.attestations_issued,
            "average_trust_tier": str(report.average_trust_tier) if report.average_trust_tier else None,
        },
        "report_hash": report.report_hash,
        "generated_at": report.generated_at.isoformat(),
        "report_data": report.report_data,
    }


@router.get("/reports/{report_id}")
async def get_compliance_report(report_id: str):
    """
    Get a previously generated compliance report.
    """
    from app.db.session import async_session_maker
    from sqlalchemy import text
    
    async with async_session_maker() as session:
        result = await session.execute(
            text("SELECT * FROM compliance_reports WHERE report_id = :report_id"),
            {"report_id": report_id}
        )
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")
        
        return {
            "report_id": row.report_id,
            "report_type": row.report_type,
            "org_id": str(row.org_id),
            "time_range": {
                "start": row.time_range_start.isoformat(),
                "end": row.time_range_end.isoformat(),
            },
            "summary": row.summary,
            "metrics": {
                "total_events": row.total_events,
                "anomalies_detected": row.anomalies_detected,
                "attestations_issued": row.attestations_issued,
                "average_trust_tier": str(row.average_trust_tier) if row.average_trust_tier else None,
            },
            "report_hash": row.report_hash,
            "generated_at": row.generated_at.isoformat(),
            "report_data": row.report_data,
        }


# ============================================================================
# Audit Export
# ============================================================================

@router.post("/audit/export")
async def export_audit_trail(
    request: AuditExportRequest,
    integration_id: Optional[str] = Query(default=None, description="Integration ID if external"),
):
    """
    Export complete audit trail for external auditors.
    
    Includes:
    - All events with hashes
    - All anomalies
    - All attestations
    - Trust tier distribution
    - Framework version
    """
    return await downstream_service.export_audit_trail(
        org_id=request.org_id,
        time_range_start=request.time_range_start,
        time_range_end=request.time_range_end,
        asset_ids=request.asset_ids,
        integration_id=integration_id,
    )


# ============================================================================
# Downstream Effects Summary
# ============================================================================

@router.get("/effects")
async def get_downstream_effects():
    """
    Get summary of how Ops data affects downstream systems.
    
    Documents the dependency relationships that make
    operating without Ops disadvantageous.
    """
    return {
        "title": "Downstream System Dependencies",
        "description": (
            "Ops operational truth is consumed by downstream systems. "
            "Higher trust tiers and attestations reduce friction and improve terms."
        ),
        "systems": {
            "claimsiq": {
                "integration": "Claims Processing",
                "uses": [
                    "Forensic timelines for claims",
                    "Evidence packs for documentation",
                    "Trust tier for verification requirements",
                    "Attestations for expedited processing",
                ],
                "trust_tier_effects": {
                    "BRONZE": "Full documentation required",
                    "SILVER": "Standard documentation",
                    "GOLD": "Reduced documentation",
                    "PLATINUM": "Minimal documentation, expedited processing",
                },
            },
            "capital": {
                "integration": "Loan Underwriting",
                "uses": [
                    "Trust tier for eligibility",
                    "Operational history for risk assessment",
                    "Anomaly history for due diligence",
                    "Attestations for collateral verification",
                ],
                "trust_tier_effects": {
                    "BRONZE": "May be ineligible or require additional verification",
                    "SILVER": "Standard terms",
                    "GOLD": "Improved terms",
                    "PLATINUM": "Best terms, priority processing",
                },
            },
            "bids": {
                "integration": "Marketplace Listing",
                "uses": [
                    "Trust tier for listing tier",
                    "Provenance badge for buyer confidence",
                    "Attestations for premium listings",
                ],
                "trust_tier_effects": {
                    "BRONZE": "Basic listing",
                    "SILVER": "Standard listing with provenance",
                    "GOLD": "Verified listing with badge",
                    "PLATINUM": "Premium listing with full attestation",
                },
            },
            "insurers": {
                "integration": "Policy Evaluation",
                "uses": [
                    "Operational history for underwriting",
                    "Evidence packs for claims",
                    "Trust tier for premium calculation",
                ],
            },
            "lenders": {
                "integration": "Asset-Backed Lending",
                "uses": [
                    "Operational history for collateral evaluation",
                    "Trust tier for risk pricing",
                    "Continuous monitoring for portfolio risk",
                ],
            },
            "auditors": {
                "integration": "Compliance Audit",
                "uses": [
                    "Append-only event history",
                    "Hash-verified integrity",
                    "Industry-standard event mapping",
                    "Compliance reports",
                ],
            },
            "regulators": {
                "integration": "Regulatory Compliance",
                "uses": [
                    "Compliance domain mappings",
                    "Regulatory filing reports",
                    "Forensic timelines for investigations",
                ],
            },
        },
        "moat_effects": {
            "without_ops": [
                "Higher documentation burden for claims",
                "Higher risk assessment for loans",
                "Lower buyer confidence for sales",
                "Manual audit processes",
                "Slower regulatory compliance",
            ],
            "with_ops": [
                "Streamlined claims processing",
                "Better loan terms",
                "Higher sale prices with provenance",
                "Automated audit trails",
                "Continuous compliance",
            ],
        },
    }
