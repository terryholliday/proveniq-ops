"""
PROVENIQ Ops - Audit Readiness Engine Schemas
Bishop compliance gap detection data contracts

Continuously detects documentation or compliance gaps before audits.
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, Any

from pydantic import BaseModel, Field

from app.core.types import Rate


class AuditCategory(str, Enum):
    """Categories of audit requirements."""
    FOOD_SAFETY = "food_safety"
    INVENTORY = "inventory"
    FINANCIAL = "financial"
    WASTE = "waste"
    RECEIVING = "receiving"
    TEMPERATURE = "temperature"
    SANITATION = "sanitation"
    EMPLOYEE = "employee"
    VENDOR = "vendor"
    REGULATORY = "regulatory"


class EvidenceType(str, Enum):
    """Types of evidence that support audit compliance."""
    DOCUMENT = "document"
    PHOTO = "photo"
    SIGNATURE = "signature"
    TIMESTAMP = "timestamp"
    SCAN_RECORD = "scan_record"
    TEMPERATURE_LOG = "temperature_log"
    RECEIPT = "receipt"
    CERTIFICATE = "certificate"
    TRAINING_RECORD = "training_record"
    INSPECTION_REPORT = "inspection_report"


class ComplianceStatus(str, Enum):
    """Status of a compliance requirement."""
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    UNKNOWN = "unknown"
    EXPIRED = "expired"


class GapSeverity(str, Enum):
    """Severity of a compliance gap."""
    CRITICAL = "critical"     # Will fail audit
    HIGH = "high"             # Likely to fail
    MEDIUM = "medium"         # May cause issues
    LOW = "low"               # Minor concern
    INFO = "info"             # Informational


class RemediationPriority(str, Enum):
    """Priority for remediation."""
    IMMEDIATE = "immediate"   # Fix now
    URGENT = "urgent"         # Fix within 24h
    HIGH = "high"             # Fix within 1 week
    NORMAL = "normal"         # Fix before audit
    LOW = "low"               # Nice to have


# =============================================================================
# AUDIT SCHEMA REQUIREMENTS
# =============================================================================

class AuditRequirement(BaseModel):
    """Single audit requirement definition."""
    requirement_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Classification
    category: AuditCategory
    code: str  # e.g., "FS-001", "INV-003"
    name: str
    description: str
    
    # Evidence requirements
    required_evidence: list[EvidenceType]
    min_evidence_count: int = 1
    
    # Timing
    frequency: str = "daily"  # daily, weekly, monthly, per_delivery, per_shift
    retention_days: int = 365
    
    # Scoring
    weight: int = 10  # Points if compliant
    critical: bool = False  # Automatic fail if missing


class AuditSchema(BaseModel):
    """Complete audit schema with all requirements."""
    schema_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    schema_name: str
    schema_version: str = "1.0"
    
    # Requirements
    requirements: list[AuditRequirement] = []
    
    # Scoring
    total_points: int = 0
    passing_score: int = 80
    
    # Metadata
    effective_date: date = Field(default_factory=date.today)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# EVIDENCE RECORDS
# =============================================================================

class EvidenceAsset(BaseModel):
    """A piece of evidence supporting compliance."""
    asset_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # What this evidences
    requirement_id: Optional[uuid.UUID] = None
    category: AuditCategory
    
    # Evidence details
    evidence_type: EvidenceType
    description: str
    
    # Asset reference
    asset_key: Optional[str] = None  # File/image key
    asset_url: Optional[str] = None
    
    # Metadata
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    captured_by: Optional[str] = None
    location_id: Optional[uuid.UUID] = None
    
    # Validity
    expires_at: Optional[datetime] = None
    is_valid: bool = True
    
    # Verification
    verified: bool = False
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None


class InventoryRecord(BaseModel):
    """Inventory record for audit purposes."""
    record_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Item
    product_id: uuid.UUID
    product_name: str
    
    # Count
    quantity: Decimal
    unit: str
    
    # Timing
    counted_at: datetime
    counted_by: Optional[str] = None
    
    # Evidence
    has_photo: bool = False
    has_signature: bool = False
    scan_verified: bool = False
    
    # Discrepancy
    expected_quantity: Optional[Decimal] = None
    variance_pct: Optional[Decimal] = None


class WasteLogEntry(BaseModel):
    """Waste log entry for audit purposes."""
    entry_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Item
    product_id: uuid.UUID
    product_name: str
    
    # Waste details
    quantity_wasted: Decimal
    unit: str
    reason: str
    
    # Timing
    wasted_at: datetime
    logged_by: Optional[str] = None
    
    # Evidence
    has_photo: bool = False
    manager_approved: bool = False
    approval_timestamp: Optional[datetime] = None


class ApprovalRecord(BaseModel):
    """Approval/authorization record."""
    approval_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # What was approved
    approval_type: str  # "waste", "order", "adjustment", "transfer"
    reference_id: uuid.UUID
    description: str
    
    # Who approved
    approver_role: str
    approver_name: Optional[str] = None
    
    # When
    approved_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Evidence
    has_signature: bool = False
    signature_asset_id: Optional[uuid.UUID] = None


# =============================================================================
# COMPLIANCE GAP
# =============================================================================

class ComplianceGap(BaseModel):
    """A detected compliance gap."""
    gap_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # What's missing
    requirement_id: uuid.UUID
    requirement_code: str
    requirement_name: str
    category: AuditCategory
    
    # Gap details
    gap_type: str  # "missing_evidence", "expired", "incomplete", "late"
    gap_description: str
    
    # Severity
    severity: GapSeverity
    is_critical: bool = False
    
    # Impact
    points_at_risk: int = 0
    
    # Time context
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    
    # Detection
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class RemediationStep(BaseModel):
    """Recommended remediation step."""
    step_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # What to fix
    gap_id: uuid.UUID
    
    # Remediation
    action: str
    description: str
    priority: RemediationPriority
    
    # Effort
    estimated_minutes: int = 15
    requires_approval: bool = False
    
    # Status
    completed: bool = False
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None


# =============================================================================
# AUDIT READINESS ASSESSMENT
# =============================================================================

class CategoryScore(BaseModel):
    """Score for a single audit category."""
    category: AuditCategory
    
    # Scoring
    max_points: int
    earned_points: int
    score_pct: Rate
    
    # Status
    status: ComplianceStatus
    
    # Gaps
    gap_count: int = 0
    critical_gaps: int = 0


class AuditReadinessResult(BaseModel):
    """
    Complete audit readiness assessment.
    The main output of the engine.
    """
    assessment_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    assessed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Overall score (0-100)
    audit_risk_score: int  # Higher = more risk
    compliance_score: int  # Higher = more compliant
    
    # Pass/fail
    would_pass_audit: bool
    passing_threshold: int = 80
    
    # Missing evidence
    missing_evidence: list[str] = []
    
    # Recommended fixes
    recommended_fixes: list[str] = []
    
    # Category breakdown
    category_scores: list[CategoryScore] = []
    
    # Gaps
    total_gaps: int = 0
    critical_gaps: int = 0
    gaps: list[ComplianceGap] = []
    
    # Remediation
    remediation_steps: list[RemediationStep] = []
    estimated_remediation_hours: Decimal = Decimal("0")
    
    # Summary
    summary: str = ""


# =============================================================================
# CONFIGURATION
# =============================================================================

class AuditReadinessConfig(BaseModel):
    """Configuration for audit readiness engine."""
    # Assessment period
    lookback_days: int = 30
    
    # Scoring thresholds
    passing_score: int = 80
    critical_threshold: int = 70
    
    # Gap detection
    max_hours_without_temp_log: int = 4
    max_days_without_inventory: int = 7
    max_days_without_waste_review: int = 1
    
    # Evidence requirements
    require_photo_for_waste: bool = True
    require_signature_for_adjustments: bool = True
    require_temp_log_frequency_hours: int = 4
    
    # Alerts
    alert_on_critical_gap: bool = True
    alert_threshold_score: int = 75
