"""
PROVENIQ Ops - Persistent Decision Trace Store
Phase 0-1: Forensic Reconstruction Capability

Every decision is persisted to enable:
- "What happened last time we ordered chicken?"
- "Why did Bishop recommend this quantity?"
- "Show me all decisions that led to this shrinkage"

This is the forensic layer that competitors cannot replicate retroactively.
"""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.db.session import async_session_maker
from app.decision.trace import DecisionTrace, TraceEvent


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal and UUID types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class PersistentTraceStore:
    """
    Persistent storage for decision traces.
    
    FORENSIC RECONSTRUCTION:
    - Every decision is persisted with full context
    - Traces are searchable by content, org, dag, status
    - Enables "What happened last time" queries
    - This data cannot be replicated by competitors who start later
    """
    
    async def save(self, trace: DecisionTrace) -> str:
        """
        Save a decision trace to the database.
        
        Returns the trace ID.
        """
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Serialize events to JSON
            events_json = [
                {
                    "event_id": str(e.event_id),
                    "timestamp": e.timestamp.isoformat(),
                    "event_type": e.event_type,
                    "node_id": e.node_id,
                    "gate_id": e.gate_id,
                    "message": e.message,
                    "details": e.details,
                }
                for e in trace.events
            ]
            
            # Insert main trace record
            await session.execute(
                text("""
                    INSERT INTO decision_traces (
                        id, dag_id, dag_name, org_id,
                        started_at, completed_at, duration_ms,
                        initial_context, final_context,
                        status, error, trace_json, created_at
                    ) VALUES (
                        :id, :dag_id, :dag_name, :org_id,
                        :started_at, :completed_at, :duration_ms,
                        :initial_context, :final_context,
                        :status, :error, :trace_json, :created_at
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        completed_at = :completed_at,
                        duration_ms = :duration_ms,
                        final_context = :final_context,
                        status = :status,
                        error = :error,
                        trace_json = :trace_json
                """),
                {
                    "id": trace.trace_id,
                    "dag_id": trace.dag_id,
                    "dag_name": trace.dag_name,
                    "org_id": trace.org_id,
                    "started_at": trace.started_at,
                    "completed_at": trace.completed_at,
                    "duration_ms": trace.duration_ms,
                    "initial_context": json.dumps(trace.initial_context, cls=DecimalEncoder),
                    "final_context": json.dumps(trace.final_context, cls=DecimalEncoder),
                    "status": trace.status,
                    "error": trace.error,
                    "trace_json": json.dumps({"events": events_json}, cls=DecimalEncoder),
                    "created_at": datetime.now(timezone.utc),
                }
            )
            
            # Insert individual trace events
            for event in trace.events:
                await session.execute(
                    text("""
                        INSERT INTO trace_events (
                            id, trace_id, timestamp, event_type,
                            node_id, gate_id, message, details, created_at
                        ) VALUES (
                            :id, :trace_id, :timestamp, :event_type,
                            :node_id, :gate_id, :message, :details, :created_at
                        )
                        ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        "id": event.event_id,
                        "trace_id": trace.trace_id,
                        "timestamp": event.timestamp,
                        "event_type": event.event_type,
                        "node_id": event.node_id,
                        "gate_id": event.gate_id,
                        "message": event.message,
                        "details": json.dumps(event.details, cls=DecimalEncoder),
                        "created_at": datetime.now(timezone.utc),
                    }
                )
            
            await session.commit()
        
        return str(trace.trace_id)
    
    async def get(self, trace_id: uuid.UUID) -> Optional[DecisionTrace]:
        """Get a trace by ID."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("SELECT * FROM decision_traces WHERE id = :id"),
                {"id": trace_id}
            )
            row = result.fetchone()
            if not row:
                return None
            
            # Get events
            events_result = await session.execute(
                text("""
                    SELECT * FROM trace_events 
                    WHERE trace_id = :trace_id 
                    ORDER BY timestamp ASC
                """),
                {"trace_id": trace_id}
            )
            
            events = [
                TraceEvent(
                    event_id=e.id,
                    timestamp=e.timestamp,
                    event_type=e.event_type,
                    node_id=e.node_id,
                    gate_id=e.gate_id,
                    message=e.message,
                    details=e.details if isinstance(e.details, dict) else json.loads(e.details) if e.details else {},
                )
                for e in events_result.fetchall()
            ]
            
            return DecisionTrace(
                trace_id=row.id,
                dag_id=row.dag_id,
                dag_name=row.dag_name,
                org_id=row.org_id,
                started_at=row.started_at,
                completed_at=row.completed_at,
                duration_ms=row.duration_ms,
                initial_context=row.initial_context if isinstance(row.initial_context, dict) else json.loads(row.initial_context) if row.initial_context else {},
                final_context=row.final_context if isinstance(row.final_context, dict) else json.loads(row.final_context) if row.final_context else {},
                status=row.status,
                error=row.error,
                events=events,
            )
    
    async def get_by_dag(
        self,
        dag_id: uuid.UUID,
        limit: int = 100,
    ) -> List[DecisionTrace]:
        """Get all traces for a DAG."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("""
                    SELECT id FROM decision_traces 
                    WHERE dag_id = :dag_id 
                    ORDER BY started_at DESC 
                    LIMIT :limit
                """),
                {"dag_id": dag_id, "limit": limit}
            )
            
            traces = []
            for row in result.fetchall():
                trace = await self.get(row.id)
                if trace:
                    traces.append(trace)
            
            return traces
    
    async def get_by_org(
        self,
        org_id: uuid.UUID,
        limit: int = 100,
        status: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> List[DecisionTrace]:
        """Get traces for an organization."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            query = "SELECT id FROM decision_traces WHERE org_id = :org_id"
            params: Dict[str, Any] = {"org_id": org_id, "limit": limit}
            
            if status:
                query += " AND status = :status"
                params["status"] = status
            if since:
                query += " AND started_at >= :since"
                params["since"] = since
            
            query += " ORDER BY started_at DESC LIMIT :limit"
            
            result = await session.execute(text(query), params)
            
            traces = []
            for row in result.fetchall():
                trace = await self.get(row.id)
                if trace:
                    traces.append(trace)
            
            return traces
    
    async def search(
        self,
        org_id: uuid.UUID,
        query: str,
        limit: int = 50,
    ) -> List[DecisionTrace]:
        """
        Search traces for decision memory.
        
        "What happened last time we ordered chicken?"
        This is the forensic reconstruction feature.
        """
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Search in dag_name, initial_context, and trace events
            result = await session.execute(
                text("""
                    SELECT DISTINCT dt.id 
                    FROM decision_traces dt
                    LEFT JOIN trace_events te ON te.trace_id = dt.id
                    WHERE dt.org_id = :org_id
                    AND (
                        dt.dag_name ILIKE :query
                        OR dt.initial_context::text ILIKE :query
                        OR dt.final_context::text ILIKE :query
                        OR te.message ILIKE :query
                        OR te.details::text ILIKE :query
                    )
                    ORDER BY dt.started_at DESC
                    LIMIT :limit
                """),
                {"org_id": org_id, "query": f"%{query}%", "limit": limit}
            )
            
            traces = []
            for row in result.fetchall():
                trace = await self.get(row.id)
                if trace:
                    traces.append(trace)
            
            return traces
    
    async def get_recent_for_product(
        self,
        org_id: uuid.UUID,
        product_id: uuid.UUID,
        limit: int = 10,
    ) -> List[DecisionTrace]:
        """
        Get recent decisions related to a product.
        
        "What did we decide about this product recently?"
        """
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("""
                    SELECT id FROM decision_traces 
                    WHERE org_id = :org_id
                    AND (
                        initial_context->>'product_id' = :product_id
                        OR final_context->>'product_id' = :product_id
                    )
                    ORDER BY started_at DESC
                    LIMIT :limit
                """),
                {"org_id": org_id, "product_id": str(product_id), "limit": limit}
            )
            
            traces = []
            for row in result.fetchall():
                trace = await self.get(row.id)
                if trace:
                    traces.append(trace)
            
            return traces
    
    async def get_stats(
        self,
        org_id: uuid.UUID,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get decision statistics for an organization."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            query = """
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'passed') as passed,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed,
                    COUNT(*) FILTER (WHERE status = 'blocked') as blocked,
                    AVG(duration_ms) as avg_duration_ms,
                    MAX(duration_ms) as max_duration_ms
                FROM decision_traces
                WHERE org_id = :org_id
            """
            params: Dict[str, Any] = {"org_id": org_id}
            
            if since:
                query += " AND started_at >= :since"
                params["since"] = since
            
            result = await session.execute(text(query), params)
            row = result.fetchone()
            
            return {
                "total_decisions": row.total or 0,
                "passed": row.passed or 0,
                "failed": row.failed or 0,
                "blocked": row.blocked or 0,
                "avg_duration_ms": float(row.avg_duration_ms) if row.avg_duration_ms else 0,
                "max_duration_ms": row.max_duration_ms or 0,
            }


# Singleton instance
trace_store = PersistentTraceStore()
