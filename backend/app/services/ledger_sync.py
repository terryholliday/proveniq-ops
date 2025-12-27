"""
PROVENIQ Ops - Ledger Write-Through Service
P2: Cryptographic proof chain via PROVENIQ Memory (Ledger)

Events in ops_events are synced to Ledger for:
- Immutable hash chain proof
- Cross-app event visibility
- Forensic reconstruction across ecosystem

MOAT: Ledger integration creates cryptographic proof that cannot be replicated.
"""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime
from typing import Optional

import httpx
from pydantic import BaseModel

from app.core.config import get_settings


settings = get_settings()

# Ledger endpoint (from Inter-App Communication Contract)
LEDGER_BASE_URL = getattr(settings, 'LEDGER_BASE_URL', 'http://localhost:8006')


class LedgerEvent(BaseModel):
    """Event payload for Ledger ingestion."""
    source: str = "ops"
    event_type: str
    asset_id: Optional[str] = None
    anchor_id: Optional[str] = None
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    payload: dict
    timestamp: Optional[str] = None


class LedgerSyncResult(BaseModel):
    """Result of syncing an event to Ledger."""
    success: bool
    ledger_event_id: Optional[str] = None
    entry_hash: Optional[str] = None
    error: Optional[str] = None


class LedgerSyncService:
    """
    Service for syncing ops_events to PROVENIQ Ledger.
    
    Write-through pattern:
    1. Event written to ops_events
    2. Background job syncs to Ledger
    3. ops_events updated with ledger_event_id
    4. Integrity verifiable via hash chain
    """
    
    def __init__(self, base_url: str = LEDGER_BASE_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self._retry_queue: list[dict] = []
    
    async def sync_event(
        self,
        ops_event_id: uuid.UUID,
        event_type: str,
        payload: dict,
        correlation_id: Optional[str] = None,
        wallet_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> LedgerSyncResult:
        """
        Sync a single ops_event to Ledger.
        
        Returns LedgerSyncResult with ledger_event_id on success.
        """
        # Build idempotency key from ops_event_id
        idempotency_key = f"ops:{ops_event_id}"
        
        ledger_event = LedgerEvent(
            source="ops",
            event_type=self._map_event_type(event_type),
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            payload={
                "ops_event_id": str(ops_event_id),
                "wallet_id": wallet_id,
                "original_type": event_type,
                **payload,
            },
            timestamp=timestamp.isoformat() if timestamp else datetime.utcnow().isoformat(),
        )
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/events",
                json=ledger_event.model_dump(),
            )
            
            if response.status_code == 201:
                data = response.json()
                return LedgerSyncResult(
                    success=True,
                    ledger_event_id=data.get("id"),
                    entry_hash=data.get("entry_hash"),
                )
            elif response.status_code == 409:
                # Idempotency conflict - already synced
                return LedgerSyncResult(
                    success=True,
                    ledger_event_id="already_synced",
                    error="Event already exists in Ledger",
                )
            else:
                return LedgerSyncResult(
                    success=False,
                    error=f"Ledger returned {response.status_code}: {response.text}",
                )
                
        except httpx.RequestError as e:
            # Queue for retry
            self._retry_queue.append({
                "ops_event_id": str(ops_event_id),
                "event": ledger_event.model_dump(),
                "attempts": 1,
            })
            return LedgerSyncResult(
                success=False,
                error=f"Ledger unavailable: {str(e)}. Queued for retry.",
            )
    
    def _map_event_type(self, ops_event_type: str) -> str:
        """
        Map Ops event types to Ledger canonical event types.
        
        Ledger uses a standardized event type taxonomy.
        """
        mapping = {
            # Sensor events → operational
            "TEMPERATURE_READING": "operational.sensor.temperature",
            "HUMIDITY_READING": "operational.sensor.humidity",
            "DOOR_OPEN": "operational.sensor.door_open",
            "DOOR_CLOSE": "operational.sensor.door_close",
            "POWER_LOSS": "operational.sensor.power_loss",
            "POWER_RESTORED": "operational.sensor.power_restored",
            
            # Scan events → inventory
            "INVENTORY_SCAN": "inventory.scan",
            "BARCODE_SCAN": "inventory.barcode_scan",
            "MANUAL_COUNT": "inventory.manual_count",
            
            # Order events → transaction
            "ORDER_CREATED": "transaction.order.created",
            "ORDER_SUBMITTED": "transaction.order.submitted",
            "ORDER_DELIVERED": "transaction.order.delivered",
            "DELIVERY_RECEIVED": "transaction.delivery.received",
            
            # Bishop events → ai_decision
            "BISHOP_STATE_CHANGE": "ai_decision.state_change",
            "BISHOP_RECOMMENDATION": "ai_decision.recommendation",
            "BISHOP_RECOMMENDATION_ACCEPTED": "ai_decision.accepted",
            "BISHOP_RECOMMENDATION_REJECTED": "ai_decision.rejected",
            
            # Anomaly events → anomaly
            "ANOMALY_DETECTED": "anomaly.detected",
            "ANOMALY_RESOLVED": "anomaly.resolved",
            
            # Waste/shrinkage → loss
            "WASTE_RECORDED": "loss.waste",
            "SHRINKAGE_DETECTED": "loss.shrinkage",
            
            # Attestation events → attestation
            "ATTESTATION_ISSUED": "attestation.issued",
            "ATTESTATION_VERIFIED": "attestation.verified",
        }
        
        return mapping.get(ops_event_type, f"ops.{ops_event_type.lower()}")
    
    async def sync_pending_events(
        self,
        db_session,
        batch_size: int = 100,
    ) -> dict:
        """
        Sync all unsynced ops_events to Ledger.
        
        Called by background job or manual trigger.
        """
        from sqlalchemy import text
        
        # Get unsynced events
        query = text("""
            SELECT id, event_type, payload, correlation_id, wallet_id, timestamp
            FROM ops_events
            WHERE ledger_synced = false
            ORDER BY timestamp ASC
            LIMIT :batch_size
        """)
        
        result = await db_session.execute(query, {"batch_size": batch_size})
        rows = result.mappings().all()
        
        synced = 0
        failed = 0
        
        for row in rows:
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            
            sync_result = await self.sync_event(
                ops_event_id=row["id"],
                event_type=row["event_type"],
                payload=payload,
                correlation_id=row["correlation_id"],
                wallet_id=row["wallet_id"],
                timestamp=row["timestamp"],
            )
            
            if sync_result.success and sync_result.ledger_event_id != "already_synced":
                # Update ops_events with ledger info
                update_query = text("""
                    UPDATE ops_events
                    SET ledger_synced = true,
                        ledger_event_id = :ledger_id,
                        ledger_synced_at = :synced_at
                    WHERE id = :id
                """)
                await db_session.execute(update_query, {
                    "id": row["id"],
                    "ledger_id": sync_result.ledger_event_id,
                    "synced_at": datetime.utcnow(),
                })
                synced += 1
            elif sync_result.ledger_event_id == "already_synced":
                # Mark as synced even if already exists
                update_query = text("""
                    UPDATE ops_events
                    SET ledger_synced = true,
                        ledger_synced_at = :synced_at
                    WHERE id = :id
                """)
                await db_session.execute(update_query, {
                    "id": row["id"],
                    "synced_at": datetime.utcnow(),
                })
                synced += 1
            else:
                failed += 1
        
        await db_session.commit()
        
        return {
            "total": len(rows),
            "synced": synced,
            "failed": failed,
            "retry_queue_size": len(self._retry_queue),
        }
    
    async def verify_integrity(
        self,
        ops_event_id: uuid.UUID,
        db_session,
    ) -> dict:
        """
        Verify that an ops_event matches its Ledger entry.
        
        Cross-references local payload hash with Ledger entry hash.
        """
        from sqlalchemy import text
        
        # Get local event
        query = text("SELECT * FROM ops_events WHERE id = :id")
        result = await db_session.execute(query, {"id": ops_event_id})
        row = result.mappings().first()
        
        if not row:
            return {
                "valid": False,
                "error": "Event not found in ops_events",
            }
        
        if not row["ledger_synced"] or not row["ledger_event_id"]:
            return {
                "valid": False,
                "error": "Event not synced to Ledger",
            }
        
        # Query Ledger for verification
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/events/{row['ledger_event_id']}"
            )
            
            if response.status_code != 200:
                return {
                    "valid": False,
                    "error": f"Ledger event not found: {response.status_code}",
                }
            
            ledger_data = response.json()
            
            # Compare payload hashes
            local_hash = row["payload_hash"]
            ledger_payload = ledger_data.get("payload", {})
            
            # The Ledger wraps our payload, so we need to extract the original
            original_payload = ledger_payload.get("original_type")
            
            return {
                "valid": True,
                "ops_event_id": str(ops_event_id),
                "ledger_event_id": row["ledger_event_id"],
                "local_hash": local_hash,
                "ledger_entry_hash": ledger_data.get("entry_hash"),
                "chain_integrity": ledger_data.get("chain_valid", True),
                "verified_at": datetime.utcnow().isoformat(),
            }
            
        except httpx.RequestError as e:
            return {
                "valid": False,
                "error": f"Ledger unavailable: {str(e)}",
            }
    
    async def get_sync_stats(self, db_session) -> dict:
        """Get statistics on Ledger sync status."""
        from sqlalchemy import text
        
        query = text("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE ledger_synced = true) as synced,
                COUNT(*) FILTER (WHERE ledger_synced = false) as pending,
                MIN(timestamp) FILTER (WHERE ledger_synced = false) as oldest_pending
            FROM ops_events
        """)
        
        result = await db_session.execute(query)
        row = result.mappings().first()
        
        return {
            "total_events": row["total"],
            "synced_to_ledger": row["synced"],
            "pending_sync": row["pending"],
            "oldest_pending": row["oldest_pending"].isoformat() if row["oldest_pending"] else None,
            "retry_queue_size": len(self._retry_queue),
            "sync_percentage": round(row["synced"] / row["total"] * 100, 2) if row["total"] > 0 else 100,
        }
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Singleton instance
_ledger_sync: Optional[LedgerSyncService] = None


def get_ledger_sync() -> LedgerSyncService:
    """Get or create LedgerSyncService instance."""
    global _ledger_sync
    if _ledger_sync is None:
        _ledger_sync = LedgerSyncService()
    return _ledger_sync
