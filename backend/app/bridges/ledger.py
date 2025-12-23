"""
PROVENIQ Ops - Ledger Bridge

Writes inventory events to the PROVENIQ Ledger for immutable audit trail.
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID
import httpx

from pydantic import BaseModel

logger = logging.getLogger(__name__)

LEDGER_API_URL = "http://localhost:8006/api/v1"


class LedgerWriteResult(BaseModel):
    """Result of writing to the Ledger"""
    event_id: str
    sequence_number: int
    entry_hash: str
    created_at: str


class LedgerBridge:
    """
    Bridge to PROVENIQ Ledger for audit trail.
    
    Ops writes events for:
    - Inventory scans
    - Shrinkage detection
    - Order placements
    - Vendor deliveries
    """
    
    def __init__(self, base_url: str = LEDGER_API_URL):
        self.base_url = base_url
    
    async def write_event(
        self,
        event_type: str,
        asset_id: Optional[str],
        actor_id: str,
        payload: dict,
        correlation_id: Optional[str] = None,
    ) -> Optional[LedgerWriteResult]:
        """Write an event to the Ledger."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/events",
                    json={
                        "source": "ops",
                        "event_type": event_type,
                        "asset_id": asset_id,
                        "actor_id": actor_id,
                        "correlation_id": correlation_id,
                        "payload": payload,
                    },
                    timeout=10.0,
                )
                
                if response.status_code != 201:
                    logger.warning(f"[LEDGER] Write failed: {response.status_code}")
                    return None
                
                data = response.json()
                event_data = data.get("data", {}).get("event", data)
                
                return LedgerWriteResult(
                    event_id=event_data.get("eventId", event_data.get("event_id", "")),
                    sequence_number=event_data.get("sequenceNumber", event_data.get("sequence_number", 0)),
                    entry_hash=event_data.get("entryHash", event_data.get("entry_hash", "")),
                    created_at=event_data.get("createdAt", event_data.get("created_at", "")),
                )
        except Exception as e:
            logger.error(f"[LEDGER] Write error: {e}")
            return None
    
    async def write_scan_completed(
        self,
        location_id: str,
        user_id: str,
        items_scanned: int,
        discrepancies_found: int,
    ) -> Optional[LedgerWriteResult]:
        """Record inventory scan completion."""
        return await self.write_event(
            event_type="OPS_SCAN_COMPLETED",
            asset_id=None,
            actor_id=user_id,
            payload={
                "location_id": location_id,
                "items_scanned": items_scanned,
                "discrepancies_found": discrepancies_found,
                "scanned_at": datetime.utcnow().isoformat(),
            },
        )
    
    async def write_shrinkage_detected(
        self,
        location_id: str,
        item_id: str,
        item_name: str,
        quantity_lost: float,
        unit_cost_cents: int,
        shrinkage_type: str,
        detected_by: str,
    ) -> Optional[LedgerWriteResult]:
        """Record shrinkage detection."""
        return await self.write_event(
            event_type="OPS_SHRINKAGE_DETECTED",
            asset_id=item_id,
            actor_id=detected_by,
            payload={
                "location_id": location_id,
                "item_name": item_name,
                "quantity_lost": quantity_lost,
                "unit_cost_cents": unit_cost_cents,
                "total_loss_cents": int(quantity_lost * unit_cost_cents),
                "shrinkage_type": shrinkage_type,
                "detected_at": datetime.utcnow().isoformat(),
            },
        )
    
    async def write_order_placed(
        self,
        location_id: str,
        order_id: str,
        vendor_id: str,
        total_cents: int,
        item_count: int,
        placed_by: str,
    ) -> Optional[LedgerWriteResult]:
        """Record order placement."""
        return await self.write_event(
            event_type="OPS_ORDER_PLACED",
            asset_id=order_id,
            actor_id=placed_by,
            payload={
                "location_id": location_id,
                "vendor_id": vendor_id,
                "total_cents": total_cents,
                "item_count": item_count,
                "placed_at": datetime.utcnow().isoformat(),
            },
        )
    
    async def write_delivery_received(
        self,
        location_id: str,
        order_id: str,
        vendor_id: str,
        items_received: int,
        items_rejected: int,
        received_by: str,
    ) -> Optional[LedgerWriteResult]:
        """Record delivery receipt."""
        return await self.write_event(
            event_type="OPS_DELIVERY_RECEIVED",
            asset_id=order_id,
            actor_id=received_by,
            payload={
                "location_id": location_id,
                "vendor_id": vendor_id,
                "items_received": items_received,
                "items_rejected": items_rejected,
                "received_at": datetime.utcnow().isoformat(),
            },
        )


# Singleton
_ledger_instance: Optional[LedgerBridge] = None


def get_ledger_bridge() -> LedgerBridge:
    """Get the Ledger bridge instance."""
    global _ledger_instance
    if _ledger_instance is None:
        _ledger_instance = LedgerBridge()
    return _ledger_instance
