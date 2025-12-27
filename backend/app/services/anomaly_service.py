"""
PROVENIQ Ops - Anomaly Context Service
Phase 0-1: Link Anomalies to Prior Operational Context

FORENSIC RECONSTRUCTION:
When shrinkage or anomalies are detected, this service captures:
- What events led up to the anomaly
- What the operational state was at detection time
- Links to baseline data used for detection
- Full context for "What happened, when, and why"

This creates the forensic layer that makes Ops irreplaceable.
"""

import uuid
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import logging

from app.db.session import async_session_maker
from app.services.events.store import event_store
from app.services.baseline_engine import baseline_engine, BaselineType

logger = logging.getLogger(__name__)


class AnomalyType(str, Enum):
    """Types of operational anomalies."""
    CONSUMPTION_SPIKE = "consumption_spike"
    CONSUMPTION_DROP = "consumption_drop"
    PRICE_ANOMALY = "price_anomaly"
    SHRINKAGE_DETECTED = "shrinkage_detected"
    DELIVERY_DELAY = "delivery_delay"
    SCAN_GAP = "scan_gap"
    ORDER_ANOMALY = "order_anomaly"


class AnomalySeverity(str, Enum):
    """Severity levels for anomalies."""
    LOW = "low"           # 2-3 sigma
    MEDIUM = "medium"     # 3-4 sigma
    HIGH = "high"         # 4-5 sigma
    CRITICAL = "critical" # >5 sigma


class AnomalyStatus(str, Enum):
    """Status of an anomaly investigation."""
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    RESOLVED = "resolved"


class AnomalyContext(BaseModel):
    """
    Full context around an detected anomaly.
    
    This is the forensic record that enables:
    - "What happened before this shrinkage?"
    - "Was this expected based on prior patterns?"
    - "What other anomalies occurred around this time?"
    """
    anomaly_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    org_id: uuid.UUID
    
    # What was detected
    anomaly_type: AnomalyType
    anomaly_severity: AnomalySeverity
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # The anomalous value vs expected
    observed_value: Decimal
    expected_value: Decimal
    deviation_sigma: Decimal  # How many standard deviations from mean
    
    # Link to baseline used for detection
    baseline_id: Optional[uuid.UUID] = None
    
    # Entity references
    product_id: Optional[uuid.UUID] = None
    location_id: Optional[uuid.UUID] = None
    order_id: Optional[uuid.UUID] = None
    shrinkage_id: Optional[uuid.UUID] = None
    
    # Prior context (forensic value)
    prior_events: List[Dict[str, Any]] = []  # Events leading up to anomaly
    prior_context: Dict[str, Any] = {}  # State at time of anomaly
    
    # Related events (discovered after detection)
    related_event_ids: List[uuid.UUID] = []
    
    # Resolution tracking
    status: AnomalyStatus = AnomalyStatus.DETECTED
    resolved_at: Optional[datetime] = None
    resolution_type: Optional[str] = None
    resolution_notes: Optional[str] = None
    resolved_by: Optional[uuid.UUID] = None
    
    # Link to decision trace if this triggered a decision
    decision_trace_id: Optional[uuid.UUID] = None


class AnomalyService:
    """
    Service for detecting and contextualizing operational anomalies.
    
    MOAT VALUE:
    - Every anomaly is captured with full context
    - Prior events are preserved for forensic reconstruction
    - Links to baselines show "what normal looks like"
    - This forensic history cannot be replicated by competitors
    """
    
    # How many prior events to capture
    PRIOR_EVENT_COUNT = 20
    
    # How far back to look for prior events (hours)
    PRIOR_EVENT_WINDOW_HOURS = 48
    
    async def detect_and_record_anomaly(
        self,
        org_id: uuid.UUID,
        anomaly_type: AnomalyType,
        observed_value: Decimal,
        location_id: Optional[uuid.UUID] = None,
        product_id: Optional[uuid.UUID] = None,
        order_id: Optional[uuid.UUID] = None,
        shrinkage_id: Optional[uuid.UUID] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> AnomalyContext:
        """
        Detect an anomaly and record it with full context.
        
        This is the core of forensic reconstruction.
        """
        # Map anomaly type to baseline type
        baseline_type_map = {
            AnomalyType.CONSUMPTION_SPIKE: BaselineType.DAILY_CONSUMPTION,
            AnomalyType.CONSUMPTION_DROP: BaselineType.DAILY_CONSUMPTION,
            AnomalyType.SHRINKAGE_DETECTED: BaselineType.SHRINKAGE_RATE,
            AnomalyType.PRICE_ANOMALY: BaselineType.PRICE_VARIANCE,
            AnomalyType.ORDER_ANOMALY: BaselineType.WEEKLY_ORDERS,
        }
        
        baseline_type = baseline_type_map.get(anomaly_type)
        
        # Check against baseline if we have a matching type
        expected_value = Decimal("0")
        deviation_sigma = Decimal("0")
        baseline_id = None
        
        if baseline_type:
            is_anomaly, deviation, baseline = await baseline_engine.check_anomaly(
                org_id=org_id,
                baseline_type=baseline_type,
                observed_value=observed_value,
                location_id=location_id,
                product_id=product_id,
            )
            if baseline:
                expected_value = baseline.mean_value
                baseline_id = baseline.baseline_id
                if deviation:
                    deviation_sigma = deviation
        
        # Determine severity based on deviation
        severity = self._calculate_severity(deviation_sigma)
        
        # Get prior events (forensic context)
        prior_events = await self._get_prior_events(
            org_id=org_id,
            location_id=location_id,
            product_id=product_id,
        )
        
        # Build prior context snapshot
        prior_context = await self._build_context_snapshot(
            org_id=org_id,
            location_id=location_id,
            product_id=product_id,
            additional_context=additional_context,
        )
        
        # Create anomaly context
        anomaly = AnomalyContext(
            org_id=org_id,
            anomaly_type=anomaly_type,
            anomaly_severity=severity,
            observed_value=observed_value,
            expected_value=expected_value,
            deviation_sigma=deviation_sigma,
            baseline_id=baseline_id,
            product_id=product_id,
            location_id=location_id,
            order_id=order_id,
            shrinkage_id=shrinkage_id,
            prior_events=prior_events,
            prior_context=prior_context,
        )
        
        # Persist the anomaly
        await self._save_anomaly(anomaly)
        
        # Publish anomaly detected event
        await event_store.append(
            event_type="ops.anomaly.detected",
            payload={
                "anomaly_id": str(anomaly.anomaly_id),
                "anomaly_type": anomaly_type.value,
                "severity": severity.value,
                "observed_value": str(observed_value),
                "expected_value": str(expected_value),
                "deviation_sigma": str(deviation_sigma),
                "product_id": str(product_id) if product_id else None,
                "location_id": str(location_id) if location_id else None,
                "prior_event_count": len(prior_events),
            },
        )
        
        logger.info(f"Anomaly detected: {anomaly_type.value} (severity={severity.value}, sigma={deviation_sigma})")
        
        return anomaly
    
    def _calculate_severity(self, deviation_sigma: Decimal) -> AnomalySeverity:
        """Calculate severity based on standard deviation."""
        if deviation_sigma >= Decimal("5"):
            return AnomalySeverity.CRITICAL
        elif deviation_sigma >= Decimal("4"):
            return AnomalySeverity.HIGH
        elif deviation_sigma >= Decimal("3"):
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW
    
    async def _get_prior_events(
        self,
        org_id: uuid.UUID,
        location_id: Optional[uuid.UUID] = None,
        product_id: Optional[uuid.UUID] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get prior events leading up to the anomaly.
        
        This is the forensic context - "What happened before?"
        """
        since = datetime.now(timezone.utc) - timedelta(hours=self.PRIOR_EVENT_WINDOW_HOURS)
        
        events = await event_store.get_forensic_timeline(
            product_id=product_id,
            location_id=location_id,
            since=since,
            limit=self.PRIOR_EVENT_COUNT,
        )
        
        # Return simplified event records
        return [
            {
                "event_id": e["event_id"],
                "event_type": e["event_type"],
                "timestamp": e["timestamp"],
                "payload_summary": self._summarize_payload(e["payload"]),
            }
            for e in events
        ]
    
    def _summarize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a summarized version of event payload for storage."""
        # Keep key fields, remove large nested data
        summary = {}
        key_fields = [
            "product_id", "product_name", "location_id", "quantity",
            "delta", "variance", "expected_qty", "actual_qty",
            "order_id", "vendor", "total_amount_micros",
        ]
        for field in key_fields:
            if field in payload:
                summary[field] = payload[field]
        return summary
    
    async def _build_context_snapshot(
        self,
        org_id: uuid.UUID,
        location_id: Optional[uuid.UUID] = None,
        product_id: Optional[uuid.UUID] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build a snapshot of operational context at anomaly time.
        
        Captures "the state of the world" when the anomaly occurred.
        """
        context: Dict[str, Any] = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Get recent event counts by type
        event_counts = await event_store.count_by_type(
            since=datetime.now(timezone.utc) - timedelta(hours=24)
        )
        context["event_counts_24h"] = event_counts
        
        # Add any additional context provided
        if additional_context:
            context["additional"] = additional_context
        
        return context
    
    async def _save_anomaly(self, anomaly: AnomalyContext) -> None:
        """Persist an anomaly to the database."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            await session.execute(
                text("""
                    INSERT INTO anomaly_contexts (
                        id, org_id, anomaly_type, anomaly_severity, detected_at,
                        observed_value, expected_value, deviation_sigma,
                        baseline_id, product_id, location_id, order_id,
                        prior_events, prior_context, related_event_ids,
                        status, shrinkage_id, decision_trace_id, created_at
                    ) VALUES (
                        :id, :org_id, :anomaly_type, :anomaly_severity, :detected_at,
                        :observed_value, :expected_value, :deviation_sigma,
                        :baseline_id, :product_id, :location_id, :order_id,
                        :prior_events, :prior_context, :related_event_ids,
                        :status, :shrinkage_id, :decision_trace_id, :created_at
                    )
                """),
                {
                    "id": anomaly.anomaly_id,
                    "org_id": anomaly.org_id,
                    "anomaly_type": anomaly.anomaly_type.value,
                    "anomaly_severity": anomaly.anomaly_severity.value,
                    "detected_at": anomaly.detected_at,
                    "observed_value": anomaly.observed_value,
                    "expected_value": anomaly.expected_value,
                    "deviation_sigma": anomaly.deviation_sigma,
                    "baseline_id": anomaly.baseline_id,
                    "product_id": anomaly.product_id,
                    "location_id": anomaly.location_id,
                    "order_id": anomaly.order_id,
                    "prior_events": json.dumps(anomaly.prior_events),
                    "prior_context": json.dumps(anomaly.prior_context),
                    "related_event_ids": [str(e) for e in anomaly.related_event_ids] if anomaly.related_event_ids else None,
                    "status": anomaly.status.value,
                    "shrinkage_id": anomaly.shrinkage_id,
                    "decision_trace_id": anomaly.decision_trace_id,
                    "created_at": datetime.now(timezone.utc),
                }
            )
            await session.commit()
    
    async def get_anomaly(self, anomaly_id: uuid.UUID) -> Optional[AnomalyContext]:
        """Get an anomaly by ID."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("SELECT * FROM anomaly_contexts WHERE id = :id"),
                {"id": anomaly_id}
            )
            row = result.fetchone()
            if not row:
                return None
            
            return self._row_to_anomaly(row)
    
    async def get_anomalies_for_product(
        self,
        org_id: uuid.UUID,
        product_id: uuid.UUID,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[AnomalyContext]:
        """Get anomalies for a specific product."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            query = """
                SELECT * FROM anomaly_contexts
                WHERE org_id = :org_id AND product_id = :product_id
            """
            params: Dict[str, Any] = {
                "org_id": org_id,
                "product_id": product_id,
                "limit": limit,
            }
            
            if since:
                query += " AND detected_at >= :since"
                params["since"] = since
            
            query += " ORDER BY detected_at DESC LIMIT :limit"
            
            result = await session.execute(text(query), params)
            return [self._row_to_anomaly(row) for row in result.fetchall()]
    
    async def get_unresolved_anomalies(
        self,
        org_id: uuid.UUID,
        severity: Optional[AnomalySeverity] = None,
        limit: int = 100,
    ) -> List[AnomalyContext]:
        """Get unresolved anomalies for an organization."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            query = """
                SELECT * FROM anomaly_contexts
                WHERE org_id = :org_id
                AND status NOT IN ('resolved', 'false_positive')
            """
            params: Dict[str, Any] = {"org_id": org_id, "limit": limit}
            
            if severity:
                query += " AND anomaly_severity = :severity"
                params["severity"] = severity.value
            
            query += " ORDER BY detected_at DESC LIMIT :limit"
            
            result = await session.execute(text(query), params)
            return [self._row_to_anomaly(row) for row in result.fetchall()]
    
    async def resolve_anomaly(
        self,
        anomaly_id: uuid.UUID,
        resolution_type: str,
        resolution_notes: str,
        resolved_by: uuid.UUID,
        is_false_positive: bool = False,
    ) -> Optional[AnomalyContext]:
        """Resolve an anomaly."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            status = AnomalyStatus.FALSE_POSITIVE if is_false_positive else AnomalyStatus.RESOLVED
            resolved_at = datetime.now(timezone.utc)
            
            await session.execute(
                text("""
                    UPDATE anomaly_contexts SET
                        status = :status,
                        resolved_at = :resolved_at,
                        resolution_type = :resolution_type,
                        resolution_notes = :resolution_notes,
                        resolved_by = :resolved_by
                    WHERE id = :id
                """),
                {
                    "id": anomaly_id,
                    "status": status.value,
                    "resolved_at": resolved_at,
                    "resolution_type": resolution_type,
                    "resolution_notes": resolution_notes,
                    "resolved_by": resolved_by,
                }
            )
            await session.commit()
        
        # Publish resolution event
        await event_store.append(
            event_type="ops.anomaly.resolved",
            payload={
                "anomaly_id": str(anomaly_id),
                "resolution_type": resolution_type,
                "is_false_positive": is_false_positive,
                "resolved_by": str(resolved_by),
            },
        )
        
        return await self.get_anomaly(anomaly_id)
    
    async def link_to_shrinkage(
        self,
        anomaly_id: uuid.UUID,
        shrinkage_id: uuid.UUID,
    ) -> None:
        """Link an anomaly to a shrinkage event."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            await session.execute(
                text("UPDATE anomaly_contexts SET shrinkage_id = :shrinkage_id WHERE id = :id"),
                {"id": anomaly_id, "shrinkage_id": shrinkage_id}
            )
            await session.commit()
    
    def _row_to_anomaly(self, row) -> AnomalyContext:
        """Convert a database row to AnomalyContext."""
        prior_events = row.prior_events
        if isinstance(prior_events, str):
            prior_events = json.loads(prior_events)
        
        prior_context = row.prior_context
        if isinstance(prior_context, str):
            prior_context = json.loads(prior_context)
        
        return AnomalyContext(
            anomaly_id=row.id,
            org_id=row.org_id,
            anomaly_type=AnomalyType(row.anomaly_type),
            anomaly_severity=AnomalySeverity(row.anomaly_severity),
            detected_at=row.detected_at,
            observed_value=row.observed_value,
            expected_value=row.expected_value,
            deviation_sigma=row.deviation_sigma,
            baseline_id=row.baseline_id,
            product_id=row.product_id,
            location_id=row.location_id,
            order_id=row.order_id,
            shrinkage_id=row.shrinkage_id,
            prior_events=prior_events or [],
            prior_context=prior_context or {},
            related_event_ids=row.related_event_ids or [],
            status=AnomalyStatus(row.status),
            resolved_at=row.resolved_at,
            resolution_type=row.resolution_type,
            resolution_notes=row.resolution_notes,
            resolved_by=row.resolved_by,
            decision_trace_id=row.decision_trace_id,
        )


# Singleton instance
anomaly_service = AnomalyService()
