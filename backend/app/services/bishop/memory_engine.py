"""
PROVENIQ Ops - Bishop Decision Memory Engine
Record decisions, context, and outcomes to prevent repeated mistakes.

GUARDRAILS:
- Memory INFORMS recommendations but NEVER overrides policy
- All records are immutable once created
- Outcomes are linked after resolution window

LOGIC:
1. Store immutable decision record
2. Link outcomes after resolution window
3. Surface historical analogs during future decisions
"""

import uuid
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Any

from app.models.memory import (
    DecisionMemoryStats,
    DecisionRecord,
    DecisionType,
    InputsSnapshot,
    MemoryConfig,
    MemoryLookupResult,
    OutcomeMetrics,
    OutcomeQuality,
    OutcomeRecord,
    ResolutionStatus,
    SimilarDecision,
)


class DecisionMemoryEngine:
    """
    Bishop Decision Memory Engine
    
    Records decisions, context, and outcomes to enable
    learning from past experience.
    
    GUARDRAIL: Memory informs recommendations but NEVER overrides policy.
    """
    
    def __init__(self) -> None:
        self._config = MemoryConfig()
        
        # Decision storage
        self._decisions: dict[uuid.UUID, DecisionRecord] = {}
        self._outcomes: dict[uuid.UUID, OutcomeRecord] = {}  # decision_id -> outcome
        
        # Indexes for fast lookup
        self._by_type: dict[DecisionType, list[uuid.UUID]] = defaultdict(list)
        self._by_hash: dict[str, list[uuid.UUID]] = defaultdict(list)
        self._by_trace: dict[uuid.UUID, uuid.UUID] = {}  # trace_id -> decision_id
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure(self, config: MemoryConfig) -> None:
        """Update memory configuration."""
        self._config = config
    
    def get_config(self) -> MemoryConfig:
        """Get current configuration."""
        return self._config
    
    # =========================================================================
    # DECISION RECORDING (Step 1)
    # =========================================================================
    
    def record_decision(
        self,
        decision_type: DecisionType,
        decision_description: str,
        decision_trace_id: uuid.UUID,
        inputs_snapshot: InputsSnapshot,
        action_taken: str,
        action_parameters: dict[str, Any],
        confidence: Decimal,
        dag_node_id: Optional[str] = None,
        policy_tokens: Optional[dict[str, Any]] = None,
    ) -> DecisionRecord:
        """
        Record an immutable decision.
        
        This is the core method for storing decisions.
        Once recorded, decisions cannot be modified.
        """
        # Compute input hash
        inputs_hash = inputs_snapshot.compute_hash()
        
        # Compute policy hash if provided
        policy_hash = None
        if policy_tokens:
            policy_str = str(sorted(policy_tokens.items()))
            policy_hash = hashlib.sha256(policy_str.encode()).hexdigest()[:16]
        
        # Determine resolution window
        resolution_hours = self._get_resolution_window(decision_type)
        
        record = DecisionRecord(
            decision_type=decision_type,
            decision_description=decision_description,
            decision_trace_id=decision_trace_id,
            dag_node_id=dag_node_id,
            inputs_snapshot=inputs_snapshot,
            inputs_hash=inputs_hash,
            action_taken=action_taken,
            action_parameters=action_parameters,
            confidence=confidence,
            policy_tokens_hash=policy_hash,
            resolution_window_hours=resolution_hours,
            resolution_due_at=datetime.utcnow() + timedelta(hours=resolution_hours),
        )
        
        # Store
        self._decisions[record.decision_id] = record
        
        # Index
        self._by_type[decision_type].append(record.decision_id)
        self._by_hash[inputs_hash].append(record.decision_id)
        self._by_trace[decision_trace_id] = record.decision_id
        
        return record
    
    def _get_resolution_window(self, decision_type: DecisionType) -> int:
        """Get resolution window hours for decision type."""
        if decision_type in (DecisionType.ORDER_PLACEMENT, DecisionType.ORDER_DELAY):
            return self._config.order_resolution_hours
        elif decision_type in (DecisionType.STOCKOUT_ALERT, DecisionType.MARGIN_ALERT, DecisionType.SCAN_ANOMALY):
            return self._config.alert_resolution_hours
        return self._config.default_resolution_hours
    
    # =========================================================================
    # OUTCOME RECORDING (Step 2)
    # =========================================================================
    
    def record_outcome(
        self,
        decision_id: uuid.UUID,
        outcome_quality: OutcomeQuality,
        outcome_description: str,
        metrics: OutcomeMetrics,
        human_feedback: Optional[str] = None,
        human_override_applied: bool = False,
        lessons_learned: Optional[list[str]] = None,
    ) -> Optional[OutcomeRecord]:
        """
        Link an outcome to a decision after resolution.
        """
        decision = self._decisions.get(decision_id)
        if not decision:
            return None
        
        # Calculate outcome score
        outcome_score = self._calculate_outcome_score(outcome_quality, metrics)
        
        outcome = OutcomeRecord(
            decision_id=decision_id,
            outcome_quality=outcome_quality,
            outcome_score=outcome_score,
            metrics=metrics,
            outcome_description=outcome_description,
            human_feedback=human_feedback,
            human_override_applied=human_override_applied,
            lessons_learned=lessons_learned or [],
        )
        
        # Store
        self._outcomes[decision_id] = outcome
        
        # Update decision status
        decision.resolution_status = ResolutionStatus.RESOLVED
        
        return outcome
    
    def _calculate_outcome_score(
        self,
        quality: OutcomeQuality,
        metrics: OutcomeMetrics,
    ) -> Decimal:
        """Calculate numerical score from outcome quality and metrics."""
        # Base score from quality
        base_scores = {
            OutcomeQuality.EXCELLENT: Decimal("0.95"),
            OutcomeQuality.GOOD: Decimal("0.80"),
            OutcomeQuality.ACCEPTABLE: Decimal("0.60"),
            OutcomeQuality.POOR: Decimal("0.35"),
            OutcomeQuality.FAILURE: Decimal("0.10"),
        }
        score = base_scores.get(quality, Decimal("0.50"))
        
        # Adjust based on metrics
        if metrics.stockout_occurred:
            score -= Decimal("0.15")
        
        if metrics.waste_delta_pct and metrics.waste_delta_pct > 0:
            score -= min(Decimal("0.10"), metrics.waste_delta_pct / 100)
        
        if metrics.margin_delta_pct and metrics.margin_delta_pct < 0:
            score -= min(Decimal("0.10"), abs(metrics.margin_delta_pct) / 100)
        
        return max(Decimal("0"), min(Decimal("1"), score))
    
    # =========================================================================
    # SIMILARITY MATCHING (Step 3)
    # =========================================================================
    
    def find_similar_decisions(
        self,
        current_inputs: InputsSnapshot,
        decision_type: Optional[DecisionType] = None,
        max_results: Optional[int] = None,
    ) -> MemoryLookupResult:
        """
        Surface historical analogs for current context.
        
        GUARDRAIL: Results inform recommendations but never override policy.
        """
        current_hash = current_inputs.compute_hash()
        max_results = max_results or self._config.max_similar_results
        
        similar = []
        
        # Get candidate decisions
        if decision_type:
            candidates = self._by_type.get(decision_type, [])
        else:
            candidates = list(self._decisions.keys())
        
        for decision_id in candidates:
            decision = self._decisions.get(decision_id)
            if not decision:
                continue
            
            # Calculate similarity
            similarity = self._calculate_similarity(current_inputs, decision.inputs_snapshot)
            
            if similarity >= self._config.similarity_threshold:
                outcome = self._outcomes.get(decision_id)
                
                similar.append(SimilarDecision(
                    decision_id=decision_id,
                    decision_type=decision.decision_type,
                    similarity_score=similarity,
                    outcome_score=outcome.outcome_score if outcome else None,
                    outcome_quality=outcome.outcome_quality if outcome else None,
                    context_delta=self._compute_context_delta(current_inputs, decision.inputs_snapshot),
                    decided_at=decision.decided_at,
                ))
        
        # Sort by combined score (similarity + outcome + recency)
        similar.sort(key=lambda s: self._rank_similar(s), reverse=True)
        similar = similar[:max_results]
        
        # Compute aggregate insights
        resolved_similar = [s for s in similar if s.outcome_score is not None]
        avg_score = None
        success_rate = None
        
        if resolved_similar:
            scores = [s.outcome_score for s in resolved_similar]
            avg_score = sum(scores) / len(scores)
            
            successes = len([s for s in resolved_similar 
                           if s.outcome_quality in (OutcomeQuality.EXCELLENT, OutcomeQuality.GOOD)])
            success_rate = Decimal(successes) / len(resolved_similar)
        
        # Generate suggestions based on history
        suggestions = self._generate_suggestions(similar)
        
        return MemoryLookupResult(
            current_context_hash=current_hash,
            similar_past_decisions=similar,
            total_similar_found=len(similar),
            avg_outcome_score=avg_score,
            historical_success_rate=success_rate,
            suggested_adjustments=suggestions,
        )
    
    def _calculate_similarity(
        self,
        current: InputsSnapshot,
        historical: InputsSnapshot,
    ) -> Decimal:
        """Calculate similarity score between two input contexts."""
        score = Decimal("0")
        factors = 0
        
        # Hash match (exact context)
        if current.snapshot_hash == historical.snapshot_hash:
            return Decimal("1.0")
        
        # Inventory similarity
        if current.inventory_levels and historical.inventory_levels:
            common_products = set(current.inventory_levels.keys()) & set(historical.inventory_levels.keys())
            if common_products:
                diffs = []
                for product in common_products:
                    curr_qty = current.inventory_levels[product]
                    hist_qty = historical.inventory_levels[product]
                    if hist_qty > 0:
                        diff = abs(curr_qty - hist_qty) / hist_qty
                        diffs.append(max(0, 1 - float(diff)))
                
                if diffs:
                    score += Decimal(str(sum(diffs) / len(diffs)))
                    factors += 1
        
        # Demand similarity
        if current.demand_forecast and historical.demand_forecast:
            common_products = set(current.demand_forecast.keys()) & set(historical.demand_forecast.keys())
            if common_products:
                diffs = []
                for product in common_products:
                    curr_demand = current.demand_forecast[product]
                    hist_demand = historical.demand_forecast[product]
                    if hist_demand > 0:
                        diff = abs(curr_demand - hist_demand) / hist_demand
                        diffs.append(max(0, 1 - float(diff)))
                
                if diffs:
                    score += Decimal(str(sum(diffs) / len(diffs)))
                    factors += 1
        
        # Risk similarity
        risk_score = Decimal("0")
        if current.stockout_risk_items == historical.stockout_risk_items:
            risk_score += Decimal("0.5")
        elif abs(current.stockout_risk_items - historical.stockout_risk_items) <= 2:
            risk_score += Decimal("0.25")
        
        if current.waste_risk_items == historical.waste_risk_items:
            risk_score += Decimal("0.5")
        elif abs(current.waste_risk_items - historical.waste_risk_items) <= 2:
            risk_score += Decimal("0.25")
        
        score += risk_score
        factors += 1
        
        # Time similarity (same day of week, similar hour)
        time_score = Decimal("0")
        if current.day_of_week == historical.day_of_week:
            time_score += Decimal("0.5")
        if abs(current.hour_of_day - historical.hour_of_day) <= 2:
            time_score += Decimal("0.5")
        
        score += time_score
        factors += 1
        
        return (score / factors).quantize(Decimal("0.01")) if factors > 0 else Decimal("0")
    
    def _compute_context_delta(
        self,
        current: InputsSnapshot,
        historical: InputsSnapshot,
    ) -> dict[str, Any]:
        """Compute delta between current and historical context."""
        delta = {}
        
        delta["stockout_risk_delta"] = current.stockout_risk_items - historical.stockout_risk_items
        delta["waste_risk_delta"] = current.waste_risk_items - historical.waste_risk_items
        delta["day_of_week_match"] = current.day_of_week == historical.day_of_week
        delta["hour_delta"] = current.hour_of_day - historical.hour_of_day
        
        return delta
    
    def _rank_similar(self, similar: SimilarDecision) -> Decimal:
        """Rank a similar decision for sorting."""
        score = Decimal("0")
        
        # Similarity weight
        score += similar.similarity_score * self._config.similarity_weight
        
        # Outcome weight (if resolved)
        if similar.outcome_score is not None:
            score += similar.outcome_score * self._config.outcome_weight
        
        # Recency weight (decay over time)
        age_days = (datetime.utcnow() - similar.decided_at).days
        recency = max(Decimal("0"), Decimal("1") - Decimal(age_days) / 365)
        score += recency * self._config.recency_weight
        
        return score
    
    def _generate_suggestions(self, similar: list[SimilarDecision]) -> list[str]:
        """Generate suggestions based on historical patterns."""
        suggestions = []
        
        if not similar:
            return suggestions
        
        # Check for poor outcomes
        poor_outcomes = [s for s in similar if s.outcome_quality in (OutcomeQuality.POOR, OutcomeQuality.FAILURE)]
        if poor_outcomes:
            suggestions.append(f"⚠️ {len(poor_outcomes)} similar past decisions had poor outcomes")
        
        # Check for high success rate
        good_outcomes = [s for s in similar if s.outcome_quality in (OutcomeQuality.EXCELLENT, OutcomeQuality.GOOD)]
        if len(good_outcomes) >= len(similar) * 0.7:
            suggestions.append("✓ Historical success rate is high for similar contexts")
        
        # Check for overrides
        # (Would need to track this in outcome records)
        
        return suggestions
    
    # =========================================================================
    # QUERY & STATS
    # =========================================================================
    
    def get_decision(self, decision_id: uuid.UUID) -> Optional[DecisionRecord]:
        """Get a specific decision."""
        return self._decisions.get(decision_id)
    
    def get_decision_by_trace(self, trace_id: uuid.UUID) -> Optional[DecisionRecord]:
        """Get decision by trace ID."""
        decision_id = self._by_trace.get(trace_id)
        if decision_id:
            return self._decisions.get(decision_id)
        return None
    
    def get_outcome(self, decision_id: uuid.UUID) -> Optional[OutcomeRecord]:
        """Get outcome for a decision."""
        return self._outcomes.get(decision_id)
    
    def get_pending_resolutions(self) -> list[DecisionRecord]:
        """Get decisions awaiting outcome recording."""
        now = datetime.utcnow()
        return [
            d for d in self._decisions.values()
            if d.resolution_status == ResolutionStatus.PENDING
            and d.resolution_due_at and d.resolution_due_at <= now
        ]
    
    def get_stats(self) -> DecisionMemoryStats:
        """Get memory statistics."""
        total = len(self._decisions)
        resolved = len(self._outcomes)
        pending = total - resolved
        
        # Count by type
        by_type = {dt.value: len(ids) for dt, ids in self._by_type.items()}
        
        # Count outcomes by quality
        quality_counts = defaultdict(int)
        scores = []
        for outcome in self._outcomes.values():
            quality_counts[outcome.outcome_quality] += 1
            scores.append(outcome.outcome_score)
        
        avg_score = sum(scores) / len(scores) if scores else None
        
        # Success rate
        successes = quality_counts[OutcomeQuality.EXCELLENT] + quality_counts[OutcomeQuality.GOOD]
        success_rate = Decimal(successes) / resolved if resolved > 0 else None
        
        # Time range
        if self._decisions:
            decisions = list(self._decisions.values())
            earliest = min(d.decided_at for d in decisions)
            latest = max(d.decided_at for d in decisions)
        else:
            earliest = None
            latest = None
        
        return DecisionMemoryStats(
            total_decisions=total,
            resolved_decisions=resolved,
            pending_decisions=pending,
            decisions_by_type=by_type,
            outcomes_excellent=quality_counts[OutcomeQuality.EXCELLENT],
            outcomes_good=quality_counts[OutcomeQuality.GOOD],
            outcomes_acceptable=quality_counts[OutcomeQuality.ACCEPTABLE],
            outcomes_poor=quality_counts[OutcomeQuality.POOR],
            outcomes_failure=quality_counts[OutcomeQuality.FAILURE],
            avg_outcome_score=avg_score,
            success_rate=success_rate,
            earliest_decision=earliest,
            latest_decision=latest,
        )
    
    def clear_data(self) -> None:
        """Clear all memory data (for testing)."""
        self._decisions.clear()
        self._outcomes.clear()
        self._by_type.clear()
        self._by_hash.clear()
        self._by_trace.clear()


# Singleton instance
memory_engine = DecisionMemoryEngine()
