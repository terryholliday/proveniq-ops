"""
PROVENIQ Ops - Bishop Salvage Bridge
Identify assets suitable for transfer, donation, or liquidation.

LOGIC:
1. Rank disposition options
2. Recommend best recovery path
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Optional

from app.models.salvage import (
    AssetCondition,
    BatchSalvageResult,
    DispositionPath,
    DispositionRanking,
    DonationOption,
    ExpirationWindow,
    LiquidationOption,
    NetworkInventory,
    NetworkLocation,
    OverstockFlag,
    OverstockReason,
    RecoveryConfidence,
    RepurposeOption,
    SalvageConfig,
    SalvageRecommendation,
    TransferOption,
)


class SalvageBridge:
    """
    Bishop Salvage Bridge
    
    Identifies assets suitable for transfer, donation, or liquidation.
    """
    
    def __init__(self) -> None:
        self._config = SalvageConfig()
        
        # Registered data
        self._overstock_flags: dict[uuid.UUID, OverstockFlag] = {}
        self._expiration_windows: dict[uuid.UUID, ExpirationWindow] = {}
        self._network_inventory: dict[uuid.UUID, NetworkInventory] = {}  # by product_id
        
        # Recommendations
        self._recommendations: dict[uuid.UUID, SalvageRecommendation] = {}
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure(self, config: SalvageConfig) -> None:
        """Update configuration."""
        self._config = config
    
    def get_config(self) -> SalvageConfig:
        """Get current configuration."""
        return self._config
    
    # =========================================================================
    # DATA REGISTRATION
    # =========================================================================
    
    def register_overstock(self, flag: OverstockFlag) -> None:
        """Register an overstock flag."""
        self._overstock_flags[flag.item_id] = flag
    
    def register_expiration(self, window: ExpirationWindow) -> None:
        """Register an expiration window."""
        self._expiration_windows[window.item_id] = window
    
    def register_network_inventory(self, inventory: NetworkInventory) -> None:
        """Register network inventory for a product."""
        self._network_inventory[inventory.product_id] = inventory
    
    # =========================================================================
    # CONDITION ASSESSMENT
    # =========================================================================
    
    def _assess_condition(self, days_until_expiry: int) -> AssetCondition:
        """Assess condition based on days until expiry."""
        if days_until_expiry >= self._config.excellent_days_remaining:
            return AssetCondition.EXCELLENT
        elif days_until_expiry >= self._config.good_days_remaining:
            return AssetCondition.GOOD
        elif days_until_expiry >= self._config.fair_days_remaining:
            return AssetCondition.FAIR
        elif days_until_expiry >= self._config.poor_days_remaining:
            return AssetCondition.POOR
        else:
            return AssetCondition.CRITICAL
    
    # =========================================================================
    # DISPOSITION OPTIONS (Step 1: Rank)
    # =========================================================================
    
    def _evaluate_transfer(
        self,
        item_id: uuid.UUID,
        product_id: uuid.UUID,
        quantity: Decimal,
        unit: str,
        value_micros: int,
        source_location_id: uuid.UUID,
    ) -> Optional[TransferOption]:
        """Evaluate transfer option."""
        network = self._network_inventory.get(product_id)
        if not network:
            return None
        
        # Find best transfer target
        best_target = None
        best_score = 0
        
        for loc in network.locations:
            if loc.location_id == source_location_id:
                continue
            if not loc.can_accept:
                continue
            if not loc.needs_product:
                continue
            
            # Score based on need and cost
            need_score = float(loc.daily_demand) / max(1, float(loc.current_inventory))
            cost_score = 1 - (loc.transfer_cost_micros / max(1, value_micros))
            score = need_score * 0.6 + cost_score * 0.4
            
            if score > best_score:
                best_score = score
                best_target = loc
        
        if not best_target:
            return None
        
        transfer_qty = min(quantity, best_target.max_accept_qty or quantity)
        transfer_value = int(value_micros * float(transfer_qty / quantity))
        net_recovery = transfer_value - best_target.transfer_cost_micros
        
        # Check if transfer makes economic sense
        recovery_pct = Decimal(net_recovery) / Decimal(value_micros) * 100 if value_micros > 0 else Decimal("0")
        if recovery_pct < self._config.min_transfer_recovery_pct:
            return None
        
        return TransferOption(
            target_location_id=best_target.location_id,
            target_location_name=best_target.location_name,
            transfer_qty=transfer_qty,
            unit=unit,
            transfer_cost_micros=best_target.transfer_cost_micros,
            value_retained_micros=transfer_value,
            net_recovery_micros=net_recovery,
            transfer_hours=best_target.transfer_hours,
            reason=f"Location needs product ({best_target.days_of_supply} days supply)",
        )
    
    def _evaluate_donation(
        self,
        quantity: Decimal,
        unit: str,
        value_micros: int,
        days_until_expiry: int,
    ) -> Optional[DonationOption]:
        """Evaluate donation option."""
        if days_until_expiry < self._config.min_days_for_donation:
            return DonationOption(
                recipient_type="food_bank",
                donate_qty=quantity,
                unit=unit,
                fair_market_value_micros=value_micros,
                tax_deduction_estimate_micros=0,
                net_recovery_micros=0,
                eligible=False,
                ineligibility_reason=f"Insufficient shelf life ({days_until_expiry} days)",
            )
        
        # Tax deduction value
        tax_benefit = int(value_micros * float(self._config.donation_tax_rate))
        
        return DonationOption(
            recipient_type="food_bank",
            recipient_name="Local Food Bank",
            donate_qty=quantity,
            unit=unit,
            fair_market_value_micros=value_micros,
            tax_deduction_estimate_micros=tax_benefit,
            net_recovery_micros=tax_benefit,
            pickup_available=True,
            donation_hours=4,
            eligible=True,
        )
    
    def _evaluate_liquidation(
        self,
        quantity: Decimal,
        unit: str,
        value_micros: int,
        condition: AssetCondition,
    ) -> LiquidationOption:
        """Evaluate liquidation option."""
        # Discount based on condition
        discount_map = {
            AssetCondition.EXCELLENT: Decimal("0.20"),
            AssetCondition.GOOD: Decimal("0.35"),
            AssetCondition.FAIR: Decimal("0.50"),
            AssetCondition.POOR: Decimal("0.70"),
            AssetCondition.CRITICAL: Decimal("0.85"),
        }
        discount = discount_map.get(condition, Decimal("0.50"))
        
        liquidation_price = int(value_micros * (1 - float(discount)))
        recovery_rate = (1 - discount) * 100
        
        # Channel based on condition
        if condition in (AssetCondition.EXCELLENT, AssetCondition.GOOD):
            channel = "discount_shelf"
            sale_window = 48
        elif condition == AssetCondition.FAIR:
            channel = "employee_sale"
            sale_window = 24
        else:
            channel = "liquidator"
            sale_window = 12
        
        return LiquidationOption(
            channel=channel,
            liquidate_qty=quantity,
            unit=unit,
            original_value_micros=value_micros,
            liquidation_price_micros=liquidation_price,
            discount_pct=discount * 100,
            net_recovery_micros=liquidation_price,
            recovery_rate_pct=recovery_rate,
            sale_window_hours=sale_window,
        )
    
    def _evaluate_repurpose(
        self,
        quantity: Decimal,
        unit: str,
        value_micros: int,
        product_name: str,
    ) -> Optional[RepurposeOption]:
        """Evaluate repurpose option."""
        # Simple heuristic - proteins and produce can be repurposed
        repurposable = any(kw in product_name.lower() for kw in [
            "chicken", "beef", "pork", "fish", "vegetable", "fruit", "produce"
        ])
        
        if not repurposable:
            return None
        
        # Repurposed value is ~60% of original
        repurposed_value = int(value_micros * 0.60)
        
        return RepurposeOption(
            new_use="staff_meal",
            repurpose_qty=quantity,
            unit=unit,
            original_value_micros=value_micros,
            repurposed_value_micros=repurposed_value,
            net_recovery_micros=repurposed_value,
            feasible=True,
        )
    
    # =========================================================================
    # RECOMMENDATION (Step 2: Best Recovery Path)
    # =========================================================================
    
    def recommend_disposition(
        self,
        item_id: uuid.UUID,
    ) -> Optional[SalvageRecommendation]:
        """
        Generate salvage recommendation for an item.
        
        Ranks all options and recommends best recovery path.
        """
        # Get item data
        overstock = self._overstock_flags.get(item_id)
        expiration = self._expiration_windows.get(item_id)
        
        if not overstock and not expiration:
            return None
        
        # Extract item details
        if overstock:
            product_id = overstock.product_id
            product_name = overstock.product_name
            quantity = overstock.excess_qty
            unit = overstock.unit
            value_micros = int(overstock.unit_cost_micros * float(quantity))
            location_id = overstock.location_id
            days_until_expiry = 14  # Assume healthy if no expiration
        else:
            product_id = expiration.product_id
            product_name = expiration.product_name
            quantity = expiration.quantity
            unit = expiration.unit
            value_micros = expiration.current_value_micros
            location_id = expiration.location_id
            days_until_expiry = expiration.days_until_expiry
        
        # Assess condition
        condition = self._assess_condition(days_until_expiry)
        
        # Evaluate all options
        options: list[DispositionRanking] = []
        
        # Transfer
        transfer = self._evaluate_transfer(
            item_id, product_id, quantity, unit, value_micros, location_id
        )
        if transfer and transfer.feasible:
            recovery_pct = Decimal(transfer.net_recovery_micros) / Decimal(value_micros) * 100 if value_micros > 0 else Decimal("0")
            options.append(DispositionRanking(
                rank=0,
                path=DispositionPath.TRANSFER,
                estimated_recovery_micros=transfer.net_recovery_micros,
                recovery_rate_pct=recovery_pct,
                confidence=RecoveryConfidence.HIGH,
                details=transfer.model_dump(),
                reasoning=f"Transfer to {transfer.target_location_name} recovers {recovery_pct:.0f}%",
            ))
        
        # Donation
        donation = self._evaluate_donation(quantity, unit, value_micros, days_until_expiry)
        if donation and donation.eligible:
            recovery_pct = Decimal(donation.net_recovery_micros) / Decimal(value_micros) * 100 if value_micros > 0 else Decimal("0")
            options.append(DispositionRanking(
                rank=0,
                path=DispositionPath.DONATE,
                estimated_recovery_micros=donation.net_recovery_micros,
                recovery_rate_pct=recovery_pct,
                confidence=RecoveryConfidence.MEDIUM,
                details=donation.model_dump(),
                reasoning=f"Donation provides {recovery_pct:.0f}% tax benefit recovery",
            ))
        
        # Liquidation
        liquidation = self._evaluate_liquidation(quantity, unit, value_micros, condition)
        recovery_pct = liquidation.recovery_rate_pct
        options.append(DispositionRanking(
            rank=0,
            path=DispositionPath.LIQUIDATE,
            estimated_recovery_micros=liquidation.net_recovery_micros,
            recovery_rate_pct=recovery_pct,
            confidence=RecoveryConfidence.HIGH if condition in (AssetCondition.EXCELLENT, AssetCondition.GOOD) else RecoveryConfidence.MEDIUM,
            details=liquidation.model_dump(),
            reasoning=f"Liquidation at {liquidation.discount_pct:.0f}% discount via {liquidation.channel}",
        ))
        
        # Repurpose
        repurpose = self._evaluate_repurpose(quantity, unit, value_micros, product_name)
        if repurpose and repurpose.feasible:
            recovery_pct = Decimal(repurpose.net_recovery_micros) / Decimal(value_micros) * 100 if value_micros > 0 else Decimal("0")
            options.append(DispositionRanking(
                rank=0,
                path=DispositionPath.REPURPOSE,
                estimated_recovery_micros=repurpose.net_recovery_micros,
                recovery_rate_pct=recovery_pct,
                confidence=RecoveryConfidence.MEDIUM,
                details=repurpose.model_dump(),
                reasoning=f"Repurpose for {repurpose.new_use} recovers {recovery_pct:.0f}%",
            ))
        
        # If condition is critical with no good options, recommend dispose
        if condition == AssetCondition.CRITICAL and (not options or max(o.estimated_recovery_micros for o in options) < value_micros * 0.1):
            options.append(DispositionRanking(
                rank=0,
                path=DispositionPath.DISPOSE,
                estimated_recovery_micros=0,
                recovery_rate_pct=Decimal("0"),
                confidence=RecoveryConfidence.HIGH,
                reasoning="Critical condition - salvage not economical",
            ))
        
        # Rank by recovery (higher is better)
        options.sort(key=lambda o: o.estimated_recovery_micros, reverse=True)
        for i, opt in enumerate(options):
            opt.rank = i + 1
        
        # Best option
        best = options[0] if options else None
        if not best:
            return None
        
        # Calculate urgency
        urgency_hours = max(0, days_until_expiry * 24 - 24)  # Act 1 day before expiry
        action_deadline = datetime.utcnow() + timedelta(hours=urgency_hours) if urgency_hours > 0 else None
        
        recommendation = SalvageRecommendation(
            item_id=item_id,
            product_id=product_id,
            product_name=product_name,
            quantity=quantity,
            unit=unit,
            condition=condition,
            days_until_expiry=days_until_expiry,
            original_value_micros=value_micros,
            recommended_path=best.path,
            estimated_recovery_micros=best.estimated_recovery_micros,
            estimated_recovery=Decimal(best.estimated_recovery_micros) / 1_000_000,
            recovery_rate_pct=best.recovery_rate_pct,
            ranked_options=options,
            transfer_target=transfer if best.path == DispositionPath.TRANSFER else None,
            donation_option=donation if best.path == DispositionPath.DONATE else None,
            liquidation_option=liquidation if best.path == DispositionPath.LIQUIDATE else None,
            action_deadline=action_deadline,
            urgency_hours=urgency_hours,
            reasoning=best.reasoning,
        )
        
        self._recommendations[item_id] = recommendation
        return recommendation
    
    def analyze_batch(
        self,
        item_ids: Optional[list[uuid.UUID]] = None,
    ) -> BatchSalvageResult:
        """Analyze multiple items for salvage."""
        if item_ids is None:
            # Analyze all flagged items
            item_ids = list(set(
                list(self._overstock_flags.keys()) + 
                list(self._expiration_windows.keys())
            ))
        
        recommendations = []
        total_at_risk = 0
        total_recovery = 0
        
        path_counts = defaultdict(int)
        urgent = []
        
        for item_id in item_ids:
            rec = self.recommend_disposition(item_id)
            if rec:
                recommendations.append(rec)
                total_at_risk += rec.original_value_micros
                total_recovery += rec.estimated_recovery_micros
                path_counts[rec.recommended_path.value] += 1
                
                if rec.urgency_hours < 24:
                    urgent.append(item_id)
        
        overall_recovery_pct = Decimal(total_recovery) / Decimal(total_at_risk) * 100 if total_at_risk > 0 else Decimal("0")
        
        return BatchSalvageResult(
            items_analyzed=len(recommendations),
            total_at_risk_value_micros=total_at_risk,
            total_estimated_recovery_micros=total_recovery,
            overall_recovery_rate_pct=overall_recovery_pct.quantize(Decimal("0.1")),
            transfer_count=path_counts.get("transfer", 0),
            donate_count=path_counts.get("donate", 0),
            liquidate_count=path_counts.get("liquidate", 0),
            repurpose_count=path_counts.get("repurpose", 0),
            dispose_count=path_counts.get("dispose", 0),
            recommendations=recommendations,
            urgent_items=urgent,
        )
    
    def get_recommendation(self, item_id: uuid.UUID) -> Optional[SalvageRecommendation]:
        """Get existing recommendation for an item."""
        return self._recommendations.get(item_id)
    
    def clear_data(self) -> None:
        """Clear all data (for testing)."""
        self._overstock_flags.clear()
        self._expiration_windows.clear()
        self._network_inventory.clear()
        self._recommendations.clear()


# Singleton instance
salvage_bridge = SalvageBridge()
