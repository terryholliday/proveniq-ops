"""
PROVENIQ Ops - Scan Anomaly Detector API Routes
Bishop passive loss prevention endpoints

DAG Node: N15

GUARDRAILS:
- This is a SIGNAL, not an accusation
- Used for operational improvement, not discipline
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query

from app.models.scananomaly import (
    HistoricalNorm,
    ScanAnomalyAlert,
    ScanAnomalyAnalysis,
    ScanAnomalyConfig,
    ScanAnomalyType,
    ScanEvent,
    Severity,
    UserAnomalySummary,
    UserProfile,
)
from app.services.bishop.scananomaly_engine import scananomaly_engine

router = APIRouter(prefix="/scananomaly", tags=["Scan Anomaly Detector"])


# =============================================================================
# ANALYSIS
# =============================================================================

@router.post("/analyze", response_model=ScanAnomalyAnalysis)
async def analyze_scans(
    window_hours: int = Query(24, ge=1, le=168),
    location_id: Optional[uuid.UUID] = None,
) -> ScanAnomalyAnalysis:
    """
    Analyze scans for anomalies.
    
    Bishop Logic (N15):
        1. Detect temporal, volume, and repetition anomalies
        2. Score severity
    
    GUARDRAILS:
        - Results are SIGNALS for operational review
        - NOT accusations of wrongdoing
    
    Returns:
        ScanAnomalyAnalysis with detected anomalies
    """
    return scananomaly_engine.analyze(
        window_hours=window_hours,
        location_id=location_id,
    )


# =============================================================================
# REAL-TIME SCAN RECORDING
# =============================================================================

@router.post("/scan")
async def record_scan(
    user_id: uuid.UUID,
    location_id: uuid.UUID,
    product_id: uuid.UUID,
    product_name: str,
    canonical_sku: str,
    quantity: int,
    scan_type: str = "inventory",
    unit_value_dollars: Optional[str] = None,
) -> dict:
    """
    Record a scan event and check for immediate anomalies.
    
    Returns alert if anomaly detected.
    """
    from app.core.types import Money
    
    scan = ScanEvent(
        user_id=user_id,
        location_id=location_id,
        product_id=product_id,
        product_name=product_name,
        canonical_sku=canonical_sku,
        quantity=quantity,
        scanned_at=datetime.utcnow(),
        scan_type=scan_type,
        unit_value_micros=Money.from_dollars(unit_value_dollars) if unit_value_dollars else None,
    )
    
    alert = scananomaly_engine.record_scan(scan)
    
    result = {
        "status": "recorded",
        "scan_id": str(scan.scan_id),
        "anomaly_detected": alert is not None,
    }
    
    if alert:
        result["alert"] = {
            "severity": alert.severity.value,
            "reason": alert.reason.value,
            "detail": alert.reason_detail,
            "disclaimer": alert.disclaimer,
        }
    
    return result


# =============================================================================
# ALERTS
# =============================================================================

@router.get("/alerts", response_model=list[ScanAnomalyAlert])
async def get_alerts(
    limit: int = Query(100, ge=1, le=1000),
    severity: Optional[Severity] = None,
    user_id: Optional[uuid.UUID] = None,
) -> list[ScanAnomalyAlert]:
    """
    Get scan anomaly alerts.
    
    Note: These are signals for review, not accusations.
    """
    return scananomaly_engine.get_alerts(
        limit=limit,
        severity=severity,
        user_id=user_id,
    )


@router.get("/alerts/high")
async def get_high_severity_alerts() -> dict:
    """Get high severity alerts requiring attention."""
    alerts = scananomaly_engine.get_alerts(severity=Severity.HIGH)
    return {
        "count": len(alerts),
        "note": "These are signals for operational review, not accusations.",
        "alerts": [a.model_dump() for a in alerts],
    }


# =============================================================================
# USER SUMMARIES
# =============================================================================

@router.get("/user/{user_id}/summary", response_model=UserAnomalySummary)
async def get_user_summary(user_id: uuid.UUID) -> dict:
    """
    Get anomaly summary for a user.
    
    IMPORTANT: This is for operational improvement, not discipline.
    """
    summary = scananomaly_engine.get_user_summary(user_id)
    if not summary:
        return {"error": "User not found", "user_id": str(user_id)}
    return summary.model_dump()


# =============================================================================
# CONFIGURATION
# =============================================================================

@router.get("/config", response_model=ScanAnomalyConfig)
async def get_config() -> ScanAnomalyConfig:
    """Get current scan anomaly configuration."""
    return scananomaly_engine.get_config()


@router.put("/config")
async def update_config(
    min_scan_interval_seconds: Optional[int] = Query(None, ge=1),
    unusual_hour_start: Optional[int] = Query(None, ge=0, le=23),
    unusual_hour_end: Optional[int] = Query(None, ge=0, le=23),
    anonymize_usernames: Optional[bool] = None,
) -> ScanAnomalyConfig:
    """Update scan anomaly configuration."""
    config = scananomaly_engine.get_config()
    
    if min_scan_interval_seconds is not None:
        config.min_scan_interval_seconds = min_scan_interval_seconds
    if unusual_hour_start is not None:
        config.unusual_hour_start = unusual_hour_start
    if unusual_hour_end is not None:
        config.unusual_hour_end = unusual_hour_end
    if anonymize_usernames is not None:
        config.anonymize_usernames = anonymize_usernames
    
    scananomaly_engine.configure(config)
    return config


# =============================================================================
# DATA REGISTRATION
# =============================================================================

@router.post("/data/user")
async def register_user(
    username: str,
    role: str,
    location_id: uuid.UUID,
    avg_scans_per_shift: Decimal = Decimal("150"),
    avg_scan_interval_seconds: Decimal = Decimal("10"),
) -> dict:
    """Register a user profile."""
    profile = UserProfile(
        user_id=uuid.uuid4(),
        username=username,
        role=role,
        location_id=location_id,
        avg_scans_per_shift=avg_scans_per_shift,
        avg_scan_interval_seconds=avg_scan_interval_seconds,
    )
    scananomaly_engine.register_user(profile)
    return {
        "status": "registered",
        "user_id": str(profile.user_id),
        "username": username,
    }


@router.post("/data/norm")
async def register_norm(
    location_id: uuid.UUID,
    avg_scans_per_hour: Decimal,
    std_scans_per_hour: Decimal,
    avg_scan_interval_seconds: Decimal = Decimal("10"),
    high_value_threshold_dollars: str = "50",
) -> dict:
    """Register historical norms for a location."""
    from app.core.types import Money
    
    norm = HistoricalNorm(
        location_id=location_id,
        avg_scans_per_hour=avg_scans_per_hour,
        std_scans_per_hour=std_scans_per_hour,
        avg_scan_interval_seconds=avg_scan_interval_seconds,
        avg_item_value_micros=10_000_000,  # $10 default
        high_value_threshold_micros=Money.from_dollars(high_value_threshold_dollars),
    )
    scananomaly_engine.register_norm(norm)
    return {
        "status": "registered",
        "location_id": str(location_id),
    }


@router.post("/data/location")
async def register_location(
    location_id: uuid.UUID,
    name: str,
) -> dict:
    """Register a location name."""
    scananomaly_engine.register_location(location_id, name)
    return {"status": "registered", "location_id": str(location_id), "name": name}


@router.delete("/data/clear")
async def clear_data() -> dict:
    """Clear all scan anomaly data (for testing)."""
    scananomaly_engine.clear_data()
    return {"status": "cleared"}


# =============================================================================
# DEMO DATA
# =============================================================================

@router.post("/demo/setup")
async def setup_demo_data() -> dict:
    """
    Set up demo data for scan anomaly testing.
    
    Creates users with various scan patterns.
    """
    scananomaly_engine.clear_data()
    
    now = datetime.utcnow()
    
    # Location
    store_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    scananomaly_engine.register_location(store_id, "Store #12")
    
    # Register norms
    norm = HistoricalNorm(
        location_id=store_id,
        avg_scans_per_hour=Decimal("25"),
        std_scans_per_hour=Decimal("8"),
        avg_scan_interval_seconds=Decimal("10"),
        avg_item_value_micros=10_000_000,
        high_value_threshold_micros=50_000_000,
    )
    scananomaly_engine.register_norm(norm)
    
    # Users
    normal_user = UserProfile(
        user_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        username="john_normal",
        role="inventory_clerk",
        location_id=store_id,
        avg_scans_per_shift=Decimal("150"),
        avg_scan_interval_seconds=Decimal("10"),
    )
    
    fast_user = UserProfile(
        user_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        username="jane_fast",
        role="inventory_clerk",
        location_id=store_id,
        avg_scans_per_shift=Decimal("200"),
        avg_scan_interval_seconds=Decimal("5"),
    )
    
    night_user = UserProfile(
        user_id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        username="bob_night",
        role="night_shift",
        location_id=store_id,
        avg_scans_per_shift=Decimal("100"),
        avg_scan_interval_seconds=Decimal("15"),
        typical_start_hour=22,
        typical_end_hour=6,
    )
    
    for user in [normal_user, fast_user, night_user]:
        scananomaly_engine.register_user(user)
    
    # Products
    products = [
        (uuid.UUID("11111111-0000-0000-0000-000000000001"), "Chicken Breast 5lb", "CHK-BRST-5LB", "12.50"),
        (uuid.UUID("11111111-0000-0000-0000-000000000002"), "Rice 25lb", "RICE-25LB", "18.99"),
        (uuid.UUID("11111111-0000-0000-0000-000000000003"), "Olive Oil 1gal", "OIL-OLV-1G", "24.99"),
    ]
    
    from app.core.types import Money
    
    # Normal scans
    for i in range(10):
        scan = ScanEvent(
            user_id=normal_user.user_id,
            location_id=store_id,
            product_id=products[i % 3][0],
            product_name=products[i % 3][1],
            canonical_sku=products[i % 3][2],
            quantity=1,
            scanned_at=now - timedelta(minutes=i*2),
            unit_value_micros=Money.from_dollars(products[i % 3][3]),
        )
        scananomaly_engine.record_scan(scan)
    
    # Rapid succession scans (should trigger anomaly)
    for i in range(8):
        scan = ScanEvent(
            user_id=fast_user.user_id,
            location_id=store_id,
            product_id=products[0][0],
            product_name=products[0][1],
            canonical_sku=products[0][2],
            quantity=1,
            scanned_at=now - timedelta(seconds=i),  # 1 second apart!
            unit_value_micros=Money.from_dollars(products[0][3]),
        )
        scananomaly_engine.record_scan(scan)
    
    # Late night scan (unusual hour)
    late_scan = ScanEvent(
        user_id=normal_user.user_id,
        location_id=store_id,
        product_id=products[1][0],
        product_name=products[1][1],
        canonical_sku=products[1][2],
        quantity=5,
        scanned_at=now.replace(hour=3, minute=30),  # 3:30 AM
        unit_value_micros=Money.from_dollars(products[1][3]),
    )
    scananomaly_engine.record_scan(late_scan)
    
    return {
        "status": "demo_data_created",
        "users": 3,
        "scans": 19,
        "expected_anomalies": [
            "jane_fast: RAPID_SUCCESSION - 8 scans in seconds",
            "john_normal: UNUSUAL_HOUR - scan at 3:30 AM",
            "jane_fast: SAME_ITEM_LOOP - same item 8x",
        ],
        "guardrail_reminder": "These are SIGNALS for review, not accusations.",
    }
