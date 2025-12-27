"""
PROVENIQ Ops - Attestation API
Phase 2-3: Attestation-as-Infrastructure

GOVERNANCE COMPLIANCE:
- Attestations state what can be PROVEN, not what is PROMISED
- Only PLATINUM tier assets are eligible
- Time-bound (always expire)
- Cryptographically verifiable WITHOUT Proveniq authentication

LANGUAGE RULES:
- AVOID: "certified", "approved", "covered", "safe"
- USE: "observed", "recorded", "attested"
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from app.services.attestation_service import (
    attestation_service,
    AttestationType,
    AttestationRequest,
    Attestation,
    EligibilityResult,
    ATTESTATION_MEANINGS,
)

router = APIRouter(prefix="/attestations", tags=["attestations"])


class EligibilityCheckRequest(BaseModel):
    """Request to check attestation eligibility."""
    asset_id: UUID
    org_id: UUID
    attestation_type: str
    time_window_start: datetime
    time_window_end: datetime


class EligibilityCheckResponse(BaseModel):
    """Response for eligibility check."""
    asset_id: str
    eligible: bool
    trust_tier: Optional[int]
    checks: List[Dict[str, Any]]
    failed_checks: List[str]
    message: str


class AttestationRequestBody(BaseModel):
    """Request body for issuing attestation."""
    asset_id: UUID
    org_id: UUID
    attestation_type: str
    time_window_start: datetime
    time_window_end: datetime
    declared_parameters: Dict[str, Any] = Field(default_factory=dict)
    requested_by: UUID


class AttestationResponse(BaseModel):
    """Response for issued attestation."""
    attestation_id: str
    asset_id: str
    org_id: str
    attestation_type: str
    attestation_meaning: str
    time_window_start: str
    time_window_end: str
    declared_parameters: Dict[str, Any]
    confidence_score: str
    evidence_count: int
    evidence_digest: str
    trust_tier_at_issuance: int
    issuer_key_id: str
    issuer_signature: str
    signature_algorithm: str
    issued_at: str
    expires_at: str
    status: str
    verification_url: Optional[str]


class VerificationResponse(BaseModel):
    """Response for attestation verification."""
    valid: bool
    attestation_id: str
    asset_id: Optional[str]
    attestation_type: Optional[str]
    time_window: Optional[Dict[str, str]]
    confidence_score: Optional[str]
    evidence_count: Optional[int]
    status: Optional[str]
    issued_at: Optional[str]
    expires_at: Optional[str]
    signature_valid: Optional[bool]
    error: Optional[str]


@router.post("/eligibility", response_model=EligibilityCheckResponse)
async def check_eligibility(request: EligibilityCheckRequest):
    """
    Check if an asset is eligible for attestation.
    
    Eligibility requires ALL of:
    - Trust Tier = PLATINUM
    - No unresolved integrity flags
    - No active SECURITY_WAIVER
    - No pending ledger reconciliation
    - Continuous telemetry coverage
    - Minimum time-in-system (90 days)
    """
    try:
        attestation_type = AttestationType(request.attestation_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid attestation type. Must be one of: {[t.value for t in AttestationType]}"
        )
    
    result = await attestation_service.check_eligibility(
        request.asset_id,
        request.org_id,
        attestation_type,
        request.time_window_start,
        request.time_window_end,
    )
    
    return EligibilityCheckResponse(
        asset_id=str(result.asset_id),
        eligible=result.eligible,
        trust_tier=result.trust_tier,
        checks=[c.model_dump() for c in result.checks],
        failed_checks=result.failed_checks,
        message=result.message,
    )


@router.post("/issue", response_model=AttestationResponse)
async def issue_attestation(request: AttestationRequestBody):
    """
    Issue an attestation for an eligible asset.
    
    Only PLATINUM tier assets can receive attestations.
    
    Attestation types:
    - OPERATION_WITHIN_SPEC: Operated within declared parameters
    - CONDITION_AT_TIME: Condition observed at a specific time
    - CONTINUITY_CONFIRMED: No detected gaps in telemetry
    
    Note: This attestation reflects observed operation during the
    specified time window. It does not predict future performance.
    """
    try:
        attestation_type = AttestationType(request.attestation_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid attestation type. Must be one of: {[t.value for t in AttestationType]}"
        )
    
    attest_request = AttestationRequest(
        asset_id=request.asset_id,
        org_id=request.org_id,
        attestation_type=attestation_type,
        time_window_start=request.time_window_start,
        time_window_end=request.time_window_end,
        declared_parameters=request.declared_parameters,
        requested_by=request.requested_by,
    )
    
    success, attestation, error = await attestation_service.issue_attestation(attest_request)
    
    if not success:
        raise HTTPException(status_code=400, detail=error)
    
    return AttestationResponse(
        attestation_id=attestation.attestation_id,
        asset_id=str(attestation.asset_id),
        org_id=str(attestation.org_id),
        attestation_type=attestation.attestation_type.value,
        attestation_meaning=attestation.attestation_meaning,
        time_window_start=attestation.time_window_start.isoformat(),
        time_window_end=attestation.time_window_end.isoformat(),
        declared_parameters=attestation.declared_parameters,
        confidence_score=str(attestation.confidence_score),
        evidence_count=attestation.evidence_count,
        evidence_digest=attestation.evidence_digest,
        trust_tier_at_issuance=attestation.trust_tier_at_issuance,
        issuer_key_id=attestation.issuer_key_id,
        issuer_signature=attestation.issuer_signature,
        signature_algorithm=attestation.signature_algorithm,
        issued_at=attestation.issued_at.isoformat(),
        expires_at=attestation.expires_at.isoformat(),
        status=attestation.status,
        verification_url=attestation.verification_url,
    )


@router.get("/{attestation_id}", response_model=AttestationResponse)
async def get_attestation(attestation_id: str):
    """
    Get an attestation by ID.
    """
    attestation = await attestation_service.get_attestation(attestation_id)
    
    if not attestation:
        raise HTTPException(status_code=404, detail="Attestation not found")
    
    return AttestationResponse(
        attestation_id=attestation.attestation_id,
        asset_id=str(attestation.asset_id),
        org_id=str(attestation.org_id),
        attestation_type=attestation.attestation_type.value,
        attestation_meaning=attestation.attestation_meaning,
        time_window_start=attestation.time_window_start.isoformat(),
        time_window_end=attestation.time_window_end.isoformat(),
        declared_parameters=attestation.declared_parameters,
        confidence_score=str(attestation.confidence_score),
        evidence_count=attestation.evidence_count,
        evidence_digest=attestation.evidence_digest,
        trust_tier_at_issuance=attestation.trust_tier_at_issuance,
        issuer_key_id=attestation.issuer_key_id,
        issuer_signature=attestation.issuer_signature,
        signature_algorithm=attestation.signature_algorithm,
        issued_at=attestation.issued_at.isoformat(),
        expires_at=attestation.expires_at.isoformat(),
        status=attestation.status,
        verification_url=attestation.verification_url,
    )


@router.get("/{attestation_id}/verify", response_model=VerificationResponse)
async def verify_attestation(attestation_id: str):
    """
    Verify an attestation cryptographically.
    
    This endpoint can be accessed WITHOUT Proveniq authentication.
    Third parties can independently verify attestation validity.
    
    Verification checks:
    1. Attestation exists
    2. Attestation has not expired
    3. Cryptographic signature is valid
    """
    valid, data, error = await attestation_service.verify_attestation(attestation_id)
    
    if not valid:
        return VerificationResponse(
            valid=False,
            attestation_id=attestation_id,
            error=error,
        )
    
    return VerificationResponse(
        valid=True,
        attestation_id=attestation_id,
        asset_id=data.get("asset_id"),
        attestation_type=data.get("attestation_type"),
        time_window=data.get("time_window"),
        confidence_score=data.get("confidence_score"),
        evidence_count=data.get("evidence_count"),
        status=data.get("status"),
        issued_at=data.get("issued_at"),
        expires_at=data.get("expires_at"),
        signature_valid=data.get("signature_valid"),
        error=None,
    )


@router.get("/", response_model=List[AttestationResponse])
async def list_attestations(
    asset_id: Optional[UUID] = None,
    org_id: Optional[UUID] = None,
    attestation_type: Optional[str] = None,
    status: Optional[str] = Query(default=None, regex="^(valid|expired|superseded)$"),
    limit: int = Query(default=50, le=200),
):
    """
    List attestations with optional filters.
    """
    attest_type = None
    if attestation_type:
        try:
            attest_type = AttestationType(attestation_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid attestation type. Must be one of: {[t.value for t in AttestationType]}"
            )
    
    attestations = await attestation_service.list_attestations(
        asset_id=asset_id,
        org_id=org_id,
        attestation_type=attest_type,
        status=status,
        limit=limit,
    )
    
    return [
        AttestationResponse(
            attestation_id=a.attestation_id,
            asset_id=str(a.asset_id),
            org_id=str(a.org_id),
            attestation_type=a.attestation_type.value,
            attestation_meaning=a.attestation_meaning,
            time_window_start=a.time_window_start.isoformat(),
            time_window_end=a.time_window_end.isoformat(),
            declared_parameters=a.declared_parameters,
            confidence_score=str(a.confidence_score),
            evidence_count=a.evidence_count,
            evidence_digest=a.evidence_digest,
            trust_tier_at_issuance=a.trust_tier_at_issuance,
            issuer_key_id=a.issuer_key_id,
            issuer_signature=a.issuer_signature,
            signature_algorithm=a.signature_algorithm,
            issued_at=a.issued_at.isoformat(),
            expires_at=a.expires_at.isoformat(),
            status=a.status,
            verification_url=a.verification_url,
        )
        for a in attestations
    ]


@router.get("/types/definitions")
async def get_attestation_types():
    """
    Get the definitions for each attestation type.
    
    Only these three types are permitted:
    - OPERATION_WITHIN_SPEC
    - CONDITION_AT_TIME
    - CONTINUITY_CONFIRMED
    
    No custom attestation types are allowed.
    """
    return {
        "types": [
            {
                "type": t.value,
                "meaning": ATTESTATION_MEANINGS[t],
                "description": _get_type_description(t),
            }
            for t in AttestationType
        ],
        "governance": {
            "eligibility": [
                "Trust Tier must be PLATINUM",
                "No unresolved integrity flags",
                "No active SECURITY_WAIVER",
                "No pending ledger reconciliation",
                "Continuous telemetry coverage for time window",
                "Minimum 90 days in system",
            ],
            "expiration": "All attestations expire. No perpetual attestations.",
            "verification": "Attestations are cryptographically signed and verifiable offline.",
        },
        "disclaimers": [
            "Attestations reflect observed operation during the specified time window.",
            "Attestations do not predict future performance.",
            "Attestations do not constitute insurance, approval, or guarantee.",
            "Proveniq Ops does not adjudicate disputes based on attestations.",
        ],
    }


def _get_type_description(attestation_type: AttestationType) -> str:
    """Get detailed description for attestation type."""
    descriptions = {
        AttestationType.OPERATION_WITHIN_SPEC: (
            "Asserts that the asset operated within the declared parameters "
            "during the specified time window. Parameters may include temperature "
            "ranges, operational hours, or other measurable conditions."
        ),
        AttestationType.CONDITION_AT_TIME: (
            "Asserts the observed condition of the asset at a specific point "
            "in time. This is a snapshot observation, not a continuous assessment."
        ),
        AttestationType.CONTINUITY_CONFIRMED: (
            "Asserts that no gaps were detected in the declared telemetry or "
            "evidence during the time window. This confirms operational continuity "
            "without asserting specific conditions."
        ),
    }
    return descriptions[attestation_type]


@router.get("/export/{attestation_id}")
async def export_attestation(attestation_id: str):
    """
    Export attestation as signed JSON for sharing.
    
    This export can be:
    - Shared via URL or file
    - Verified by third parties independently
    - Stored for records
    
    Proveniq does NOT track who verifies exported attestations.
    """
    attestation = await attestation_service.get_attestation(attestation_id)
    
    if not attestation:
        raise HTTPException(status_code=404, detail="Attestation not found")
    
    return {
        "format": "proveniq-ops-attestation-v1",
        "attestation": {
            "id": attestation.attestation_id,
            "asset_id": str(attestation.asset_id),
            "type": attestation.attestation_type.value,
            "meaning": attestation.attestation_meaning,
            "time_window": {
                "start": attestation.time_window_start.isoformat(),
                "end": attestation.time_window_end.isoformat(),
            },
            "declared_parameters": attestation.declared_parameters,
            "confidence_score": str(attestation.confidence_score),
            "evidence": {
                "count": attestation.evidence_count,
                "digest": attestation.evidence_digest,
            },
            "trust_tier_at_issuance": attestation.trust_tier_at_issuance,
        },
        "signature": {
            "algorithm": attestation.signature_algorithm,
            "key_id": attestation.issuer_key_id,
            "value": attestation.issuer_signature,
        },
        "lifecycle": {
            "issued_at": attestation.issued_at.isoformat(),
            "expires_at": attestation.expires_at.isoformat(),
            "status": attestation.status,
        },
        "verification": {
            "url": f"https://ops.proveniq.com/api/attestations/{attestation_id}/verify",
            "instructions": "Submit this attestation_id to the verification endpoint to confirm validity.",
        },
        "disclaimers": [
            "This attestation reflects observed operation during the specified time window.",
            "It does not predict future performance.",
            "It does not constitute insurance, approval, or guarantee.",
        ],
    }
