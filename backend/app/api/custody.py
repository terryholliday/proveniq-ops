"""
PROVENIQ Ops - Chain of Custody API Routes
Bishop high-risk item tracking endpoints

GUARDRAILS:
- No disciplinary language
- This is TRACEABILITY, not surveillance
- Track movement without assigning blame
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query

from app.models.custody import (
    ActorRole,
    ChainGap,
    ChainStatus,
    CustodyAction,
    CustodyChain,
    CustodyConfig,
    CustodyHop,
    CustodyQuery,
    CustodyReport,
    DisposalEvent,
    ItemRiskLevel,
    PrepEvent,
    ReceivingEvent,
    TransferEvent,
)
from app.services.bishop.custody_engine import custody_engine

router = APIRouter(prefix="/custody", tags=["Chain of Custody"])


# =============================================================================
# CHAIN MANAGEMENT
# =============================================================================

@router.post("/chain", response_model=CustodyChain)
async def create_chain(
    item_id: uuid.UUID,
    product_id: Optional[uuid.UUID] = None,
    product_name: Optional[str] = None,
    batch_id: Optional[str] = None,
    lot_number: Optional[str] = None,
    risk_level: ItemRiskLevel = ItemRiskLevel.STANDARD,
) -> CustodyChain:
    """
    Create a new custody chain for an item.
    
    GUARDRAIL: This is traceability, not surveillance.
    """
    return custody_engine.create_chain(
        item_id=item_id,
        product_id=product_id,
        product_name=product_name,
        batch_id=batch_id,
        lot_number=lot_number,
        risk_level=risk_level,
    )


@router.get("/chain/{item_id}", response_model=CustodyChain)
async def get_chain(item_id: uuid.UUID) -> dict:
    """Get custody chain for an item."""
    chain = custody_engine.get_chain(item_id)
    if not chain:
        return {"error": "No custody chain for item", "item_id": str(item_id)}
    return chain.model_dump()


# =============================================================================
# HOP RECORDING
# =============================================================================

@router.post("/hop", response_model=CustodyHop)
async def append_hop(
    item_id: uuid.UUID,
    actor_role: ActorRole,
    action: CustodyAction,
    location_id: Optional[uuid.UUID] = None,
    location_name: Optional[str] = None,
    quantity: Optional[Decimal] = None,
    quantity_unit: Optional[str] = None,
    notes: Optional[str] = None,
    verified: bool = False,
    verification_method: Optional[str] = None,
) -> CustodyHop:
    """
    Append a custody hop to the chain.
    
    Each hop represents a state change for the item.
    """
    return custody_engine.append_hop(
        item_id=item_id,
        actor_role=actor_role,
        action=action,
        location_id=location_id,
        location_name=location_name,
        quantity=quantity,
        quantity_unit=quantity_unit,
        notes=notes,
        verified=verified,
        verification_method=verification_method,
    )


# =============================================================================
# EVENT PROCESSING
# =============================================================================

@router.post("/event/receiving")
async def process_receiving_event(
    item_id: uuid.UUID,
    product_id: uuid.UUID,
    vendor_id: uuid.UUID,
    vendor_name: str,
    quantity_received: Decimal,
    quantity_unit: str,
    location_id: uuid.UUID,
    location_name: str,
    po_number: Optional[str] = None,
    inspection_passed: bool = True,
    temperature_ok: Optional[bool] = None,
    packaging_ok: Optional[bool] = None,
) -> dict:
    """Process a receiving event into custody hop."""
    event = ReceivingEvent(
        item_id=item_id,
        product_id=product_id,
        vendor_id=vendor_id,
        vendor_name=vendor_name,
        quantity_received=quantity_received,
        quantity_unit=quantity_unit,
        location_id=location_id,
        location_name=location_name,
        po_number=po_number,
        inspection_passed=inspection_passed,
        temperature_ok=temperature_ok,
        packaging_ok=packaging_ok,
    )
    
    hop = custody_engine.process_receiving(event)
    chain = custody_engine.get_chain(item_id)
    
    return {
        "hop": hop.model_dump(),
        "chain_status": chain.status.value if chain else None,
        "total_hops": len(chain.custody_chain) if chain else 0,
    }


@router.post("/event/prep")
async def process_prep_event(
    item_id: uuid.UUID,
    prep_type: str,
    input_quantity: Decimal,
    quantity_unit: str,
    location_id: uuid.UUID,
    location_name: str,
    output_quantity: Optional[Decimal] = None,
) -> dict:
    """Process a prep event into custody hop."""
    event = PrepEvent(
        item_id=item_id,
        prep_type=prep_type,
        input_quantity=input_quantity,
        output_quantity=output_quantity,
        quantity_unit=quantity_unit,
        location_id=location_id,
        location_name=location_name,
    )
    
    hop = custody_engine.process_prep(event)
    chain = custody_engine.get_chain(item_id)
    
    return {
        "hop": hop.model_dump(),
        "chain_status": chain.status.value if chain else None,
    }


@router.post("/event/transfer")
async def process_transfer_event(
    item_id: uuid.UUID,
    from_location_id: uuid.UUID,
    from_location_name: str,
    to_location_id: uuid.UUID,
    to_location_name: str,
    quantity_transferred: Decimal,
    quantity_unit: str,
    sent_verified: bool = False,
    received_verified: bool = False,
) -> dict:
    """Process a transfer event into custody hops."""
    event = TransferEvent(
        item_id=item_id,
        from_location_id=from_location_id,
        from_location_name=from_location_name,
        to_location_id=to_location_id,
        to_location_name=to_location_name,
        quantity_transferred=quantity_transferred,
        quantity_unit=quantity_unit,
        sent_verified=sent_verified,
        received_verified=received_verified,
    )
    
    out_hop, in_hop = custody_engine.process_transfer(event)
    chain = custody_engine.get_chain(item_id)
    
    return {
        "outbound_hop": out_hop.model_dump(),
        "inbound_hop": in_hop.model_dump(),
        "chain_status": chain.status.value if chain else None,
    }


@router.post("/event/disposal")
async def process_disposal_event(
    item_id: uuid.UUID,
    disposal_type: str,
    disposal_reason: str,
    quantity_disposed: Decimal,
    quantity_unit: str,
    location_id: uuid.UUID,
    location_name: str,
    verified_by_role: Optional[ActorRole] = None,
) -> dict:
    """Process a disposal event into custody hop."""
    event = DisposalEvent(
        item_id=item_id,
        disposal_type=disposal_type,
        disposal_reason=disposal_reason,
        quantity_disposed=quantity_disposed,
        quantity_unit=quantity_unit,
        location_id=location_id,
        location_name=location_name,
        verified_by_role=verified_by_role,
    )
    
    hop = custody_engine.process_disposal(event)
    chain = custody_engine.get_chain(item_id)
    
    return {
        "hop": hop.model_dump(),
        "chain_status": chain.status.value if chain else None,
        "chain_closed": chain.chain_closed.isoformat() if chain and chain.chain_closed else None,
    }


# =============================================================================
# GAP DETECTION
# =============================================================================

@router.get("/gaps")
async def get_gaps(
    item_id: Optional[uuid.UUID] = None,
    unresolved_only: bool = False,
) -> dict:
    """
    Get detected gaps in custody chains.
    
    GUARDRAIL: Gaps are for traceability, not accusations.
    """
    gaps = custody_engine.get_gaps(
        item_id=item_id,
        unresolved_only=unresolved_only,
    )
    
    return {
        "count": len(gaps),
        "gaps": [g.model_dump() for g in gaps],
        "disclaimer": "Gap detection is for traceability. Not for disciplinary purposes.",
    }


@router.post("/gaps/{gap_id}/resolve")
async def resolve_gap(
    gap_id: uuid.UUID,
    resolution_notes: str,
) -> dict:
    """Mark a gap as resolved with notes."""
    success = custody_engine.resolve_gap(gap_id, resolution_notes)
    
    if success:
        return {"status": "resolved", "gap_id": str(gap_id)}
    return {"error": "Gap not found", "gap_id": str(gap_id)}


# =============================================================================
# QUERY
# =============================================================================

@router.get("/chains")
async def query_chains(
    product_id: Optional[uuid.UUID] = None,
    batch_id: Optional[str] = None,
    location_id: Optional[uuid.UUID] = None,
    risk_level: Optional[ItemRiskLevel] = None,
    status: Optional[ChainStatus] = None,
    has_gaps: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """Query custody chains with filters."""
    query = CustodyQuery(
        product_id=product_id,
        batch_id=batch_id,
        location_id=location_id,
        risk_level=risk_level,
        status=status,
        has_gaps=has_gaps,
    )
    
    chains = custody_engine.query_chains(query)[:limit]
    
    return {
        "count": len(chains),
        "chains": [c.model_dump() for c in chains],
    }


@router.get("/report", response_model=CustodyReport)
async def get_report() -> CustodyReport:
    """Generate custody report."""
    return custody_engine.get_report()


# =============================================================================
# CONFIGURATION
# =============================================================================

@router.get("/config", response_model=CustodyConfig)
async def get_config() -> CustodyConfig:
    """Get custody configuration."""
    return custody_engine.get_config()


@router.put("/config")
async def update_config(
    max_hours_between_hops: Optional[int] = Query(None, ge=1),
    auto_escalate_gaps: Optional[bool] = None,
) -> CustodyConfig:
    """Update custody configuration."""
    config = custody_engine.get_config()
    
    if max_hours_between_hops is not None:
        config.max_hours_between_hops = max_hours_between_hops
    if auto_escalate_gaps is not None:
        config.auto_escalate_gaps = auto_escalate_gaps
    
    custody_engine.configure(config)
    return config


@router.delete("/data/clear")
async def clear_data() -> dict:
    """Clear all custody data (for testing)."""
    custody_engine.clear_data()
    return {"status": "cleared"}


# =============================================================================
# DEMO
# =============================================================================

@router.post("/demo/setup")
async def setup_demo() -> dict:
    """
    Set up demo data for chain of custody testing.
    
    Creates sample chains with hops and gaps.
    """
    custody_engine.clear_data()
    
    # Location IDs
    receiving_dock = uuid.UUID("11111111-1111-1111-1111-111111111111")
    walk_in_cooler = uuid.UUID("22222222-2222-2222-2222-222222222222")
    prep_station = uuid.UUID("33333333-3333-3333-3333-333333333333")
    line_station = uuid.UUID("44444444-4444-4444-4444-444444444444")
    
    # Item 1: Chicken - complete chain with no gaps
    chicken_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    chicken_chain = custody_engine.create_chain(
        item_id=chicken_id,
        product_name="Chicken Breast Case",
        batch_id="BATCH-2024-001",
        lot_number="LOT-CHK-1234",
        risk_level=ItemRiskLevel.HIGH,
    )
    
    # Receiving
    custody_engine.append_hop(
        item_id=chicken_id,
        actor_role=ActorRole.RECEIVING_TEAM,
        action=CustodyAction.RECEIVED,
        location_id=receiving_dock,
        location_name="Receiving Dock",
        quantity=Decimal("40"),
        quantity_unit="lb",
        verified=True,
        verification_method="scan",
    )
    
    # Inspection
    custody_engine.append_hop(
        item_id=chicken_id,
        actor_role=ActorRole.RECEIVING_TEAM,
        action=CustodyAction.INSPECTED,
        location_id=receiving_dock,
        location_name="Receiving Dock",
        quantity=Decimal("40"),
        quantity_unit="lb",
        notes="Temperature: 38°F. Packaging intact.",
        verified=True,
    )
    
    # Storage
    custody_engine.append_hop(
        item_id=chicken_id,
        actor_role=ActorRole.STORAGE_TEAM,
        action=CustodyAction.STORED,
        location_id=walk_in_cooler,
        location_name="Walk-in Cooler",
        quantity=Decimal("40"),
        quantity_unit="lb",
    )
    
    # Prep retrieval
    custody_engine.append_hop(
        item_id=chicken_id,
        actor_role=ActorRole.PREP_TEAM,
        action=CustodyAction.RETRIEVED,
        location_id=walk_in_cooler,
        location_name="Walk-in Cooler",
        quantity=Decimal("20"),
        quantity_unit="lb",
    )
    
    # Prep
    custody_engine.append_hop(
        item_id=chicken_id,
        actor_role=ActorRole.PREP_TEAM,
        action=CustodyAction.PREPPED,
        location_id=prep_station,
        location_name="Prep Station A",
        quantity=Decimal("18"),
        quantity_unit="lb",
        notes="Trimmed and portioned",
    )
    
    # Item 2: Wine - regulated item with gap
    wine_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    wine_chain = custody_engine.create_chain(
        item_id=wine_id,
        product_name="Cooking Wine Case",
        batch_id="BATCH-2024-002",
        risk_level=ItemRiskLevel.REGULATED,
    )
    
    # Receiving
    custody_engine.append_hop(
        item_id=wine_id,
        actor_role=ActorRole.RECEIVING_TEAM,
        action=CustodyAction.RECEIVED,
        location_id=receiving_dock,
        location_name="Receiving Dock",
        quantity=Decimal("12"),
        quantity_unit="bottles",
        verified=True,
    )
    
    # Storage (with time gap - simulated by setting timestamp)
    from datetime import timedelta
    custody_engine.append_hop(
        item_id=wine_id,
        actor_role=ActorRole.STORAGE_TEAM,
        action=CustodyAction.STORED,
        location_id=walk_in_cooler,
        location_name="Secure Storage",
        quantity=Decimal("12"),
        quantity_unit="bottles",
        timestamp=datetime.utcnow() + timedelta(hours=30),  # 30h gap
    )
    
    # Item 3: Produce - disposed item
    produce_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    produce_chain = custody_engine.create_chain(
        item_id=produce_id,
        product_name="Mixed Greens",
        batch_id="BATCH-2024-003",
        risk_level=ItemRiskLevel.STANDARD,
    )
    
    custody_engine.append_hop(
        item_id=produce_id,
        actor_role=ActorRole.RECEIVING_TEAM,
        action=CustodyAction.RECEIVED,
        location_id=receiving_dock,
        location_name="Receiving Dock",
        quantity=Decimal("10"),
        quantity_unit="lb",
    )
    
    custody_engine.append_hop(
        item_id=produce_id,
        actor_role=ActorRole.STORAGE_TEAM,
        action=CustodyAction.STORED,
        location_id=walk_in_cooler,
        location_name="Walk-in Cooler",
        quantity=Decimal("10"),
        quantity_unit="lb",
    )
    
    # Partial disposal
    custody_engine.append_hop(
        item_id=produce_id,
        actor_role=ActorRole.MANAGER,
        action=CustodyAction.DISPOSED,
        location_id=walk_in_cooler,
        location_name="Walk-in Cooler",
        quantity=Decimal("2"),
        quantity_unit="lb",
        notes="expired: Past use-by date",
        verified=True,
    )
    
    # Get report
    report = custody_engine.get_report()
    gaps = custody_engine.get_gaps()
    
    return {
        "status": "demo_data_created",
        "chains_created": 3,
        "items": [
            {
                "name": "Chicken Breast",
                "risk_level": "HIGH",
                "hops": 5,
                "status": "active",
                "gaps": 0,
            },
            {
                "name": "Cooking Wine",
                "risk_level": "REGULATED",
                "hops": 2,
                "status": "gap_detected",
                "gaps": 1,
                "gap_reason": "30h time gap between receiving and storage",
            },
            {
                "name": "Mixed Greens",
                "risk_level": "STANDARD",
                "hops": 3,
                "status": "disposed",
                "gaps": 0,
            },
        ],
        "report_summary": {
            "total_chains": report.total_chains,
            "chains_with_gaps": report.chains_with_gaps,
            "high_risk_chains": report.high_risk_chains,
            "regulated_chains": report.regulated_chains,
        },
        "guardrail_reminder": "This is traceability, NOT surveillance. No disciplinary language.",
    }
