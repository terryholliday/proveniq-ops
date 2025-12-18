"""
PROVENIQ Ops - Bishop Cost Per Serving Engine
Translate inventory fluctuations into real-time menu profitability insight.

DAG Nodes: N17, N37

LOGIC:
1. Calculate rolling cost-per-serving
2. Detect margin compression
3. Flag threshold breaches

GUARDRAILS:
- Do not suggest menu price changes unless enabled
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.core.types import Money
from app.models.menucost import (
    Ingredient,
    IngredientCostImpact,
    MarginAlert,
    MarginAlertType,
    MarginStatus,
    MenuCostAnalysis,
    MenuCostConfig,
    MenuItem,
    Recipe,
    RecipeIngredient,
    UnitOfMeasure,
)


class MenuCostEngine:
    """
    Bishop Cost Per Serving Engine
    
    Translates inventory cost fluctuations into menu profitability insights.
    
    Maps to DAG nodes: N17 (cost facts), N37 (margin alerts)
    """
    
    def __init__(self) -> None:
        self._config = MenuCostConfig()
        
        # Data stores
        self._ingredients: dict[uuid.UUID, Ingredient] = {}
        self._recipes: dict[uuid.UUID, Recipe] = {}
        self._menu_items: dict[uuid.UUID, MenuItem] = {}
        
        # Cost history for rolling averages
        self._ingredient_cost_history: dict[uuid.UUID, list[tuple[datetime, int]]] = defaultdict(list)
        self._menu_cost_history: dict[uuid.UUID, list[tuple[datetime, int]]] = defaultdict(list)
        
        # Generated alerts
        self._alerts: list[MarginAlert] = []
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure(self, config: MenuCostConfig) -> None:
        """Update engine configuration."""
        self._config = config
    
    def get_config(self) -> MenuCostConfig:
        """Get current configuration."""
        return self._config
    
    # =========================================================================
    # DATA REGISTRATION
    # =========================================================================
    
    def register_ingredient(self, ingredient: Ingredient) -> None:
        """Register an ingredient with current cost."""
        # Calculate cost per unit
        if ingredient.purchase_qty > 0:
            ingredient.cost_per_unit_micros = int(
                Decimal(ingredient.current_cost_micros) / ingredient.purchase_qty
            )
        
        self._ingredients[ingredient.ingredient_id] = ingredient
        
        # Record to history
        self._ingredient_cost_history[ingredient.ingredient_id].append(
            (datetime.utcnow(), ingredient.current_cost_micros)
        )
    
    def update_ingredient_cost(
        self,
        ingredient_id: uuid.UUID,
        new_cost_micros: int,
    ) -> Optional[Ingredient]:
        """Update ingredient cost (e.g., from new invoice)."""
        ingredient = self._ingredients.get(ingredient_id)
        if not ingredient:
            return None
        
        ingredient.current_cost_micros = new_cost_micros
        if ingredient.purchase_qty > 0:
            ingredient.cost_per_unit_micros = int(
                Decimal(new_cost_micros) / ingredient.purchase_qty
            )
        ingredient.last_cost_update = datetime.utcnow()
        
        # Record to history
        self._ingredient_cost_history[ingredient_id].append(
            (datetime.utcnow(), new_cost_micros)
        )
        
        # Update 30-day average
        ingredient.cost_30d_avg_micros = self._calculate_rolling_avg(
            ingredient_id, "ingredient"
        )
        
        # Determine trend
        if ingredient.cost_30d_avg_micros:
            if new_cost_micros > ingredient.cost_30d_avg_micros * 1.05:
                ingredient.cost_trend = "up"
            elif new_cost_micros < ingredient.cost_30d_avg_micros * 0.95:
                ingredient.cost_trend = "down"
            else:
                ingredient.cost_trend = "stable"
        
        return ingredient
    
    def register_recipe(self, recipe: Recipe) -> None:
        """Register a recipe and calculate costs."""
        self._calculate_recipe_cost(recipe)
        self._recipes[recipe.recipe_id] = recipe
    
    def register_menu_item(self, item: MenuItem) -> None:
        """Register a menu item."""
        self._calculate_margins(item)
        self._menu_items[item.menu_item_id] = item
        
        # Record to history
        self._menu_cost_history[item.menu_item_id].append(
            (datetime.utcnow(), item.cost_per_serving_micros)
        )
    
    # =========================================================================
    # COST CALCULATIONS (N17)
    # =========================================================================
    
    def _calculate_recipe_cost(self, recipe: Recipe) -> None:
        """Calculate total recipe cost from ingredients."""
        total_cost = 0
        
        for ri in recipe.ingredients:
            ingredient = self._ingredients.get(ri.ingredient_id)
            if ingredient:
                # Calculate ingredient cost based on usage
                # Convert units if needed (simplified - assumes same unit)
                base_cost = ingredient.cost_per_unit_micros * float(ri.quantity)
                
                # Apply waste factor
                if self._config.include_waste_factor:
                    base_cost *= float(ri.waste_factor)
                
                ri.cost_micros = int(base_cost)
                total_cost += ri.cost_micros
        
        recipe.total_ingredient_cost_micros = total_cost
        
        # Calculate per-serving cost
        if recipe.portions_per_batch > 0:
            recipe.cost_per_serving_micros = total_cost // recipe.portions_per_batch
        else:
            recipe.cost_per_serving_micros = total_cost
    
    def _calculate_margins(self, item: MenuItem) -> None:
        """Calculate margins for a menu item."""
        if item.menu_price_micros > 0:
            item.gross_margin_micros = item.menu_price_micros - item.cost_per_serving_micros
            item.gross_margin_percent = (
                Decimal(item.gross_margin_micros) / Decimal(item.menu_price_micros) * 100
            ).quantize(Decimal("0.01"))
        else:
            item.gross_margin_micros = 0
            item.gross_margin_percent = Decimal("0")
        
        # Determine status
        item.margin_status = self._get_margin_status(item.gross_margin_percent)
    
    def _get_margin_status(self, margin_percent: Decimal) -> MarginStatus:
        """Determine margin status based on thresholds."""
        if margin_percent < 0:
            return MarginStatus.NEGATIVE
        elif margin_percent < self._config.margin_critical_percent:
            return MarginStatus.CRITICAL
        elif margin_percent < self._config.margin_warning_percent:
            return MarginStatus.WARNING
        else:
            return MarginStatus.HEALTHY
    
    def _calculate_rolling_avg(
        self,
        entity_id: uuid.UUID,
        entity_type: str,
    ) -> Optional[int]:
        """Calculate rolling average cost."""
        history = (
            self._ingredient_cost_history.get(entity_id)
            if entity_type == "ingredient"
            else self._menu_cost_history.get(entity_id)
        )
        
        if not history:
            return None
        
        cutoff = datetime.utcnow() - timedelta(days=self._config.rolling_avg_days)
        recent = [cost for ts, cost in history if ts >= cutoff]
        
        if not recent:
            return None
        
        return sum(recent) // len(recent)
    
    def recalculate_all_costs(self) -> None:
        """Recalculate all recipe and menu item costs."""
        # Recalculate recipes
        for recipe in self._recipes.values():
            self._calculate_recipe_cost(recipe)
        
        # Update menu items
        for item in self._menu_items.values():
            recipe = self._recipes.get(item.recipe_id) if item.recipe_id else None
            if recipe:
                item.cost_per_serving_micros = recipe.cost_per_serving_micros
            self._calculate_margins(item)
            
            # Record to history
            self._menu_cost_history[item.menu_item_id].append(
                (datetime.utcnow(), item.cost_per_serving_micros)
            )
    
    # =========================================================================
    # MARGIN ANALYSIS (N37)
    # =========================================================================
    
    def analyze_menu_costs(self) -> MenuCostAnalysis:
        """
        Analyze all menu items for cost/margin status.
        
        Returns comprehensive analysis with alerts.
        """
        self._alerts = []
        
        healthy = 0
        warning = 0
        critical = 0
        negative = 0
        
        margin_sum = Decimal("0")
        
        for item in self._menu_items.values():
            # Check for cost changes
            alert = self._check_for_alert(item)
            if alert:
                self._alerts.append(alert)
            
            # Count by status
            if item.margin_status == MarginStatus.HEALTHY:
                healthy += 1
            elif item.margin_status == MarginStatus.WARNING:
                warning += 1
            elif item.margin_status == MarginStatus.CRITICAL:
                critical += 1
            elif item.margin_status == MarginStatus.NEGATIVE:
                negative += 1
            
            margin_sum += item.gross_margin_percent
        
        # Calculate average margin
        item_count = len(self._menu_items)
        avg_margin = margin_sum / item_count if item_count > 0 else Decimal("0")
        
        # Get top issues
        sorted_by_margin = sorted(
            self._menu_items.values(),
            key=lambda x: x.gross_margin_percent
        )
        
        return MenuCostAnalysis(
            total_menu_items=item_count,
            items_analyzed=item_count,
            healthy_count=healthy,
            warning_count=warning,
            critical_count=critical,
            negative_margin_count=negative,
            alerts=self._alerts,
            top_margin_compression=sorted_by_margin[:5],
            avg_margin_percent=avg_margin.quantize(Decimal("0.01")),
        )
    
    def _check_for_alert(self, item: MenuItem) -> Optional[MarginAlert]:
        """Check if menu item should generate an alert."""
        # Get previous cost from history
        history = self._menu_cost_history.get(item.menu_item_id, [])
        
        if len(history) < 2:
            # No previous data to compare
            if item.margin_status in (MarginStatus.CRITICAL, MarginStatus.NEGATIVE):
                return self._create_threshold_alert(item, None, None)
            return None
        
        # Compare to previous
        prev_cost = history[-2][1] if len(history) >= 2 else history[-1][1]
        current_cost = item.cost_per_serving_micros
        
        if prev_cost == 0:
            return None
        
        cost_change_pct = (
            Decimal(current_cost - prev_cost) / Decimal(prev_cost) * 100
        ).quantize(Decimal("0.01"))
        
        # Check if change exceeds threshold
        if abs(cost_change_pct) < self._config.cost_change_alert_percent:
            # Small change, but check margin status
            if item.margin_status in (MarginStatus.CRITICAL, MarginStatus.NEGATIVE):
                return self._create_threshold_alert(item, prev_cost, cost_change_pct)
            return None
        
        # Calculate previous margin
        prev_margin_pct = (
            Decimal(item.menu_price_micros - prev_cost) / Decimal(item.menu_price_micros) * 100
        ).quantize(Decimal("0.01")) if item.menu_price_micros > 0 else Decimal("0")
        
        # Determine alert type
        if cost_change_pct > 0 and item.gross_margin_percent < prev_margin_pct:
            alert_type = MarginAlertType.MARGIN_COMPRESSION
        elif cost_change_pct > self._config.cost_change_alert_percent * 2:
            alert_type = MarginAlertType.COST_SPIKE
        else:
            alert_type = MarginAlertType.MARGIN_SHIFT
        
        # Get cost drivers
        cost_drivers = self._get_cost_drivers(item)
        
        # Threshold breach check
        threshold_breached = None
        if item.gross_margin_percent < item.min_margin_percent:
            threshold_breached = "minimum"
        elif item.gross_margin_percent < item.target_margin_percent:
            threshold_breached = "target"
        
        # Price suggestion (only if enabled)
        price_suggestion = None
        if self._config.price_suggestions_enabled and threshold_breached:
            # Calculate price needed to hit target margin
            target_margin = item.target_margin_percent / 100
            price_suggestion = int(
                Decimal(item.cost_per_serving_micros) / (1 - target_margin)
            )
        
        return MarginAlert(
            alert_type=alert_type,
            menu_item_id=item.menu_item_id,
            menu_item_name=item.name,
            category=item.category,
            previous_cost_micros=prev_cost,
            current_cost_micros=current_cost,
            cost_change_micros=current_cost - prev_cost,
            cost_change_percent=cost_change_pct,
            previous_margin_percent=prev_margin_pct,
            new_margin_percent=item.gross_margin_percent,
            margin_change_percent=item.gross_margin_percent - prev_margin_pct,
            margin_status=item.margin_status,
            threshold_breached=threshold_breached,
            cost_drivers=cost_drivers,
            price_suggestion_micros=price_suggestion,
            price_suggestion_enabled=self._config.price_suggestions_enabled,
        )
    
    def _create_threshold_alert(
        self,
        item: MenuItem,
        prev_cost: Optional[int],
        cost_change_pct: Optional[Decimal],
    ) -> MarginAlert:
        """Create threshold breach alert."""
        threshold_breached = "critical" if item.margin_status == MarginStatus.NEGATIVE else "minimum"
        
        return MarginAlert(
            alert_type=MarginAlertType.THRESHOLD_BREACH,
            menu_item_id=item.menu_item_id,
            menu_item_name=item.name,
            category=item.category,
            previous_cost_micros=prev_cost or item.cost_per_serving_micros,
            current_cost_micros=item.cost_per_serving_micros,
            cost_change_micros=0,
            cost_change_percent=cost_change_pct or Decimal("0"),
            previous_margin_percent=item.gross_margin_percent,
            new_margin_percent=item.gross_margin_percent,
            margin_change_percent=Decimal("0"),
            margin_status=item.margin_status,
            threshold_breached=threshold_breached,
            cost_drivers=[],
            price_suggestion_enabled=self._config.price_suggestions_enabled,
        )
    
    def _get_cost_drivers(self, item: MenuItem) -> list[dict]:
        """Identify ingredients driving cost changes."""
        if not item.recipe_id:
            return []
        
        recipe = self._recipes.get(item.recipe_id)
        if not recipe:
            return []
        
        drivers = []
        for ri in recipe.ingredients:
            ingredient = self._ingredients.get(ri.ingredient_id)
            if not ingredient or not ingredient.cost_30d_avg_micros:
                continue
            
            # Calculate change from average
            current = ingredient.current_cost_micros
            avg = ingredient.cost_30d_avg_micros
            
            if avg > 0:
                change_pct = ((current - avg) / avg * 100)
                if abs(change_pct) > 5:  # Only significant changes
                    impact = ri.cost_micros - int(
                        Decimal(avg) / ingredient.purchase_qty * ri.quantity
                    )
                    drivers.append({
                        "ingredient": ingredient.name,
                        "change_pct": round(change_pct, 1),
                        "impact_micros": impact,
                    })
        
        # Sort by absolute impact
        drivers.sort(key=lambda x: abs(x["impact_micros"]), reverse=True)
        return drivers[:5]
    
    # =========================================================================
    # INGREDIENT IMPACT ANALYSIS
    # =========================================================================
    
    def analyze_ingredient_impact(
        self,
        ingredient_id: uuid.UUID,
    ) -> Optional[IngredientCostImpact]:
        """Analyze impact of an ingredient's cost change across the menu."""
        ingredient = self._ingredients.get(ingredient_id)
        if not ingredient:
            return None
        
        # Find all recipes using this ingredient
        affected_recipes = []
        for recipe in self._recipes.values():
            for ri in recipe.ingredients:
                if ri.ingredient_id == ingredient_id:
                    affected_recipes.append(recipe)
                    break
        
        # Find menu items
        affected_items = []
        total_impact = 0
        
        for recipe in affected_recipes:
            for item in self._menu_items.values():
                if item.recipe_id == recipe.recipe_id:
                    affected_items.append(item.name)
                    # Calculate impact (simplified)
                    if ingredient.cost_30d_avg_micros:
                        impact = ingredient.current_cost_micros - ingredient.cost_30d_avg_micros
                        total_impact += impact
        
        prev_cost = ingredient.cost_30d_avg_micros or ingredient.current_cost_micros
        change_pct = Decimal("0")
        if prev_cost > 0:
            change_pct = (
                Decimal(ingredient.current_cost_micros - prev_cost) / Decimal(prev_cost) * 100
            ).quantize(Decimal("0.01"))
        
        return IngredientCostImpact(
            ingredient_id=ingredient_id,
            ingredient_name=ingredient.name,
            previous_cost_micros=prev_cost,
            current_cost_micros=ingredient.current_cost_micros,
            change_percent=change_pct,
            affected_items=len(affected_items),
            total_margin_impact_micros=total_impact,
            affected_menu_items=affected_items,
        )
    
    # =========================================================================
    # QUERY
    # =========================================================================
    
    def get_menu_item(self, menu_item_id: uuid.UUID) -> Optional[MenuItem]:
        """Get a specific menu item."""
        return self._menu_items.get(menu_item_id)
    
    def get_all_menu_items(self) -> list[MenuItem]:
        """Get all menu items sorted by margin."""
        return sorted(
            self._menu_items.values(),
            key=lambda x: x.gross_margin_percent,
            reverse=True
        )
    
    def get_alerts(self, limit: int = 100) -> list[MarginAlert]:
        """Get generated alerts."""
        return self._alerts[-limit:]
    
    def get_items_by_status(self, status: MarginStatus) -> list[MenuItem]:
        """Get menu items by margin status."""
        return [i for i in self._menu_items.values() if i.margin_status == status]
    
    def clear_data(self) -> None:
        """Clear all data (for testing)."""
        self._ingredients.clear()
        self._recipes.clear()
        self._menu_items.clear()
        self._ingredient_cost_history.clear()
        self._menu_cost_history.clear()
        self._alerts.clear()


# Singleton instance
menucost_engine = MenuCostEngine()
