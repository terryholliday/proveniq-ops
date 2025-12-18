"""
PROVENIQ Ops - Bishop What-If Scenario Simulator
Simulate alternative futures without executing any action.

GUARDRAILS:
- Simulation outputs are ADVISORY ONLY
- NEVER modifies inventory, orders, or ledger entries
- No downstream execution nodes may consume this output

LOGIC:
1. Clone current state
2. Apply hypothetical deltas
3. Re-run forecast, waste, cash, margin calculations
4. Compare against baseline
"""

import uuid
import copy
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.core.types import Money
from app.models.whatif import (
    CashFlowDelta,
    DelayOrderScenario,
    DemandForecastSnapshot,
    DemandShiftScenario,
    ImpactSeverity,
    InventorySnapshot,
    LiquiditySnapshot,
    MarginDelta,
    MarginSnapshot,
    PolicyTokens,
    PriceShiftScenario,
    ScenarioComparison,
    ScenarioDelta,
    ScenarioResult,
    ScenarioType,
    SimulationState,
    SimulatorConfig,
    StockoutDelta,
    SupplyDisruptionScenario,
    VendorChangeScenario,
    WasteDelta,
)


class WhatIfSimulator:
    """
    Bishop What-If Scenario Simulator
    
    Simulates alternative futures WITHOUT executing any action.
    
    IMPORTANT: This is READ-ONLY. It NEVER modifies:
    - Inventory
    - Orders
    - Ledger entries
    - Any real system state
    
    All outputs are ADVISORY ONLY.
    """
    
    def __init__(self) -> None:
        self._config = SimulatorConfig()
        
        # Current state snapshots (would be populated from real services)
        self._current_inventory: Optional[InventorySnapshot] = None
        self._current_demand: Optional[DemandForecastSnapshot] = None
        self._current_liquidity: Optional[LiquiditySnapshot] = None
        self._current_margins: Optional[MarginSnapshot] = None
        self._current_policy: PolicyTokens = PolicyTokens()
        
        # Simulation history (for comparison)
        self._simulation_history: list[ScenarioResult] = []
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure(self, config: SimulatorConfig) -> None:
        """Update simulator configuration."""
        self._config = config
    
    def get_config(self) -> SimulatorConfig:
        """Get current configuration."""
        return self._config
    
    # =========================================================================
    # STATE REGISTRATION (from real services)
    # =========================================================================
    
    def update_inventory_snapshot(self, snapshot: InventorySnapshot) -> None:
        """Update current inventory state from real inventory service."""
        self._current_inventory = snapshot
    
    def update_demand_snapshot(self, snapshot: DemandForecastSnapshot) -> None:
        """Update current demand forecast from real forecasting service."""
        self._current_demand = snapshot
    
    def update_liquidity_snapshot(self, snapshot: LiquiditySnapshot) -> None:
        """Update current liquidity state from real ledger service."""
        self._current_liquidity = snapshot
    
    def update_margin_snapshot(self, snapshot: MarginSnapshot) -> None:
        """Update current margin state from real menu cost service."""
        self._current_margins = snapshot
    
    def update_policy(self, policy: PolicyTokens) -> None:
        """Update current policy tokens."""
        self._current_policy = policy
    
    # =========================================================================
    # STATE CLONING (Step 1)
    # =========================================================================
    
    def _clone_current_state(self) -> SimulationState:
        """
        Clone current state for simulation.
        
        This creates a DEEP COPY - modifications to the clone
        do NOT affect real system state.
        """
        return SimulationState(
            inventory=copy.deepcopy(self._current_inventory) or InventorySnapshot(),
            demand=copy.deepcopy(self._current_demand) or DemandForecastSnapshot(),
            liquidity=copy.deepcopy(self._current_liquidity) or LiquiditySnapshot(
                cash_balance_micros=0,
                available_balance_micros=0,
            ),
            margins=copy.deepcopy(self._current_margins) or MarginSnapshot(),
            policy=copy.deepcopy(self._current_policy),
            is_baseline=True,
        )
    
    # =========================================================================
    # SCENARIO APPLICATION (Step 2)
    # =========================================================================
    
    def _apply_delay_order(
        self,
        state: SimulationState,
        scenario: DelayOrderScenario,
    ) -> SimulationState:
        """Apply order delay scenario to state."""
        modified = copy.deepcopy(state)
        modified.is_baseline = False
        modified.applied_scenario = f"Delay order by {scenario.delay_hours}h"
        
        # Simulate inventory depletion during delay
        for product_id in scenario.affected_products:
            if product_id in modified.inventory.items:
                # Calculate depletion during delay
                daily_demand = modified.demand.daily_demand.get(product_id, Decimal("0"))
                hours_demand = daily_demand * Decimal(scenario.delay_hours) / Decimal("24")
                
                # Reduce inventory
                current = modified.inventory.items[product_id]
                modified.inventory.items[product_id] = max(Decimal("0"), current - hours_demand)
        
        # Cash flow improves temporarily (delayed payment)
        # Simplified: assume $5k per order delayed
        modified.liquidity.available_balance_micros += 5_000_000_000
        
        return modified
    
    def _apply_vendor_change(
        self,
        state: SimulationState,
        scenario: VendorChangeScenario,
    ) -> SimulationState:
        """Apply vendor change scenario to state."""
        modified = copy.deepcopy(state)
        modified.is_baseline = False
        modified.applied_scenario = f"Switch from {scenario.from_vendor} to {scenario.to_vendor}"
        
        # Apply price change to margins
        for product_id in scenario.affected_products:
            if product_id in modified.margins.margins:
                current_margin = modified.margins.margins[product_id]
                # Price increase reduces margin, decrease improves it
                margin_impact = -scenario.price_change_pct * Decimal("0.5")  # Rough approximation
                modified.margins.margins[product_id] = current_margin + margin_impact
        
        # Lead time change affects stockout risk (handled in calculation)
        
        return modified
    
    def _apply_price_shift(
        self,
        state: SimulationState,
        scenario: PriceShiftScenario,
    ) -> SimulationState:
        """Apply price shift scenario to state."""
        modified = copy.deepcopy(state)
        modified.is_baseline = False
        modified.applied_scenario = f"Price shift: {scenario.price_change_pct}%"
        
        # Price change affects margins
        if scenario.product_id and scenario.product_id in modified.margins.margins:
            current_margin = modified.margins.margins[scenario.product_id]
            # Cost increase reduces margin
            margin_impact = -scenario.price_change_pct * Decimal("0.7")
            modified.margins.margins[scenario.product_id] = current_margin + margin_impact
        else:
            # Apply to all margins
            for product_id in modified.margins.margins:
                current = modified.margins.margins[product_id]
                margin_impact = -scenario.price_change_pct * Decimal("0.7")
                modified.margins.margins[product_id] = current + margin_impact
        
        # Recalculate average
        if modified.margins.margins:
            modified.margins.avg_margin_pct = sum(modified.margins.margins.values()) / len(modified.margins.margins)
        
        return modified
    
    def _apply_demand_shift(
        self,
        state: SimulationState,
        scenario: DemandShiftScenario,
    ) -> SimulationState:
        """Apply demand spike/drop scenario to state."""
        modified = copy.deepcopy(state)
        modified.is_baseline = False
        
        direction = "spike" if scenario.demand_change_pct > 0 else "drop"
        modified.applied_scenario = f"Demand {direction}: {scenario.demand_change_pct}%"
        
        # Adjust demand forecast
        multiplier = Decimal("1") + scenario.demand_change_pct / Decimal("100")
        
        products_to_adjust = scenario.affected_products or list(modified.demand.daily_demand.keys())
        for product_id in products_to_adjust:
            if product_id in modified.demand.daily_demand:
                modified.demand.daily_demand[product_id] *= multiplier
        
        return modified
    
    def _apply_supply_disruption(
        self,
        state: SimulationState,
        scenario: SupplyDisruptionScenario,
    ) -> SimulationState:
        """Apply supply disruption scenario to state."""
        modified = copy.deepcopy(state)
        modified.is_baseline = False
        modified.applied_scenario = f"Supply disruption: {scenario.vendor_name} for {scenario.disruption_days}d"
        
        # Simulate inventory depletion during disruption
        for product_id in scenario.affected_products:
            if product_id in modified.inventory.items:
                daily_demand = modified.demand.daily_demand.get(product_id, Decimal("0"))
                depletion = daily_demand * scenario.disruption_days
                
                current = modified.inventory.items[product_id]
                modified.inventory.items[product_id] = max(Decimal("0"), current - depletion)
        
        return modified
    
    # =========================================================================
    # CALCULATIONS (Step 3)
    # =========================================================================
    
    def _calculate_stockout_risk(self, state: SimulationState) -> tuple[Decimal, int, int]:
        """
        Calculate stockout risk hours and affected items.
        
        Returns: (avg_stockout_hours, items_at_risk, items_critical)
        """
        items_at_risk = 0
        items_critical = 0
        total_risk_hours = Decimal("0")
        
        for product_id, qty in state.inventory.items.items():
            daily_demand = state.demand.daily_demand.get(product_id, Decimal("1"))
            if daily_demand > 0:
                days_of_supply = qty / daily_demand
                hours_of_supply = days_of_supply * Decimal("24")
                
                if hours_of_supply < state.policy.stockout_critical_days * 24:
                    items_critical += 1
                    items_at_risk += 1
                    # Risk hours = how many hours until stockout
                    total_risk_hours += max(Decimal("0"), Decimal(state.policy.stockout_critical_days * 24) - hours_of_supply)
                elif hours_of_supply < state.policy.stockout_warning_days * 24:
                    items_at_risk += 1
        
        avg_risk = total_risk_hours / max(1, items_at_risk) if items_at_risk > 0 else Decimal("0")
        return avg_risk, items_at_risk, items_critical
    
    def _calculate_cash_impact(
        self,
        baseline: SimulationState,
        scenario: SimulationState,
    ) -> CashFlowDelta:
        """Calculate cash flow impact."""
        baseline_balance = baseline.liquidity.available_balance_micros
        scenario_balance = scenario.liquidity.available_balance_micros
        delta = scenario_balance - baseline_balance
        
        crosses_threshold = (
            scenario_balance < self._current_policy.minimum_reserve_micros and
            baseline_balance >= self._current_policy.minimum_reserve_micros
        )
        
        # Calculate runway change (simplified)
        daily_burn = baseline.liquidity.obligations_7d_micros / 7 if baseline.liquidity.obligations_7d_micros > 0 else 1
        runway_change = Decimal(delta) / Decimal(max(1, daily_burn))
        
        return CashFlowDelta(
            baseline_balance_micros=baseline_balance,
            scenario_balance_micros=scenario_balance,
            delta_micros=delta,
            crosses_reserve_threshold=crosses_threshold,
            days_of_runway_change=runway_change.quantize(Decimal("0.1")),
        )
    
    def _calculate_waste_risk(
        self,
        baseline: SimulationState,
        scenario: SimulationState,
    ) -> WasteDelta:
        """Calculate waste risk change."""
        # Simplified: overstock items have waste risk
        baseline_waste = Decimal("0")
        scenario_waste = Decimal("0")
        
        for product_id, qty in baseline.inventory.items.items():
            daily_demand = baseline.demand.daily_demand.get(product_id, Decimal("1"))
            days_of_supply = qty / daily_demand if daily_demand > 0 else Decimal("30")
            if days_of_supply > 14:  # Overstock
                baseline_waste += Decimal("0.5")  # 0.5% waste risk per overstock item
        
        for product_id, qty in scenario.inventory.items.items():
            daily_demand = scenario.demand.daily_demand.get(product_id, Decimal("1"))
            days_of_supply = qty / daily_demand if daily_demand > 0 else Decimal("30")
            if days_of_supply > 14:
                scenario_waste += Decimal("0.5")
        
        return WasteDelta(
            baseline_waste_pct=baseline_waste,
            scenario_waste_pct=scenario_waste,
            delta_pct=scenario_waste - baseline_waste,
        )
    
    def _calculate_margin_impact(
        self,
        baseline: SimulationState,
        scenario: SimulationState,
    ) -> MarginDelta:
        """Calculate margin impact."""
        baseline_avg = baseline.margins.avg_margin_pct or Decimal("50")
        scenario_avg = scenario.margins.avg_margin_pct or Decimal("50")
        
        # Count items with decreased margin
        decreased = 0
        below_threshold = 0
        
        for product_id, margin in scenario.margins.margins.items():
            baseline_margin = baseline.margins.margins.get(product_id, margin)
            if margin < baseline_margin:
                decreased += 1
            if margin < self._current_policy.margin_critical_pct:
                below_threshold += 1
        
        return MarginDelta(
            baseline_avg_margin_pct=baseline_avg,
            scenario_avg_margin_pct=scenario_avg,
            delta_pct=scenario_avg - baseline_avg,
            items_margin_decreased=decreased,
            items_below_threshold=below_threshold,
        )
    
    # =========================================================================
    # IMPACT CLASSIFICATION
    # =========================================================================
    
    def _classify_impact(self, delta: ScenarioDelta) -> ImpactSeverity:
        """Classify the overall impact severity."""
        # Check stockout risk
        if delta.stockout_risk_hours > self._config.high_stockout_hours:
            return ImpactSeverity.CRITICAL
        if delta.stockout_risk_hours > self._config.moderate_stockout_hours:
            return ImpactSeverity.HIGH
        
        # Check cash impact
        cash_abs = abs(delta.cash_flow_change_micros)
        if cash_abs > self._config.high_cash_impact:
            return ImpactSeverity.HIGH
        if cash_abs > self._config.moderate_cash_impact:
            return ImpactSeverity.MODERATE
        
        # Check margin impact
        if delta.margin_change_pct < Decimal("-10"):
            return ImpactSeverity.HIGH
        if delta.margin_change_pct < Decimal("-5"):
            return ImpactSeverity.MODERATE
        
        # Check stockout moderate
        if delta.stockout_risk_hours > self._config.low_stockout_hours:
            return ImpactSeverity.MODERATE
        if delta.stockout_risk_hours > self._config.negligible_stockout_hours:
            return ImpactSeverity.LOW
        
        return ImpactSeverity.NEGLIGIBLE
    
    # =========================================================================
    # CONFIDENCE CALCULATION
    # =========================================================================
    
    def _calculate_confidence(self, scenario_type: ScenarioType) -> Decimal:
        """Calculate simulation confidence based on scenario type."""
        base = self._config.base_confidence
        
        # Adjust based on scenario complexity
        adjustments = {
            ScenarioType.DELAY_ORDER: Decimal("0"),
            ScenarioType.PRICE_SHIFT: Decimal("-0.05"),
            ScenarioType.VENDOR_CHANGE: Decimal("-0.10"),
            ScenarioType.DEMAND_SPIKE: Decimal("-0.10"),
            ScenarioType.DEMAND_DROP: Decimal("-0.08"),
            ScenarioType.SUPPLY_DISRUPTION: Decimal("-0.15"),
            ScenarioType.CUSTOM: Decimal("-0.20"),
        }
        
        adjustment = adjustments.get(scenario_type, Decimal("0"))
        return max(Decimal("0.50"), base + adjustment)
    
    # =========================================================================
    # MAIN SIMULATION ENTRY POINTS
    # =========================================================================
    
    def simulate_delay_order(self, scenario: DelayOrderScenario) -> ScenarioResult:
        """Simulate delaying an order."""
        start_time = time.time()
        
        # Step 1: Clone state
        baseline = self._clone_current_state()
        
        # Step 2: Apply scenario
        modified = self._apply_delay_order(baseline, scenario)
        
        # Step 3: Calculate impacts
        baseline_risk, _, _ = self._calculate_stockout_risk(baseline)
        scenario_risk, items_at_risk, items_critical = self._calculate_stockout_risk(modified)
        
        stockout_delta = StockoutDelta(
            baseline_risk_hours=baseline_risk,
            scenario_risk_hours=scenario_risk,
            delta_hours=scenario_risk - baseline_risk,
            items_newly_at_risk=items_at_risk,
        )
        
        cash_delta = self._calculate_cash_impact(baseline, modified)
        waste_delta = self._calculate_waste_risk(baseline, modified)
        margin_delta = self._calculate_margin_impact(baseline, modified)
        
        delta = ScenarioDelta(
            stockout_risk_hours=stockout_delta.delta_hours,
            cash_flow_change_micros=cash_delta.delta_micros,
            waste_risk_change_pct=waste_delta.delta_pct,
            margin_change_pct=margin_delta.delta_pct,
            stockout_detail=stockout_delta,
            cashflow_detail=cash_delta,
            waste_detail=waste_delta,
            margin_detail=margin_delta,
        )
        
        # Step 4: Generate result
        impact = self._classify_impact(delta)
        confidence = self._calculate_confidence(ScenarioType.DELAY_ORDER)
        
        # Generate recommendations
        recommendations = []
        warnings = []
        
        if stockout_delta.delta_hours > 0:
            warnings.append(f"Stockout risk increases by {stockout_delta.delta_hours:.0f} hours")
        if cash_delta.delta_micros > 0:
            recommendations.append(f"Cash position improves by ${cash_delta.delta_micros / 1_000_000:.0f}")
        if cash_delta.crosses_reserve_threshold:
            warnings.append("WARNING: Scenario crosses minimum reserve threshold")
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        result = ScenarioResult(
            scenario_type=ScenarioType.DELAY_ORDER,
            scenario_description=f"Delay order by {scenario.delay_hours} hours",
            delta=delta,
            confidence=confidence,
            impact_severity=impact,
            recommendations=recommendations,
            warnings=warnings,
            simulation_duration_ms=duration_ms,
        )
        
        self._simulation_history.append(result)
        return result
    
    def simulate_demand_shift(self, scenario: DemandShiftScenario) -> ScenarioResult:
        """Simulate demand spike or drop."""
        start_time = time.time()
        
        baseline = self._clone_current_state()
        modified = self._apply_demand_shift(baseline, scenario)
        
        baseline_risk, _, _ = self._calculate_stockout_risk(baseline)
        scenario_risk, items_at_risk, items_critical = self._calculate_stockout_risk(modified)
        
        stockout_delta = StockoutDelta(
            baseline_risk_hours=baseline_risk,
            scenario_risk_hours=scenario_risk,
            delta_hours=scenario_risk - baseline_risk,
            items_newly_at_risk=items_at_risk,
        )
        
        cash_delta = self._calculate_cash_impact(baseline, modified)
        waste_delta = self._calculate_waste_risk(baseline, modified)
        margin_delta = self._calculate_margin_impact(baseline, modified)
        
        delta = ScenarioDelta(
            stockout_risk_hours=stockout_delta.delta_hours,
            cash_flow_change_micros=cash_delta.delta_micros,
            waste_risk_change_pct=waste_delta.delta_pct,
            margin_change_pct=margin_delta.delta_pct,
            stockout_detail=stockout_delta,
            cashflow_detail=cash_delta,
            waste_detail=waste_delta,
            margin_detail=margin_delta,
        )
        
        scenario_type = ScenarioType.DEMAND_SPIKE if scenario.demand_change_pct > 0 else ScenarioType.DEMAND_DROP
        impact = self._classify_impact(delta)
        confidence = self._calculate_confidence(scenario_type)
        
        recommendations = []
        warnings = []
        
        if scenario.demand_change_pct > 0:
            if stockout_delta.delta_hours > 12:
                warnings.append(f"Demand spike creates {stockout_delta.delta_hours:.0f}h additional stockout risk")
                recommendations.append("Consider expediting orders for affected products")
        else:
            if waste_delta.delta_pct > 0:
                warnings.append(f"Demand drop increases waste risk by {waste_delta.delta_pct:.1f}%")
                recommendations.append("Consider promotional pricing or donation for excess inventory")
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        result = ScenarioResult(
            scenario_type=scenario_type,
            scenario_description=f"Demand shift: {scenario.demand_change_pct:+.0f}% for {scenario.duration_days} days",
            delta=delta,
            confidence=confidence,
            impact_severity=impact,
            recommendations=recommendations,
            warnings=warnings,
            simulation_duration_ms=duration_ms,
        )
        
        self._simulation_history.append(result)
        return result
    
    def simulate_price_shift(self, scenario: PriceShiftScenario) -> ScenarioResult:
        """Simulate vendor price change."""
        start_time = time.time()
        
        baseline = self._clone_current_state()
        modified = self._apply_price_shift(baseline, scenario)
        
        baseline_risk, _, _ = self._calculate_stockout_risk(baseline)
        scenario_risk, items_at_risk, _ = self._calculate_stockout_risk(modified)
        
        stockout_delta = StockoutDelta(
            baseline_risk_hours=baseline_risk,
            scenario_risk_hours=scenario_risk,
            delta_hours=scenario_risk - baseline_risk,
        )
        
        cash_delta = self._calculate_cash_impact(baseline, modified)
        waste_delta = self._calculate_waste_risk(baseline, modified)
        margin_delta = self._calculate_margin_impact(baseline, modified)
        
        delta = ScenarioDelta(
            stockout_risk_hours=stockout_delta.delta_hours,
            cash_flow_change_micros=cash_delta.delta_micros,
            waste_risk_change_pct=waste_delta.delta_pct,
            margin_change_pct=margin_delta.delta_pct,
            stockout_detail=stockout_delta,
            cashflow_detail=cash_delta,
            waste_detail=waste_delta,
            margin_detail=margin_delta,
        )
        
        impact = self._classify_impact(delta)
        confidence = self._calculate_confidence(ScenarioType.PRICE_SHIFT)
        
        recommendations = []
        warnings = []
        
        if scenario.price_change_pct > 0:
            warnings.append(f"Price increase of {scenario.price_change_pct}% reduces margins")
            if margin_delta.items_below_threshold > 0:
                warnings.append(f"{margin_delta.items_below_threshold} items fall below margin threshold")
            recommendations.append("Evaluate alternative vendors or menu price adjustment")
        else:
            recommendations.append(f"Price decrease of {abs(scenario.price_change_pct)}% improves margins")
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        result = ScenarioResult(
            scenario_type=ScenarioType.PRICE_SHIFT,
            scenario_description=f"Price shift: {scenario.price_change_pct:+.1f}%",
            delta=delta,
            confidence=confidence,
            impact_severity=impact,
            recommendations=recommendations,
            warnings=warnings,
            simulation_duration_ms=duration_ms,
        )
        
        self._simulation_history.append(result)
        return result
    
    def simulate_supply_disruption(self, scenario: SupplyDisruptionScenario) -> ScenarioResult:
        """Simulate supply chain disruption."""
        start_time = time.time()
        
        baseline = self._clone_current_state()
        modified = self._apply_supply_disruption(baseline, scenario)
        
        baseline_risk, _, _ = self._calculate_stockout_risk(baseline)
        scenario_risk, items_at_risk, items_critical = self._calculate_stockout_risk(modified)
        
        stockout_delta = StockoutDelta(
            baseline_risk_hours=baseline_risk,
            scenario_risk_hours=scenario_risk,
            delta_hours=scenario_risk - baseline_risk,
            items_newly_at_risk=items_at_risk,
        )
        
        cash_delta = self._calculate_cash_impact(baseline, modified)
        waste_delta = self._calculate_waste_risk(baseline, modified)
        margin_delta = self._calculate_margin_impact(baseline, modified)
        
        delta = ScenarioDelta(
            stockout_risk_hours=stockout_delta.delta_hours,
            cash_flow_change_micros=cash_delta.delta_micros,
            waste_risk_change_pct=waste_delta.delta_pct,
            margin_change_pct=margin_delta.delta_pct,
            stockout_detail=stockout_delta,
            cashflow_detail=cash_delta,
            waste_detail=waste_delta,
            margin_detail=margin_delta,
        )
        
        impact = self._classify_impact(delta)
        confidence = self._calculate_confidence(ScenarioType.SUPPLY_DISRUPTION)
        
        recommendations = []
        warnings = []
        
        warnings.append(f"Supply disruption from {scenario.vendor_name} for {scenario.disruption_days} days")
        if items_critical > 0:
            warnings.append(f"CRITICAL: {items_critical} items reach critical stockout")
        if items_at_risk > 0:
            recommendations.append(f"Identify backup vendors for {items_at_risk} affected products")
        recommendations.append("Consider expedited orders from alternative suppliers")
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        result = ScenarioResult(
            scenario_type=ScenarioType.SUPPLY_DISRUPTION,
            scenario_description=f"Supply disruption: {scenario.vendor_name} for {scenario.disruption_days}d",
            delta=delta,
            confidence=confidence,
            impact_severity=impact,
            recommendations=recommendations,
            warnings=warnings,
            simulation_duration_ms=duration_ms,
        )
        
        self._simulation_history.append(result)
        return result
    
    # =========================================================================
    # COMPARISON
    # =========================================================================
    
    def compare_scenarios(self, scenario_ids: list[uuid.UUID]) -> ScenarioComparison:
        """Compare multiple simulation results."""
        scenarios = [
            s for s in self._simulation_history
            if s.scenario_id in scenario_ids
        ]
        
        if not scenarios:
            return ScenarioComparison(scenarios=[])
        
        # Find best scenario (lowest negative impact)
        best = min(scenarios, key=lambda s: (
            float(s.delta.stockout_risk_hours) * 2 +  # Weight stockout heavily
            abs(float(s.delta.margin_change_pct)) +
            float(s.delta.waste_risk_change_pct)
        ))
        
        return ScenarioComparison(
            scenarios=scenarios,
            recommended_scenario_id=best.scenario_id,
            recommendation_reason=f"Lowest combined impact: {best.impact_severity.value}",
        )
    
    # =========================================================================
    # QUERY
    # =========================================================================
    
    def get_simulation_history(self, limit: int = 20) -> list[ScenarioResult]:
        """Get recent simulation history."""
        return self._simulation_history[-limit:]
    
    def clear_history(self) -> None:
        """Clear simulation history."""
        self._simulation_history.clear()


# Singleton instance
whatif_simulator = WhatIfSimulator()
