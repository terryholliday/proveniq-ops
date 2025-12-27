"""
PROVENIQ Ops - Persistent Event Store
Phase 0-1: DATA GRAVITY

This is the foundation of the moat. Every event is:
- Persisted to PostgreSQL (append-only)
- Hashed for integrity
- Synced to Ledger for external auditability

After 6-12 months, customers cannot migrate without losing this truth.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def canonicalize(data: Any) -> str:
    """Canonicalize JSON payload for hashing (sort keys, consistent formatting)."""
    return json.dumps(data, sort_keys=True, separators=(',', ':'), cls=DecimalEncoder)


def hash_payload(data: Any) -> str:
    """SHA-256 hash of canonical payload."""
    canonical = canonicalize(data)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


class PersistentEventStore:
    """
    Persistent event store for Ops.
    
    DATA GRAVITY PRINCIPLE:
    - Every event is append-only (never update, never delete)
    - Events are hashed for integrity verification
    - Events sync to external Ledger for auditability
    - After months of use, this data cannot be replicated elsewhere
    
    This replaces the in-memory EventPublisher._event_log
    """
    
    async def append(
        self,
        event_type: str,
        payload: Dict[str, Any],
        wallet_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Append an event to the persistent store.
        
        Returns the stored event with its ID and hash.
        """
        event_id = uuid.uuid4()
        timestamp = datetime.now(timezone.utc)
        correlation_id = correlation_id or str(uuid.uuid4())
        idempotency_key = idempotency_key or str(uuid.uuid4())
        
        # Hash the payload for integrity
        payload_hash = hash_payload(payload)
        
        async with async_session_maker() as session:
            # Check idempotency
            from sqlalchemy import text
            existing = await session.execute(
                text("SELECT id FROM ops_events WHERE idempotency_key = :key"),
                {"key": idempotency_key}
            )
            if existing.fetchone():
                # Return existing event (idempotent)
                result = await session.execute(
                    text("SELECT * FROM ops_events WHERE idempotency_key = :key"),
                    {"key": idempotency_key}
                )
                row = result.fetchone()
                return {
                    "event_id": str(row.id),
                    "event_type": row.event_type,
                    "timestamp": row.timestamp.isoformat(),
                    "payload": row.payload,
                    "payload_hash": row.payload_hash,
                    "idempotent": True,
                }
            
            # Insert new event
            await session.execute(
                text("""
                    INSERT INTO ops_events (
                        id, event_type, timestamp, wallet_id, correlation_id,
                        idempotency_key, version, source_app, payload, payload_hash,
                        ledger_synced, created_at
                    ) VALUES (
                        :id, :event_type, :timestamp, :wallet_id, :correlation_id,
                        :idempotency_key, :version, :source_app, :payload, :payload_hash,
                        :ledger_synced, :created_at
                    )
                """),
                {
                    "id": event_id,
                    "event_type": event_type,
                    "timestamp": timestamp,
                    "wallet_id": wallet_id,
                    "correlation_id": correlation_id,
                    "idempotency_key": idempotency_key,
                    "version": "1.0",
                    "source_app": "OPS",
                    "payload": json.dumps(payload, cls=DecimalEncoder),
                    "payload_hash": payload_hash,
                    "ledger_synced": False,
                    "created_at": timestamp,
                }
            )
            await session.commit()
        
        return {
            "event_id": str(event_id),
            "event_type": event_type,
            "timestamp": timestamp.isoformat(),
            "correlation_id": correlation_id,
            "payload": payload,
            "payload_hash": payload_hash,
            "idempotent": False,
        }
    
    async def get_by_id(self, event_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get a single event by ID."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            result = await session.execute(
                text("SELECT * FROM ops_events WHERE id = :id"),
                {"id": event_id}
            )
            row = result.fetchone()
            if not row:
                return None
            return self._row_to_dict(row)
    
    async def get_by_correlation(self, correlation_id: str) -> List[Dict[str, Any]]:
        """Get all events with a correlation ID (for tracing related events)."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            result = await session.execute(
                text("""
                    SELECT * FROM ops_events 
                    WHERE correlation_id = :correlation_id 
                    ORDER BY timestamp ASC
                """),
                {"correlation_id": correlation_id}
            )
            return [self._row_to_dict(row) for row in result.fetchall()]
    
    async def get_by_type(
        self,
        event_type: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get events by type with optional time range."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            query = "SELECT * FROM ops_events WHERE event_type = :event_type"
            params: Dict[str, Any] = {"event_type": event_type}
            
            if since:
                query += " AND timestamp >= :since"
                params["since"] = since
            if until:
                query += " AND timestamp <= :until"
                params["until"] = until
            
            query += " ORDER BY timestamp DESC LIMIT :limit"
            params["limit"] = limit
            
            result = await session.execute(text(query), params)
            return [self._row_to_dict(row) for row in result.fetchall()]
    
    async def get_unsynced_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get events not yet synced to Ledger."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            result = await session.execute(
                text("""
                    SELECT * FROM ops_events 
                    WHERE ledger_synced = false 
                    ORDER BY timestamp ASC 
                    LIMIT :limit
                """),
                {"limit": limit}
            )
            return [self._row_to_dict(row) for row in result.fetchall()]
    
    async def mark_synced(
        self,
        event_id: uuid.UUID,
        ledger_event_id: str,
    ) -> None:
        """Mark an event as synced to Ledger."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            await session.execute(
                text("""
                    UPDATE ops_events 
                    SET ledger_synced = true, 
                        ledger_event_id = :ledger_event_id,
                        ledger_synced_at = :synced_at
                    WHERE id = :id
                """),
                {
                    "id": event_id,
                    "ledger_event_id": ledger_event_id,
                    "synced_at": datetime.now(timezone.utc),
                }
            )
            await session.commit()
    
    async def search(
        self,
        query: str,
        event_types: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search events by payload content.
        Used for forensic reconstruction: "What happened with product X?"
        """
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            sql = """
                SELECT * FROM ops_events 
                WHERE payload::text ILIKE :query
            """
            params: Dict[str, Any] = {"query": f"%{query}%"}
            
            if event_types:
                sql += " AND event_type = ANY(:types)"
                params["types"] = event_types
            if since:
                sql += " AND timestamp >= :since"
                params["since"] = since
            
            sql += " ORDER BY timestamp DESC LIMIT :limit"
            params["limit"] = limit
            
            result = await session.execute(text(sql), params)
            return [self._row_to_dict(row) for row in result.fetchall()]
    
    async def get_forensic_timeline(
        self,
        product_id: Optional[uuid.UUID] = None,
        location_id: Optional[uuid.UUID] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        Get forensic timeline for a product or location.
        
        This is the "What happened, when, and why" feature.
        Critical for Phase 0-1 lock-in.
        """
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            conditions = []
            params: Dict[str, Any] = {"limit": limit}
            
            if product_id:
                conditions.append("payload->>'product_id' = :product_id")
                params["product_id"] = str(product_id)
            if location_id:
                conditions.append("payload->>'location_id' = :location_id")
                params["location_id"] = str(location_id)
            if since:
                conditions.append("timestamp >= :since")
                params["since"] = since
            if until:
                conditions.append("timestamp <= :until")
                params["until"] = until
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            result = await session.execute(
                text(f"""
                    SELECT * FROM ops_events 
                    WHERE {where_clause}
                    ORDER BY timestamp ASC 
                    LIMIT :limit
                """),
                params
            )
            return [self._row_to_dict(row) for row in result.fetchall()]
    
    async def count_by_type(
        self,
        since: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Get event counts by type (for metrics)."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            query = """
                SELECT event_type, COUNT(*) as count 
                FROM ops_events
            """
            params: Dict[str, Any] = {}
            
            if since:
                query += " WHERE timestamp >= :since"
                params["since"] = since
            
            query += " GROUP BY event_type"
            
            result = await session.execute(text(query), params)
            return {row.event_type: row.count for row in result.fetchall()}
    
    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert a database row to a dictionary."""
        return {
            "event_id": str(row.id),
            "event_type": row.event_type,
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            "wallet_id": row.wallet_id,
            "correlation_id": row.correlation_id,
            "idempotency_key": row.idempotency_key,
            "version": row.version,
            "source_app": row.source_app,
            "payload": row.payload if isinstance(row.payload, dict) else json.loads(row.payload) if row.payload else {},
            "payload_hash": row.payload_hash,
            "ledger_synced": row.ledger_synced,
            "ledger_event_id": row.ledger_event_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


# Singleton instance
event_store = PersistentEventStore()
