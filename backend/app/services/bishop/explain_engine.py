"""
PROVENIQ Ops - Bishop Explain Engine
Explain any Bishop recommendation in plain language.

LOGIC:
1. Retrieve inputs, policies, confidence
2. Summarize reasoning
3. Present alternatives considered
"""

import uuid
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any

from app.models.explain import (
    AlternativeConsidered,
    AlternativeStatus,
    ConfidenceLevel,
    DecisionTrace,
    DecisionType,
    DetailedExplanation,
    ExplainConfig,
    Explanation,
    InputUsed,
    PolicyApplied,
    QuickExplanation,
)


class ExplainEngine:
    """
    Bishop Explain Engine
    
    Explains any Bishop recommendation in plain language.
    """
    
    def __init__(self) -> None:
        self._config = ExplainConfig()
        
        # Decision traces storage
        self._traces: dict[uuid.UUID, DecisionTrace] = {}
        
        # Explanation cache
        self._explanations: dict[uuid.UUID, Explanation] = {}
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure(self, config: ExplainConfig) -> None:
        """Update configuration."""
        self._config = config
    
    def get_config(self) -> ExplainConfig:
        """Get current configuration."""
        return self._config
    
    # =========================================================================
    # TRACE REGISTRATION
    # =========================================================================
    
    def register_trace(self, trace: DecisionTrace) -> None:
        """Register a decision trace for later explanation."""
        self._traces[trace.trace_id] = trace
    
    def get_trace(self, trace_id: uuid.UUID) -> Optional[DecisionTrace]:
        """Get a decision trace."""
        return self._traces.get(trace_id)
    
    # =========================================================================
    # EXPLANATION GENERATION
    # =========================================================================
    
    def _determine_confidence_level(self, confidence: Decimal) -> ConfidenceLevel:
        """Determine confidence level from score."""
        if confidence >= self._config.very_high_threshold:
            return ConfidenceLevel.VERY_HIGH
        elif confidence >= self._config.high_threshold:
            return ConfidenceLevel.HIGH
        elif confidence >= self._config.medium_threshold:
            return ConfidenceLevel.MEDIUM
        elif confidence >= self._config.low_threshold:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    def _generate_summary(self, trace: DecisionTrace) -> str:
        """Generate plain language summary."""
        decision_type = trace.decision_type
        recommendation = trace.recommendation
        confidence_pct = int(trace.confidence_score * 100)
        
        summaries = {
            DecisionType.ORDER_RECOMMENDATION: (
                f"Bishop recommends {recommendation}. "
                f"This decision is based on current inventory levels, demand forecast, and vendor availability. "
                f"Confidence: {confidence_pct}%."
            ),
            DecisionType.STOCKOUT_ALERT: (
                f"Bishop has detected a stockout risk: {recommendation}. "
                f"Based on current burn rate and inventory, action is recommended. "
                f"Confidence: {confidence_pct}%."
            ),
            DecisionType.VENDOR_SELECTION: (
                f"Bishop recommends vendor: {recommendation}. "
                f"Selection based on reliability score, pricing, and availability. "
                f"Confidence: {confidence_pct}%."
            ),
            DecisionType.DELAY_RECOMMENDATION: (
                f"Bishop recommends: {recommendation}. "
                f"This is based on cash flow analysis and downstream risk assessment. "
                f"Confidence: {confidence_pct}%."
            ),
            DecisionType.SALVAGE_RECOMMENDATION: (
                f"Bishop recommends disposition: {recommendation}. "
                f"This maximizes recovery value for at-risk inventory. "
                f"Confidence: {confidence_pct}%."
            ),
            DecisionType.REBALANCE_RECOMMENDATION: (
                f"Bishop recommends rebalancing: {recommendation}. "
                f"This optimizes inventory distribution across locations. "
                f"Confidence: {confidence_pct}%."
            ),
            DecisionType.WASTE_ALERT: (
                f"Bishop has flagged waste risk: {recommendation}. "
                f"Action recommended to minimize loss. "
                f"Confidence: {confidence_pct}%."
            ),
            DecisionType.PRICE_ALERT: (
                f"Bishop has detected: {recommendation}. "
                f"Price movement may impact margins. "
                f"Confidence: {confidence_pct}%."
            ),
            DecisionType.AUDIT_ALERT: (
                f"Bishop has identified: {recommendation}. "
                f"Compliance gap should be addressed. "
                f"Confidence: {confidence_pct}%."
            ),
            DecisionType.BENCHMARK_INSIGHT: (
                f"Bishop benchmark insight: {recommendation}. "
                f"Based on anonymous peer comparison. "
                f"Confidence: {confidence_pct}%."
            ),
        }
        
        return summaries.get(decision_type, f"Bishop recommends: {recommendation}. Confidence: {confidence_pct}%.")
    
    def _generate_reasoning_steps(self, trace: DecisionTrace) -> list[str]:
        """Generate step-by-step reasoning."""
        steps = []
        
        # Step 1: What triggered this
        if trace.inputs_used:
            primary_inputs = trace.inputs_used[:2]
            input_names = [i.input_name for i in primary_inputs]
            steps.append(f"Analyzed {', '.join(input_names)} to assess situation.")
        
        # Step 2: What policies were applied
        satisfied_policies = [p for p in trace.policies_applied if p.was_satisfied]
        if satisfied_policies:
            steps.append(f"Verified compliance with {len(satisfied_policies)} policies.")
        
        blocked_policies = [p for p in trace.policies_applied if not p.was_satisfied]
        if blocked_policies:
            steps.append(f"Note: {len(blocked_policies)} policy constraint(s) affected options.")
        
        # Step 3: Alternatives evaluated
        if trace.alternatives_considered:
            steps.append(f"Evaluated {len(trace.alternatives_considered)} alternative approaches.")
        
        # Step 4: Scoring
        confidence_level = self._determine_confidence_level(trace.confidence_score)
        steps.append(f"Calculated {confidence_level.value.replace('_', ' ')} confidence based on data quality and historical accuracy.")
        
        # Step 5: Final recommendation
        steps.append(f"Selected best option: {trace.recommendation}.")
        
        return steps[:self._config.max_reasoning_steps]
    
    def _format_inputs_used(self, trace: DecisionTrace) -> list[str]:
        """Format inputs as plain language list."""
        inputs = []
        
        for inp in trace.inputs_used[:self._config.max_inputs_to_show]:
            if inp.weight and inp.weight > Decimal("0.2"):
                inputs.append(f"{inp.input_name}: {inp.value} (key factor)")
            else:
                inputs.append(f"{inp.input_name}: {inp.value}")
        
        return inputs
    
    def _format_alternatives_rejected(self, trace: DecisionTrace) -> list[str]:
        """Format rejected alternatives as plain language list."""
        alternatives = []
        
        for alt in trace.alternatives_considered[:self._config.max_alternatives_to_show]:
            reason_text = {
                AlternativeStatus.LOWER_SCORE: "scored lower",
                AlternativeStatus.POLICY_VIOLATION: "violated policy",
                AlternativeStatus.INSUFFICIENT_DATA: "insufficient data",
                AlternativeStatus.RISK_TOO_HIGH: "risk too high",
                AlternativeStatus.COST_TOO_HIGH: "cost too high",
                AlternativeStatus.NOT_FEASIBLE: "not feasible",
                AlternativeStatus.TIMING_ISSUE: "timing conflict",
            }
            reason = reason_text.get(alt.rejection_reason, "not optimal")
            alternatives.append(f"{alt.alternative_name}: {reason}")
        
        return alternatives
    
    def _generate_confidence_factors(self, trace: DecisionTrace) -> list[str]:
        """Generate factors affecting confidence."""
        factors = []
        
        # Data quality
        if len(trace.inputs_used) >= 5:
            factors.append("Multiple data sources available")
        elif len(trace.inputs_used) >= 3:
            factors.append("Adequate data sources")
        else:
            factors.append("Limited data sources")
        
        # Policy compliance
        all_satisfied = all(p.was_satisfied for p in trace.policies_applied)
        if all_satisfied:
            factors.append("All policies satisfied")
        else:
            factors.append("Some policy constraints applied")
        
        # Alternatives
        if trace.alternatives_considered:
            best_alt_score = max((a.score or Decimal("0")) for a in trace.alternatives_considered)
            if trace.confidence_score - best_alt_score > Decimal("0.2"):
                factors.append("Clear winner among alternatives")
            else:
                factors.append("Close alternatives considered")
        
        return factors
    
    def _generate_what_would_change(self, trace: DecisionTrace) -> list[str]:
        """Generate hints about what would change the decision."""
        hints = []
        
        # Based on decision type
        if trace.decision_type == DecisionType.ORDER_RECOMMENDATION:
            hints.append("Different demand forecast could change order quantity")
            hints.append("Vendor price change could affect vendor selection")
        elif trace.decision_type == DecisionType.DELAY_RECOMMENDATION:
            hints.append("Improved cash flow would enable immediate ordering")
            hints.append("Higher stockout risk would prioritize speed")
        elif trace.decision_type == DecisionType.SALVAGE_RECOMMENDATION:
            hints.append("Transfer opportunity at another location would increase recovery")
            hints.append("Longer shelf life would enable different disposition")
        elif trace.decision_type == DecisionType.VENDOR_SELECTION:
            hints.append("Better reliability score from another vendor")
            hints.append("Price decrease from alternative vendor")
        
        return hints[:3]
    
    def explain(self, trace_id: uuid.UUID) -> Optional[Explanation]:
        """
        Generate explanation for a decision trace.
        
        Main entry point for the engine.
        """
        trace = self._traces.get(trace_id)
        if not trace:
            return None
        
        # Check cache
        if trace_id in self._explanations:
            return self._explanations[trace_id]
        
        # Generate explanation components
        summary = self._generate_summary(trace)
        inputs_used = self._format_inputs_used(trace)
        alternatives_rejected = self._format_alternatives_rejected(trace)
        reasoning_steps = self._generate_reasoning_steps(trace)
        confidence_level = self._determine_confidence_level(trace.confidence_score)
        confidence_factors = self._generate_confidence_factors(trace)
        what_would_change = self._generate_what_would_change(trace)
        
        # Primary factor
        primary_factor = None
        if trace.inputs_used:
            highest_weight = max(trace.inputs_used, key=lambda i: i.weight or Decimal("0"))
            if highest_weight.weight and highest_weight.weight > Decimal("0.2"):
                primary_factor = f"{highest_weight.input_name} ({highest_weight.value})"
        
        # Secondary factors
        secondary_factors = [
            i.input_name for i in trace.inputs_used[1:4]
            if i.weight and i.weight > Decimal("0.1")
        ]
        
        # Policy summary
        policies_summary = None
        if trace.policies_applied:
            satisfied = len([p for p in trace.policies_applied if p.was_satisfied])
            total = len(trace.policies_applied)
            policies_summary = f"{satisfied}/{total} policies satisfied"
        
        explanation = Explanation(
            decision_trace_id=trace_id,
            decision_type=trace.decision_type,
            summary=summary,
            inputs_used=inputs_used,
            confidence=trace.confidence_score,
            alternatives_rejected=alternatives_rejected,
            confidence_level=confidence_level,
            confidence_factors=confidence_factors,
            reasoning_steps=reasoning_steps,
            primary_factor=primary_factor,
            secondary_factors=secondary_factors,
            what_would_change=what_would_change,
            policies_summary=policies_summary,
        )
        
        # Cache
        self._explanations[trace_id] = explanation
        
        return explanation
    
    def explain_quick(self, trace_id: uuid.UUID) -> Optional[QuickExplanation]:
        """Generate quick one-liner explanation."""
        trace = self._traces.get(trace_id)
        if not trace:
            return None
        
        # One-liner based on type
        one_liners = {
            DecisionType.ORDER_RECOMMENDATION: f"Order {trace.recommendation} based on demand forecast",
            DecisionType.STOCKOUT_ALERT: f"Stockout risk: {trace.recommendation}",
            DecisionType.VENDOR_SELECTION: f"Best vendor: {trace.recommendation}",
            DecisionType.DELAY_RECOMMENDATION: f"Cash flow recommendation: {trace.recommendation}",
            DecisionType.SALVAGE_RECOMMENDATION: f"Salvage: {trace.recommendation}",
            DecisionType.WASTE_ALERT: f"Waste risk: {trace.recommendation}",
        }
        
        one_liner = one_liners.get(trace.decision_type, trace.recommendation)
        
        # Key reason
        key_reason = "Data-driven recommendation"
        if trace.inputs_used:
            key_reason = f"Primary factor: {trace.inputs_used[0].input_name}"
        
        return QuickExplanation(
            decision_trace_id=trace_id,
            one_liner=one_liner,
            confidence_pct=int(trace.confidence_score * 100),
            key_reason=key_reason,
        )
    
    def explain_detailed(self, trace_id: uuid.UUID) -> Optional[DetailedExplanation]:
        """Generate detailed explanation with full context."""
        trace = self._traces.get(trace_id)
        if not trace:
            return None
        
        explanation = self.explain(trace_id)
        if not explanation:
            return None
        
        # Find similar past decisions
        similar = []
        for t_id, t in self._traces.items():
            if t_id != trace_id and t.decision_type == trace.decision_type:
                similar.append({
                    "trace_id": str(t_id),
                    "recommendation": t.recommendation,
                    "timestamp": t.decision_timestamp.isoformat(),
                })
        
        return DetailedExplanation(
            explanation=explanation,
            trace=trace,
            similar_past_decisions=similar[:5],
            related_alerts=[],
            can_be_overridden=True,
            override_requires="Manager approval for policy override",
        )
    
    def clear_data(self) -> None:
        """Clear all data (for testing)."""
        self._traces.clear()
        self._explanations.clear()


# Singleton instance
explain_engine = ExplainEngine()
