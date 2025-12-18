"""
PROVENIQ Ops - Audit Service
Immutable logging for Bishop decisions and human overrides.

This is PERMANENT INFRASTRUCTURE.
All logs are append-only and become training data for future ML.

RULE: Every Bishop decision, every human override, every block — logged.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from collections import deque

from app.models.audit import (
    AuditEventType,
    BishopStateLog,
    BlockAuditLog,
    ExecutionAuditLog,
    OverrideAuditLog,
    OverrideType,
    ProposalAuditLog,
    ReasonCode,
)


class AuditService:
    """
    Centralized audit logging service.
    
    In production, this writes to:
    - PostgreSQL (primary storage)
    - Event stream (for real-time monitoring)
    - S3/blob storage (for ML training exports)
    
    For now, uses in-memory storage with structured output.
    """
    
    def __init__(self) -> None:
        # In-memory storage (replace with DB in production)
        self._state_logs: deque[BishopStateLog] = deque(maxlen=10000)
        self._proposal_logs: deque[ProposalAuditLog] = deque(maxlen=10000)
        self._override_logs: deque[OverrideAuditLog] = deque(maxlen=10000)
        self._block_logs: deque[BlockAuditLog] = deque(maxlen=10000)
        self._execution_logs: deque[ExecutionAuditLog] = deque(maxlen=10000)
        
        # Current trace context (thread-local in production)
        self._current_trace_id: Optional[uuid.UUID] = None
    
    # =========================================================================
    # TRACE CONTEXT
    # =========================================================================
    
    def start_trace(self) -> uuid.UUID:
        """Start a new trace for a decision chain."""
        self._current_trace_id = uuid.uuid4()
        return self._current_trace_id
    
    def get_trace_id(self) -> uuid.UUID:
        """Get current trace ID or create new one."""
        if not self._current_trace_id:
            self._current_trace_id = uuid.uuid4()
        return self._current_trace_id
    
    def end_trace(self) -> None:
        """End current trace context."""
        self._current_trace_id = None
    
    # =========================================================================
    # STATE TRANSITION LOGGING
    # =========================================================================
    
    def log_state_transition(
        self,
        previous_state: Optional[str],
        new_state: str,
        trigger_event: str,
        user_id: Optional[uuid.UUID] = None,
        session_id: Optional[uuid.UUID] = None,
        location_id: Optional[uuid.UUID] = None,
        context_data: Optional[dict] = None,
    ) -> BishopStateLog:
        """
        Log a Bishop FSM state transition.
        
        Every state change is recorded for analysis.
        """
        log = BishopStateLog(
            previous_state=previous_state,
            new_state=new_state,
            trigger_event=trigger_event,
            user_id=user_id,
            session_id=session_id,
            location_id=location_id,
            context_data=context_data or {},
            trace_id=self.get_trace_id(),
        )
        
        self._state_logs.append(log)
        self._emit_log("STATE_TRANSITION", log)
        return log
    
    # =========================================================================
    # PROPOSAL LOGGING
    # =========================================================================
    
    def log_proposal_generated(
        self,
        proposal_id: uuid.UUID,
        proposal_type: str,
        dag_node_id: str,
        recommendation: dict,
        confidence: Decimal,
        reason_codes: list[str],
        policy_tokens: Optional[list[uuid.UUID]] = None,
        gates_passed: Optional[list[str]] = None,
    ) -> ProposalAuditLog:
        """Log when Bishop generates a proposal."""
        log = ProposalAuditLog(
            event_type=AuditEventType.PROPOSAL_GENERATED,
            proposal_id=proposal_id,
            proposal_type=proposal_type,
            dag_node_id=dag_node_id,
            bishop_recommendation=recommendation,
            bishop_confidence=confidence,
            bishop_reason_codes=reason_codes,
            policy_tokens=policy_tokens or [],
            gates_passed=gates_passed or [],
            trace_id=self.get_trace_id(),
        )
        
        self._proposal_logs.append(log)
        self._emit_log("PROPOSAL_GENERATED", log)
        return log
    
    def log_proposal_decision(
        self,
        proposal_id: uuid.UUID,
        decision: str,  # approved, rejected, modified
        user_id: uuid.UUID,
        reason_codes: list[str],
        notes: Optional[str] = None,
        final_action: Optional[dict] = None,
    ) -> ProposalAuditLog:
        """Log human decision on a proposal."""
        event_type = {
            "approved": AuditEventType.PROPOSAL_APPROVED,
            "rejected": AuditEventType.PROPOSAL_REJECTED,
            "modified": AuditEventType.PROPOSAL_MODIFIED,
        }.get(decision, AuditEventType.PROPOSAL_APPROVED)
        
        # Find original proposal
        original = next(
            (p for p in self._proposal_logs if p.proposal_id == proposal_id),
            None
        )
        
        log = ProposalAuditLog(
            event_type=event_type,
            proposal_id=proposal_id,
            proposal_type=original.proposal_type if original else "unknown",
            dag_node_id=original.dag_node_id if original else "unknown",
            bishop_recommendation=original.bishop_recommendation if original else {},
            bishop_confidence=original.bishop_confidence if original else Decimal("0"),
            bishop_reason_codes=original.bishop_reason_codes if original else [],
            human_decision=decision,
            human_user_id=user_id,
            human_reason_codes=reason_codes,
            human_notes=notes,
            final_action=final_action,
            policy_tokens=original.policy_tokens if original else [],
            trace_id=self.get_trace_id(),
            parent_trace_id=original.trace_id if original else None,
        )
        
        self._proposal_logs.append(log)
        self._emit_log(f"PROPOSAL_{decision.upper()}", log)
        return log
    
    # =========================================================================
    # OVERRIDE LOGGING
    # =========================================================================
    
    def log_override(
        self,
        override_type: OverrideType,
        reason_codes: list[ReasonCode],
        proposal_id: uuid.UUID,
        bishop_value: Any,
        bishop_confidence: Decimal,
        human_value: Any,
        user_id: uuid.UUID,
        user_role: str,
        notes: Optional[str] = None,
        context_snapshot: Optional[dict] = None,
    ) -> OverrideAuditLog:
        """
        Log when a human overrides Bishop's recommendation.
        
        This is CRITICAL training data:
        - What did Bishop recommend?
        - What did the human choose instead?
        - Why?
        - Was the human right? (tracked later)
        """
        log = OverrideAuditLog(
            override_type=override_type,
            reason_codes=reason_codes,
            bishop_proposal_id=proposal_id,
            bishop_value=bishop_value,
            bishop_confidence=bishop_confidence,
            human_value=human_value,
            human_user_id=user_id,
            human_role=user_role,
            human_notes=notes,
            context_snapshot=context_snapshot or {},
            trace_id=self.get_trace_id(),
        )
        
        self._override_logs.append(log)
        self._emit_log("OVERRIDE", log)
        return log
    
    def update_override_outcome(
        self,
        log_id: uuid.UUID,
        was_correct: bool,
        notes: Optional[str] = None,
    ) -> Optional[OverrideAuditLog]:
        """
        Update an override log with outcome data.
        Called later when we know if the human was right.
        """
        for log in self._override_logs:
            if log.log_id == log_id:
                log.outcome_tracked = True
                log.outcome_was_correct = was_correct
                log.outcome_notes = notes
                self._emit_log("OVERRIDE_OUTCOME", log)
                return log
        return None
    
    # =========================================================================
    # BLOCK LOGGING
    # =========================================================================
    
    def log_block(
        self,
        blocked_action: str,
        entity_id: uuid.UUID,
        entity_type: str,
        blocker: str,
        dag_node_id: str,
        reason_codes: list[ReasonCode],
        reason_details: Optional[dict] = None,
        blocked_value_micros: Optional[int] = None,
        threshold_value_micros: Optional[int] = None,
        confidence: Optional[Decimal] = None,
    ) -> BlockAuditLog:
        """Log when an action is blocked by Bishop or a policy gate."""
        log = BlockAuditLog(
            blocked_action=blocked_action,
            blocked_entity_id=entity_id,
            blocked_entity_type=entity_type,
            blocker=blocker,
            dag_node_id=dag_node_id,
            reason_codes=reason_codes,
            reason_details=reason_details or {},
            blocked_value_micros=blocked_value_micros,
            threshold_value_micros=threshold_value_micros,
            confidence_at_block=confidence,
            trace_id=self.get_trace_id(),
        )
        
        self._block_logs.append(log)
        self._emit_log("BLOCK", log)
        return log
    
    def resolve_block(
        self,
        log_id: uuid.UUID,
        resolution_type: str,
        resolved_by: uuid.UUID,
    ) -> Optional[BlockAuditLog]:
        """Mark a block as resolved."""
        for log in self._block_logs:
            if log.log_id == log_id:
                log.resolved = True
                log.resolution_type = resolution_type
                log.resolved_by = resolved_by
                log.resolved_at = datetime.utcnow()
                self._emit_log("BLOCK_RESOLVED", log)
                return log
        return None
    
    # =========================================================================
    # EXECUTION LOGGING
    # =========================================================================
    
    def log_execution(
        self,
        execution_type: str,
        entity_id: uuid.UUID,
        entity_type: str,
        dag_node_id: str,
        proposal_id: uuid.UUID,
        executed_by: str,
        execution_method: str,
        approval_token_id: Optional[uuid.UUID] = None,
        policy_tokens: Optional[list[uuid.UUID]] = None,
        value_micros: Optional[int] = None,
        quantity: Optional[int] = None,
        side_effects: Optional[list[str]] = None,
    ) -> ExecutionAuditLog:
        """Log when an action is actually executed."""
        log = ExecutionAuditLog(
            execution_type=execution_type,
            entity_id=entity_id,
            entity_type=entity_type,
            dag_node_id=dag_node_id,
            proposal_id=proposal_id,
            approval_token_id=approval_token_id,
            policy_tokens=policy_tokens or [],
            executed_by=executed_by,
            execution_method=execution_method,
            executed_value_micros=value_micros,
            executed_quantity=quantity,
            side_effects_declared=side_effects or [],
            trace_id=self.get_trace_id(),
            decision_trace_id=self.get_trace_id(),
        )
        
        self._execution_logs.append(log)
        self._emit_log("EXECUTION", log)
        return log
    
    # =========================================================================
    # QUERY
    # =========================================================================
    
    def get_state_logs(
        self,
        limit: int = 100,
        state_filter: Optional[str] = None,
    ) -> list[BishopStateLog]:
        """Get recent state transition logs."""
        logs = list(self._state_logs)
        if state_filter:
            logs = [l for l in logs if l.new_state == state_filter]
        return logs[-limit:]
    
    def get_proposal_logs(
        self,
        limit: int = 100,
        event_type: Optional[AuditEventType] = None,
    ) -> list[ProposalAuditLog]:
        """Get recent proposal logs."""
        logs = list(self._proposal_logs)
        if event_type:
            logs = [l for l in logs if l.event_type == event_type]
        return logs[-limit:]
    
    def get_override_logs(
        self,
        limit: int = 100,
        override_type: Optional[OverrideType] = None,
    ) -> list[OverrideAuditLog]:
        """Get recent override logs."""
        logs = list(self._override_logs)
        if override_type:
            logs = [l for l in logs if l.override_type == override_type]
        return logs[-limit:]
    
    def get_block_logs(
        self,
        limit: int = 100,
        resolved: Optional[bool] = None,
    ) -> list[BlockAuditLog]:
        """Get recent block logs."""
        logs = list(self._block_logs)
        if resolved is not None:
            logs = [l for l in logs if l.resolved == resolved]
        return logs[-limit:]
    
    def get_trace(self, trace_id: uuid.UUID) -> dict:
        """Get all logs for a trace ID."""
        return {
            "trace_id": str(trace_id),
            "state_logs": [l for l in self._state_logs if l.trace_id == trace_id],
            "proposal_logs": [l for l in self._proposal_logs if l.trace_id == trace_id],
            "override_logs": [l for l in self._override_logs if l.trace_id == trace_id],
            "block_logs": [l for l in self._block_logs if l.trace_id == trace_id],
            "execution_logs": [l for l in self._execution_logs if l.trace_id == trace_id],
        }
    
    # =========================================================================
    # METRICS
    # =========================================================================
    
    def get_metrics(self) -> dict:
        """Get audit log metrics."""
        proposal_logs = list(self._proposal_logs)
        override_logs = list(self._override_logs)
        
        # Count by decision type
        approved = len([l for l in proposal_logs if l.human_decision == "approved"])
        rejected = len([l for l in proposal_logs if l.human_decision == "rejected"])
        modified = len([l for l in proposal_logs if l.human_decision == "modified"])
        
        # Override accuracy (when tracked)
        tracked_overrides = [l for l in override_logs if l.outcome_tracked]
        correct_overrides = [l for l in tracked_overrides if l.outcome_was_correct]
        
        return {
            "total_state_transitions": len(self._state_logs),
            "total_proposals": len([l for l in proposal_logs if l.event_type == AuditEventType.PROPOSAL_GENERATED]),
            "proposals_approved": approved,
            "proposals_rejected": rejected,
            "proposals_modified": modified,
            "total_overrides": len(override_logs),
            "total_blocks": len(self._block_logs),
            "unresolved_blocks": len([l for l in self._block_logs if not l.resolved]),
            "total_executions": len(self._execution_logs),
            "override_accuracy": (
                len(correct_overrides) / len(tracked_overrides) 
                if tracked_overrides else None
            ),
        }
    
    # =========================================================================
    # INTERNAL
    # =========================================================================
    
    def _emit_log(self, event_type: str, log: Any) -> None:
        """
        Emit log to external systems.
        
        In production:
        - Write to PostgreSQL
        - Publish to event stream
        - Send to monitoring
        """
        # For now, just print structured output
        print(f"[AUDIT] {event_type}: {log.log_id}")


# Singleton instance
audit_service = AuditService()
