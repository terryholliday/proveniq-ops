"""BISHOP Shrinkage Service - Detection, Classification, and Reporting"""
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.bishop.models import ShrinkageEvent, ShrinkageType, BishopItem, BishopScan


class ShrinkageService:
    """Service for managing shrinkage detection and reporting."""

    def __init__(self, db: Session):
        self.db = db

    def create_event(
        self,
        location_id: UUID,
        shrinkage_type: ShrinkageType,
        quantity_lost: int,
        item_id: UUID | None = None,
        scan_id: UUID | None = None,
        sku: str | None = None,
        item_name: str | None = None,
        unit_cost: float | None = None,
        notes: str | None = None,
        evidence_url: str | None = None,
    ) -> ShrinkageEvent:
        """Create a new shrinkage event."""
        # Calculate total loss value
        total_loss_value = None
        if unit_cost:
            total_loss_value = quantity_lost * unit_cost

        event = ShrinkageEvent(
            location_id=location_id,
            item_id=item_id,
            scan_id=scan_id,
            shrinkage_type=shrinkage_type,
            sku=sku,
            item_name=item_name,
            quantity_lost=quantity_lost,
            unit_cost=unit_cost,
            total_loss_value=total_loss_value,
            notes=notes,
            evidence_url=evidence_url,
            detected_at=datetime.utcnow(),
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def detect_from_scan(
        self,
        scan: BishopScan,
        discrepancies: list[dict[str, Any]],
    ) -> list[ShrinkageEvent]:
        """
        Automatically detect shrinkage from scan discrepancies.
        
        Only creates events for negative discrepancies (missing items).
        """
        events = []

        for disc in discrepancies:
            difference = disc.get("difference", 0)
            
            # Only flag negative discrepancies (items missing)
            if difference < 0:
                # Try to get item details
                item = self.db.query(BishopItem).filter(
                    BishopItem.sku == disc.get("sku")
                ).first()

                unit_cost = item.unit_cost if item else None

                event = self.create_event(
                    location_id=scan.location_id,
                    shrinkage_type=ShrinkageType.UNKNOWN,  # Needs classification
                    quantity_lost=abs(difference),
                    item_id=item.id if item else None,
                    scan_id=scan.id,
                    sku=disc.get("sku"),
                    item_name=disc.get("name"),
                    unit_cost=unit_cost,
                    notes=f"Auto-detected from scan. Expected: {disc.get('expected')}, Found: {disc.get('detected')}",
                )
                events.append(event)

        return events

    def classify_event(
        self,
        event: ShrinkageEvent,
        shrinkage_type: ShrinkageType,
        notes: str | None = None,
    ) -> ShrinkageEvent:
        """Classify/reclassify a shrinkage event."""
        event.shrinkage_type = shrinkage_type
        if notes:
            existing_notes = event.notes or ""
            event.notes = f"{existing_notes}\n[Classification]: {notes}".strip()
        
        self.db.commit()
        self.db.refresh(event)
        return event

    def resolve_event(self, event: ShrinkageEvent) -> ShrinkageEvent:
        """Mark a shrinkage event as resolved."""
        event.resolved = True
        event.resolved_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_report(
        self,
        location_id: UUID,
        days: int = 30,
    ) -> dict[str, Any]:
        """
        Generate a shrinkage report for a location.
        
        Args:
            location_id: Location to report on
            days: Number of days to include in report
            
        Returns:
            Aggregated shrinkage data
        """
        period_start = datetime.utcnow() - timedelta(days=days)
        period_end = datetime.utcnow()

        # Query events in period
        events = self.db.query(ShrinkageEvent).filter(
            ShrinkageEvent.location_id == location_id,
            ShrinkageEvent.detected_at >= period_start,
        ).all()

        # Aggregate by type
        by_type: dict[str, float] = {}
        for event in events:
            type_key = event.shrinkage_type.value
            by_type[type_key] = by_type.get(type_key, 0) + (event.total_loss_value or 0)

        # Top shrinkage items
        item_losses: dict[str, dict[str, Any]] = {}
        for event in events:
            sku = event.sku or "UNKNOWN"
            if sku not in item_losses:
                item_losses[sku] = {
                    "sku": sku,
                    "name": event.item_name,
                    "total_quantity": 0,
                    "total_value": 0,
                    "events": 0,
                }
            item_losses[sku]["total_quantity"] += event.quantity_lost
            item_losses[sku]["total_value"] += event.total_loss_value or 0
            item_losses[sku]["events"] += 1

        top_items = sorted(
            item_losses.values(),
            key=lambda x: x["total_value"],
            reverse=True,
        )[:10]

        return {
            "location_id": str(location_id),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "total_events": len(events),
            "total_loss_value": sum(e.total_loss_value or 0 for e in events),
            "by_type": by_type,
            "top_items": top_items,
            "resolved_count": sum(1 for e in events if e.resolved),
            "unresolved_count": sum(1 for e in events if not e.resolved),
        }
