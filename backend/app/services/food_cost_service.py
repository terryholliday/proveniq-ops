"""
PROVENIQ Ops - Food Cost Management Service

Restaurant success metrics:
- Target food cost: 28-35% of revenue
- Prime cost (food + labor): under 65%
- Waste under 5% of food purchases

This service:
- Tracks ingredient costs from vendors
- Calculates menu item food costs from recipes
- Monitors food cost percentage trends
- Alerts on cost overruns and price increases
"""

import uuid
import json
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
import logging

from app.db.session import async_session_maker
from app.services.events.store import event_store

logger = logging.getLogger(__name__)


class IngredientCategory(str, Enum):
    """Categories for food ingredients."""
    PROTEIN = "protein"
    PRODUCE = "produce"
    DAIRY = "dairy"
    DRY_GOODS = "dry_goods"
    BEVERAGES = "beverages"
    FROZEN = "frozen"
    BAKERY = "bakery"
    CONDIMENTS = "condiments"
    SUPPLIES = "supplies"


class CostSource(str, Enum):
    """Source of cost information."""
    INVOICE = "invoice"
    QUOTE = "quote"
    MANUAL = "manual"
    VENDOR_SYNC = "vendor_sync"
    DELIVERY = "delivery"


class Ingredient(BaseModel):
    """Ingredient model."""
    id: Optional[uuid.UUID] = None
    org_id: uuid.UUID
    name: str
    category: IngredientCategory
    subcategory: Optional[str] = None
    
    base_unit: str
    purchase_unit: str
    purchase_to_base_ratio: Decimal = Decimal("1")
    
    current_cost_per_unit: int  # cents
    is_perishable: bool = True
    shelf_life_days: Optional[int] = None
    requires_refrigeration: bool = False
    requires_freezer: bool = False
    
    par_level: Optional[Decimal] = None
    reorder_point: Optional[Decimal] = None
    preferred_vendor_id: Optional[uuid.UUID] = None


class MenuItem(BaseModel):
    """Menu item with costing."""
    id: Optional[uuid.UUID] = None
    org_id: uuid.UUID
    name: str
    category: str
    
    menu_price: int  # cents
    calculated_food_cost: Optional[int] = None  # cents
    food_cost_percentage: Optional[Decimal] = None
    target_food_cost_pct: Decimal = Decimal("30")


class RecipeItem(BaseModel):
    """Recipe ingredient line."""
    ingredient_id: uuid.UUID
    quantity: Decimal
    unit: str
    waste_factor: Decimal = Decimal("1.0")


class FoodCostReport(BaseModel):
    """Food cost report."""
    org_id: uuid.UUID
    report_date: date
    report_type: str
    
    total_food_sales: Optional[int] = None
    beginning_inventory_value: Optional[int] = None
    purchases: Optional[int] = None
    ending_inventory_value: Optional[int] = None
    calculated_cogs: Optional[int] = None
    
    total_waste_value: Optional[int] = None
    food_cost_percentage: Optional[Decimal] = None
    target_food_cost_pct: Optional[Decimal] = None
    variance_from_target: Optional[Decimal] = None
    
    alerts: List[Dict[str, Any]] = []


class FoodCostService:
    """
    Service for food cost management.
    
    MOAT PRINCIPLE:
    - Accumulated cost data becomes irreplaceable
    - Vendor price history informs negotiations
    - Recipe costing ties to menu profitability
    - Cost trends predict margin issues before they hurt
    """
    
    async def create_ingredient(
        self,
        org_id: uuid.UUID,
        name: str,
        category: IngredientCategory,
        base_unit: str,
        purchase_unit: str,
        current_cost_per_unit: int,
        purchase_to_base_ratio: Decimal = Decimal("1"),
        subcategory: Optional[str] = None,
        is_perishable: bool = True,
        shelf_life_days: Optional[int] = None,
        requires_refrigeration: bool = False,
        requires_freezer: bool = False,
        par_level: Optional[Decimal] = None,
        reorder_point: Optional[Decimal] = None,
        preferred_vendor_id: Optional[uuid.UUID] = None,
    ) -> Ingredient:
        """Create a new ingredient."""
        ingredient_id = uuid.uuid4()
        
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            await session.execute(
                text("""
                    INSERT INTO ingredients (
                        id, org_id, name, category, subcategory,
                        base_unit, purchase_unit, purchase_to_base_ratio,
                        current_cost_per_unit, cost_updated_at,
                        is_perishable, shelf_life_days, requires_refrigeration, requires_freezer,
                        par_level, reorder_point, preferred_vendor_id,
                        status, created_at
                    ) VALUES (
                        :id, :org_id, :name, :category, :subcategory,
                        :base_unit, :purchase_unit, :ratio,
                        :cost, NOW(),
                        :perishable, :shelf_life, :refrigeration, :freezer,
                        :par, :reorder, :vendor,
                        'active', NOW()
                    )
                """),
                {
                    "id": ingredient_id,
                    "org_id": org_id,
                    "name": name,
                    "category": category.value,
                    "subcategory": subcategory,
                    "base_unit": base_unit,
                    "purchase_unit": purchase_unit,
                    "ratio": purchase_to_base_ratio,
                    "cost": current_cost_per_unit,
                    "perishable": is_perishable,
                    "shelf_life": shelf_life_days,
                    "refrigeration": requires_refrigeration,
                    "freezer": requires_freezer,
                    "par": par_level,
                    "reorder": reorder_point,
                    "vendor": preferred_vendor_id,
                }
            )
            
            # Record initial cost
            await session.execute(
                text("""
                    INSERT INTO ingredient_costs (
                        id, ingredient_id, cost_per_unit, unit, effective_date, source, recorded_at
                    ) VALUES (
                        gen_random_uuid(), :ingredient_id, :cost, :unit, CURRENT_DATE, 'manual', NOW()
                    )
                """),
                {
                    "ingredient_id": ingredient_id,
                    "cost": current_cost_per_unit,
                    "unit": base_unit,
                }
            )
            
            await session.commit()
        
        # Log event
        await event_store.append(
            event_type="ops.ingredient.created",
            payload={
                "ingredient_id": str(ingredient_id),
                "org_id": str(org_id),
                "name": name,
                "category": category.value,
                "cost_per_unit": current_cost_per_unit,
            },
            org_id=org_id,
        )
        
        logger.info(f"Created ingredient: {name} ({ingredient_id})")
        
        return Ingredient(
            id=ingredient_id,
            org_id=org_id,
            name=name,
            category=category,
            subcategory=subcategory,
            base_unit=base_unit,
            purchase_unit=purchase_unit,
            purchase_to_base_ratio=purchase_to_base_ratio,
            current_cost_per_unit=current_cost_per_unit,
            is_perishable=is_perishable,
            shelf_life_days=shelf_life_days,
            requires_refrigeration=requires_refrigeration,
            requires_freezer=requires_freezer,
            par_level=par_level,
            reorder_point=reorder_point,
            preferred_vendor_id=preferred_vendor_id,
        )
    
    async def update_ingredient_cost(
        self,
        ingredient_id: uuid.UUID,
        new_cost: int,
        source: CostSource,
        vendor_id: Optional[uuid.UUID] = None,
        invoice_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update ingredient cost and record history.
        
        Returns cost change info for alerting.
        """
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Get current cost
            result = await session.execute(
                text("SELECT current_cost_per_unit, name, org_id FROM ingredients WHERE id = :id"),
                {"id": ingredient_id}
            )
            row = result.fetchone()
            
            if not row:
                raise ValueError(f"Ingredient not found: {ingredient_id}")
            
            old_cost = row.current_cost_per_unit
            name = row.name
            org_id = row.org_id
            
            # Calculate change
            cost_change = new_cost - old_cost
            cost_change_pct = (cost_change / old_cost * 100) if old_cost > 0 else 0
            
            # Update current cost
            await session.execute(
                text("""
                    UPDATE ingredients
                    SET current_cost_per_unit = :cost, cost_updated_at = NOW(), updated_at = NOW()
                    WHERE id = :id
                """),
                {"id": ingredient_id, "cost": new_cost}
            )
            
            # Record cost history
            await session.execute(
                text("""
                    INSERT INTO ingredient_costs (
                        id, ingredient_id, vendor_id, cost_per_unit, unit, effective_date, source, invoice_id, recorded_at
                    ) VALUES (
                        gen_random_uuid(), :ingredient_id, :vendor_id, :cost, 
                        (SELECT base_unit FROM ingredients WHERE id = :ingredient_id),
                        CURRENT_DATE, :source, :invoice_id, NOW()
                    )
                """),
                {
                    "ingredient_id": ingredient_id,
                    "vendor_id": vendor_id,
                    "cost": new_cost,
                    "source": source.value,
                    "invoice_id": invoice_id,
                }
            )
            
            # Update rolling averages
            await self._update_cost_averages(session, ingredient_id)
            
            await session.commit()
        
        # Log event
        await event_store.append(
            event_type="ops.ingredient.cost_updated",
            payload={
                "ingredient_id": str(ingredient_id),
                "org_id": str(org_id),
                "name": name,
                "old_cost": old_cost,
                "new_cost": new_cost,
                "change_cents": cost_change,
                "change_pct": round(cost_change_pct, 2),
                "source": source.value,
                "vendor_id": str(vendor_id) if vendor_id else None,
            },
            org_id=org_id,
        )
        
        return {
            "ingredient_id": str(ingredient_id),
            "name": name,
            "old_cost": old_cost,
            "new_cost": new_cost,
            "change_cents": cost_change,
            "change_pct": round(cost_change_pct, 2),
            "alert": abs(cost_change_pct) > 10,  # Alert if >10% change
        }
    
    async def _update_cost_averages(self, session, ingredient_id: uuid.UUID) -> None:
        """Update rolling average costs."""
        from sqlalchemy import text
        
        # 30-day average
        result = await session.execute(
            text("""
                SELECT AVG(cost_per_unit) as avg_cost
                FROM ingredient_costs
                WHERE ingredient_id = :id
                AND effective_date >= CURRENT_DATE - INTERVAL '30 days'
            """),
            {"id": ingredient_id}
        )
        avg_30 = result.fetchone()
        
        # 90-day average
        result = await session.execute(
            text("""
                SELECT AVG(cost_per_unit) as avg_cost
                FROM ingredient_costs
                WHERE ingredient_id = :id
                AND effective_date >= CURRENT_DATE - INTERVAL '90 days'
            """),
            {"id": ingredient_id}
        )
        avg_90 = result.fetchone()
        
        await session.execute(
            text("""
                UPDATE ingredients
                SET avg_cost_30d = :avg_30, avg_cost_90d = :avg_90
                WHERE id = :id
            """),
            {
                "id": ingredient_id,
                "avg_30": int(avg_30.avg_cost) if avg_30 and avg_30.avg_cost else None,
                "avg_90": int(avg_90.avg_cost) if avg_90 and avg_90.avg_cost else None,
            }
        )
    
    async def create_menu_item(
        self,
        org_id: uuid.UUID,
        name: str,
        category: str,
        menu_price: int,
        target_food_cost_pct: Decimal = Decimal("30"),
        subcategory: Optional[str] = None,
    ) -> MenuItem:
        """Create a menu item."""
        item_id = uuid.uuid4()
        
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            await session.execute(
                text("""
                    INSERT INTO menu_items (
                        id, org_id, name, category, subcategory, menu_price, target_food_cost_pct, status, created_at
                    ) VALUES (
                        :id, :org_id, :name, :category, :subcategory, :price, :target, 'active', NOW()
                    )
                """),
                {
                    "id": item_id,
                    "org_id": org_id,
                    "name": name,
                    "category": category,
                    "subcategory": subcategory,
                    "price": menu_price,
                    "target": target_food_cost_pct,
                }
            )
            await session.commit()
        
        await event_store.append(
            event_type="ops.menu_item.created",
            payload={
                "menu_item_id": str(item_id),
                "org_id": str(org_id),
                "name": name,
                "menu_price": menu_price,
            },
            org_id=org_id,
        )
        
        return MenuItem(
            id=item_id,
            org_id=org_id,
            name=name,
            category=category,
            menu_price=menu_price,
            target_food_cost_pct=target_food_cost_pct,
        )
    
    async def set_recipe(
        self,
        menu_item_id: uuid.UUID,
        ingredients: List[RecipeItem],
    ) -> Dict[str, Any]:
        """
        Set the recipe for a menu item.
        
        Replaces existing recipe and recalculates food cost.
        """
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Clear existing recipe
            await session.execute(
                text("DELETE FROM recipes WHERE menu_item_id = :id"),
                {"id": menu_item_id}
            )
            
            total_cost = 0
            
            for item in ingredients:
                # Get ingredient cost
                result = await session.execute(
                    text("SELECT current_cost_per_unit, base_unit FROM ingredients WHERE id = :id"),
                    {"id": item.ingredient_id}
                )
                ing = result.fetchone()
                
                if not ing:
                    continue
                
                # Calculate line cost with waste factor
                line_cost = int(float(item.quantity) * ing.current_cost_per_unit * float(item.waste_factor))
                total_cost += line_cost
                
                await session.execute(
                    text("""
                        INSERT INTO recipes (
                            id, menu_item_id, ingredient_id, quantity, unit, waste_factor, calculated_cost, created_at
                        ) VALUES (
                            gen_random_uuid(), :menu_item_id, :ingredient_id, :qty, :unit, :waste, :cost, NOW()
                        )
                    """),
                    {
                        "menu_item_id": menu_item_id,
                        "ingredient_id": item.ingredient_id,
                        "qty": item.quantity,
                        "unit": item.unit,
                        "waste": item.waste_factor,
                        "cost": line_cost,
                    }
                )
            
            # Get menu price to calculate percentage
            result = await session.execute(
                text("SELECT menu_price, org_id, name FROM menu_items WHERE id = :id"),
                {"id": menu_item_id}
            )
            menu_item = result.fetchone()
            
            food_cost_pct = (total_cost / menu_item.menu_price * 100) if menu_item and menu_item.menu_price > 0 else 0
            
            # Update menu item with calculated cost
            await session.execute(
                text("""
                    UPDATE menu_items
                    SET calculated_food_cost = :cost, food_cost_percentage = :pct, updated_at = NOW()
                    WHERE id = :id
                """),
                {"id": menu_item_id, "cost": total_cost, "pct": round(food_cost_pct, 2)}
            )
            
            await session.commit()
        
        await event_store.append(
            event_type="ops.recipe.updated",
            payload={
                "menu_item_id": str(menu_item_id),
                "org_id": str(menu_item.org_id) if menu_item else None,
                "name": menu_item.name if menu_item else None,
                "ingredient_count": len(ingredients),
                "calculated_food_cost": total_cost,
                "food_cost_percentage": round(food_cost_pct, 2),
            },
            org_id=menu_item.org_id if menu_item else None,
        )
        
        return {
            "menu_item_id": str(menu_item_id),
            "ingredient_count": len(ingredients),
            "calculated_food_cost": total_cost,
            "food_cost_percentage": round(food_cost_pct, 2),
        }
    
    async def recalculate_all_recipes(self, org_id: uuid.UUID) -> Dict[str, Any]:
        """
        Recalculate food costs for all menu items.
        
        Run after ingredient costs change.
        """
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Get all menu items
            result = await session.execute(
                text("SELECT id FROM menu_items WHERE org_id = :org_id AND status = 'active'"),
                {"org_id": org_id}
            )
            
            updated = 0
            alerts = []
            
            for row in result.fetchall():
                menu_item_id = row.id
                
                # Recalculate each recipe
                cost_result = await session.execute(
                    text("""
                        SELECT SUM(r.quantity * i.current_cost_per_unit * r.waste_factor) as total_cost
                        FROM recipes r
                        JOIN ingredients i ON r.ingredient_id = i.id
                        WHERE r.menu_item_id = :id
                    """),
                    {"id": menu_item_id}
                )
                cost_row = cost_result.fetchone()
                
                if cost_row and cost_row.total_cost:
                    total_cost = int(cost_row.total_cost)
                    
                    # Get menu price
                    price_result = await session.execute(
                        text("SELECT menu_price, name, target_food_cost_pct FROM menu_items WHERE id = :id"),
                        {"id": menu_item_id}
                    )
                    price_row = price_result.fetchone()
                    
                    if price_row:
                        food_cost_pct = (total_cost / price_row.menu_price * 100) if price_row.menu_price > 0 else 0
                        
                        await session.execute(
                            text("""
                                UPDATE menu_items
                                SET calculated_food_cost = :cost, food_cost_percentage = :pct, updated_at = NOW()
                                WHERE id = :id
                            """),
                            {"id": menu_item_id, "cost": total_cost, "pct": round(food_cost_pct, 2)}
                        )
                        
                        # Check for alert
                        if price_row.target_food_cost_pct and food_cost_pct > float(price_row.target_food_cost_pct):
                            alerts.append({
                                "menu_item": price_row.name,
                                "food_cost_pct": round(food_cost_pct, 2),
                                "target": float(price_row.target_food_cost_pct),
                                "over_by": round(food_cost_pct - float(price_row.target_food_cost_pct), 2),
                            })
                        
                        updated += 1
            
            await session.commit()
        
        return {
            "items_updated": updated,
            "alerts": alerts,
            "alert_count": len(alerts),
        }
    
    async def get_cost_trend(
        self,
        ingredient_id: uuid.UUID,
        days: int = 90,
    ) -> Dict[str, Any]:
        """Get cost trend for an ingredient."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("""
                    SELECT effective_date, cost_per_unit, source, vendor_id
                    FROM ingredient_costs
                    WHERE ingredient_id = :id
                    AND effective_date >= CURRENT_DATE - :days * INTERVAL '1 day'
                    ORDER BY effective_date ASC
                """),
                {"id": ingredient_id, "days": days}
            )
            
            costs = []
            for row in result.fetchall():
                costs.append({
                    "date": row.effective_date.isoformat(),
                    "cost": row.cost_per_unit,
                    "source": row.source,
                })
            
            # Get ingredient info
            info_result = await session.execute(
                text("SELECT name, current_cost_per_unit, avg_cost_30d, avg_cost_90d FROM ingredients WHERE id = :id"),
                {"id": ingredient_id}
            )
            info = info_result.fetchone()
            
            return {
                "ingredient_id": str(ingredient_id),
                "name": info.name if info else None,
                "current_cost": info.current_cost_per_unit if info else None,
                "avg_30d": info.avg_cost_30d if info else None,
                "avg_90d": info.avg_cost_90d if info else None,
                "history": costs,
                "trend": self._calculate_trend(costs) if costs else "stable",
            }
    
    def _calculate_trend(self, costs: List[Dict]) -> str:
        """Calculate cost trend direction."""
        if len(costs) < 2:
            return "stable"
        
        first_half = sum(c["cost"] for c in costs[:len(costs)//2]) / (len(costs)//2)
        second_half = sum(c["cost"] for c in costs[len(costs)//2:]) / (len(costs) - len(costs)//2)
        
        change_pct = (second_half - first_half) / first_half * 100 if first_half > 0 else 0
        
        if change_pct > 5:
            return "increasing"
        elif change_pct < -5:
            return "decreasing"
        return "stable"
    
    async def generate_food_cost_report(
        self,
        org_id: uuid.UUID,
        report_date: date,
        total_food_sales: Optional[int] = None,
        beginning_inventory: Optional[int] = None,
        ending_inventory: Optional[int] = None,
    ) -> FoodCostReport:
        """
        Generate daily food cost report.
        
        Food Cost % = (Beginning Inventory + Purchases - Ending Inventory) / Food Sales
        """
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Get purchases for the day
            purchases_result = await session.execute(
                text("""
                    SELECT COALESCE(SUM(total), 0) as purchases
                    FROM food_orders
                    WHERE org_id = :org_id
                    AND DATE(actual_delivery) = :date
                    AND status = 'delivered'
                """),
                {"org_id": org_id, "date": report_date}
            )
            purchases_row = purchases_result.fetchone()
            purchases = purchases_row.purchases if purchases_row else 0
            
            # Get waste for the day
            waste_result = await session.execute(
                text("""
                    SELECT 
                        COALESCE(SUM(estimated_cost), 0) as total_waste,
                        waste_type,
                        COUNT(*) as count
                    FROM food_waste
                    WHERE org_id = :org_id
                    AND waste_date = :date
                    GROUP BY waste_type
                """),
                {"org_id": org_id, "date": report_date}
            )
            
            waste_by_type = {}
            total_waste = 0
            for row in waste_result.fetchall():
                waste_by_type[row.waste_type] = {"cost": row.total_waste, "count": row.count}
                total_waste += row.total_waste
            
            # Calculate COGS
            cogs = None
            food_cost_pct = None
            
            if beginning_inventory is not None and ending_inventory is not None:
                cogs = beginning_inventory + purchases - ending_inventory
                
                if total_food_sales and total_food_sales > 0:
                    food_cost_pct = Decimal(str(cogs / total_food_sales * 100))
            
            # Target (industry standard 28-35%)
            target_pct = Decimal("32")
            variance = food_cost_pct - target_pct if food_cost_pct else None
            
            # Generate alerts
            alerts = []
            if food_cost_pct and food_cost_pct > 35:
                alerts.append({
                    "type": "high_food_cost",
                    "message": f"Food cost {food_cost_pct:.1f}% exceeds 35% threshold",
                    "severity": "high",
                })
            if total_waste > 0 and purchases > 0 and (total_waste / purchases * 100) > 5:
                alerts.append({
                    "type": "high_waste",
                    "message": f"Waste {total_waste/100:.2f} is {total_waste/purchases*100:.1f}% of purchases",
                    "severity": "medium",
                })
            
            # Save report
            await session.execute(
                text("""
                    INSERT INTO food_cost_reports (
                        id, org_id, report_date, report_type,
                        total_food_sales, beginning_inventory_value, purchases, ending_inventory_value,
                        calculated_cogs, total_waste_value, waste_by_type,
                        food_cost_percentage, target_food_cost_pct, variance_from_target,
                        alerts, generated_at
                    ) VALUES (
                        gen_random_uuid(), :org_id, :date, 'daily',
                        :sales, :begin_inv, :purchases, :end_inv,
                        :cogs, :waste, :waste_by_type,
                        :food_cost_pct, :target, :variance,
                        :alerts, NOW()
                    )
                    ON CONFLICT (org_id, report_date, report_type) 
                    DO UPDATE SET
                        total_food_sales = :sales,
                        beginning_inventory_value = :begin_inv,
                        purchases = :purchases,
                        ending_inventory_value = :end_inv,
                        calculated_cogs = :cogs,
                        total_waste_value = :waste,
                        waste_by_type = :waste_by_type,
                        food_cost_percentage = :food_cost_pct,
                        variance_from_target = :variance,
                        alerts = :alerts,
                        generated_at = NOW()
                """),
                {
                    "org_id": org_id,
                    "date": report_date,
                    "sales": total_food_sales,
                    "begin_inv": beginning_inventory,
                    "purchases": purchases,
                    "end_inv": ending_inventory,
                    "cogs": cogs,
                    "waste": total_waste,
                    "waste_by_type": json.dumps(waste_by_type),
                    "food_cost_pct": food_cost_pct,
                    "target": target_pct,
                    "variance": variance,
                    "alerts": json.dumps(alerts),
                }
            )
            await session.commit()
        
        return FoodCostReport(
            org_id=org_id,
            report_date=report_date,
            report_type="daily",
            total_food_sales=total_food_sales,
            beginning_inventory_value=beginning_inventory,
            purchases=purchases,
            ending_inventory_value=ending_inventory,
            calculated_cogs=cogs,
            total_waste_value=total_waste,
            food_cost_percentage=food_cost_pct,
            target_food_cost_pct=target_pct,
            variance_from_target=variance,
            alerts=alerts,
        )
    
    async def get_menu_profitability(
        self,
        org_id: uuid.UUID,
    ) -> List[Dict[str, Any]]:
        """Get profitability analysis for all menu items."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("""
                    SELECT 
                        id, name, category, menu_price, calculated_food_cost, 
                        food_cost_percentage, target_food_cost_pct, avg_daily_sales
                    FROM menu_items
                    WHERE org_id = :org_id AND status = 'active'
                    ORDER BY food_cost_percentage DESC NULLS LAST
                """),
                {"org_id": org_id}
            )
            
            items = []
            for row in result.fetchall():
                gross_profit = row.menu_price - (row.calculated_food_cost or 0)
                gross_margin = (gross_profit / row.menu_price * 100) if row.menu_price > 0 else 0
                
                status = "good"
                if row.food_cost_percentage:
                    if row.food_cost_percentage > 40:
                        status = "critical"
                    elif row.food_cost_percentage > 35:
                        status = "warning"
                    elif row.target_food_cost_pct and row.food_cost_percentage > row.target_food_cost_pct:
                        status = "over_target"
                
                items.append({
                    "id": str(row.id),
                    "name": row.name,
                    "category": row.category,
                    "menu_price": row.menu_price,
                    "food_cost": row.calculated_food_cost,
                    "food_cost_pct": float(row.food_cost_percentage) if row.food_cost_percentage else None,
                    "target_pct": float(row.target_food_cost_pct) if row.target_food_cost_pct else None,
                    "gross_profit": gross_profit,
                    "gross_margin_pct": round(gross_margin, 2),
                    "avg_daily_sales": float(row.avg_daily_sales) if row.avg_daily_sales else None,
                    "status": status,
                })
            
            return items


# Singleton instance
food_cost_service = FoodCostService()
