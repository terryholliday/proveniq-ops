"""
PROVENIQ Ops - Bishop Multi-Location Rebalancer
Optimize inventory across locations as a single intelligent network.

DAG Nodes: N18, N35

LOGIC:
1. Identify overstock vs stockout risk
2. Propose transfers minimizing total cost

GUARDRAILS:
- Respect location autonomy unless enabled
"""

import uuid
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.core.types import Money
from app.models.rebalance import (
    DemandForecast,
    Location,
    LocationInventory,
    LocationType,
    NetworkAnalysis,
    ProductNetworkStatus,
    RebalanceAlert,
    RebalanceConfig,
    TransferAlertType,
    TransferCost,
    TransferProposal,
    TransferStatus,
)


class RebalanceEngine:
    """
    Bishop Multi-Location Rebalancer
    
    Optimizes inventory across locations as a unified network.
    
    Maps to DAG nodes: N18 (network facts), N35 (transfer proposals)
    
    GUARDRAIL: Respects location autonomy by default.
    """
    
    def __init__(self) -> None:
        self._config = RebalanceConfig()
        
        # Data stores
        self._locations: dict[uuid.UUID, Location] = {}
        self._inventory: dict[tuple[uuid.UUID, uuid.UUID], LocationInventory] = {}  # (loc, prod) -> inv
        self._transfer_costs: dict[tuple[uuid.UUID, uuid.UUID], TransferCost] = {}  # (from, to) -> cost
        self._forecasts: dict[tuple[uuid.UUID, uuid.UUID], DemandForecast] = {}  # (loc, prod) -> forecast
        
        # Generated proposals
        self._proposals: list[TransferProposal] = []
        self._alerts: list[RebalanceAlert] = []
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure(self, config: RebalanceConfig) -> None:
        """Update engine configuration."""
        self._config = config
    
    def get_config(self) -> RebalanceConfig:
        """Get current configuration."""
        return self._config
    
    # =========================================================================
    # DATA REGISTRATION
    # =========================================================================
    
    def register_location(self, location: Location) -> None:
        """Register a location in the network."""
        self._locations[location.location_id] = location
    
    def register_inventory(self, inventory: LocationInventory) -> None:
        """Register inventory for a product at a location."""
        key = (inventory.location_id, inventory.product_id)
        
        # Calculate days of supply if forecast exists
        forecast_key = key
        forecast = self._forecasts.get(forecast_key)
        if forecast and forecast.daily_demand > 0:
            inventory.days_of_supply = Decimal(inventory.on_hand_qty) / forecast.daily_demand
            inventory.stockout_risk = inventory.days_of_supply < self._config.stockout_risk_days
            inventory.overstock = inventory.days_of_supply > self._config.overstock_days
        
        self._inventory[key] = inventory
    
    def register_transfer_cost(self, cost: TransferCost) -> None:
        """Register transfer cost between locations."""
        key = (cost.from_location_id, cost.to_location_id)
        self._transfer_costs[key] = cost
    
    def register_forecast(self, forecast: DemandForecast) -> None:
        """Register demand forecast for a product at a location."""
        key = (forecast.location_id, forecast.product_id)
        
        # Calculate days until stockout
        inv_key = key
        inventory = self._inventory.get(inv_key)
        if inventory and forecast.daily_demand > 0:
            forecast.days_until_stockout = Decimal(inventory.on_hand_qty) / forecast.daily_demand
        
        self._forecasts[key] = forecast
    
    # =========================================================================
    # AUTONOMY CHECKS (GUARDRAIL)
    # =========================================================================
    
    def _can_transfer_from(self, location_id: uuid.UUID) -> tuple[bool, Optional[str]]:
        """Check if transfers are allowed from this location."""
        location = self._locations.get(location_id)
        if not location:
            return False, "Location not found"
        
        if self._config.respect_location_autonomy:
            if not location.allow_outbound_transfers:
                return False, f"{location.name} does not allow outbound transfers"
        
        return True, None
    
    def _can_transfer_to(self, location_id: uuid.UUID) -> tuple[bool, Optional[str]]:
        """Check if transfers are allowed to this location."""
        location = self._locations.get(location_id)
        if not location:
            return False, "Location not found"
        
        if self._config.respect_location_autonomy:
            if not location.allow_inbound_transfers:
                return False, f"{location.name} does not allow inbound transfers"
        
        return True, None
    
    def _requires_approval(
        self,
        from_location_id: uuid.UUID,
        to_location_id: uuid.UUID,
    ) -> bool:
        """Determine if transfer requires approval."""
        from_loc = self._locations.get(from_location_id)
        to_loc = self._locations.get(to_location_id)
        
        if not from_loc or not to_loc:
            return True
        
        # Auto-approve between owned locations if enabled
        if self._config.auto_approve_owned_locations:
            if from_loc.location_type == LocationType.OWNED and to_loc.location_type == LocationType.OWNED:
                return False
        
        # Check location-specific settings
        return from_loc.requires_approval or to_loc.requires_approval
    
    # =========================================================================
    # NETWORK ANALYSIS (N18)
    # =========================================================================
    
    def _get_product_network_status(self, product_id: uuid.UUID) -> Optional[ProductNetworkStatus]:
        """Analyze network-wide status for a product."""
        # Find all inventory for this product
        product_inv = [
            inv for (loc_id, prod_id), inv in self._inventory.items()
            if prod_id == product_id
        ]
        
        if not product_inv:
            return None
        
        first_inv = product_inv[0]
        total_qty = sum(inv.on_hand_qty for inv in product_inv)
        
        # Calculate total demand
        total_demand = 0
        for inv in product_inv:
            forecast = self._forecasts.get((inv.location_id, product_id))
            if forecast:
                total_demand += forecast.total_forecast_qty
        
        # Count location states
        at_risk = len([inv for inv in product_inv if inv.stockout_risk])
        overstocked = len([inv for inv in product_inv if inv.overstock])
        with_stock = len([inv for inv in product_inv if inv.on_hand_qty > 0])
        
        # Calculate imbalance score
        if len(product_inv) > 1 and total_qty > 0:
            # Standard deviation of days of supply as imbalance indicator
            dos_values = [float(inv.days_of_supply or 0) for inv in product_inv]
            avg_dos = sum(dos_values) / len(dos_values)
            variance = sum((d - avg_dos) ** 2 for d in dos_values) / len(dos_values)
            std_dos = variance ** 0.5
            # Normalize to 0-1 scale
            imbalance = min(Decimal("1"), Decimal(str(std_dos / 30)) if avg_dos > 0 else Decimal("0"))
        else:
            imbalance = Decimal("0")
        
        # Calculate transferable quantity
        transferable = sum(
            max(0, inv.on_hand_qty - inv.safety_stock)
            for inv in product_inv
            if inv.overstock
        )
        
        # Location details
        location_status = []
        for inv in product_inv:
            status = "balanced"
            if inv.stockout_risk:
                status = "at_risk"
            elif inv.overstock:
                status = "overstocked"
            
            location_status.append({
                "location_id": str(inv.location_id),
                "location_name": inv.location_name,
                "on_hand": inv.on_hand_qty,
                "days_of_supply": float(inv.days_of_supply or 0),
                "status": status,
            })
        
        return ProductNetworkStatus(
            product_id=product_id,
            product_name=first_inv.product_name,
            canonical_sku=first_inv.canonical_sku,
            total_network_qty=total_qty,
            total_network_demand=total_demand,
            locations_with_stock=with_stock,
            locations_at_risk=at_risk,
            locations_overstocked=overstocked,
            imbalance_score=imbalance,
            transferable_qty=transferable,
            location_status=location_status,
        )
    
    def analyze_network(self) -> NetworkAnalysis:
        """Analyze the complete inventory network."""
        # Get unique products
        products = set(prod_id for (loc_id, prod_id) in self._inventory.keys())
        
        # Analyze each product
        product_statuses = []
        for product_id in products:
            status = self._get_product_network_status(product_id)
            if status:
                product_statuses.append(status)
        
        # Count location health
        location_health: dict[uuid.UUID, str] = {}
        for (loc_id, prod_id), inv in self._inventory.items():
            current = location_health.get(loc_id, "healthy")
            if inv.stockout_risk:
                location_health[loc_id] = "at_risk"
            elif inv.overstock and current != "at_risk":
                location_health[loc_id] = "overstocked"
        
        healthy = len([h for h in location_health.values() if h == "healthy"])
        at_risk = len([h for h in location_health.values() if h == "at_risk"])
        overstocked = len([h for h in location_health.values() if h == "overstocked"])
        
        # Products needing rebalance
        needs_rebalance = [s for s in product_statuses if s.imbalance_score > Decimal("0.3")]
        
        # Calculate imbalance value
        imbalance_value = sum(
            s.transferable_qty * self._get_avg_unit_cost(s.product_id)
            for s in needs_rebalance
        )
        
        # Get top issues
        top_risks = sorted(
            [s for s in product_statuses if s.locations_at_risk > 0],
            key=lambda x: x.locations_at_risk,
            reverse=True
        )[:5]
        
        top_overstock = sorted(
            [s for s in product_statuses if s.locations_overstocked > 0],
            key=lambda x: x.transferable_qty,
            reverse=True
        )[:5]
        
        return NetworkAnalysis(
            total_locations=len(self._locations),
            total_products=len(products),
            healthy_locations=healthy,
            at_risk_locations=at_risk,
            overstocked_locations=overstocked,
            products_needing_rebalance=len(needs_rebalance),
            total_imbalance_value_micros=imbalance_value,
            top_stockout_risks=top_risks,
            top_overstock=top_overstock,
            total_recommended_transfers=len(self._proposals),
        )
    
    def _get_avg_unit_cost(self, product_id: uuid.UUID) -> int:
        """Get average unit cost for a product across locations."""
        costs = [
            inv.unit_cost_micros
            for (loc_id, prod_id), inv in self._inventory.items()
            if prod_id == product_id
        ]
        return sum(costs) // len(costs) if costs else 0
    
    # =========================================================================
    # TRANSFER PROPOSAL GENERATION (N35)
    # =========================================================================
    
    def _calculate_transfer_cost(
        self,
        from_loc: uuid.UUID,
        to_loc: uuid.UUID,
        qty: int,
    ) -> int:
        """Calculate total cost for a transfer."""
        cost_info = self._transfer_costs.get((from_loc, to_loc))
        if not cost_info:
            # Default cost if not specified
            return qty * 500_000  # $0.50 per unit default
        
        return cost_info.base_cost_micros + (cost_info.per_unit_cost_micros * qty)
    
    def _find_best_source(
        self,
        product_id: uuid.UUID,
        target_loc: uuid.UUID,
        needed_qty: int,
    ) -> Optional[tuple[uuid.UUID, int, int]]:
        """
        Find best source location for a transfer.
        
        Returns: (source_location_id, available_qty, transfer_cost)
        """
        best_source = None
        best_cost = float('inf')
        best_qty = 0
        
        for (loc_id, prod_id), inv in self._inventory.items():
            if prod_id != product_id:
                continue
            if loc_id == target_loc:
                continue
            
            # Check autonomy
            can_transfer, _ = self._can_transfer_from(loc_id)
            if not can_transfer:
                continue
            
            # Check available quantity (above safety stock)
            available = max(0, inv.on_hand_qty - inv.safety_stock)
            if available <= 0:
                continue
            
            # Don't create stockout risk at source
            forecast = self._forecasts.get((loc_id, product_id))
            if forecast and forecast.daily_demand > 0:
                remaining_dos = Decimal(available) / forecast.daily_demand
                if remaining_dos < self._config.stockout_risk_days:
                    continue
            
            transfer_qty = min(available, needed_qty)
            cost = self._calculate_transfer_cost(loc_id, target_loc, transfer_qty)
            
            # Check cost constraint
            inv_value = transfer_qty * inv.unit_cost_micros
            if inv_value > 0:
                cost_pct = Decimal(cost) / Decimal(inv_value) * 100
                if cost_pct > self._config.max_transfer_cost_pct:
                    continue
            
            if cost < best_cost:
                best_source = loc_id
                best_cost = cost
                best_qty = transfer_qty
        
        if best_source:
            return (best_source, best_qty, int(best_cost))
        return None
    
    def generate_proposals(self) -> RebalanceAlert:
        """
        Generate transfer proposals for the network.
        
        Identifies stockout risks and proposes transfers from overstocked locations.
        """
        self._proposals = []
        
        stockout_preventions = 0
        overstock_reductions = 0
        total_transfer_cost = 0
        total_inv_value = 0
        proposals_need_approval = 0
        auto_approvable = 0
        
        # Find locations at stockout risk
        for (loc_id, prod_id), inv in self._inventory.items():
            if not inv.stockout_risk:
                continue
            
            # Check if can receive
            can_receive, reason = self._can_transfer_to(loc_id)
            if not can_receive:
                continue
            
            # Calculate needed quantity
            forecast = self._forecasts.get((loc_id, prod_id))
            if forecast and forecast.daily_demand > 0:
                # Target: enough for stockout_risk_days + buffer
                target_dos = self._config.stockout_risk_days * 2
                target_qty = int(forecast.daily_demand * target_dos)
                needed = max(0, target_qty - inv.on_hand_qty)
            else:
                needed = inv.par_level - inv.on_hand_qty if inv.par_level > inv.on_hand_qty else 0
            
            if needed < self._config.min_transfer_qty:
                continue
            
            # Find best source
            source = self._find_best_source(prod_id, loc_id, needed)
            if not source:
                continue
            
            source_loc, transfer_qty, transfer_cost = source
            
            # Check minimum value
            inv_value = transfer_qty * inv.unit_cost_micros
            if inv_value < self._config.min_transfer_value_micros:
                continue
            
            # Get source inventory
            source_inv = self._inventory.get((source_loc, prod_id))
            if not source_inv:
                continue
            
            # Create proposal
            from_loc = self._locations.get(source_loc)
            to_loc = self._locations.get(loc_id)
            
            requires_approval = self._requires_approval(source_loc, loc_id)
            
            # Calculate benefit
            days_added = None
            if forecast and forecast.daily_demand > 0:
                days_added = Decimal(transfer_qty) / forecast.daily_demand
            
            proposal = TransferProposal(
                alert_type=TransferAlertType.STOCKOUT_PREVENTION,
                product_id=prod_id,
                product_name=inv.product_name,
                canonical_sku=inv.canonical_sku,
                from_location_id=source_loc,
                from_location_name=from_loc.name if from_loc else "Unknown",
                to_location_id=loc_id,
                to_location_name=to_loc.name if to_loc else "Unknown",
                recommended_qty=transfer_qty,
                from_current_qty=source_inv.on_hand_qty,
                from_after_qty=source_inv.on_hand_qty - transfer_qty,
                to_current_qty=inv.on_hand_qty,
                to_after_qty=inv.on_hand_qty + transfer_qty,
                transfer_cost_micros=transfer_cost,
                inventory_value_micros=inv_value,
                stockout_prevented=True,
                days_of_supply_added=days_added,
                requires_approval=requires_approval,
                reason_codes=["stockout_risk", "network_rebalance"],
                confidence=Decimal("0.8"),
            )
            
            self._proposals.append(proposal)
            stockout_preventions += 1
            total_transfer_cost += transfer_cost
            total_inv_value += inv_value
            
            if requires_approval:
                proposals_need_approval += 1
            else:
                auto_approvable += 1
        
        # Calculate estimated savings (rough: 2x inventory value for prevented stockout)
        estimated_savings = total_inv_value * 2  # Lost sales value
        
        # Count network status
        at_risk = len([inv for inv in self._inventory.values() if inv.stockout_risk])
        overstocked = len([inv for inv in self._inventory.values() if inv.overstock])
        balanced = len(self._locations) - at_risk - overstocked
        
        alert = RebalanceAlert(
            alert_type=TransferAlertType.REBALANCE_OPPORTUNITY,
            total_proposals=len(self._proposals),
            stockout_preventions=stockout_preventions,
            overstock_reductions=overstock_reductions,
            total_transfer_cost_micros=total_transfer_cost,
            total_inventory_value_micros=total_inv_value,
            estimated_savings_micros=estimated_savings,
            locations_with_stockout_risk=at_risk,
            locations_with_overstock=overstocked,
            locations_balanced=balanced,
            proposals=self._proposals,
            proposals_requiring_approval=proposals_need_approval,
            auto_approvable=auto_approvable,
        )
        
        self._alerts.append(alert)
        return alert
    
    # =========================================================================
    # PROPOSAL MANAGEMENT
    # =========================================================================
    
    def approve_proposal(self, proposal_id: uuid.UUID) -> Optional[TransferProposal]:
        """Approve a transfer proposal."""
        for proposal in self._proposals:
            if proposal.proposal_id == proposal_id:
                proposal.status = TransferStatus.APPROVED
                return proposal
        return None
    
    def reject_proposal(self, proposal_id: uuid.UUID) -> Optional[TransferProposal]:
        """Reject a transfer proposal."""
        for proposal in self._proposals:
            if proposal.proposal_id == proposal_id:
                proposal.status = TransferStatus.REJECTED
                return proposal
        return None
    
    # =========================================================================
    # QUERY
    # =========================================================================
    
    def get_proposals(
        self,
        status: Optional[TransferStatus] = None,
    ) -> list[TransferProposal]:
        """Get transfer proposals, optionally filtered by status."""
        if status:
            return [p for p in self._proposals if p.status == status]
        return self._proposals
    
    def get_alerts(self, limit: int = 100) -> list[RebalanceAlert]:
        """Get rebalance alerts."""
        return self._alerts[-limit:]
    
    def get_location_inventory(self, location_id: uuid.UUID) -> list[LocationInventory]:
        """Get all inventory for a location."""
        return [
            inv for (loc_id, prod_id), inv in self._inventory.items()
            if loc_id == location_id
        ]
    
    def clear_data(self) -> None:
        """Clear all data (for testing)."""
        self._locations.clear()
        self._inventory.clear()
        self._transfer_costs.clear()
        self._forecasts.clear()
        self._proposals.clear()
        self._alerts.clear()


# Singleton instance
rebalance_engine = RebalanceEngine()
