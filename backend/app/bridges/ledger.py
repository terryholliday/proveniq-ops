"""
PROVENIQ Ops - Ledger Bridge

CANONICAL SCHEMA v1.0.0
- Uses DOMAIN_NOUN_VERB_PAST event naming
- Publishes to /api/v1/events/canonical endpoint
- Includes idempotency_key for duplicate prevention
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4
import httpx

from pydantic import BaseModel

logger = logging.getLogger(__name__)

LEDGER_API_URL = "http://localhost:8006"
SCHEMA_VERSION = "1.0.0"
PRODUCER = "ops"
PRODUCER_VERSION = "1.0.0"


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
    
    def _hash_payload(self, payload: dict) -> str:
        """Calculate SHA256 hash of payload."""
        payload_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(payload_str.encode()).hexdigest()

    async def write_event(
        self,
        event_type: str,
        asset_id: Optional[str],
        actor_id: str,
        payload: dict,
        correlation_id: Optional[str] = None,
    ) -> Optional[LedgerWriteResult]:
        """Write a canonical event to the Ledger."""
        corr_id = correlation_id or str(uuid4())
        idempotency_key = f"ops_{uuid4()}"
        occurred_at = datetime.utcnow().isoformat() + "Z"
        canonical_hash = self._hash_payload(payload)

        canonical_event = {
            "schema_version": SCHEMA_VERSION,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "committed_at": occurred_at,
            "correlation_id": corr_id,
            "idempotency_key": idempotency_key,
            "producer": PRODUCER,
            "producer_version": PRODUCER_VERSION,
            "subject": {
                "asset_id": asset_id or "SYSTEM",
            },
            "payload": {
                **payload,
                "actor_id": actor_id,
            },
            "canonical_hash_hex": canonical_hash,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/events/canonical",
                    json=canonical_event,
                    timeout=10.0,
                )
                
                if response.status_code not in (200, 201):
                    logger.warning(f"[LEDGER] Write failed: {response.status_code} {response.text}")
                    return None
                
                data = response.json()
                
                return LedgerWriteResult(
                    event_id=data.get("event_id", ""),
                    sequence_number=data.get("sequence_number", 0),
                    entry_hash=data.get("entry_hash", ""),
                    created_at=data.get("committed_at", ""),
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
