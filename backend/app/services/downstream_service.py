"""
PROVENIQ Ops - Downstream Integration Service
Phase 4-5: Regulatory & Capital Dependence

GOAL:
- Capital systems require Ops truth
- Claims systems defer to Ops timelines
- Loss prevention provable through Ops
- Operating without Ops = riskier, more expensive, harder to insure/finance/exit

This service:
- Manages integrations with ClaimsIQ, Capital, Bids
- Provides evidence packs for downstream systems
- Generates compliance reports and audit exports
- Tracks all downstream requests for audit trail
"""

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

from app.db.session import async_session_maker
from app.services.trust_tier_engine import trust_tier_engine, TrustTier
from app.services.attestation_service import attestation_service
from app.services.events.store import event_store

logger = logging.getLogger(__name__)


class SystemType(str, Enum):
    """Types of downstream systems."""
    CLAIMSIQ = "claimsiq"
    CAPITAL = "capital"
    BIDS = "bids"
    INSURER = "insurer"
    LENDER = "lender"
    REGULATOR = "regulator"
    AUDITOR = "auditor"


class RequestType(str, Enum):
    """Types of downstream requests."""
    TIMELINE = "timeline"
    ATTESTATION = "attestation"
    TRUST_TIER = "trust_tier"
    EVIDENCE_PACK = "evidence_pack"
    COMPLIANCE_REPORT = "compliance_report"
    AUDIT_EXPORT = "audit_export"


class ReportType(str, Enum):
    """Types of compliance reports."""
    OPERATIONAL_SUMMARY = "operational_summary"
    COMPLIANCE_AUDIT = "compliance_audit"
    INSURANCE_EVIDENCE = "insurance_evidence"
    REGULATORY_FILING = "regulatory_filing"
    LOSS_PREVENTION = "loss_prevention"
    INCIDENT_TIMELINE = "incident_timeline"


class DownstreamIntegration(BaseModel):
    """Registered downstream system."""
    integration_id: str
    system_name: str
    system_type: SystemType
    api_endpoint: Optional[str] = None
    webhook_url: Optional[str] = None
    shared_event_types: List[str] = []
    trust_tier_threshold: Optional[int] = None
    attestation_required: bool = False
    status: str = "active"


class EvidencePack(BaseModel):
    """Evidence package for downstream systems."""
    pack_id: str
    asset_id: uuid.UUID
    org_id: uuid.UUID
    requested_by: str
    
    # Trust context
    trust_tier: int
    trust_tier_name: str
    
    # Time range
    time_range_start: datetime
    time_range_end: datetime
    
    # Evidence
    events: List[Dict[str, Any]]
    event_count: int
    event_types: List[str]
    
    # Anomalies
    anomalies: List[Dict[str, Any]]
    anomaly_count: int
    
    # Attestations (if any)
    attestations: List[Dict[str, Any]]
    
    # Industry mappings
    insurance_relevant_events: int
    compliance_relevant_events: int
    
    # Integrity
    evidence_digest: str
    generated_at: datetime


class ComplianceReport(BaseModel):
    """Generated compliance/audit report."""
    report_id: str
    report_type: ReportType
    org_id: uuid.UUID
    
    # Scope
    asset_ids: List[uuid.UUID]
    time_range_start: datetime
    time_range_end: datetime
    
    # Content
    summary: str
    report_data: Dict[str, Any]
    
    # Metrics
    total_events: int
    anomalies_detected: int
    attestations_issued: int
    average_trust_tier: Optional[Decimal] = None
    
    # Integrity
    report_hash: str
    signature: Optional[str] = None
    
    generated_at: datetime


class DownstreamService:
    """
    Service for downstream system integration.
    
    MOAT PRINCIPLE:
    - ClaimsIQ, Capital, Bids depend on Ops truth
    - External insurers/lenders request Ops evidence
    - Operating without Ops becomes disadvantageous
    - Creates network effects and switching costs
    """
    
    async def register_integration(
        self,
        system_name: str,
        system_type: SystemType,
        api_endpoint: Optional[str] = None,
        webhook_url: Optional[str] = None,
        shared_event_types: List[str] = None,
        trust_tier_threshold: Optional[int] = None,
        attestation_required: bool = False,
    ) -> DownstreamIntegration:
        """Register a new downstream integration."""
        integration_id = f"{system_type.value}-{uuid.uuid4().hex[:12]}"
        
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            await session.execute(
                text("""
                    INSERT INTO downstream_integrations (
                        id, integration_id, system_name, system_type,
                        api_endpoint, webhook_url, auth_type,
                        shared_event_types, trust_tier_threshold, attestation_required,
                        status, created_at
                    ) VALUES (
                        gen_random_uuid(), :integration_id, :system_name, :system_type,
                        :api_endpoint, :webhook_url, 'api_key',
                        :shared_events, :tier_threshold, :attest_required,
                        'active', NOW()
                    )
                """),
                {
                    "integration_id": integration_id,
                    "system_name": system_name,
                    "system_type": system_type.value,
                    "api_endpoint": api_endpoint,
                    "webhook_url": webhook_url,
                    "shared_events": shared_event_types or [],
                    "tier_threshold": trust_tier_threshold,
                    "attest_required": attestation_required,
                }
            )
            await session.commit()
        
        logger.info(f"Registered downstream integration: {integration_id}")
        
        return DownstreamIntegration(
            integration_id=integration_id,
            system_name=system_name,
            system_type=system_type,
            api_endpoint=api_endpoint,
            webhook_url=webhook_url,
            shared_event_types=shared_event_types or [],
            trust_tier_threshold=trust_tier_threshold,
            attestation_required=attestation_required,
        )
    
    async def get_evidence_pack(
        self,
        asset_id: uuid.UUID,
        org_id: uuid.UUID,
        time_range_start: datetime,
        time_range_end: datetime,
        integration_id: str,
    ) -> EvidencePack:
        """
        Generate an evidence pack for a downstream system.
        
        Used by:
        - ClaimsIQ for claims processing
        - Capital for loan underwriting
        - Insurers for policy evaluation
        """
        # Get trust tier
        tier_result = await trust_tier_engine.get_tier(asset_id)
        trust_tier = tier_result.tier.value if tier_result else 1
        trust_tier_name = tier_result.tier_name if tier_result else "BRONZE"
        
        # Get events
        events = await event_store.get_events_for_asset(
            str(asset_id),
            time_range_start,
            time_range_end,
        )
        
        # Get anomalies
        anomalies = await self._get_anomalies(asset_id, org_id, time_range_start, time_range_end)
        
        # Get attestations
        attestations = await attestation_service.list_attestations(
            asset_id=asset_id,
            status="valid",
            limit=20,
        )
        
        # Count industry-relevant events
        insurance_relevant = 0
        compliance_relevant = 0
        event_types = set()
        
        for event in events:
            event_types.add(event.get("event_type", ""))
            mapping = await self._get_event_mapping(event.get("event_type", ""))
            if mapping:
                if mapping.get("insurance_category"):
                    insurance_relevant += 1
                if mapping.get("compliance_domain"):
                    compliance_relevant += 1
        
        # Compute evidence digest
        evidence_data = json.dumps({
            "asset_id": str(asset_id),
            "events": [e.get("id") for e in events],
            "anomalies": [a.get("id") for a in anomalies],
        }, sort_keys=True)
        evidence_digest = hashlib.sha256(evidence_data.encode()).hexdigest()
        
        pack_id = f"evp-{uuid.uuid4().hex[:12]}"
        
        # Log the request
        await self._log_request(
            integration_id=integration_id,
            request_type=RequestType.EVIDENCE_PACK,
            asset_id=asset_id,
            org_id=org_id,
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            response_status="success",
            events_returned=len(events),
            trust_tier=trust_tier,
        )
        
        return EvidencePack(
            pack_id=pack_id,
            asset_id=asset_id,
            org_id=org_id,
            requested_by=integration_id,
            trust_tier=trust_tier,
            trust_tier_name=trust_tier_name,
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            events=[self._sanitize_event(e) for e in events],
            event_count=len(events),
            event_types=list(event_types),
            anomalies=anomalies,
            anomaly_count=len(anomalies),
            attestations=[self._format_attestation(a) for a in attestations],
            insurance_relevant_events=insurance_relevant,
            compliance_relevant_events=compliance_relevant,
            evidence_digest=evidence_digest,
            generated_at=datetime.now(timezone.utc),
        )
    
    async def get_timeline_for_claims(
        self,
        asset_id: uuid.UUID,
        org_id: uuid.UUID,
        incident_time: datetime,
        integration_id: str = "claimsiq",
    ) -> Dict[str, Any]:
        """
        Get forensic timeline for ClaimsIQ claims processing.
        
        Returns events before and after incident for context.
        """
        # Get 30 days before and 7 days after incident
        time_start = incident_time - timedelta(days=30)
        time_end = incident_time + timedelta(days=7)
        
        pack = await self.get_evidence_pack(
            asset_id, org_id, time_start, time_end, integration_id
        )
        
        # Separate pre and post incident events
        pre_incident = [e for e in pack.events if datetime.fromisoformat(e["timestamp"]) < incident_time]
        post_incident = [e for e in pack.events if datetime.fromisoformat(e["timestamp"]) >= incident_time]
        
        return {
            "asset_id": str(asset_id),
            "incident_time": incident_time.isoformat(),
            "trust_tier": pack.trust_tier,
            "trust_tier_name": pack.trust_tier_name,
            "timeline": {
                "pre_incident": {
                    "events": pre_incident,
                    "count": len(pre_incident),
                    "period": f"{time_start.isoformat()} to {incident_time.isoformat()}",
                },
                "post_incident": {
                    "events": post_incident,
                    "count": len(post_incident),
                    "period": f"{incident_time.isoformat()} to {time_end.isoformat()}",
                },
            },
            "anomalies": pack.anomalies,
            "attestations": pack.attestations,
            "evidence_digest": pack.evidence_digest,
            "claims_relevance": {
                "insurance_relevant_events": pack.insurance_relevant_events,
                "shrinkage_events": len([e for e in pack.events if "shrinkage" in e.get("event_type", "")]),
            },
        }
    
    async def check_capital_eligibility(
        self,
        asset_id: uuid.UUID,
        org_id: uuid.UUID,
        integration_id: str = "capital",
    ) -> Dict[str, Any]:
        """
        Check asset eligibility for Capital lending.
        
        Returns trust tier and operational history summary.
        """
        tier_result = await trust_tier_engine.get_tier(asset_id)
        
        if not tier_result:
            await self._log_request(
                integration_id=integration_id,
                request_type=RequestType.TRUST_TIER,
                asset_id=asset_id,
                org_id=org_id,
                response_status="denied",
            )
            return {
                "eligible": False,
                "reason": "No trust tier calculated for this asset",
                "recommendation": "Calculate trust tier first",
            }
        
        # Get recent anomalies
        anomalies = await self._get_anomalies(
            asset_id, org_id,
            datetime.now(timezone.utc) - timedelta(days=90),
            datetime.now(timezone.utc),
        )
        unresolved = [a for a in anomalies if a.get("status") not in ("resolved", "false_positive")]
        
        # Eligibility rules
        eligible = tier_result.tier.value >= 2  # At least SILVER
        
        await self._log_request(
            integration_id=integration_id,
            request_type=RequestType.TRUST_TIER,
            asset_id=asset_id,
            org_id=org_id,
            response_status="success",
            trust_tier=tier_result.tier.value,
        )
        
        return {
            "asset_id": str(asset_id),
            "eligible": eligible,
            "trust_tier": tier_result.tier.value,
            "trust_tier_name": tier_result.tier_name,
            "days_in_system": tier_result.days_in_system,
            "driver_scores": {
                "evidence_quality": str(tier_result.scores.evidence_quality),
                "telemetry_continuity": str(tier_result.scores.telemetry_continuity),
                "human_discipline": str(tier_result.scores.human_discipline),
                "integrity": str(tier_result.scores.integrity),
            },
            "unresolved_anomalies": len(unresolved),
            "risk_assessment": {
                "level": "low" if tier_result.tier.value >= 3 else "medium" if tier_result.tier.value >= 2 else "high",
                "factors": tier_result.risk_factors,
            },
            "recommendation": "Eligible for standard terms" if eligible else "Additional verification required",
        }
    
    async def check_bids_eligibility(
        self,
        asset_id: uuid.UUID,
        org_id: uuid.UUID,
        integration_id: str = "bids",
    ) -> Dict[str, Any]:
        """
        Check asset eligibility for Bids marketplace listing.
        
        Returns trust tier and provenance summary.
        """
        tier_result = await trust_tier_engine.get_tier(asset_id)
        
        if not tier_result:
            return {
                "eligible": False,
                "listing_tier": None,
                "reason": "No trust tier calculated",
            }
        
        # Get attestations
        attestations = await attestation_service.list_attestations(
            asset_id=asset_id,
            status="valid",
            limit=5,
        )
        
        await self._log_request(
            integration_id=integration_id,
            request_type=RequestType.TRUST_TIER,
            asset_id=asset_id,
            org_id=org_id,
            response_status="success",
            trust_tier=tier_result.tier.value,
        )
        
        # Listing tier based on trust tier
        listing_tiers = {
            1: "basic",
            2: "standard",
            3: "verified",
            4: "premium",
        }
        
        return {
            "asset_id": str(asset_id),
            "eligible": True,  # All assets can list, tier affects presentation
            "listing_tier": listing_tiers.get(tier_result.tier.value, "basic"),
            "trust_tier": tier_result.tier.value,
            "trust_tier_name": tier_result.tier_name,
            "days_in_system": tier_result.days_in_system,
            "has_attestation": len(attestations) > 0,
            "attestation_count": len(attestations),
            "provenance_badge": "attestable" if tier_result.tier == TrustTier.PLATINUM else "verified" if tier_result.tier == TrustTier.GOLD else "tracked",
            "buyer_confidence_indicator": {
                "level": "highest" if tier_result.tier.value >= 4 else "high" if tier_result.tier.value >= 3 else "standard",
                "operational_history_days": tier_result.days_in_system,
                "continuous_monitoring": tier_result.scores.telemetry_continuity > Decimal("0.7"),
            },
        }
    
    async def generate_compliance_report(
        self,
        org_id: uuid.UUID,
        report_type: ReportType,
        time_range_start: datetime,
        time_range_end: datetime,
        asset_ids: Optional[List[uuid.UUID]] = None,
        requested_by: Optional[str] = None,
    ) -> ComplianceReport:
        """
        Generate a compliance/audit report.
        
        Used by:
        - Internal compliance teams
        - External auditors
        - Regulatory filings
        """
        report_id = f"rpt-{uuid.uuid4().hex[:12]}"
        
        # Get events for org (or specific assets)
        events = await self._get_org_events(org_id, time_range_start, time_range_end, asset_ids)
        
        # Get anomalies
        anomalies = await self._get_org_anomalies(org_id, time_range_start, time_range_end, asset_ids)
        
        # Get attestations
        attestations = await self._get_org_attestations(org_id, time_range_start, time_range_end, asset_ids)
        
        # Get trust tier distribution
        tier_dist = await trust_tier_engine.get_tier_distribution(org_id)
        
        # Calculate average trust tier
        total_assets = sum(tier_dist.values())
        if total_assets > 0:
            weighted_sum = (
                tier_dist["BRONZE"] * 1 +
                tier_dist["SILVER"] * 2 +
                tier_dist["GOLD"] * 3 +
                tier_dist["PLATINUM"] * 4
            )
            avg_tier = Decimal(str(weighted_sum / total_assets))
        else:
            avg_tier = None
        
        # Build report data based on type
        report_data = self._build_report_data(
            report_type, events, anomalies, attestations, tier_dist, time_range_start, time_range_end
        )
        
        # Generate summary
        summary = self._generate_report_summary(report_type, events, anomalies, attestations)
        
        # Compute report hash
        report_content = json.dumps(report_data, sort_keys=True, default=str)
        report_hash = hashlib.sha512(report_content.encode()).hexdigest()
        
        # Save report
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            await session.execute(
                text("""
                    INSERT INTO compliance_reports (
                        id, report_id, report_type, org_id,
                        asset_ids, time_range_start, time_range_end,
                        report_data, summary,
                        total_events, anomalies_detected, attestations_issued, average_trust_tier,
                        report_hash, requested_by_integration,
                        generated_at
                    ) VALUES (
                        gen_random_uuid(), :report_id, :report_type, :org_id,
                        :asset_ids, :time_start, :time_end,
                        :report_data, :summary,
                        :total_events, :anomalies, :attestations, :avg_tier,
                        :report_hash, :requested_by,
                        NOW()
                    )
                """),
                {
                    "report_id": report_id,
                    "report_type": report_type.value,
                    "org_id": org_id,
                    "asset_ids": asset_ids,
                    "time_start": time_range_start,
                    "time_end": time_range_end,
                    "report_data": json.dumps(report_data, default=str),
                    "summary": summary,
                    "total_events": len(events),
                    "anomalies": len(anomalies),
                    "attestations": len(attestations),
                    "avg_tier": avg_tier,
                    "report_hash": report_hash,
                    "requested_by": requested_by,
                }
            )
            await session.commit()
        
        if requested_by:
            await self._log_request(
                integration_id=requested_by,
                request_type=RequestType.COMPLIANCE_REPORT,
                org_id=org_id,
                time_range_start=time_range_start,
                time_range_end=time_range_end,
                response_status="success",
                events_returned=len(events),
            )
        
        return ComplianceReport(
            report_id=report_id,
            report_type=report_type,
            org_id=org_id,
            asset_ids=asset_ids or [],
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            summary=summary,
            report_data=report_data,
            total_events=len(events),
            anomalies_detected=len(anomalies),
            attestations_issued=len(attestations),
            average_trust_tier=avg_tier,
            report_hash=report_hash,
            generated_at=datetime.now(timezone.utc),
        )
    
    async def export_audit_trail(
        self,
        org_id: uuid.UUID,
        time_range_start: datetime,
        time_range_end: datetime,
        asset_ids: Optional[List[uuid.UUID]] = None,
        integration_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Export complete audit trail for external auditors.
        
        Includes all events, decisions, anomalies, and attestations.
        """
        events = await self._get_org_events(org_id, time_range_start, time_range_end, asset_ids)
        anomalies = await self._get_org_anomalies(org_id, time_range_start, time_range_end, asset_ids)
        attestations = await self._get_org_attestations(org_id, time_range_start, time_range_end, asset_ids)
        tier_dist = await trust_tier_engine.get_tier_distribution(org_id)
        
        export_id = f"audit-{uuid.uuid4().hex[:12]}"
        
        export_data = {
            "export_id": export_id,
            "org_id": str(org_id),
            "time_range": {
                "start": time_range_start.isoformat(),
                "end": time_range_end.isoformat(),
            },
            "scope": {
                "asset_ids": [str(a) for a in asset_ids] if asset_ids else "all",
            },
            "summary": {
                "total_events": len(events),
                "total_anomalies": len(anomalies),
                "total_attestations": len(attestations),
                "trust_tier_distribution": tier_dist,
            },
            "events": events,
            "anomalies": anomalies,
            "attestations": [self._format_attestation(a) for a in attestations],
            "integrity": {
                "export_hash": hashlib.sha256(json.dumps(events, default=str).encode()).hexdigest(),
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
            "framework_version": "1.0.0",
        }
        
        if integration_id:
            await self._log_request(
                integration_id=integration_id,
                request_type=RequestType.AUDIT_EXPORT,
                org_id=org_id,
                time_range_start=time_range_start,
                time_range_end=time_range_end,
                response_status="success",
                events_returned=len(events),
            )
        
        return export_data
    
    async def _get_anomalies(
        self,
        asset_id: uuid.UUID,
        org_id: uuid.UUID,
        time_start: datetime,
        time_end: datetime,
    ) -> List[Dict[str, Any]]:
        """Get anomalies for an asset in time range."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("""
                    SELECT id, anomaly_type, anomaly_severity, status, detected_at, context_data
                    FROM anomaly_contexts
                    WHERE (product_id = :asset_id OR org_id = :org_id)
                    AND detected_at BETWEEN :start AND :end
                    ORDER BY detected_at DESC
                """),
                {"asset_id": asset_id, "org_id": org_id, "start": time_start, "end": time_end}
            )
            
            anomalies = []
            for row in result.fetchall():
                anomalies.append({
                    "id": str(row.id),
                    "type": row.anomaly_type,
                    "severity": row.anomaly_severity,
                    "status": row.status,
                    "detected_at": row.detected_at.isoformat() if row.detected_at else None,
                })
            
            return anomalies
    
    async def _get_org_events(
        self,
        org_id: uuid.UUID,
        time_start: datetime,
        time_end: datetime,
        asset_ids: Optional[List[uuid.UUID]] = None,
    ) -> List[Dict[str, Any]]:
        """Get events for an organization."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            query = """
                SELECT id, event_type, timestamp, payload, payload_hash
                FROM ops_events
                WHERE payload->>'org_id' = :org_id
                AND timestamp BETWEEN :start AND :end
            """
            params = {"org_id": str(org_id), "start": time_start, "end": time_end}
            
            if asset_ids:
                query += " AND payload->>'asset_id' = ANY(:asset_ids)"
                params["asset_ids"] = [str(a) for a in asset_ids]
            
            query += " ORDER BY timestamp ASC LIMIT 10000"
            
            result = await session.execute(text(query), params)
            
            events = []
            for row in result.fetchall():
                events.append({
                    "id": str(row.id),
                    "event_type": row.event_type,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    "payload": row.payload,
                    "payload_hash": row.payload_hash,
                })
            
            return events
    
    async def _get_org_anomalies(
        self,
        org_id: uuid.UUID,
        time_start: datetime,
        time_end: datetime,
        asset_ids: Optional[List[uuid.UUID]] = None,
    ) -> List[Dict[str, Any]]:
        """Get anomalies for an organization."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            query = """
                SELECT id, product_id, anomaly_type, anomaly_severity, status, detected_at
                FROM anomaly_contexts
                WHERE org_id = :org_id
                AND detected_at BETWEEN :start AND :end
            """
            params = {"org_id": org_id, "start": time_start, "end": time_end}
            
            if asset_ids:
                query += " AND product_id = ANY(:asset_ids)"
                params["asset_ids"] = asset_ids
            
            query += " ORDER BY detected_at DESC"
            
            result = await session.execute(text(query), params)
            
            anomalies = []
            for row in result.fetchall():
                anomalies.append({
                    "id": str(row.id),
                    "asset_id": str(row.product_id) if row.product_id else None,
                    "type": row.anomaly_type,
                    "severity": row.anomaly_severity,
                    "status": row.status,
                    "detected_at": row.detected_at.isoformat() if row.detected_at else None,
                })
            
            return anomalies
    
    async def _get_org_attestations(
        self,
        org_id: uuid.UUID,
        time_start: datetime,
        time_end: datetime,
        asset_ids: Optional[List[uuid.UUID]] = None,
    ) -> List:
        """Get attestations for an organization."""
        attestations = await attestation_service.list_attestations(
            org_id=org_id,
            limit=1000,
        )
        
        # Filter by time range and asset_ids
        filtered = []
        for a in attestations:
            if a.issued_at >= time_start and a.issued_at <= time_end:
                if asset_ids is None or a.asset_id in asset_ids:
                    filtered.append(a)
        
        return filtered
    
    async def _get_event_mapping(self, event_type: str) -> Optional[Dict[str, Any]]:
        """Get industry mapping for an event type."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("SELECT * FROM event_taxonomy WHERE ops_event_type = :event_type"),
                {"event_type": event_type}
            )
            row = result.fetchone()
            
            if row:
                return {
                    "insurance_category": row.insurance_category,
                    "compliance_domain": row.compliance_domain,
                    "claims_weight": float(row.claims_weight),
                }
            return None
    
    async def _log_request(
        self,
        integration_id: str,
        request_type: RequestType,
        asset_id: Optional[uuid.UUID] = None,
        org_id: Optional[uuid.UUID] = None,
        time_range_start: Optional[datetime] = None,
        time_range_end: Optional[datetime] = None,
        response_status: str = "success",
        events_returned: Optional[int] = None,
        trust_tier: Optional[int] = None,
        attestation_id: Optional[str] = None,
    ) -> None:
        """Log downstream request for audit trail."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            await session.execute(
                text("""
                    INSERT INTO downstream_requests (
                        id, integration_id, request_type,
                        asset_id, org_id, time_range_start, time_range_end,
                        response_status, events_returned, trust_tier_at_request, attestation_id,
                        requested_at
                    ) VALUES (
                        gen_random_uuid(), :integration_id, :request_type,
                        :asset_id, :org_id, :time_start, :time_end,
                        :status, :events, :tier, :attest_id,
                        NOW()
                    )
                """),
                {
                    "integration_id": integration_id,
                    "request_type": request_type.value,
                    "asset_id": asset_id,
                    "org_id": org_id,
                    "time_start": time_range_start,
                    "time_end": time_range_end,
                    "status": response_status,
                    "events": events_returned,
                    "tier": trust_tier,
                    "attest_id": attestation_id,
                }
            )
            await session.commit()
    
    def _sanitize_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize event for external consumption."""
        return {
            "id": str(event.get("id", "")),
            "event_type": event.get("event_type", ""),
            "timestamp": event.get("timestamp", ""),
            "payload_hash": event.get("payload_hash", ""),
        }
    
    def _format_attestation(self, attestation) -> Dict[str, Any]:
        """Format attestation for external consumption."""
        return {
            "attestation_id": attestation.attestation_id,
            "type": attestation.attestation_type.value,
            "time_window": {
                "start": attestation.time_window_start.isoformat(),
                "end": attestation.time_window_end.isoformat(),
            },
            "confidence_score": str(attestation.confidence_score),
            "status": attestation.status,
            "issued_at": attestation.issued_at.isoformat(),
            "expires_at": attestation.expires_at.isoformat(),
        }
    
    def _build_report_data(
        self,
        report_type: ReportType,
        events: List[Dict],
        anomalies: List[Dict],
        attestations: List,
        tier_dist: Dict[str, int],
        time_start: datetime,
        time_end: datetime,
    ) -> Dict[str, Any]:
        """Build report data based on type."""
        base_data = {
            "period": {
                "start": time_start.isoformat(),
                "end": time_end.isoformat(),
            },
            "metrics": {
                "total_events": len(events),
                "total_anomalies": len(anomalies),
                "total_attestations": len(attestations),
            },
            "trust_tier_distribution": tier_dist,
        }
        
        if report_type == ReportType.OPERATIONAL_SUMMARY:
            base_data["event_breakdown"] = self._group_events_by_type(events)
            base_data["anomaly_breakdown"] = self._group_anomalies_by_type(anomalies)
        
        elif report_type == ReportType.INSURANCE_EVIDENCE:
            base_data["insurance_relevant"] = [e for e in events if "shrinkage" in e.get("event_type", "") or "anomaly" in e.get("event_type", "")]
            base_data["loss_events"] = len([e for e in events if "shrinkage" in e.get("event_type", "")])
        
        elif report_type == ReportType.LOSS_PREVENTION:
            base_data["shrinkage_events"] = [e for e in events if "shrinkage" in e.get("event_type", "")]
            base_data["shrinkage_count"] = len(base_data["shrinkage_events"])
            base_data["anomalies_by_severity"] = self._group_anomalies_by_severity(anomalies)
        
        return base_data
    
    def _generate_report_summary(
        self,
        report_type: ReportType,
        events: List[Dict],
        anomalies: List[Dict],
        attestations: List,
    ) -> str:
        """Generate plain-language report summary."""
        summaries = {
            ReportType.OPERATIONAL_SUMMARY: f"Operational summary: {len(events)} events recorded, {len(anomalies)} anomalies detected, {len(attestations)} attestations issued.",
            ReportType.COMPLIANCE_AUDIT: f"Compliance audit: {len(events)} auditable events, {len(anomalies)} exceptions flagged.",
            ReportType.INSURANCE_EVIDENCE: f"Insurance evidence pack: {len(events)} events supporting claims documentation.",
            ReportType.REGULATORY_FILING: f"Regulatory filing data: {len(events)} compliance-relevant events.",
            ReportType.LOSS_PREVENTION: f"Loss prevention report: {len([e for e in events if 'shrinkage' in e.get('event_type', '')])} shrinkage events detected.",
            ReportType.INCIDENT_TIMELINE: f"Incident timeline: {len(events)} events in forensic reconstruction.",
        }
        return summaries.get(report_type, f"Report: {len(events)} events, {len(anomalies)} anomalies.")
    
    def _group_events_by_type(self, events: List[Dict]) -> Dict[str, int]:
        """Group events by type."""
        grouped = {}
        for e in events:
            event_type = e.get("event_type", "unknown")
            grouped[event_type] = grouped.get(event_type, 0) + 1
        return grouped
    
    def _group_anomalies_by_type(self, anomalies: List[Dict]) -> Dict[str, int]:
        """Group anomalies by type."""
        grouped = {}
        for a in anomalies:
            anom_type = a.get("type", "unknown")
            grouped[anom_type] = grouped.get(anom_type, 0) + 1
        return grouped
    
    def _group_anomalies_by_severity(self, anomalies: List[Dict]) -> Dict[str, int]:
        """Group anomalies by severity."""
        grouped = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for a in anomalies:
            severity = a.get("severity", "medium")
            if severity in grouped:
                grouped[severity] += 1
        return grouped


# Singleton instance
downstream_service = DownstreamService()
