"""
PROVENIQ Ops - Scan Anomaly Detector Schemas
Bishop passive loss prevention data contracts

DAG Node: N15

GUARDRAILS:
- This is a SIGNAL, not an accusation
- Used for operational improvement, not discipline
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.core.types import IntQuantity, Quantity, Rate


class ScanAnomalyType(str, Enum):
    """Scan anomaly classifications."""
    SCAN_ANOMALY = "SCAN_ANOMALY"
    TEMPORAL_ANOMALY = "TEMPORAL_ANOMALY"
    VOLUME_ANOMALY = "VOLUME_ANOMALY"
    REPETITION_ANOMALY = "REPETITION_ANOMALY"
    PATTERN_ANOMALY = "PATTERN_ANOMALY"


class Severity(str, Enum):
    """Anomaly severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AnomalyReason(str, Enum):
    """Standardized anomaly reasons."""
    # Temporal
    UNUSUAL_HOUR = "unusual_hour"
    RAPID_SUCCESSION = "rapid_succession"
    LONG_GAP = "long_gap"
    
    # Volume
    HIGH_VOLUME = "high_volume"
    LOW_VOLUME = "low_volume"
    QUANTITY_SPIKE = "quantity_spike"
    
    # Repetition
    DUPLICATE_SCAN = "duplicate_scan"
    REPEATED_VOID = "repeated_void"
    SAME_ITEM_LOOP = "same_item_loop"
    
    # Pattern
    SELECTIVE_SCANNING = "selective_scanning"
    CATEGORY_SKIP = "category_skip"
    VALUE_THRESHOLD = "value_threshold"


# =============================================================================
# SCAN EVENT MODELS
# =============================================================================

class ScanEvent(BaseModel):
    """Individual scan event."""
    scan_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    location_id: uuid.UUID
    
    # What was scanned
    product_id: uuid.UUID
    product_name: str
    canonical_sku: str
    quantity: IntQuantity
    
    # Timing
    scanned_at: datetime
    
    # Context
    scan_type: str = "inventory"  # inventory, receiving, void, adjustment
    session_id: Optional[uuid.UUID] = None
    
    # Value (for threshold detection)
    unit_value_micros: Optional[int] = None


class UserProfile(BaseModel):
    """User profile with scan behavior norms."""
    user_id: uuid.UUID
    username: str
    role: str
    location_id: uuid.UUID
    
    # Historical norms
    avg_scans_per_shift: Quantity
    avg_scan_interval_seconds: Quantity
    typical_start_hour: int = 6
    typical_end_hour: int = 22
    
    # Behavioral baseline
    usual_categories: list[str] = []
    unusual_hour_threshold: int = 2  # Hours outside typical range
    
    # Stats
    total_scans: int = 0
    anomaly_count: int = 0


class HistoricalNorm(BaseModel):
    """Historical norms for a location/role."""
    location_id: uuid.UUID
    role: Optional[str] = None
    
    # Volume norms
    avg_scans_per_hour: Quantity
    std_scans_per_hour: Quantity
    
    # Timing norms
    avg_scan_interval_seconds: Quantity
    min_scan_interval_seconds: int = 2  # Faster than this is suspicious
    
    # Value norms
    avg_item_value_micros: int
    high_value_threshold_micros: int


# =============================================================================
# ANOMALY ALERT MODELS
# =============================================================================

class ScanAnomalyAlert(BaseModel):
    """
    Bishop scan anomaly alert.
    
    IMPORTANT: This is a SIGNAL for operational review.
    It is NOT an accusation of wrongdoing.
    """
    alert_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    alert_type: ScanAnomalyType = ScanAnomalyType.SCAN_ANOMALY
    
    # Who (anonymizable for privacy)
    user_id: uuid.UUID
    username: Optional[str] = None  # Can be masked
    location_id: uuid.UUID
    location_name: Optional[str] = None
    
    # Severity
    severity: Severity
    anomaly_score: Quantity  # 0-1
    
    # What
    reason: AnomalyReason
    reason_detail: str
    
    # Evidence (facts only, no conclusions)
    scan_count: Optional[int] = None
    time_window_minutes: Optional[int] = None
    affected_scans: list[uuid.UUID] = []
    
    # Context
    baseline_value: Optional[str] = None  # What's normal
    observed_value: Optional[str] = None  # What was detected
    deviation_factor: Optional[Quantity] = None  # How far from normal
    
    # Metadata
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    
    # GUARDRAIL reminder
    disclaimer: str = "This is a signal for operational review, not an accusation."
    
    class Config:
        json_schema_extra = {
            "example": {
                "alert_type": "SCAN_ANOMALY",
                "user_id": "uuid",
                "severity": "MEDIUM",
                "reason": "rapid_succession",
                "reason_detail": "15 scans in 30 seconds (normal: 2-3)",
                "disclaimer": "This is a signal for operational review, not an accusation."
            }
        }


# =============================================================================
# ANALYSIS MODELS
# =============================================================================

class UserAnomalySummary(BaseModel):
    """Summary of anomalies for a user (for review, not discipline)."""
    user_id: uuid.UUID
    username: str
    
    # Counts
    total_alerts: int
    low_severity: int
    medium_severity: int
    high_severity: int
    
    # Types
    alerts_by_type: dict[str, int] = Field(default_factory=dict)
    
    # Trend
    alerts_last_7d: int
    alerts_last_30d: int
    trend: str = "stable"  # increasing, decreasing, stable
    
    # Context (not accusations)
    possible_causes: list[str] = []


class ScanAnomalyAnalysis(BaseModel):
    """Complete scan anomaly analysis."""
    analysis_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Scope
    time_window_hours: int
    scans_analyzed: int
    users_analyzed: int
    
    # Results
    anomalies_detected: int
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    
    # Breakdown
    by_type: dict[str, int] = Field(default_factory=dict)
    by_location: dict[str, int] = Field(default_factory=dict)
    
    # Alerts
    alerts: list[ScanAnomalyAlert] = []
    
    # System health note
    note: str = "Anomalies are signals for process review, not individual accusations."


# =============================================================================
# CONFIGURATION
# =============================================================================

class ScanAnomalyConfig(BaseModel):
    """Configuration for scan anomaly detector."""
    # Temporal thresholds
    min_scan_interval_seconds: int = 2  # Faster = suspicious
    unusual_hour_start: int = 22  # 10 PM
    unusual_hour_end: int = 5  # 5 AM
    
    # Volume thresholds
    high_volume_stddev: Quantity = Field(default=Decimal("2.0"))  # >2 std dev
    low_volume_stddev: Quantity = Field(default=Decimal("2.0"))
    
    # Repetition thresholds
    duplicate_window_seconds: int = 60
    max_same_item_scans: int = 5
    
    # Severity scoring
    low_threshold: Quantity = Field(default=Decimal("0.3"))
    medium_threshold: Quantity = Field(default=Decimal("0.6"))
    high_threshold: Quantity = Field(default=Decimal("0.8"))
    
    # Privacy
    anonymize_usernames: bool = False
    
    # Analysis window
    default_analysis_hours: int = 24
