"""
PROVENIQ Ops - Smart Receiving API Routes
Bishop scan-to-PO reconciliation endpoints
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.models.receiving import (
    AcceptReceivingRequest,
    DockScan,
    POLineItem,
    POStatus,
    PurchaseOrder,
    ReceivingReconciliation,
    ReceivingResponse,
    ReceivingSession,
    VendorSubstitutionRule,
)
from app.services.bishop.receiving_engine import receiving_engine

router = APIRouter(prefix="/receiving", tags=["Smart Receiving"])


# =============================================================================
# SESSION MANAGEMENT
# =============================================================================

@router.post("/session/start", response_model=ReceivingSession)
async def start_receiving_session(po_id: uuid.UUID) -> ReceivingSession:
    """
    Start a new receiving session for a purchase order.
    
    Initiates scan-to-PO reconciliation workflow.
    """
    try:
        return receiving_engine.start_session(po_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/session/{session_id}", response_model=ReceivingSession)
async def get_session(session_id: uuid.UUID) -> ReceivingSession:
    """Get an active receiving session."""
    session = receiving_engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


@router.post("/session/{session_id}/scan", response_model=DockScan)
async def add_dock_scan(
    session_id: uuid.UUID,
    barcode: str,
    quantity: int,
    condition: str = "good",
    lot_number: Optional[str] = None,
    expiry_date: Optional[datetime] = None,
) -> DockScan:
    """
    Add a scan to an active receiving session.
    
    Barcode is automatically matched to product if registered.
    """
    scan = DockScan(
        barcode=barcode,
        quantity_scanned=quantity,
        condition=condition,
        lot_number=lot_number,
        expiry_date=expiry_date,
    )
    try:
        return receiving_engine.add_scan(session_id, scan)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# RECONCILIATION
# =============================================================================

@router.post("/session/{session_id}/reconcile", response_model=ReceivingReconciliation)
async def reconcile_session(session_id: uuid.UUID) -> ReceivingReconciliation:
    """
    Reconcile scans against PO.
    
    Bishop Logic:
        1. Match scans to PO line items
        2. Detect shorts, overages, substitutions, damage flags
        3. Generate adjustment proposal
    
    Returns discrepancy report with recommended action.
    """
    try:
        return receiving_engine.reconcile(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/session/{session_id}/accept", response_model=ReceivingResponse)
async def accept_receiving(
    session_id: uuid.UUID,
    accept_substitutions: bool = False,
    accept_shorts: bool = False,
    notes: Optional[str] = None,
) -> ReceivingResponse:
    """
    Accept receiving with adjustments.
    
    GUARDRAIL: Never closes PO without explicit confirmation.
    """
    request = AcceptReceivingRequest(
        session_id=session_id,
        accept_substitutions=accept_substitutions,
        accept_shorts=accept_shorts,
        notes=notes,
    )
    return receiving_engine.accept_receiving(request)


# =============================================================================
# PURCHASE ORDER MANAGEMENT
# =============================================================================

@router.get("/po/{po_id}", response_model=PurchaseOrder)
async def get_purchase_order(po_id: uuid.UUID) -> PurchaseOrder:
    """Get a registered purchase order."""
    po = receiving_engine.get_purchase_order(po_id)
    if not po:
        raise HTTPException(status_code=404, detail=f"PO {po_id} not found")
    return po


@router.post("/po/register", response_model=dict)
async def register_purchase_order(po: PurchaseOrder) -> dict:
    """Register a purchase order for receiving."""
    receiving_engine.register_purchase_order(po)
    return {"status": "registered", "po_id": str(po.po_id)}


# =============================================================================
# DATA REGISTRATION (for testing/setup)
# =============================================================================

@router.post("/data/barcode")
async def register_barcode(
    barcode: str,
    product_id: uuid.UUID,
    product_name: str,
) -> dict:
    """Register barcode to product mapping."""
    receiving_engine.register_barcode(barcode, product_id, product_name)
    return {"status": "registered", "barcode": barcode}


@router.post("/data/substitution")
async def register_substitution_rule(
    vendor_id: uuid.UUID,
    original_product_id: uuid.UUID,
    substitute_product_id: uuid.UUID,
    substitute_sku: str,
    price_adjustment: Decimal = Decimal("0.00"),
    requires_approval: bool = True,
) -> dict:
    """Register a vendor substitution rule."""
    rule = VendorSubstitutionRule(
        vendor_id=vendor_id,
        original_product_id=original_product_id,
        substitute_product_id=substitute_product_id,
        substitute_sku=substitute_sku,
        price_adjustment=price_adjustment,
        requires_approval=requires_approval,
    )
    receiving_engine.register_substitution_rule(rule)
    return {"status": "registered"}


@router.delete("/data/clear")
async def clear_receiving_data() -> dict:
    """Clear all receiving engine data (for testing)."""
    receiving_engine.clear_data()
    return {"status": "cleared"}


# =============================================================================
# DEMO DATA
# =============================================================================

@router.post("/demo/setup")
async def setup_demo_data() -> dict:
    """
    Set up demo data for receiving workflow testing.
    
    Creates a sample PO with products ready for receiving.
    """
    receiving_engine.clear_data()
    
    # IDs
    po_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    vendor_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    
    product1_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    product2_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    product3_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    substitute_id = uuid.UUID("44444444-4444-4444-4444-444444444444")
    
    # Register barcodes
    receiving_engine.register_barcode("012345678901", product1_id, "Chicken Breast 5lb")
    receiving_engine.register_barcode("012345678902", product2_id, "Tomato Paste 6oz")
    receiving_engine.register_barcode("012345678903", product3_id, "Rice 25lb Bag")
    receiving_engine.register_barcode("012345678904", substitute_id, "Tomato Sauce 6oz")
    
    # Register substitution rule (Tomato Paste -> Tomato Sauce allowed)
    receiving_engine.register_substitution_rule(VendorSubstitutionRule(
        vendor_id=vendor_id,
        original_product_id=product2_id,
        substitute_product_id=substitute_id,
        substitute_sku="TOM-SAUCE-6OZ",
        requires_approval=True,
    ))
    
    # Create PO
    po = PurchaseOrder(
        po_id=po_id,
        po_number="PO-2024-001234",
        vendor_id=vendor_id,
        vendor_name="Sysco",
        order_date=datetime.utcnow() - timedelta(days=2),
        expected_delivery=datetime.utcnow(),
        line_items=[
            POLineItem(
                line_id=uuid.uuid4(),
                product_id=product1_id,
                product_name="Chicken Breast 5lb",
                vendor_sku="CHK-BRST-5LB",
                quantity_ordered=10,
                unit_price=Decimal("12.50"),
            ),
            POLineItem(
                line_id=uuid.uuid4(),
                product_id=product2_id,
                product_name="Tomato Paste 6oz",
                vendor_sku="TOM-PASTE-6OZ",
                quantity_ordered=24,
                unit_price=Decimal("1.25"),
            ),
            POLineItem(
                line_id=uuid.uuid4(),
                product_id=product3_id,
                product_name="Rice 25lb Bag",
                vendor_sku="RICE-25LB",
                quantity_ordered=5,
                unit_price=Decimal("18.99"),
            ),
        ],
    )
    receiving_engine.register_purchase_order(po)
    
    return {
        "status": "demo_data_created",
        "po_id": str(po_id),
        "po_number": "PO-2024-001234",
        "barcodes": {
            "012345678901": "Chicken Breast 5lb (10 ordered)",
            "012345678902": "Tomato Paste 6oz (24 ordered)",
            "012345678903": "Rice 25lb Bag (5 ordered)",
            "012345678904": "Tomato Sauce 6oz (SUBSTITUTE for Tomato Paste)",
        },
        "test_scenarios": [
            "Scan all items exactly → RECEIVING_COMPLETE",
            "Scan 8 chicken instead of 10 → SHORT",
            "Scan 012345678904 instead of 012345678902 → SUBSTITUTION",
            "Scan with condition='damaged' → DAMAGED",
        ],
    }
