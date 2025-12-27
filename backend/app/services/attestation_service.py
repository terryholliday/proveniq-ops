"""
PROVENIQ Ops - Attestation Service
Phase 2-3: Attestation-as-Infrastructure

GOVERNANCE (BINDING):
- Attestations state what can be PROVEN, not what is PROMISED
- Attestations are descriptive, NEVER prescriptive
- Only PLATINUM tier assets are eligible
- Time-bound (always expire, never perpetual)
- Cryptographically signed (verifiable offline)
- 3 types only: OPERATION_WITHIN_SPEC, CONDITION_AT_TIME, CONTINUITY_CONFIRMED

PROHIBITED LANGUAGE:
- "certified", "approved", "covered", "safe"
USE: "observed", "recorded", "attested"

IDENTITY:
Ops is an Independent Attestation Authority.
Ops does NOT insure, guarantee, or adjudicate.
"""

import os
import uuid
import json
import hashlib
import base64
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
import logging

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet

from app.db.session import async_session_maker
from app.services.trust_tier_engine import trust_tier_engine, TrustTier
from app.services.events.store import event_store

logger = logging.getLogger(__name__)


class AttestationType(str, Enum):
    """
    Authorized attestation types (NO CUSTOM TYPES).
    """
    OPERATION_WITHIN_SPEC = "OPERATION_WITHIN_SPEC"
    CONDITION_AT_TIME = "CONDITION_AT_TIME"
    CONTINUITY_CONFIRMED = "CONTINUITY_CONFIRMED"


ATTESTATION_MEANINGS = {
    AttestationType.OPERATION_WITHIN_SPEC: "Operated within declared parameters during the time window",
    AttestationType.CONDITION_AT_TIME: "Condition observed at a specific point in time",
    AttestationType.CONTINUITY_CONFIRMED: "No detected gaps in declared telemetry/evidence",
}


class EligibilityCheck(BaseModel):
    """Result of a single eligibility check."""
    check_name: str
    passed: bool
    reason: str
    value: Optional[Any] = None


class EligibilityResult(BaseModel):
    """Complete eligibility assessment."""
    asset_id: uuid.UUID
    eligible: bool
    checks: List[EligibilityCheck]
    failed_checks: List[str]
    trust_tier: Optional[int] = None
    message: str


class AttestationRequest(BaseModel):
    """Request to create an attestation."""
    asset_id: uuid.UUID
    org_id: uuid.UUID
    attestation_type: AttestationType
    time_window_start: datetime
    time_window_end: datetime
    declared_parameters: Dict[str, Any] = {}
    requested_by: uuid.UUID


class Attestation(BaseModel):
    """Issued attestation."""
    attestation_id: str
    asset_id: uuid.UUID
    org_id: uuid.UUID
    attestation_type: AttestationType
    attestation_meaning: str
    
    # Time window
    time_window_start: datetime
    time_window_end: datetime
    
    # Content
    declared_parameters: Dict[str, Any]
    confidence_score: Decimal
    evidence_count: int
    evidence_digest: str
    
    # Trust context
    trust_tier_at_issuance: int
    
    # Signature
    issuer_key_id: str
    issuer_signature: str
    signature_algorithm: str
    
    # Lifecycle
    issued_at: datetime
    expires_at: datetime
    status: str = "valid"
    
    # Verification
    verification_url: Optional[str] = None


class AttestationService:
    """
    Service for issuing and verifying Ops Attestations.
    
    MOAT PRINCIPLE:
    - Attestations are earned through operational discipline
    - Only PLATINUM tier assets can receive attestations
    - Third parties can verify without Proveniq access
    - Competitors cannot issue valid Proveniq attestations
    """
    
    def __init__(self):
        self._active_key: Optional[Dict] = None
        self._encryption_key = os.getenv("ATTESTATION_ENCRYPTION_KEY", Fernet.generate_key())
        if isinstance(self._encryption_key, str):
            self._encryption_key = self._encryption_key.encode()
    
    async def check_eligibility(
        self,
        asset_id: uuid.UUID,
        org_id: uuid.UUID,
        attestation_type: AttestationType,
        time_window_start: datetime,
        time_window_end: datetime,
    ) -> EligibilityResult:
        """
        Check if an asset is eligible for attestation.
        
        ALL conditions must be met:
        1. Trust Tier = PLATINUM
        2. No unresolved integrity flags
        3. No active SECURITY_WAIVER
        4. No pending ledger reconciliation
        5. Continuous telemetry coverage
        6. Minimum time-in-system threshold
        """
        checks: List[EligibilityCheck] = []
        
        # Check 1: Trust Tier must be PLATINUM
        tier_result = await trust_tier_engine.get_tier(asset_id)
        if tier_result:
            tier_check = EligibilityCheck(
                check_name="trust_tier_platinum",
                passed=tier_result.tier == TrustTier.PLATINUM,
                reason=f"Trust tier is {tier_result.tier_name}" if tier_result.tier != TrustTier.PLATINUM else "Trust tier is PLATINUM",
                value=tier_result.tier.value,
            )
        else:
            tier_check = EligibilityCheck(
                check_name="trust_tier_platinum",
                passed=False,
                reason="No trust tier calculated for this asset",
                value=None,
            )
        checks.append(tier_check)
        
        # Check 2: No unresolved integrity flags
        integrity_check = await self._check_integrity_flags(asset_id, org_id)
        checks.append(integrity_check)
        
        # Check 3: No active SECURITY_WAIVER
        waiver_check = await self._check_security_waivers(asset_id)
        checks.append(waiver_check)
        
        # Check 4: No pending ledger reconciliation
        ledger_check = await self._check_ledger_status(asset_id)
        checks.append(ledger_check)
        
        # Check 5: Continuous telemetry coverage for time window
        telemetry_check = await self._check_telemetry_coverage(
            asset_id, time_window_start, time_window_end
        )
        checks.append(telemetry_check)
        
        # Check 6: Minimum time-in-system
        time_check = await self._check_time_in_system(asset_id)
        checks.append(time_check)
        
        # Aggregate results
        failed_checks = [c.check_name for c in checks if not c.passed]
        eligible = len(failed_checks) == 0
        
        if eligible:
            message = "Asset is eligible for attestation"
        else:
            message = f"Asset is not eligible: {', '.join(failed_checks)}"
        
        return EligibilityResult(
            asset_id=asset_id,
            eligible=eligible,
            checks=checks,
            failed_checks=failed_checks,
            trust_tier=tier_result.tier.value if tier_result else None,
            message=message,
        )
    
    async def _check_integrity_flags(
        self,
        asset_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> EligibilityCheck:
        """Check for unresolved integrity flags."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("""
                    SELECT COUNT(*) as unresolved
                    FROM anomaly_contexts
                    WHERE (product_id = :asset_id OR org_id = :org_id)
                    AND status NOT IN ('resolved', 'false_positive')
                    AND anomaly_severity IN ('high', 'critical')
                """),
                {"asset_id": asset_id, "org_id": org_id}
            )
            row = result.fetchone()
            
            unresolved = row.unresolved if row else 0
            
            return EligibilityCheck(
                check_name="no_integrity_flags",
                passed=unresolved == 0,
                reason="No unresolved integrity flags" if unresolved == 0 else f"{unresolved} unresolved integrity flags",
                value=unresolved,
            )
    
    async def _check_security_waivers(self, asset_id: uuid.UUID) -> EligibilityCheck:
        """Check for active security waivers."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("""
                    SELECT COUNT(*) as active_waivers
                    FROM security_waivers
                    WHERE asset_id = :asset_id
                    AND status = 'active'
                    AND (expires_at IS NULL OR expires_at > NOW())
                """),
                {"asset_id": asset_id}
            )
            row = result.fetchone()
            
            active = row.active_waivers if row else 0
            
            return EligibilityCheck(
                check_name="no_security_waiver",
                passed=active == 0,
                reason="No active security waivers" if active == 0 else f"{active} active security waivers",
                value=active,
            )
    
    async def _check_ledger_status(self, asset_id: uuid.UUID) -> EligibilityCheck:
        """Check for pending ledger reconciliation."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("""
                    SELECT COUNT(*) as pending
                    FROM ops_events
                    WHERE payload->>'asset_id' = :asset_id
                    AND ledger_synced = false
                    AND timestamp > NOW() - INTERVAL '24 hours'
                """),
                {"asset_id": str(asset_id)}
            )
            row = result.fetchone()
            
            pending = row.pending if row else 0
            
            return EligibilityCheck(
                check_name="no_pending_ledger",
                passed=pending == 0,
                reason="No pending ledger sync" if pending == 0 else f"{pending} events pending ledger sync",
                value=pending,
            )
    
    async def _check_telemetry_coverage(
        self,
        asset_id: uuid.UUID,
        time_start: datetime,
        time_end: datetime,
    ) -> EligibilityCheck:
        """Check for continuous telemetry coverage in time window."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Check for gaps > 24 hours in the time window
            result = await session.execute(
                text("""
                    WITH event_gaps AS (
                        SELECT 
                            timestamp,
                            LAG(timestamp) OVER (ORDER BY timestamp) as prev_timestamp,
                            EXTRACT(EPOCH FROM (timestamp - LAG(timestamp) OVER (ORDER BY timestamp))) / 3600 as gap_hours
                        FROM ops_events
                        WHERE payload->>'asset_id' = :asset_id
                        AND timestamp BETWEEN :start AND :end
                    )
                    SELECT 
                        COUNT(*) FILTER (WHERE gap_hours > 24) as critical_gaps,
                        MAX(gap_hours) as max_gap_hours
                    FROM event_gaps
                    WHERE prev_timestamp IS NOT NULL
                """),
                {"asset_id": str(asset_id), "start": time_start, "end": time_end}
            )
            row = result.fetchone()
            
            critical_gaps = row.critical_gaps if row and row.critical_gaps else 0
            max_gap = row.max_gap_hours if row and row.max_gap_hours else 0
            
            return EligibilityCheck(
                check_name="telemetry_continuity",
                passed=critical_gaps == 0,
                reason="Continuous telemetry coverage" if critical_gaps == 0 else f"{critical_gaps} gaps > 24 hours detected",
                value={"critical_gaps": critical_gaps, "max_gap_hours": float(max_gap) if max_gap else 0},
            )
    
    async def _check_time_in_system(self, asset_id: uuid.UUID) -> EligibilityCheck:
        """Check minimum time-in-system (90 days for PLATINUM attestation)."""
        tier_result = await trust_tier_engine.get_tier(asset_id)
        
        if not tier_result:
            return EligibilityCheck(
                check_name="time_in_system",
                passed=False,
                reason="No tier data available",
                value=0,
            )
        
        min_days = 90  # PLATINUM requirement
        
        return EligibilityCheck(
            check_name="time_in_system",
            passed=tier_result.days_in_system >= min_days,
            reason=f"{tier_result.days_in_system} days in system" if tier_result.days_in_system >= min_days else f"Only {tier_result.days_in_system} days (need {min_days})",
            value=tier_result.days_in_system,
        )
    
    async def issue_attestation(
        self,
        request: AttestationRequest,
    ) -> Tuple[bool, Optional[Attestation], Optional[str]]:
        """
        Issue an attestation for an eligible asset.
        
        Returns (success, attestation, error_message)
        """
        # Check eligibility first
        eligibility = await self.check_eligibility(
            request.asset_id,
            request.org_id,
            request.attestation_type,
            request.time_window_start,
            request.time_window_end,
        )
        
        if not eligibility.eligible:
            # Log the failed request
            await self._log_request(request, eligibility, None)
            return False, None, eligibility.message
        
        # Gather evidence for the time window
        evidence_ids, evidence_digest = await self._gather_evidence(
            request.asset_id,
            request.time_window_start,
            request.time_window_end,
        )
        
        if len(evidence_ids) == 0:
            return False, None, "No evidence found for the specified time window"
        
        # Calculate confidence score
        confidence = await self._calculate_confidence(
            request.asset_id,
            request.attestation_type,
            evidence_ids,
        )
        
        # Get signing key
        key = await self._get_active_signing_key()
        
        # Generate attestation ID (UUIDv7-style for time-sortability)
        attestation_id = self._generate_attestation_id()
        
        # Calculate expiration (based on attestation type and evidence volatility)
        expires_at = self._calculate_expiration(request.attestation_type, request.time_window_end)
        
        # Build attestation payload
        payload = {
            "attestation_id": attestation_id,
            "asset_id": str(request.asset_id),
            "attestation_type": request.attestation_type.value,
            "time_window_start": request.time_window_start.isoformat(),
            "time_window_end": request.time_window_end.isoformat(),
            "declared_parameters": request.declared_parameters,
            "confidence_score": str(confidence),
            "evidence_count": len(evidence_ids),
            "evidence_digest": evidence_digest,
            "trust_tier_at_issuance": 4,  # PLATINUM
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        
        # Sign the attestation
        signature = self._sign_payload(payload, key)
        
        # Build attestation object
        attestation = Attestation(
            attestation_id=attestation_id,
            asset_id=request.asset_id,
            org_id=request.org_id,
            attestation_type=request.attestation_type,
            attestation_meaning=ATTESTATION_MEANINGS[request.attestation_type],
            time_window_start=request.time_window_start,
            time_window_end=request.time_window_end,
            declared_parameters=request.declared_parameters,
            confidence_score=confidence,
            evidence_count=len(evidence_ids),
            evidence_digest=evidence_digest,
            trust_tier_at_issuance=4,
            issuer_key_id=key["key_id"],
            issuer_signature=signature,
            signature_algorithm="Ed25519",
            issued_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            status="valid",
            verification_url=f"/api/attestations/{attestation_id}/verify",
        )
        
        # Persist attestation
        await self._save_attestation(attestation, evidence_ids)
        
        # Log successful request
        await self._log_request(request, eligibility, attestation.attestation_id)
        
        logger.info(f"Attestation issued: {attestation_id} for asset {request.asset_id}")
        
        return True, attestation, None
    
    async def _gather_evidence(
        self,
        asset_id: uuid.UUID,
        time_start: datetime,
        time_end: datetime,
    ) -> Tuple[List[uuid.UUID], str]:
        """Gather evidence events and compute digest."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("""
                    SELECT id, payload_hash
                    FROM ops_events
                    WHERE payload->>'asset_id' = :asset_id
                    AND timestamp BETWEEN :start AND :end
                    ORDER BY timestamp ASC
                """),
                {"asset_id": str(asset_id), "start": time_start, "end": time_end}
            )
            
            event_ids = []
            hashes = []
            
            for row in result.fetchall():
                event_ids.append(row.id)
                if row.payload_hash:
                    hashes.append(row.payload_hash)
            
            # Compute evidence digest (SHA-512 of concatenated hashes)
            if hashes:
                combined = "".join(sorted(hashes))
                evidence_digest = hashlib.sha512(combined.encode()).hexdigest()
            else:
                evidence_digest = hashlib.sha512(b"no_hashes").hexdigest()
            
            return event_ids, evidence_digest
    
    async def _calculate_confidence(
        self,
        asset_id: uuid.UUID,
        attestation_type: AttestationType,
        evidence_ids: List[uuid.UUID],
    ) -> Decimal:
        """Calculate confidence score for attestation."""
        base_confidence = Decimal("0.7")
        
        # Boost for evidence count
        evidence_boost = min(Decimal(str(len(evidence_ids) / 100)), Decimal("0.15"))
        
        # Get tier data for additional factors
        tier_result = await trust_tier_engine.get_tier(asset_id)
        if tier_result:
            # Boost from composite score
            tier_boost = tier_result.scores.composite * Decimal("0.1")
        else:
            tier_boost = Decimal("0")
        
        confidence = base_confidence + evidence_boost + tier_boost
        
        return min(confidence, Decimal("0.99"))
    
    async def _get_active_signing_key(self) -> Dict:
        """Get the active signing key, creating one if needed."""
        if self._active_key:
            return self._active_key
        
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("""
                    SELECT key_id, public_key_pem, private_key_encrypted, key_algorithm
                    FROM attestation_keys
                    WHERE status = 'active'
                    ORDER BY version DESC
                    LIMIT 1
                """)
            )
            row = result.fetchone()
            
            if row:
                # Decrypt private key
                fernet = Fernet(self._encryption_key)
                private_key_pem = fernet.decrypt(row.private_key_encrypted)
                
                self._active_key = {
                    "key_id": row.key_id,
                    "public_key_pem": row.public_key_pem,
                    "private_key": ed25519.Ed25519PrivateKey.from_private_bytes(
                        serialization.load_pem_private_key(
                            private_key_pem,
                            password=None,
                            backend=default_backend()
                        ).private_bytes_raw()
                    ),
                    "algorithm": row.key_algorithm,
                }
            else:
                # Generate new key
                self._active_key = await self._create_signing_key()
        
        return self._active_key
    
    async def _create_signing_key(self) -> Dict:
        """Create a new Ed25519 signing key."""
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Serialize keys
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        
        # Encrypt private key
        fernet = Fernet(self._encryption_key)
        encrypted_private = fernet.encrypt(private_pem)
        
        key_id = f"ops-attest-{uuid.uuid4().hex[:16]}"
        
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            await session.execute(
                text("""
                    INSERT INTO attestation_keys (
                        id, key_id, version,
                        public_key_pem, private_key_encrypted, key_algorithm,
                        status, created_at, activated_at, created_by
                    ) VALUES (
                        gen_random_uuid(), :key_id, 1,
                        :public_pem, :private_encrypted, 'Ed25519',
                        'active', NOW(), NOW(), 'SYSTEM'
                    )
                """),
                {
                    "key_id": key_id,
                    "public_pem": public_pem,
                    "private_encrypted": encrypted_private,
                }
            )
            await session.commit()
        
        return {
            "key_id": key_id,
            "public_key_pem": public_pem,
            "private_key": private_key,
            "algorithm": "Ed25519",
        }
    
    def _sign_payload(self, payload: Dict, key: Dict) -> str:
        """Sign attestation payload with Ed25519."""
        canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = key["private_key"].sign(canonical.encode())
        return base64.b64encode(signature).decode()
    
    def _generate_attestation_id(self) -> str:
        """Generate UUIDv7-style attestation ID."""
        timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        timestamp_hex = format(timestamp_ms, '012x')
        random_hex = uuid.uuid4().hex[12:]
        return f"{timestamp_hex[:8]}-{timestamp_hex[8:12]}-7{random_hex[:3]}-{random_hex[3:7]}-{random_hex[7:19]}"
    
    def _calculate_expiration(
        self,
        attestation_type: AttestationType,
        time_window_end: datetime,
    ) -> datetime:
        """Calculate attestation expiration based on type."""
        now = datetime.now(timezone.utc)
        
        # Expiration scales with evidence volatility
        if attestation_type == AttestationType.CONDITION_AT_TIME:
            # Point-in-time observations expire faster
            expiry = now + timedelta(days=30)
        elif attestation_type == AttestationType.OPERATION_WITHIN_SPEC:
            # Operational attestations last longer
            expiry = now + timedelta(days=90)
        else:  # CONTINUITY_CONFIRMED
            # Continuity attestations based on window size
            window_days = (time_window_end - now).days if time_window_end > now else 0
            expiry = now + timedelta(days=max(60, window_days))
        
        return expiry
    
    async def _save_attestation(
        self,
        attestation: Attestation,
        evidence_ids: List[uuid.UUID],
    ) -> None:
        """Persist attestation to database."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            await session.execute(
                text("""
                    INSERT INTO ops_attestations (
                        id, attestation_id, asset_id, org_id,
                        attestation_type, time_window_start, time_window_end,
                        declared_parameters, confidence_score,
                        evidence_event_ids, evidence_count, evidence_digest,
                        trust_tier_at_issuance,
                        issuer_key_id, issuer_signature, signature_algorithm,
                        issued_at, expires_at, status,
                        verification_url, verification_count,
                        created_at
                    ) VALUES (
                        gen_random_uuid(), :attestation_id, :asset_id, :org_id,
                        :type, :window_start, :window_end,
                        :params, :confidence,
                        :evidence_ids, :evidence_count, :evidence_digest,
                        :tier,
                        :key_id, :signature, :algorithm,
                        :issued, :expires, 'valid',
                        :verify_url, 0,
                        NOW()
                    )
                """),
                {
                    "attestation_id": attestation.attestation_id,
                    "asset_id": attestation.asset_id,
                    "org_id": attestation.org_id,
                    "type": attestation.attestation_type.value,
                    "window_start": attestation.time_window_start,
                    "window_end": attestation.time_window_end,
                    "params": json.dumps(attestation.declared_parameters),
                    "confidence": attestation.confidence_score,
                    "evidence_ids": evidence_ids,
                    "evidence_count": attestation.evidence_count,
                    "evidence_digest": attestation.evidence_digest,
                    "tier": attestation.trust_tier_at_issuance,
                    "key_id": attestation.issuer_key_id,
                    "signature": attestation.issuer_signature,
                    "algorithm": attestation.signature_algorithm,
                    "issued": attestation.issued_at,
                    "expires": attestation.expires_at,
                    "verify_url": attestation.verification_url,
                }
            )
            await session.commit()
    
    async def _log_request(
        self,
        request: AttestationRequest,
        eligibility: EligibilityResult,
        attestation_id: Optional[str],
    ) -> None:
        """Log attestation request."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            status = "approved" if attestation_id else "rejected"
            
            await session.execute(
                text("""
                    INSERT INTO attestation_requests (
                        id, asset_id, org_id, requested_by,
                        attestation_type, time_window_start, time_window_end,
                        eligibility_status, eligibility_checks, failed_checks,
                        status, attestation_id, failure_reason,
                        requested_at, processed_at
                    ) VALUES (
                        gen_random_uuid(), :asset_id, :org_id, :requested_by,
                        :type, :window_start, :window_end,
                        :elig_status, :elig_checks, :failed,
                        :status, :attest_id, :failure,
                        NOW(), NOW()
                    )
                """),
                {
                    "asset_id": request.asset_id,
                    "org_id": request.org_id,
                    "requested_by": request.requested_by,
                    "type": request.attestation_type.value,
                    "window_start": request.time_window_start,
                    "window_end": request.time_window_end,
                    "elig_status": "eligible" if eligibility.eligible else "ineligible",
                    "elig_checks": json.dumps([c.model_dump() for c in eligibility.checks]),
                    "failed": eligibility.failed_checks if eligibility.failed_checks else None,
                    "status": status,
                    "attest_id": uuid.UUID(attestation_id.replace("-", "")[:32].ljust(32, "0")) if attestation_id else None,
                    "failure": eligibility.message if not attestation_id else None,
                }
            )
            await session.commit()
    
    async def verify_attestation(
        self,
        attestation_id: str,
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Verify an attestation cryptographically.
        
        This can be done WITHOUT Proveniq authentication.
        Returns (valid, attestation_data, error_message)
        """
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Get attestation
            result = await session.execute(
                text("""
                    SELECT a.*, k.public_key_pem
                    FROM ops_attestations a
                    JOIN attestation_keys k ON a.issuer_key_id = k.key_id
                    WHERE a.attestation_id = :id
                """),
                {"id": attestation_id}
            )
            row = result.fetchone()
            
            if not row:
                return False, None, "Attestation not found"
            
            # Check expiration
            if row.expires_at < datetime.now(timezone.utc):
                return False, None, "Attestation has expired"
            
            # Reconstruct payload
            payload = {
                "attestation_id": row.attestation_id,
                "asset_id": str(row.asset_id),
                "attestation_type": row.attestation_type,
                "time_window_start": row.time_window_start.isoformat(),
                "time_window_end": row.time_window_end.isoformat(),
                "declared_parameters": row.declared_parameters,
                "confidence_score": str(row.confidence_score),
                "evidence_count": row.evidence_count,
                "evidence_digest": row.evidence_digest,
                "trust_tier_at_issuance": row.trust_tier_at_issuance,
                "issued_at": row.issued_at.isoformat(),
                "expires_at": row.expires_at.isoformat(),
            }
            
            # Verify signature
            try:
                public_key = serialization.load_pem_public_key(
                    row.public_key_pem.encode(),
                    backend=default_backend()
                )
                canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
                signature = base64.b64decode(row.issuer_signature)
                public_key.verify(signature, canonical.encode())
                
                # Update verification count
                await session.execute(
                    text("""
                        UPDATE ops_attestations
                        SET verification_count = verification_count + 1,
                            last_verified_at = NOW()
                        WHERE attestation_id = :id
                    """),
                    {"id": attestation_id}
                )
                await session.commit()
                
                return True, {
                    "attestation_id": attestation_id,
                    "asset_id": str(row.asset_id),
                    "attestation_type": row.attestation_type,
                    "time_window": {
                        "start": row.time_window_start.isoformat(),
                        "end": row.time_window_end.isoformat(),
                    },
                    "confidence_score": str(row.confidence_score),
                    "evidence_count": row.evidence_count,
                    "status": "valid",
                    "issued_at": row.issued_at.isoformat(),
                    "expires_at": row.expires_at.isoformat(),
                    "signature_valid": True,
                }, None
                
            except Exception as e:
                logger.error(f"Signature verification failed: {e}")
                return False, None, "Signature verification failed"
    
    async def get_attestation(self, attestation_id: str) -> Optional[Attestation]:
        """Get attestation by ID."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("SELECT * FROM ops_attestations WHERE attestation_id = :id"),
                {"id": attestation_id}
            )
            row = result.fetchone()
            
            if not row:
                return None
            
            return Attestation(
                attestation_id=row.attestation_id,
                asset_id=row.asset_id,
                org_id=row.org_id,
                attestation_type=AttestationType(row.attestation_type),
                attestation_meaning=ATTESTATION_MEANINGS[AttestationType(row.attestation_type)],
                time_window_start=row.time_window_start,
                time_window_end=row.time_window_end,
                declared_parameters=row.declared_parameters,
                confidence_score=row.confidence_score,
                evidence_count=row.evidence_count,
                evidence_digest=row.evidence_digest,
                trust_tier_at_issuance=row.trust_tier_at_issuance,
                issuer_key_id=row.issuer_key_id,
                issuer_signature=row.issuer_signature,
                signature_algorithm=row.signature_algorithm,
                issued_at=row.issued_at,
                expires_at=row.expires_at,
                status=row.status,
                verification_url=row.verification_url,
            )
    
    async def list_attestations(
        self,
        asset_id: Optional[uuid.UUID] = None,
        org_id: Optional[uuid.UUID] = None,
        attestation_type: Optional[AttestationType] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Attestation]:
        """List attestations with filters."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            query = "SELECT * FROM ops_attestations WHERE 1=1"
            params = {"limit": limit}
            
            if asset_id:
                query += " AND asset_id = :asset_id"
                params["asset_id"] = asset_id
            if org_id:
                query += " AND org_id = :org_id"
                params["org_id"] = org_id
            if attestation_type:
                query += " AND attestation_type = :type"
                params["type"] = attestation_type.value
            if status:
                query += " AND status = :status"
                params["status"] = status
            
            query += " ORDER BY issued_at DESC LIMIT :limit"
            
            result = await session.execute(text(query), params)
            
            attestations = []
            for row in result.fetchall():
                attestations.append(Attestation(
                    attestation_id=row.attestation_id,
                    asset_id=row.asset_id,
                    org_id=row.org_id,
                    attestation_type=AttestationType(row.attestation_type),
                    attestation_meaning=ATTESTATION_MEANINGS[AttestationType(row.attestation_type)],
                    time_window_start=row.time_window_start,
                    time_window_end=row.time_window_end,
                    declared_parameters=row.declared_parameters,
                    confidence_score=row.confidence_score,
                    evidence_count=row.evidence_count,
                    evidence_digest=row.evidence_digest,
                    trust_tier_at_issuance=row.trust_tier_at_issuance,
                    issuer_key_id=row.issuer_key_id,
                    issuer_signature=row.issuer_signature,
                    signature_algorithm=row.signature_algorithm,
                    issued_at=row.issued_at,
                    expires_at=row.expires_at,
                    status=row.status,
                    verification_url=row.verification_url,
                ))
            
            return attestations


# Singleton instance
attestation_service = AttestationService()
