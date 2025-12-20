"""BISHOP Scan Service - AI Vision Analysis for Shelf Scanning"""
import hashlib
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.bishop.models import BishopScan, BishopScanStatus, BishopShelf, BishopItem


class ScanService:
    """Service for managing shelf scans and AI vision analysis."""

    def __init__(self, db: Session):
        self.db = db

    def create_scan(
        self,
        location_id: UUID,
        scanned_by_id: UUID,
        shelf_id: UUID | None = None,
        image_url: str | None = None,
    ) -> BishopScan:
        """Create a new scan record."""
        image_hash = None
        if image_url:
            # In production, this would hash the actual image bytes
            image_hash = hashlib.sha512(image_url.encode()).hexdigest()

        scan = BishopScan(
            location_id=location_id,
            shelf_id=shelf_id,
            scanned_by_id=scanned_by_id,
            status=BishopScanStatus.IDLE,
            image_url=image_url,
            image_hash=image_hash,
            started_at=datetime.utcnow(),
        )
        self.db.add(scan)
        self.db.commit()
        self.db.refresh(scan)
        return scan

    def get_scan(self, scan_id: UUID) -> BishopScan | None:
        """Get a scan by ID."""
        return self.db.query(BishopScan).filter(BishopScan.id == scan_id).first()

    def analyze_image(self, image_url: str, shelf: BishopShelf | None = None) -> dict[str, Any]:
        """
        Analyze a shelf image using AI vision.
        
        In production, this would call an AI vision API (e.g., OpenAI Vision, Google Vision).
        Returns detected items and their quantities.
        """
        # MOCK: Simulated AI vision response
        detected_items = {
            "items": [
                {"sku": "SYSCO-001", "name": "Tomato Sauce Case", "detected_quantity": 8},
                {"sku": "SYSCO-002", "name": "Olive Oil 1gal", "detected_quantity": 3},
                {"sku": "USF-101", "name": "Flour 50lb Bag", "detected_quantity": 2},
            ],
            "confidence": 0.92,
            "scan_quality": "good",
        }

        discrepancies = []
        if shelf and shelf.expected_inventory:
            # Compare detected vs expected
            expected = shelf.expected_inventory
            for item in detected_items["items"]:
                sku = item["sku"]
                if sku in expected:
                    expected_qty = expected[sku]
                    detected_qty = item["detected_quantity"]
                    if detected_qty != expected_qty:
                        discrepancies.append({
                            "sku": sku,
                            "name": item["name"],
                            "expected": expected_qty,
                            "detected": detected_qty,
                            "difference": detected_qty - expected_qty,
                        })

        return {
            "detected_items": detected_items,
            "discrepancies": discrepancies,
        }

    def calculate_risk_score(self, discrepancies: list[dict[str, Any]]) -> float:
        """
        Calculate a risk score (0-100) based on discrepancies.
        
        Higher score = higher risk of shrinkage/issues.
        """
        if not discrepancies:
            return 0.0

        total_variance = sum(abs(d.get("difference", 0)) for d in discrepancies)
        total_items = len(discrepancies)

        # Simple scoring: more variance = higher risk
        base_score = min(total_variance * 5, 50)  # Up to 50 from variance
        frequency_score = min(total_items * 10, 50)  # Up to 50 from frequency

        return min(base_score + frequency_score, 100.0)

    def generate_suggested_order(
        self,
        shelf: BishopShelf,
        detected_items: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Generate a suggested order based on detected inventory vs par levels.
        
        Returns None if no items need reordering.
        """
        items_to_order = []
        
        # Get items on this shelf
        shelf_items = self.db.query(BishopItem).filter(BishopItem.shelf_id == shelf.id).all()
        
        detected_by_sku = {
            item["sku"]: item["detected_quantity"]
            for item in detected_items.get("items", [])
        }

        for item in shelf_items:
            detected_qty = detected_by_sku.get(item.sku, 0)
            
            if item.reorder_point and detected_qty <= item.reorder_point:
                # Calculate order quantity to reach par level
                order_qty = (item.par_level or item.reorder_point * 2) - detected_qty
                if order_qty > 0:
                    items_to_order.append({
                        "sku": item.sku,
                        "vendor_sku": item.vendor_sku,
                        "name": item.name,
                        "quantity": order_qty,
                        "unit": item.quantity_unit,
                        "unit_cost": item.unit_cost,
                        "line_total": order_qty * (item.unit_cost or 0),
                        "vendor": item.vendor_name,
                    })

        if not items_to_order:
            return None

        total = sum(item["line_total"] for item in items_to_order)

        return {
            "items": items_to_order,
            "total": total,
            "generated_at": datetime.utcnow().isoformat(),
        }
