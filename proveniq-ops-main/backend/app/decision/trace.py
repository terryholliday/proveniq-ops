"""
PROVENIQ Ops - Decision Trace

Immutable audit trail for all decisions.
Enables "Explain-This" and "What happened last time" features.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
import logging
import json

logger = logging.getLogger(__name__)


class TraceEvent(BaseModel):
    """A single event in the decision trace"""
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: str
    node_id: Optional[str] = None
    gate_id: Optional[str] = None
    message: str
    details: Dict[str, Any] = {}


class DecisionTrace(BaseModel):
    """
    Immutable trace of a decision execution.
    
    Used for:
    - Audit trail
    - Explain-This feature
    - Decision memory ("What happened last time")
    - Debugging and analysis
    """
    trace_id: UUID = Field(default_factory=uuid4)
    dag_id: UUID
    dag_name: str
    org_id: UUID
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    
    # Context
    initial_context: Dict[str, Any] = {}
    final_context: Dict[str, Any] = {}
    
    # Events
    events: List[TraceEvent] = []
    
    # Outcome
    status: str = "pending"  # pending, passed, failed, blocked
    error: Optional[str] = None
    
    def start(self) -> None:
        """Mark trace as started"""
        self.started_at = datetime.utcnow()
        self._log_event("trace_started", "Decision execution started")
    
    def complete(self, status: str, final_context: Dict[str, Any]) -> None:
        """Mark trace as complete"""
        self.completed_at = datetime.utcnow()
        self.status = status
        self.final_context = final_context
        
        if self.started_at:
            self.duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)
        
        self._log_event("trace_completed", f"Decision execution completed: {status}")
    
    def log_node_start(self, node_id: str, node_name: str) -> None:
        """Log node execution start"""
        self._log_event(
            "node_started",
            f"Node '{node_name}' started",
            node_id=node_id,
        )
    
    def log_node_complete(self, node_id: str, result: Dict[str, Any]) -> None:
        """Log node execution complete"""
        self._log_event(
            "node_completed",
            f"Node completed successfully",
            node_id=node_id,
            details={"result": result},
        )
    
    def log_node_blocked(self, node_id: str, reason: str) -> None:
        """Log node blocked"""
        self._log_event(
            "node_blocked",
            f"Node blocked: {reason}",
            node_id=node_id,
        )
    
    def log_node_error(self, node_id: str, error: str) -> None:
        """Log node error"""
        self._log_event(
            "node_error",
            f"Node failed: {error}",
            node_id=node_id,
            details={"error": error},
        )
        self.error = error
    
    def log_gate_result(self, node_id: str, gate_id: str, result: Any) -> None:
        """Log gate evaluation result"""
        self._log_event(
            "gate_evaluated",
            f"Gate '{gate_id}' evaluated: {'passed' if result.passed else 'failed'}",
            node_id=node_id,
            gate_id=gate_id,
            details={
                "passed": result.passed,
                "message": result.message,
                "details": result.details,
            },
        )
    
    def _log_event(
        self,
        event_type: str,
        message: str,
        node_id: Optional[str] = None,
        gate_id: Optional[str] = None,
        details: Dict[str, Any] = {},
    ) -> None:
        """Internal method to log an event"""
        event = TraceEvent(
            event_type=event_type,
            node_id=node_id,
            gate_id=gate_id,
            message=message,
            details=details,
        )
        self.events.append(event)
        logger.debug(f"[Trace {self.trace_id}] {event_type}: {message}")
    
    def explain(self) -> str:
        """
        Generate human-readable explanation of the decision.
        
        Used for "Explain-This" feature.
        """
        lines = [
            f"# Decision: {self.dag_name}",
            f"Trace ID: {self.trace_id}",
            f"Status: {self.status.upper()}",
            f"Duration: {self.duration_ms}ms" if self.duration_ms else "",
            "",
            "## Execution Timeline:",
        ]
        
        for event in self.events:
            timestamp = event.timestamp.strftime("%H:%M:%S.%f")[:-3]
            prefix = ""
            if event.node_id:
                prefix = f"[{event.node_id}]"
            if event.gate_id:
                prefix = f"[{event.node_id}/{event.gate_id}]"
            
            lines.append(f"  {timestamp} {prefix} {event.message}")
            
            if event.details:
                for key, value in event.details.items():
                    if key != "result":  # Skip verbose result dumps
                        lines.append(f"           {key}: {value}")
        
        if self.error:
            lines.append("")
            lines.append(f"## Error: {self.error}")
        
        return "\n".join(lines)
    
    def to_json(self) -> str:
        """Serialize trace to JSON for storage"""
        return self.model_dump_json(indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "DecisionTrace":
        """Deserialize trace from JSON"""
        return cls.model_validate_json(json_str)


class TraceStore:
    """
    Storage for decision traces.
    
    In production, this would persist to PostgreSQL.
    Currently uses in-memory storage.
    """
    
    def __init__(self):
        self._traces: Dict[UUID, DecisionTrace] = {}
    
    async def save(self, trace: DecisionTrace) -> None:
        """Save a trace"""
        self._traces[trace.trace_id] = trace
        logger.info(f"Saved trace {trace.trace_id} for {trace.dag_name}")
    
    async def get(self, trace_id: UUID) -> Optional[DecisionTrace]:
        """Get a trace by ID"""
        return self._traces.get(trace_id)
    
    async def get_by_dag(self, dag_id: UUID) -> List[DecisionTrace]:
        """Get all traces for a DAG"""
        return [t for t in self._traces.values() if t.dag_id == dag_id]
    
    async def get_by_org(
        self,
        org_id: UUID,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> List[DecisionTrace]:
        """Get traces for an organization"""
        traces = [t for t in self._traces.values() if t.org_id == org_id]
        
        if status:
            traces = [t for t in traces if t.status == status]
        
        # Sort by started_at descending
        traces.sort(key=lambda t: t.started_at or datetime.min, reverse=True)
        
        return traces[:limit]
    
    async def search(
        self,
        org_id: UUID,
        query: str,
        limit: int = 50,
    ) -> List[DecisionTrace]:
        """
        Search traces for decision memory.
        
        "What happened last time we ordered chicken?"
        """
        query_lower = query.lower()
        matches = []
        
        for trace in self._traces.values():
            if trace.org_id != org_id:
                continue
            
            # Search in dag name
            if query_lower in trace.dag_name.lower():
                matches.append(trace)
                continue
            
            # Search in context
            context_str = json.dumps(trace.initial_context).lower()
            if query_lower in context_str:
                matches.append(trace)
                continue
            
            # Search in events
            for event in trace.events:
                if query_lower in event.message.lower():
                    matches.append(trace)
                    break
        
        # Sort by recency
        matches.sort(key=lambda t: t.started_at or datetime.min, reverse=True)
        
        return matches[:limit]
