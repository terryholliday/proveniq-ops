"""
PROVENIQ Ops - Bishop Cost of Delay Calculator
Quantify the financial impact of inaction.

LOGIC:
1. Calculate savings from delay
2. Calculate downstream risk costs
3. Net the difference
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.core.types import Money
from app.models.costdelay import (
    BatchDelayAnalysis,
    CostDelayConfig,
    DelayAnalysis,
    DelayReason,
    DelayRecommendation,
    DelayRiskCosts,
    DelaySavings,
    DemandForecastItem,
    LiquidityState,
    MultiDelayComparison,
    PendingOrder,
    RiskCost,
    RiskType,
    WasteRiskItem,
)


class CostOfDelayCalculator:
    """
    Bishop Cost of Delay Calculator
    
    Quantifies the financial impact of delaying orders.
    """
    
    def __init__(self) -> None:
        self._config = CostDelayConfig()
        
        # Registered data
        self._pending_orders: dict[uuid.UUID, PendingOrder] = {}
        self._demand_forecasts: dict[uuid.UUID, DemandForecastItem] = {}  # by product_id
        self._waste_risks: dict[uuid.UUID, WasteRiskItem] = {}  # by product_id
        self._liquidity: Optional[LiquidityState] = None
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure(self, config: CostDelayConfig) -> None:
        """Update configuration."""
        self._config = config
    
    def get_config(self) -> CostDelayConfig:
        """Get current configuration."""
        return self._config
    
    # =========================================================================
    # DATA REGISTRATION
    # =========================================================================
    
    def register_order(self, order: PendingOrder) -> None:
        """Register a pending order."""
        self._pending_orders[order.order_id] = order
    
    def register_demand_forecast(self, forecast: DemandForecastItem) -> None:
        """Register demand forecast for a product."""
        self._demand_forecasts[forecast.product_id] = forecast
    
    def register_waste_risk(self, risk: WasteRiskItem) -> None:
        """Register waste risk for a product."""
        self._waste_risks[risk.product_id] = risk
    
    def update_liquidity(self, state: LiquidityState) -> None:
        """Update current liquidity state."""
        self._liquidity = state
    
    # =========================================================================
    # SAVINGS CALCULATION (Step 1)
    # =========================================================================
    
    def _calculate_savings(
        self,
        order: PendingOrder,
        delay_hours: int,
    ) -> DelaySavings:
        """Calculate savings from delaying an order."""
        order_value = order.total_cost_micros
        
        # Cash retained = order value (not spent yet)
        cash_retained = order_value
        
        # Interest saved (opportunity cost of money)
        delay_days = Decimal(delay_hours) / Decimal("24")
        interest_saved = int(order_value * self._config.daily_interest_rate * delay_days)
        
        # Negotiation potential (longer delay = more time to negotiate)
        negotiation_potential = 0
        if delay_hours >= 48:
            # Assume 1-2% potential savings from negotiation
            negotiation_potential = int(order_value * Decimal("0.015"))
        
        # Batch consolidation (if delaying allows combining with other orders)
        consolidation_savings = 0
        if delay_hours >= 24:
            # Estimate shipping savings from consolidation
            consolidation_savings = int(order_value * Decimal("0.02"))
        
        total = cash_retained + interest_saved + negotiation_potential + consolidation_savings
        
        return DelaySavings(
            cash_retained_micros=cash_retained,
            interest_saved_micros=interest_saved,
            negotiation_potential_micros=negotiation_potential,
            consolidation_savings_micros=consolidation_savings,
            total_savings_micros=total,
        )
    
    # =========================================================================
    # RISK COST CALCULATION (Step 2)
    # =========================================================================
    
    def _calculate_risk_costs(
        self,
        order: PendingOrder,
        delay_hours: int,
    ) -> DelayRiskCosts:
        """Calculate downstream risk costs from delay."""
        risks = []
        
        # Get products in this order
        order_products = {item.get("product_id") for item in order.items if item.get("product_id")}
        
        # Calculate stockout risk
        stockout_risk = self._calculate_stockout_risk(order, delay_hours, order_products)
        if stockout_risk:
            risks.append(stockout_risk)
        
        # Calculate lost sales risk
        lost_sales_risk = self._calculate_lost_sales_risk(order, delay_hours, order_products)
        if lost_sales_risk:
            risks.append(lost_sales_risk)
        
        # Calculate expedited shipping risk
        expedited_risk = self._calculate_expedited_shipping_risk(order, delay_hours)
        if expedited_risk:
            risks.append(expedited_risk)
        
        # Calculate emergency vendor risk
        emergency_risk = self._calculate_emergency_vendor_risk(order, delay_hours)
        if emergency_risk:
            risks.append(emergency_risk)
        
        # Calculate waste increase risk (if delay causes overstock later)
        waste_risk = self._calculate_waste_increase_risk(order, delay_hours, order_products)
        if waste_risk:
            risks.append(waste_risk)
        
        # Calculate customer impact risk
        customer_risk = self._calculate_customer_impact_risk(order, delay_hours, order_products)
        if customer_risk:
            risks.append(customer_risk)
        
        # Totals
        total_expected = sum(r.expected_cost_micros for r in risks)
        worst_case = sum(r.impact_micros for r in risks)
        
        # Primary risk
        primary = None
        primary_hours = 0
        if risks:
            primary_risk = max(risks, key=lambda r: r.expected_cost_micros)
            primary = primary_risk.risk_type
            primary_hours = primary_risk.hours_until_risk
        
        return DelayRiskCosts(
            risks=risks,
            total_expected_cost_micros=total_expected,
            worst_case_cost_micros=worst_case,
            primary_risk=primary,
            primary_risk_hours=primary_hours,
        )
    
    def _calculate_stockout_risk(
        self,
        order: PendingOrder,
        delay_hours: int,
        products: set,
    ) -> Optional[RiskCost]:
        """Calculate stockout risk cost."""
        max_probability = Decimal("0")
        total_impact = 0
        min_hours = 999
        
        for product_id in products:
            if product_id and product_id in self._demand_forecasts:
                forecast = self._demand_forecasts[product_id]
                
                # Calculate if delay causes stockout
                delay_days = Decimal(delay_hours) / Decimal("24")
                demand_during_delay = forecast.daily_demand * delay_days
                
                if forecast.current_inventory - demand_during_delay <= 0:
                    # Stockout would occur
                    probability = min(Decimal("0.95"), Decimal("0.5") + forecast.stockout_risk_pct)
                    max_probability = max(max_probability, probability)
                    
                    # Impact = lost margin + customer impact
                    item_value = next(
                        (i.get("unit_cost", 0) * i.get("qty", 0) for i in order.items 
                         if i.get("product_id") == product_id), 0
                    )
                    impact = int(item_value * self._config.stockout_cost_multiplier)
                    total_impact += impact
                    
                    # Hours until stockout
                    if forecast.daily_demand > 0:
                        hours = int(float(forecast.current_inventory / forecast.daily_demand) * 24)
                        min_hours = min(min_hours, hours)
        
        if max_probability > 0:
            expected = int(total_impact * max_probability)
            return RiskCost(
                risk_type=RiskType.STOCKOUT,
                description=f"Stockout risk if order delayed {delay_hours}h",
                probability_pct=max_probability * 100,
                impact_micros=total_impact,
                expected_cost_micros=expected,
                hours_until_risk=min_hours if min_hours < 999 else delay_hours,
            )
        
        return None
    
    def _calculate_lost_sales_risk(
        self,
        order: PendingOrder,
        delay_hours: int,
        products: set,
    ) -> Optional[RiskCost]:
        """Calculate lost sales risk from stockout."""
        # Lost sales = extension of stockout risk
        # Assume 50% of stockout value is permanent lost sales
        
        for product_id in products:
            if product_id and product_id in self._demand_forecasts:
                forecast = self._demand_forecasts[product_id]
                
                if forecast.days_of_supply * 24 < delay_hours:
                    # Would run out during delay
                    stockout_hours = delay_hours - int(forecast.days_of_supply * 24)
                    hourly_demand_value = int(order.total_cost_micros / len(order.items) / 24)
                    
                    impact = stockout_hours * hourly_demand_value
                    probability = min(Decimal("0.70"), forecast.stockout_risk_pct + Decimal("0.3"))
                    
                    return RiskCost(
                        risk_type=RiskType.LOST_SALES,
                        description=f"Potential lost sales from {stockout_hours}h stockout",
                        probability_pct=probability * 100,
                        impact_micros=impact,
                        expected_cost_micros=int(impact * probability),
                        hours_until_risk=int(forecast.days_of_supply * 24),
                    )
        
        return None
    
    def _calculate_expedited_shipping_risk(
        self,
        order: PendingOrder,
        delay_hours: int,
    ) -> Optional[RiskCost]:
        """Calculate risk of needing expedited shipping later."""
        if delay_hours < 24:
            return None
        
        # If we delay now, we may need to expedite later
        # Probability increases with delay length
        probability = min(Decimal("0.60"), Decimal(delay_hours) / 200)
        
        # Expedited shipping premium
        shipping_estimate = int(order.total_cost_micros * Decimal("0.05"))  # 5% of order = shipping
        premium = int(shipping_estimate * (self._config.expedited_shipping_multiplier - 1))
        
        if premium > 0:
            return RiskCost(
                risk_type=RiskType.EXPEDITED_SHIPPING,
                description="May need expedited shipping if delayed",
                probability_pct=probability * 100,
                impact_micros=premium,
                expected_cost_micros=int(premium * probability),
                hours_until_risk=delay_hours,
            )
        
        return None
    
    def _calculate_emergency_vendor_risk(
        self,
        order: PendingOrder,
        delay_hours: int,
    ) -> Optional[RiskCost]:
        """Calculate risk of needing emergency vendor."""
        if delay_hours < 48:
            return None
        
        # Emergency vendor = higher prices
        probability = min(Decimal("0.40"), Decimal(delay_hours) / 300)
        premium = int(order.total_cost_micros * (self._config.emergency_vendor_multiplier - 1))
        
        if premium > 0:
            return RiskCost(
                risk_type=RiskType.EMERGENCY_VENDOR,
                description="May need emergency vendor at premium pricing",
                probability_pct=probability * 100,
                impact_micros=premium,
                expected_cost_micros=int(premium * probability),
                hours_until_risk=delay_hours + 24,
            )
        
        return None
    
    def _calculate_waste_increase_risk(
        self,
        order: PendingOrder,
        delay_hours: int,
        products: set,
    ) -> Optional[RiskCost]:
        """Calculate risk that delay leads to overstock and waste later."""
        # If we rush order after delay, might over-order
        if delay_hours < 72:
            return None
        
        waste_risk_value = 0
        for product_id in products:
            if product_id and product_id in self._waste_risks:
                risk = self._waste_risks[product_id]
                waste_risk_value += risk.value_at_risk_micros
        
        if waste_risk_value > 0:
            probability = Decimal("0.20")  # 20% chance delay causes overstock
            return RiskCost(
                risk_type=RiskType.WASTE_INCREASE,
                description="Risk of overstock/waste from rushed reorder",
                probability_pct=probability * 100,
                impact_micros=waste_risk_value,
                expected_cost_micros=int(waste_risk_value * probability),
                hours_until_risk=delay_hours + 48,
            )
        
        return None
    
    def _calculate_customer_impact_risk(
        self,
        order: PendingOrder,
        delay_hours: int,
        products: set,
    ) -> Optional[RiskCost]:
        """Calculate customer impact from potential stockout."""
        # Only if high stockout probability
        for product_id in products:
            if product_id and product_id in self._demand_forecasts:
                forecast = self._demand_forecasts[product_id]
                
                if forecast.days_of_supply < self._config.critical_days_of_supply:
                    # Critical item - customer impact likely
                    probability = min(Decimal("0.50"), forecast.stockout_risk_pct + Decimal("0.2"))
                    
                    return RiskCost(
                        risk_type=RiskType.CUSTOMER_IMPACT,
                        description="Customer experience impact from menu 86",
                        probability_pct=probability * 100,
                        impact_micros=self._config.customer_impact_per_stockout_micros,
                        expected_cost_micros=int(self._config.customer_impact_per_stockout_micros * probability),
                        hours_until_risk=int(forecast.days_of_supply * 24),
                    )
        
        return None
    
    # =========================================================================
    # RECOMMENDATION
    # =========================================================================
    
    def _determine_recommendation(
        self,
        savings: DelaySavings,
        risks: DelayRiskCosts,
        delay_hours: int,
        order: PendingOrder,
    ) -> tuple[DelayRecommendation, str]:
        """Determine recommendation based on analysis."""
        net = savings.total_savings_micros - risks.total_expected_cost_micros
        
        # Check for critical items
        has_critical = any(
            self._demand_forecasts.get(item.get("product_id")) 
            and self._demand_forecasts[item.get("product_id")].days_of_supply < self._config.critical_days_of_supply
            for item in order.items if item.get("product_id")
        )
        
        # Already delayed too long?
        if order.delay_hours > self._config.max_any_delay_hours:
            return DelayRecommendation.EXPEDITE, "Order already delayed beyond safe limit"
        
        # Critical item with stockout risk?
        if has_critical and risks.primary_risk == RiskType.STOCKOUT:
            return DelayRecommendation.PROCEED_NOW, f"Critical item at stockout risk in {risks.primary_risk_hours}h"
        
        # Net positive with acceptable risk?
        if net > 0:
            if risks.total_expected_cost_micros < order.total_cost_micros * Decimal("0.05"):
                return DelayRecommendation.DELAY_SAFE, f"Delay saves ${net / 1_000_000:.0f} with minimal risk"
            else:
                return DelayRecommendation.DELAY_RISKY, f"Delay saves ${net / 1_000_000:.0f} but monitor closely"
        
        # Net negative?
        if net < 0:
            return DelayRecommendation.PROCEED_NOW, f"Delay costs ${abs(net) / 1_000_000:.0f} more than it saves"
        
        # Neutral - consider liquidity
        if self._liquidity and self._liquidity.is_constrained:
            return DelayRecommendation.DELAY_RISKY, "Cash constrained - delay with caution"
        
        return DelayRecommendation.PROCEED_NOW, "No significant benefit to delay"
    
    # =========================================================================
    # MAIN ANALYSIS
    # =========================================================================
    
    def analyze_delay(
        self,
        order_id: uuid.UUID,
        delay_hours: int,
        delay_reason: Optional[DelayReason] = None,
    ) -> Optional[DelayAnalysis]:
        """
        Analyze the cost of delaying a specific order.
        
        Returns complete analysis with savings, risks, and recommendation.
        """
        order = self._pending_orders.get(order_id)
        if not order:
            return None
        
        # Step 1: Calculate savings
        savings = self._calculate_savings(order, delay_hours)
        
        # Step 2: Calculate risk costs
        risks = self._calculate_risk_costs(order, delay_hours)
        
        # Step 3: Net the difference
        net_micros = savings.total_savings_micros - risks.total_expected_cost_micros
        
        # Convert to dollars for readability
        cash_saved = Decimal(savings.total_savings_micros) / 1_000_000
        risk_cost = Decimal(risks.total_expected_cost_micros) / 1_000_000
        net_dollars = Decimal(net_micros) / 1_000_000
        
        # Determine recommendation
        recommendation, reason = self._determine_recommendation(savings, risks, delay_hours, order)
        
        # Warnings
        warnings = []
        if risks.primary_risk == RiskType.STOCKOUT:
            warnings.append(f"Stockout risk in {risks.primary_risk_hours} hours")
        if delay_hours > self._config.max_safe_delay_hours:
            warnings.append(f"Delay exceeds safe limit of {self._config.max_safe_delay_hours}h")
        if self._liquidity and self._liquidity.is_constrained:
            warnings.append("Operating under liquidity constraints")
        
        return DelayAnalysis(
            order_id=order_id,
            order_total_micros=order.total_cost_micros,
            delay_hours=delay_hours,
            delay_reason=delay_reason,
            cash_saved_now_micros=savings.total_savings_micros,
            risk_cost_later_micros=risks.total_expected_cost_micros,
            net_effect_micros=net_micros,
            cash_saved_now=cash_saved.quantize(Decimal("0.01")),
            risk_cost_later=risk_cost.quantize(Decimal("0.01")),
            net_effect=net_dollars.quantize(Decimal("0.01")),
            savings_breakdown=savings,
            risk_breakdown=risks,
            recommendation=recommendation,
            recommendation_reason=reason,
            warnings=warnings,
        )
    
    def compare_delay_scenarios(
        self,
        order_id: uuid.UUID,
        delay_options: list[int] = [0, 24, 48, 72],
    ) -> Optional[MultiDelayComparison]:
        """Compare multiple delay scenarios for an order."""
        scenarios = []
        
        for hours in delay_options:
            analysis = self.analyze_delay(order_id, hours)
            if analysis:
                scenarios.append(analysis)
        
        if not scenarios:
            return None
        
        # Find optimal
        optimal = max(scenarios, key=lambda s: s.net_effect_micros)
        
        return MultiDelayComparison(
            order_id=order_id,
            scenarios=scenarios,
            optimal_delay_hours=optimal.delay_hours,
            optimal_net_effect_micros=optimal.net_effect_micros,
            recommendation=f"Optimal: {optimal.delay_hours}h delay saves ${optimal.net_effect / 1_000_000:.0f}",
        )
    
    def analyze_all_orders(self, delay_hours: int = 24) -> BatchDelayAnalysis:
        """Analyze delaying all pending orders."""
        analyses = []
        
        for order_id in self._pending_orders:
            analysis = self.analyze_delay(order_id, delay_hours)
            if analysis:
                analyses.append(analysis)
        
        # Categorize
        proceed = [a.order_id for a in analyses if a.recommendation == DelayRecommendation.PROCEED_NOW]
        safe = [a.order_id for a in analyses if a.recommendation == DelayRecommendation.DELAY_SAFE]
        risky = [a.order_id for a in analyses if a.recommendation in (DelayRecommendation.DELAY_RISKY, DelayRecommendation.DELAY_PARTIAL)]
        
        total_value = sum(a.order_total_micros for a in analyses)
        total_saved = sum(a.cash_saved_now_micros for a in analyses)
        total_risk = sum(a.risk_cost_later_micros for a in analyses)
        
        return BatchDelayAnalysis(
            order_count=len(analyses),
            total_order_value_micros=total_value,
            total_cash_saved_micros=total_saved,
            total_risk_cost_micros=total_risk,
            net_effect_micros=total_saved - total_risk,
            order_analyses=analyses,
            orders_to_proceed=proceed,
            orders_safe_to_delay=safe,
            orders_risky_to_delay=risky,
        )
    
    def clear_data(self) -> None:
        """Clear all data (for testing)."""
        self._pending_orders.clear()
        self._demand_forecasts.clear()
        self._waste_risks.clear()
        self._liquidity = None


# Singleton instance
costdelay_calculator = CostOfDelayCalculator()
