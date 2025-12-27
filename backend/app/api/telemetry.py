"""
PROVENIQ Ops - Telemetry Ingestion API
P1: Continuous sensor data for DATA GRAVITY moat

This is the core of Phase 0-1: Data Gravity & Forensic Lock-In.
After 6-12 months, customers cannot migrate without losing truth.
"""

import hashlib
import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db


router = APIRouter(prefix="/telemetry", tags=["Telemetry & Events"])


# =============================================================================
# SCHEMAS
# =============================================================================

class EventType(str, Enum):
    """Canonical event types for ops_events table."""
    # Sensor events
    TEMPERATURE_READING = "TEMPERATURE_READING"
    HUMIDITY_READING = "HUMIDITY_READING"
    DOOR_OPEN = "DOOR_OPEN"
    DOOR_CLOSE = "DOOR_CLOSE"
    POWER_LOSS = "POWER_LOSS"
    POWER_RESTORED = "POWER_RESTORED"
    
    # Scan events
    INVENTORY_SCAN = "INVENTORY_SCAN"
    BARCODE_SCAN = "BARCODE_SCAN"
    MANUAL_COUNT = "MANUAL_COUNT"
    
    # Operational events
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_DELIVERED = "ORDER_DELIVERED"
    DELIVERY_RECEIVED = "DELIVERY_RECEIVED"
    
    # Bishop events
    BISHOP_STATE_CHANGE = "BISHOP_STATE_CHANGE"
    BISHOP_RECOMMENDATION = "BISHOP_RECOMMENDATION"
    BISHOP_RECOMMENDATION_ACCEPTED = "BISHOP_RECOMMENDATION_ACCEPTED"
    BISHOP_RECOMMENDATION_REJECTED = "BISHOP_RECOMMENDATION_REJECTED"
    
    # Anomaly events
    ANOMALY_DETECTED = "ANOMALY_DETECTED"
    ANOMALY_RESOLVED = "ANOMALY_RESOLVED"
    
    # Waste events
    WASTE_RECORDED = "WASTE_RECORDED"
    SHRINKAGE_DETECTED = "SHRINKAGE_DETECTED"
    
    # Attestation events
    ATTESTATION_ISSUED = "ATTESTATION_ISSUED"
    ATTESTATION_VERIFIED = "ATTESTATION_VERIFIED"


class TelemetryEventCreate(BaseModel):
    """Ingest a telemetry event into the ops_events table."""
    event_type: EventType
    wallet_id: Optional[str] = Field(None, max_length=255, description="Pseudonymous org/location identifier")
    correlation_id: Optional[str] = Field(None, max_length=255, description="Links related events")
    idempotency_key: Optional[str] = Field(None, max_length=255, description="Prevents duplicate ingestion")
    payload: dict = Field(default_factory=dict, description="Event-specific data")
    source_app: str = Field("OPS", max_length=50)
    version: str = Field("1.0", max_length=20)


class TelemetryEventRead(BaseModel):
    """Response model for telemetry events."""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    event_type: str
    timestamp: datetime
    wallet_id: Optional[str]
    correlation_id: Optional[str]
    payload: dict
    payload_hash: str
    ledger_synced: bool
    created_at: datetime


class SensorReadingCreate(BaseModel):
    """Convenience schema for sensor readings."""
    sensor_id: str = Field(..., max_length=100)
    sensor_type: str = Field(..., max_length=50)  # temperature, humidity, door, power
    location_id: Optional[uuid.UUID] = None
    asset_id: Optional[uuid.UUID] = None
    value: Decimal
    unit: str = Field(..., max_length=20)  # °F, °C, %, boolean
    wallet_id: Optional[str] = None


class BishopRecommendationCreate(BaseModel):
    """Record a Bishop recommendation for audit trail."""
    org_id: uuid.UUID
    recommendation_type: str = Field(..., max_length=100)  # reorder, investigate, alert
    recommendation_text: str
    context: dict = Field(default_factory=dict)
    confidence_score: Decimal = Field(..., ge=0, le=1)
    related_product_ids: list[uuid.UUID] = Field(default_factory=list)
    related_order_ids: list[uuid.UUID] = Field(default_factory=list)


class BishopAcceptanceCreate(BaseModel):
    """Record acceptance/rejection of a Bishop recommendation."""
    recommendation_event_id: uuid.UUID
    accepted: bool
    user_id: Optional[uuid.UUID] = None
    rejection_reason: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None


class AnomalyCreate(BaseModel):
    """Record an anomaly detection."""
    org_id: uuid.UUID
    anomaly_type: str = Field(..., max_length=100)
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    observed_value: Decimal
    expected_value: Decimal
    deviation_sigma: Decimal
    baseline_id: Optional[uuid.UUID] = None
    product_id: Optional[uuid.UUID] = None
    location_id: Optional[uuid.UUID] = None
    prior_events: list[dict] = Field(default_factory=list)
    prior_context: dict = Field(default_factory=dict)


class EventQueryParams(BaseModel):
    """Query parameters for event search."""
    wallet_id: Optional[str] = None
    event_type: Optional[EventType] = None
    correlation_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(100, le=1000)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def compute_payload_hash(payload: dict) -> str:
    """Compute SHA-256 hash of payload for integrity verification."""
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(payload_json.encode()).hexdigest()


# =============================================================================
# P1: TELEMETRY INGESTION ENDPOINTS
# =============================================================================

@router.post("/events", response_model=TelemetryEventRead, status_code=status.HTTP_201_CREATED)
async def ingest_event(
    event: TelemetryEventCreate,
    db: AsyncSession = Depends(get_db),
) -> TelemetryEventRead:
    """
    Ingest a telemetry event into the ops_events table.
    
    This is the core DATA GRAVITY endpoint. Events are:
    - Immutable (append-only)
    - Hashed for integrity verification
    - Queued for Ledger sync
    
    After 6-12 months, this data becomes irreplaceable.
    """
    event_id = uuid.uuid4()
    now = datetime.utcnow()
    payload_hash = compute_payload_hash(event.payload)
    
    query = text("""
        INSERT INTO ops_events (
            id, event_type, timestamp, wallet_id, correlation_id, 
            idempotency_key, version, source_app, payload, payload_hash,
            ledger_synced, created_at
        ) VALUES (
            :id, :event_type, :timestamp, :wallet_id, :correlation_id,
            :idempotency_key, :version, :source_app, :payload, :payload_hash,
            :ledger_synced, :created_at
        )
        ON CONFLICT (idempotency_key) DO NOTHING
        RETURNING *
    """)
    
    result = await db.execute(query, {
        "id": event_id,
        "event_type": event.event_type.value,
        "timestamp": now,
        "wallet_id": event.wallet_id,
        "correlation_id": event.correlation_id,
        "idempotency_key": event.idempotency_key,
        "version": event.version,
        "source_app": event.source_app,
        "payload": json.dumps(event.payload),
        "payload_hash": payload_hash,
        "ledger_synced": False,
        "created_at": now,
    })
    
    row = result.mappings().first()
    await db.commit()
    
    if not row:
        # Idempotency key conflict - return existing event
        existing = await db.execute(
            text("SELECT * FROM ops_events WHERE idempotency_key = :key"),
            {"key": event.idempotency_key}
        )
        row = existing.mappings().first()
    
    return TelemetryEventRead(
        id=row["id"],
        event_type=row["event_type"],
        timestamp=row["timestamp"],
        wallet_id=row["wallet_id"],
        correlation_id=row["correlation_id"],
        payload=row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"]),
        payload_hash=row["payload_hash"],
        ledger_synced=row["ledger_synced"],
        created_at=row["created_at"],
    )


@router.post("/sensors", response_model=TelemetryEventRead, status_code=status.HTTP_201_CREATED)
async def ingest_sensor_reading(
    reading: SensorReadingCreate,
    db: AsyncSession = Depends(get_db),
) -> TelemetryEventRead:
    """
    Convenience endpoint for sensor readings.
    
    Maps sensor data to the appropriate event type and ingests.
    """
    # Map sensor type to event type
    sensor_event_map = {
        "temperature": EventType.TEMPERATURE_READING,
        "humidity": EventType.HUMIDITY_READING,
        "door": EventType.DOOR_OPEN if reading.value > 0 else EventType.DOOR_CLOSE,
        "power": EventType.POWER_RESTORED if reading.value > 0 else EventType.POWER_LOSS,
    }
    
    event_type = sensor_event_map.get(reading.sensor_type.lower(), EventType.TEMPERATURE_READING)
    
    payload = {
        "sensor_id": reading.sensor_id,
        "sensor_type": reading.sensor_type,
        "location_id": str(reading.location_id) if reading.location_id else None,
        "asset_id": str(reading.asset_id) if reading.asset_id else None,
        "value": float(reading.value),
        "unit": reading.unit,
    }
    
    event = TelemetryEventCreate(
        event_type=event_type,
        wallet_id=reading.wallet_id,
        payload=payload,
        idempotency_key=f"{reading.sensor_id}:{datetime.utcnow().isoformat()}",
    )
    
    return await ingest_event(event, db)


@router.get("/events", response_model=list[TelemetryEventRead])
async def query_events(
    wallet_id: Optional[str] = None,
    event_type: Optional[EventType] = None,
    correlation_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db),
) -> list[TelemetryEventRead]:
    """
    Query telemetry events.
    
    Used for forensic reconstruction and audit trails.
    """
    query_str = "SELECT * FROM ops_events WHERE 1=1"
    params = {}
    
    if wallet_id:
        query_str += " AND wallet_id = :wallet_id"
        params["wallet_id"] = wallet_id
    if event_type:
        query_str += " AND event_type = :event_type"
        params["event_type"] = event_type.value
    if correlation_id:
        query_str += " AND correlation_id = :correlation_id"
        params["correlation_id"] = correlation_id
    if start_time:
        query_str += " AND timestamp >= :start_time"
        params["start_time"] = start_time
    if end_time:
        query_str += " AND timestamp <= :end_time"
        params["end_time"] = end_time
    
    query_str += " ORDER BY timestamp DESC LIMIT :limit"
    params["limit"] = limit
    
    result = await db.execute(text(query_str), params)
    rows = result.mappings().all()
    
    return [TelemetryEventRead(
        id=r["id"],
        event_type=r["event_type"],
        timestamp=r["timestamp"],
        wallet_id=r["wallet_id"],
        correlation_id=r["correlation_id"],
        payload=r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"]) if r["payload"] else {},
        payload_hash=r["payload_hash"],
        ledger_synced=r["ledger_synced"],
        created_at=r["created_at"],
    ) for r in rows]


@router.get("/events/{event_id}", response_model=TelemetryEventRead)
async def get_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TelemetryEventRead:
    """Get a specific event by ID."""
    result = await db.execute(
        text("SELECT * FROM ops_events WHERE id = :id"),
        {"id": event_id}
    )
    row = result.mappings().first()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )
    
    return TelemetryEventRead(
        id=row["id"],
        event_type=row["event_type"],
        timestamp=row["timestamp"],
        wallet_id=row["wallet_id"],
        correlation_id=row["correlation_id"],
        payload=row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"]) if row["payload"] else {},
        payload_hash=row["payload_hash"],
        ledger_synced=row["ledger_synced"],
        created_at=row["created_at"],
    )


# =============================================================================
# P2: BISHOP RECOMMENDATION → ACCEPTANCE FLOW
# =============================================================================

@router.post("/bishop/recommendations", response_model=TelemetryEventRead, status_code=status.HTTP_201_CREATED)
async def record_bishop_recommendation(
    recommendation: BishopRecommendationCreate,
    db: AsyncSession = Depends(get_db),
) -> TelemetryEventRead:
    """
    Record a Bishop AI recommendation.
    
    Creates an audit trail for:
    - What Bishop recommended
    - Why (context and confidence)
    - When
    
    Human must accept/reject via separate endpoint.
    """
    payload = {
        "org_id": str(recommendation.org_id),
        "recommendation_type": recommendation.recommendation_type,
        "recommendation_text": recommendation.recommendation_text,
        "context": recommendation.context,
        "confidence_score": float(recommendation.confidence_score),
        "related_product_ids": [str(p) for p in recommendation.related_product_ids],
        "related_order_ids": [str(o) for o in recommendation.related_order_ids],
        "status": "pending",  # Awaiting human decision
    }
    
    event = TelemetryEventCreate(
        event_type=EventType.BISHOP_RECOMMENDATION,
        wallet_id=str(recommendation.org_id),
        payload=payload,
        correlation_id=f"bishop-rec-{uuid.uuid4()}",
    )
    
    return await ingest_event(event, db)


@router.post("/bishop/acceptance", response_model=TelemetryEventRead, status_code=status.HTTP_201_CREATED)
async def record_bishop_acceptance(
    acceptance: BishopAcceptanceCreate,
    db: AsyncSession = Depends(get_db),
) -> TelemetryEventRead:
    """
    Record acceptance or rejection of a Bishop recommendation.
    
    CRITICAL for Trust Tier calculation:
    - Consistent acceptance → higher trust
    - Frequent rejection → lower trust (operator doesn't trust system)
    - Override without reason → trust degradation
    """
    # Get the original recommendation
    rec_result = await db.execute(
        text("SELECT * FROM ops_events WHERE id = :id"),
        {"id": acceptance.recommendation_event_id}
    )
    rec_row = rec_result.mappings().first()
    
    if not rec_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation event {acceptance.recommendation_event_id} not found",
        )
    
    event_type = EventType.BISHOP_RECOMMENDATION_ACCEPTED if acceptance.accepted else EventType.BISHOP_RECOMMENDATION_REJECTED
    
    payload = {
        "recommendation_event_id": str(acceptance.recommendation_event_id),
        "accepted": acceptance.accepted,
        "user_id": str(acceptance.user_id) if acceptance.user_id else None,
        "rejection_reason": acceptance.rejection_reason,
        "notes": acceptance.notes,
        "original_recommendation": rec_row["payload"],
    }
    
    event = TelemetryEventCreate(
        event_type=event_type,
        wallet_id=rec_row["wallet_id"],
        payload=payload,
        correlation_id=rec_row["correlation_id"],  # Link to original recommendation
    )
    
    return await ingest_event(event, db)


@router.get("/bishop/recommendations/pending")
async def get_pending_recommendations(
    org_id: uuid.UUID,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Get pending Bishop recommendations awaiting human decision.
    """
    query = text("""
        SELECT e.* 
        FROM ops_events e
        WHERE e.event_type = 'BISHOP_RECOMMENDATION'
          AND e.wallet_id = :org_id
          AND NOT EXISTS (
              SELECT 1 FROM ops_events a 
              WHERE a.correlation_id = e.correlation_id
                AND a.event_type IN ('BISHOP_RECOMMENDATION_ACCEPTED', 'BISHOP_RECOMMENDATION_REJECTED')
          )
        ORDER BY e.timestamp DESC
        LIMIT :limit
    """)
    
    result = await db.execute(query, {"org_id": str(org_id), "limit": limit})
    rows = result.mappings().all()
    
    return [{
        "event_id": str(r["id"]),
        "timestamp": r["timestamp"].isoformat(),
        "recommendation": r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"]),
    } for r in rows]


# =============================================================================
# P3: ANOMALY & SHRINKAGE EVENTS (ClaimsIQ Bridge)
# =============================================================================

@router.post("/anomalies", status_code=status.HTTP_201_CREATED)
async def record_anomaly(
    anomaly: AnomalyCreate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Record an anomaly detection.
    
    Creates records in both:
    - ops_events (for telemetry trail)
    - anomaly_contexts (for forensic context)
    """
    anomaly_id = uuid.uuid4()
    now = datetime.utcnow()
    
    # Insert into anomaly_contexts
    anomaly_query = text("""
        INSERT INTO anomaly_contexts (
            id, org_id, anomaly_type, anomaly_severity, detected_at,
            observed_value, expected_value, deviation_sigma, baseline_id,
            product_id, location_id, prior_events, prior_context, status, created_at
        ) VALUES (
            :id, :org_id, :anomaly_type, :anomaly_severity, :detected_at,
            :observed_value, :expected_value, :deviation_sigma, :baseline_id,
            :product_id, :location_id, :prior_events, :prior_context, :status, :created_at
        )
        RETURNING *
    """)
    
    await db.execute(anomaly_query, {
        "id": anomaly_id,
        "org_id": anomaly.org_id,
        "anomaly_type": anomaly.anomaly_type,
        "anomaly_severity": anomaly.severity,
        "detected_at": now,
        "observed_value": anomaly.observed_value,
        "expected_value": anomaly.expected_value,
        "deviation_sigma": anomaly.deviation_sigma,
        "baseline_id": anomaly.baseline_id,
        "product_id": anomaly.product_id,
        "location_id": anomaly.location_id,
        "prior_events": json.dumps(anomaly.prior_events),
        "prior_context": json.dumps(anomaly.prior_context),
        "status": "detected",
        "created_at": now,
    })
    
    # Also record in ops_events for telemetry trail
    event_payload = {
        "anomaly_id": str(anomaly_id),
        "anomaly_type": anomaly.anomaly_type,
        "severity": anomaly.severity,
        "observed_value": float(anomaly.observed_value),
        "expected_value": float(anomaly.expected_value),
        "deviation_sigma": float(anomaly.deviation_sigma),
        "product_id": str(anomaly.product_id) if anomaly.product_id else None,
        "location_id": str(anomaly.location_id) if anomaly.location_id else None,
    }
    
    event = TelemetryEventCreate(
        event_type=EventType.ANOMALY_DETECTED,
        wallet_id=str(anomaly.org_id),
        payload=event_payload,
        correlation_id=f"anomaly-{anomaly_id}",
    )
    
    await ingest_event(event, db)
    await db.commit()
    
    return {
        "anomaly_id": str(anomaly_id),
        "status": "detected",
        "severity": anomaly.severity,
        "message": f"Anomaly recorded. Deviation: {anomaly.deviation_sigma:.2f}σ from expected.",
    }


@router.post("/shrinkage", status_code=status.HTTP_201_CREATED)
async def record_shrinkage(
    org_id: uuid.UUID,
    product_id: uuid.UUID,
    expected_quantity: Decimal,
    actual_quantity: Decimal,
    location_id: Optional[uuid.UUID] = None,
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Record a shrinkage event (missing inventory).
    
    This is a CLAIMSIQ BRIDGE point:
    - Shrinkage events can trigger ClaimsIQ claims
    - Evidence is preserved in ops_events for claim support
    """
    shrinkage_qty = expected_quantity - actual_quantity
    shrinkage_pct = (shrinkage_qty / expected_quantity * 100) if expected_quantity > 0 else 0
    
    # Determine severity
    if shrinkage_pct >= 20:
        severity = "critical"
    elif shrinkage_pct >= 10:
        severity = "high"
    elif shrinkage_pct >= 5:
        severity = "medium"
    else:
        severity = "low"
    
    payload = {
        "product_id": str(product_id),
        "location_id": str(location_id) if location_id else None,
        "expected_quantity": float(expected_quantity),
        "actual_quantity": float(actual_quantity),
        "shrinkage_quantity": float(shrinkage_qty),
        "shrinkage_percentage": float(shrinkage_pct),
        "severity": severity,
        "notes": notes,
        "claimsiq_eligible": severity in ("high", "critical"),
    }
    
    event = TelemetryEventCreate(
        event_type=EventType.SHRINKAGE_DETECTED,
        wallet_id=str(org_id),
        payload=payload,
        correlation_id=f"shrinkage-{product_id}-{datetime.utcnow().date()}",
    )
    
    result = await ingest_event(event, db)
    
    return {
        "event_id": str(result.id),
        "shrinkage_quantity": float(shrinkage_qty),
        "shrinkage_percentage": round(float(shrinkage_pct), 2),
        "severity": severity,
        "claimsiq_eligible": severity in ("high", "critical"),
        "message": f"Shrinkage detected: {shrinkage_qty} units ({shrinkage_pct:.1f}%)",
    }


# =============================================================================
# INTEGRITY VERIFICATION
# =============================================================================

@router.get("/verify/{event_id}")
async def verify_event_integrity(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Verify the integrity of a stored event.
    
    Recomputes the payload hash and compares to stored hash.
    """
    result = await db.execute(
        text("SELECT * FROM ops_events WHERE id = :id"),
        {"id": event_id}
    )
    row = result.mappings().first()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )
    
    payload = row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"]) if row["payload"] else {}
    recomputed_hash = compute_payload_hash(payload)
    stored_hash = row["payload_hash"]
    
    is_valid = recomputed_hash == stored_hash
    
    return {
        "event_id": str(event_id),
        "integrity_valid": is_valid,
        "stored_hash": stored_hash,
        "recomputed_hash": recomputed_hash,
        "verified_at": datetime.utcnow().isoformat(),
        "message": "Event integrity verified" if is_valid else "INTEGRITY VIOLATION DETECTED",
    }


# =============================================================================
# P3: CLAIMSIQ SHRINKAGE BRIDGE
# =============================================================================

@router.post("/shrinkage/claim", status_code=status.HTTP_201_CREATED)
async def submit_shrinkage_claim(
    org_id: uuid.UUID,
    shrinkage_event_id: uuid.UUID,
    product_name: str,
    unit_cost_cents: int,
    claim_type: str = "unknown",
    photos: list[str] = [],
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Submit a shrinkage event to ClaimsIQ as a claim.
    
    P3: DOWNSTREAM COUPLING
    - Creates dependency between Ops and ClaimsIQ
    - Trust Tier affects claim processing friction
    - Attestations enable auto-approval
    """
    from app.bridges.claimsiq_bridge import (
        get_claimsiq_bridge,
        ShrinkageClaimRequest,
        ShrinkageClaimType,
    )
    
    # Get the original shrinkage event
    result = await db.execute(
        text("SELECT * FROM ops_events WHERE id = :id"),
        {"id": shrinkage_event_id}
    )
    event_row = result.mappings().first()
    
    if not event_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shrinkage event {shrinkage_event_id} not found",
        )
    
    payload = event_row["payload"] if isinstance(event_row["payload"], dict) else json.loads(event_row["payload"])
    
    # Get trust tier for this org
    trust_result = await db.execute(
        text("""
            SELECT current_tier FROM asset_trust_tiers 
            WHERE org_id = :org_id 
            ORDER BY calculated_at DESC LIMIT 1
        """),
        {"org_id": org_id}
    )
    trust_row = trust_result.mappings().first()
    trust_tier = trust_row["current_tier"] if trust_row else "BRONZE"
    
    # Build claim request
    claim_request = ShrinkageClaimRequest(
        org_id=org_id,
        ops_event_id=shrinkage_event_id,
        ops_correlation_id=event_row["correlation_id"] or f"shrinkage-{shrinkage_event_id}",
        claim_type=ShrinkageClaimType(claim_type) if claim_type in [e.value for e in ShrinkageClaimType] else ShrinkageClaimType.UNKNOWN,
        product_id=uuid.UUID(payload["product_id"]),
        product_name=product_name,
        expected_quantity=Decimal(str(payload["expected_quantity"])),
        actual_quantity=Decimal(str(payload["actual_quantity"])),
        shrinkage_quantity=Decimal(str(payload["shrinkage_quantity"])),
        shrinkage_percentage=Decimal(str(payload["shrinkage_percentage"])),
        unit_cost_cents=unit_cost_cents,
        total_loss_cents=int(payload["shrinkage_quantity"] * unit_cost_cents),
        evidence_event_ids=[shrinkage_event_id],
        supporting_photos=photos,
        notes=notes,
        ops_trust_tier=trust_tier,
    )
    
    # Submit to ClaimsIQ
    bridge = get_claimsiq_bridge()
    claim_response = await bridge.submit_shrinkage_claim(claim_request)
    
    # Record the claim submission event
    claim_event = TelemetryEventCreate(
        event_type=EventType.SHRINKAGE_DETECTED,  # Reuse type, payload distinguishes
        wallet_id=str(org_id),
        payload={
            "action": "claim_submitted",
            "shrinkage_event_id": str(shrinkage_event_id),
            "claim_id": str(claim_response.claim_id),
            "claim_number": claim_response.claim_number,
            "status": claim_response.status,
            "auto_approved": claim_response.auto_approved,
            "friction_level": claim_response.friction_level,
            "trust_tier": trust_tier,
        },
        correlation_id=event_row["correlation_id"],
    )
    await ingest_event(claim_event, db)
    
    return {
        "claim_id": str(claim_response.claim_id),
        "claim_number": claim_response.claim_number,
        "status": claim_response.status,
        "auto_approved": claim_response.auto_approved,
        "friction_level": claim_response.friction_level,
        "trust_tier_applied": trust_tier,
        "next_steps": claim_response.next_steps,
        "estimated_payout_cents": claim_response.estimated_payout_cents,
    }


# =============================================================================
# P2: LEDGER WRITE-THROUGH INTEGRATION
# =============================================================================

@router.post("/ledger/sync", status_code=status.HTTP_200_OK)
async def sync_events_to_ledger(
    batch_size: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Sync pending ops_events to PROVENIQ Ledger.
    
    P2: CRYPTOGRAPHIC PROOF CHAIN
    - Events synced to Ledger get hash chain proof
    - Cross-app visibility
    - Forensic reconstruction across ecosystem
    """
    from app.services.ledger_sync import get_ledger_sync
    
    sync_service = get_ledger_sync()
    result = await sync_service.sync_pending_events(db, batch_size)
    
    return {
        "action": "ledger_sync",
        "batch_size": batch_size,
        **result,
        "message": f"Synced {result['synced']} events to Ledger",
    }


@router.get("/ledger/stats")
async def get_ledger_sync_stats(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get Ledger sync statistics."""
    from app.services.ledger_sync import get_ledger_sync
    
    sync_service = get_ledger_sync()
    return await sync_service.get_sync_stats(db)


@router.get("/ledger/verify/{event_id}")
async def verify_ledger_integrity(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Verify an ops_event against its Ledger entry.
    
    Cross-references local hash with Ledger chain hash.
    """
    from app.services.ledger_sync import get_ledger_sync
    
    sync_service = get_ledger_sync()
    return await sync_service.verify_integrity(event_id, db)


@router.get("/stats")
async def get_telemetry_stats(
    wallet_id: Optional[str] = None,
    hours: int = Query(24, le=168),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get telemetry statistics for monitoring.
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    
    query_str = """
        SELECT 
            event_type,
            COUNT(*) as count,
            MIN(timestamp) as first_event,
            MAX(timestamp) as last_event
        FROM ops_events
        WHERE timestamp >= :since
    """
    params = {"since": since}
    
    if wallet_id:
        query_str += " AND wallet_id = :wallet_id"
        params["wallet_id"] = wallet_id
    
    query_str += " GROUP BY event_type ORDER BY count DESC"
    
    result = await db.execute(text(query_str), params)
    rows = result.mappings().all()
    
    total_events = sum(r["count"] for r in rows)
    
    return {
        "period_hours": hours,
        "wallet_id": wallet_id,
        "total_events": total_events,
        "by_type": [{
            "event_type": r["event_type"],
            "count": r["count"],
            "first_event": r["first_event"].isoformat() if r["first_event"] else None,
            "last_event": r["last_event"].isoformat() if r["last_event"] else None,
        } for r in rows],
    }
