"""
PROVENIQ Ops - Audit Readiness API Routes
Bishop compliance gap detection endpoints

Continuously detects documentation or compliance gaps before audits.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query

from app.models.auditready import (
    ApprovalRecord,
    AuditCategory,
    AuditReadinessConfig,
    AuditReadinessResult,
    AuditSchema,
    EvidenceAsset,
    EvidenceType,
    InventoryRecord,
    WasteLogEntry,
)
from app.services.bishop.auditready_engine import auditready_engine

router = APIRouter(prefix="/auditready", tags=["Audit Readiness"])


# =============================================================================
# ASSESSMENT
# =============================================================================

@router.get("/assess", response_model=AuditReadinessResult)
async def assess_readiness(
    period_days: int = Query(30, ge=1, le=365),
) -> AuditReadinessResult:
    """
    Run complete audit readiness assessment.
    
    Returns:
    - audit_risk_score: 0-100 (higher = more risk)
    - missing_evidence: List of missing documentation
    - recommended_fixes: Priority-ordered remediation steps
    """
    return auditready_engine.assess_readiness(period_days)


@router.get("/score")
async def get_quick_score(
    period_days: int = Query(30, ge=1, le=365),
) -> dict:
    """Get quick audit risk score without full details."""
    result = auditready_engine.assess_readiness(period_days)
    
    return {
        "audit_risk_score": result.audit_risk_score,
        "compliance_score": result.compliance_score,
        "would_pass_audit": result.would_pass_audit,
        "total_gaps": result.total_gaps,
        "critical_gaps": result.critical_gaps,
        "summary": result.summary,
    }


# =============================================================================
# SCHEMA
# =============================================================================

@router.get("/schema", response_model=AuditSchema)
async def get_audit_schema() -> AuditSchema:
    """Get the current audit schema with all requirements."""
    return auditready_engine.get_schema()


@router.get("/requirements")
async def get_requirements(
    category: Optional[AuditCategory] = None,
) -> dict:
    """Get audit requirements, optionally filtered by category."""
    schema = auditready_engine.get_schema()
    requirements = schema.requirements
    
    if category:
        requirements = [r for r in requirements if r.category == category]
    
    return {
        "total": len(requirements),
        "requirements": [r.model_dump() for r in requirements],
    }


# =============================================================================
# EVIDENCE REGISTRATION
# =============================================================================

@router.post("/evidence")
async def register_evidence(
    category: AuditCategory,
    evidence_type: EvidenceType,
    description: str,
    asset_key: Optional[str] = None,
    captured_by: Optional[str] = None,
    location_id: Optional[uuid.UUID] = None,
    requirement_id: Optional[uuid.UUID] = None,
) -> dict:
    """Register a piece of evidence supporting compliance."""
    evidence = EvidenceAsset(
        category=category,
        evidence_type=evidence_type,
        description=description,
        asset_key=asset_key,
        captured_by=captured_by,
        location_id=location_id,
        requirement_id=requirement_id,
    )
    
    auditready_engine.register_evidence(evidence)
    
    return {
        "status": "registered",
        "asset_id": str(evidence.asset_id),
        "category": category.value,
        "evidence_type": evidence_type.value,
    }


@router.post("/evidence/temperature")
async def register_temperature_log(
    temperature_f: Decimal,
    location_name: str,
    location_id: Optional[uuid.UUID] = None,
    captured_by: Optional[str] = None,
) -> dict:
    """Register a temperature log entry."""
    evidence = EvidenceAsset(
        category=AuditCategory.FOOD_SAFETY,
        evidence_type=EvidenceType.TEMPERATURE_LOG,
        description=f"Temperature: {temperature_f}°F at {location_name}",
        captured_by=captured_by,
        location_id=location_id,
    )
    
    auditready_engine.register_evidence(evidence)
    
    return {
        "status": "registered",
        "asset_id": str(evidence.asset_id),
        "temperature_f": str(temperature_f),
        "location": location_name,
    }


@router.post("/evidence/receiving")
async def register_receiving_evidence(
    vendor_name: str,
    po_number: Optional[str] = None,
    has_temperature_check: bool = False,
    temperature_f: Optional[Decimal] = None,
    has_signature: bool = False,
    location_id: Optional[uuid.UUID] = None,
    captured_by: Optional[str] = None,
) -> dict:
    """Register receiving documentation."""
    registered = []
    
    # Receipt evidence
    receipt = EvidenceAsset(
        category=AuditCategory.RECEIVING,
        evidence_type=EvidenceType.RECEIPT,
        description=f"Delivery from {vendor_name}" + (f" PO#{po_number}" if po_number else ""),
        captured_by=captured_by,
        location_id=location_id,
    )
    auditready_engine.register_evidence(receipt)
    registered.append("receipt")
    
    # Temperature check
    if has_temperature_check:
        temp = EvidenceAsset(
            category=AuditCategory.FOOD_SAFETY,
            evidence_type=EvidenceType.TEMPERATURE_LOG,
            description=f"Receiving temp check: {temperature_f}°F from {vendor_name}",
            captured_by=captured_by,
            location_id=location_id,
        )
        auditready_engine.register_evidence(temp)
        registered.append("temperature_log")
    
    # Signature
    if has_signature:
        sig = EvidenceAsset(
            category=AuditCategory.RECEIVING,
            evidence_type=EvidenceType.SIGNATURE,
            description=f"Delivery signature for {vendor_name}",
            captured_by=captured_by,
            location_id=location_id,
        )
        auditready_engine.register_evidence(sig)
        registered.append("signature")
    
    return {
        "status": "registered",
        "vendor": vendor_name,
        "evidence_types": registered,
    }


# =============================================================================
# INVENTORY RECORDS
# =============================================================================

@router.post("/inventory")
async def register_inventory_record(
    product_id: uuid.UUID,
    product_name: str,
    quantity: Decimal,
    unit: str,
    counted_by: Optional[str] = None,
    has_photo: bool = False,
    has_signature: bool = False,
    scan_verified: bool = False,
    expected_quantity: Optional[Decimal] = None,
) -> dict:
    """Register an inventory count record."""
    variance = None
    if expected_quantity and expected_quantity > 0:
        variance = abs(quantity - expected_quantity) / expected_quantity * 100
    
    record = InventoryRecord(
        product_id=product_id,
        product_name=product_name,
        quantity=quantity,
        unit=unit,
        counted_at=datetime.utcnow(),
        counted_by=counted_by,
        has_photo=has_photo,
        has_signature=has_signature,
        scan_verified=scan_verified,
        expected_quantity=expected_quantity,
        variance_pct=variance,
    )
    
    auditready_engine.register_inventory_record(record)
    
    # Also register as evidence
    evidence = EvidenceAsset(
        category=AuditCategory.INVENTORY,
        evidence_type=EvidenceType.SCAN_RECORD if scan_verified else EvidenceType.DOCUMENT,
        description=f"Inventory count: {product_name} = {quantity} {unit}",
        captured_by=counted_by,
    )
    auditready_engine.register_evidence(evidence)
    
    return {
        "status": "registered",
        "record_id": str(record.record_id),
        "product": product_name,
        "quantity": str(quantity),
        "variance_pct": str(variance) if variance else None,
    }


# =============================================================================
# WASTE LOGS
# =============================================================================

@router.post("/waste")
async def register_waste_log(
    product_id: uuid.UUID,
    product_name: str,
    quantity_wasted: Decimal,
    unit: str,
    reason: str,
    logged_by: Optional[str] = None,
    has_photo: bool = False,
    manager_approved: bool = False,
) -> dict:
    """Register a waste log entry."""
    entry = WasteLogEntry(
        product_id=product_id,
        product_name=product_name,
        quantity_wasted=quantity_wasted,
        unit=unit,
        reason=reason,
        wasted_at=datetime.utcnow(),
        logged_by=logged_by,
        has_photo=has_photo,
        manager_approved=manager_approved,
        approval_timestamp=datetime.utcnow() if manager_approved else None,
    )
    
    auditready_engine.register_waste_log(entry)
    
    # Register evidence
    evidence = EvidenceAsset(
        category=AuditCategory.WASTE,
        evidence_type=EvidenceType.DOCUMENT,
        description=f"Waste: {quantity_wasted} {unit} {product_name} - {reason}",
        captured_by=logged_by,
    )
    auditready_engine.register_evidence(evidence)
    
    if has_photo:
        photo = EvidenceAsset(
            category=AuditCategory.WASTE,
            evidence_type=EvidenceType.PHOTO,
            description=f"Waste photo: {product_name}",
            captured_by=logged_by,
        )
        auditready_engine.register_evidence(photo)
    
    return {
        "status": "registered",
        "entry_id": str(entry.entry_id),
        "product": product_name,
        "quantity": str(quantity_wasted),
        "has_photo": has_photo,
        "manager_approved": manager_approved,
    }


# =============================================================================
# APPROVALS
# =============================================================================

@router.post("/approval")
async def register_approval(
    approval_type: str,
    reference_id: uuid.UUID,
    description: str,
    approver_role: str,
    approver_name: Optional[str] = None,
    has_signature: bool = False,
) -> dict:
    """Register an approval record."""
    approval = ApprovalRecord(
        approval_type=approval_type,
        reference_id=reference_id,
        description=description,
        approver_role=approver_role,
        approver_name=approver_name,
        has_signature=has_signature,
    )
    
    auditready_engine.register_approval(approval)
    
    if has_signature:
        evidence = EvidenceAsset(
            category=AuditCategory.INVENTORY if approval_type == "adjustment" else AuditCategory.WASTE,
            evidence_type=EvidenceType.SIGNATURE,
            description=f"Approval signature: {description}",
            captured_by=approver_name,
        )
        auditready_engine.register_evidence(evidence)
    
    return {
        "status": "registered",
        "approval_id": str(approval.approval_id),
        "type": approval_type,
    }


# =============================================================================
# CONFIGURATION
# =============================================================================

@router.get("/config", response_model=AuditReadinessConfig)
async def get_config() -> AuditReadinessConfig:
    """Get audit readiness configuration."""
    return auditready_engine.get_config()


@router.put("/config")
async def update_config(
    passing_score: Optional[int] = Query(None, ge=0, le=100),
    lookback_days: Optional[int] = Query(None, ge=1),
    require_photo_for_waste: Optional[bool] = None,
) -> AuditReadinessConfig:
    """Update audit readiness configuration."""
    config = auditready_engine.get_config()
    
    if passing_score is not None:
        config.passing_score = passing_score
    if lookback_days is not None:
        config.lookback_days = lookback_days
    if require_photo_for_waste is not None:
        config.require_photo_for_waste = require_photo_for_waste
    
    auditready_engine.configure(config)
    return config


@router.delete("/data/clear")
async def clear_data() -> dict:
    """Clear all audit readiness data (for testing)."""
    auditready_engine.clear_data()
    return {"status": "cleared"}


# =============================================================================
# DEMO
# =============================================================================

@router.post("/demo/setup")
async def setup_demo() -> dict:
    """
    Set up demo data for audit readiness testing.
    
    Creates sample evidence with some gaps.
    """
    auditready_engine.clear_data()
    
    now = datetime.utcnow()
    
    # Good: Regular temperature logs (but with a gap)
    for hour in [0, 4, 8, 16, 20]:  # Missing 12:00 log
        evidence = EvidenceAsset(
            category=AuditCategory.FOOD_SAFETY,
            evidence_type=EvidenceType.TEMPERATURE_LOG,
            description=f"Walk-in cooler: 38°F",
            captured_at=now.replace(hour=hour, minute=0),
            captured_by="Kitchen Staff",
        )
        auditready_engine.register_evidence(evidence)
    
    # Good: Receiving documentation
    for vendor in ["Sysco", "US Foods"]:
        receipt = EvidenceAsset(
            category=AuditCategory.RECEIVING,
            evidence_type=EvidenceType.RECEIPT,
            description=f"Delivery from {vendor}",
            captured_at=now - timedelta(days=1),
        )
        auditready_engine.register_evidence(receipt)
        
        sig = EvidenceAsset(
            category=AuditCategory.RECEIVING,
            evidence_type=EvidenceType.SIGNATURE,
            description=f"Delivery signature for {vendor}",
            captured_at=now - timedelta(days=1),
        )
        auditready_engine.register_evidence(sig)
    
    # Partial: Weekly inventory (only 2 weeks of 4)
    for week in [1, 3]:
        inv = EvidenceAsset(
            category=AuditCategory.INVENTORY,
            evidence_type=EvidenceType.SCAN_RECORD,
            description="Weekly inventory count",
            captured_at=now - timedelta(weeks=week),
        )
        auditready_engine.register_evidence(inv)
    
    # Gap: Waste log without photo or approval
    waste = WasteLogEntry(
        product_id=uuid.uuid4(),
        product_name="Mixed Greens",
        quantity_wasted=Decimal("5"),
        unit="lb",
        reason="expired",
        wasted_at=now - timedelta(days=2),
        logged_by="Line Cook",
        has_photo=False,  # Missing!
        manager_approved=False,  # Missing!
    )
    auditready_engine.register_waste_log(waste)
    
    waste_evidence = EvidenceAsset(
        category=AuditCategory.WASTE,
        evidence_type=EvidenceType.DOCUMENT,
        description="Waste: 5 lb Mixed Greens - expired",
        captured_at=now - timedelta(days=2),
    )
    auditready_engine.register_evidence(waste_evidence)
    
    # Run assessment
    from datetime import timedelta
    result = auditready_engine.assess_readiness(30)
    
    return {
        "status": "demo_data_created",
        "evidence_registered": {
            "temperature_logs": 5,
            "receiving_docs": 4,
            "inventory_counts": 2,
            "waste_logs": 1,
        },
        "intentional_gaps": [
            "Missing temperature log at 12:00",
            "Missing weekly inventory for weeks 2 and 4",
            "Waste log missing photo",
            "Waste log missing manager approval",
        ],
        "assessment": {
            "audit_risk_score": result.audit_risk_score,
            "compliance_score": result.compliance_score,
            "would_pass_audit": result.would_pass_audit,
            "total_gaps": result.total_gaps,
            "critical_gaps": result.critical_gaps,
            "summary": result.summary,
        },
        "top_fixes": result.recommended_fixes[:5],
    }


# Import timedelta for demo
from datetime import timedelta
