"""
PROVENIQ Ops - Perishable Inventory Service

FIFO enforcement and expiration tracking for food inventory.

Key functions:
- Track inventory by lot/received date
- Enforce First-In-First-Out usage
- Predict spoilage before it happens
- Alert on expiring items
- Link to waste when items expire
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


class InventoryStatus(str, Enum):
    """Status of inventory item."""
    AVAILABLE = "available"
    RESERVED = "reserved"
    EXPIRED = "expired"
    WASTED = "wasted"
    CONSUMED = "consumed"


class StorageLocation(str, Enum):
    """Storage locations."""
    WALK_IN = "walk_in"
    FREEZER = "freezer"
    DRY_STORAGE = "dry_storage"
    LINE = "line"
    PREP = "prep"


class InventoryItem(BaseModel):
    """A single inventory lot."""
    id: Optional[uuid.UUID] = None
    org_id: uuid.UUID
    location_id: Optional[uuid.UUID] = None
    ingredient_id: uuid.UUID
    
    quantity_on_hand: Decimal
    unit: str
    
    lot_number: Optional[str] = None
    received_date: date
    expiration_date: Optional[date] = None
    days_until_expiration: Optional[int] = None
    
    unit_cost_at_receipt: int  # cents
    total_value: int  # cents
    
    storage_location: Optional[str] = None
    status: InventoryStatus = InventoryStatus.AVAILABLE


class ExpirationAlert(BaseModel):
    """Alert for expiring inventory."""
    inventory_id: uuid.UUID
    ingredient_name: str
    quantity: Decimal
    unit: str
    expiration_date: date
    days_remaining: int
    value: int  # cents
    storage_location: Optional[str]
    urgency: str  # critical, warning, notice


class PerishableInventoryService:
    """
    Service for perishable inventory management.
    
    MOAT PRINCIPLE:
    - Expiration tracking prevents waste
    - FIFO enforcement ensures quality
    - Lot tracking supports recalls and claims
    - Predictive spoilage saves money
    """
    
    async def receive_inventory(
        self,
        org_id: uuid.UUID,
        ingredient_id: uuid.UUID,
        quantity: Decimal,
        unit: str,
        unit_cost: int,
        received_date: Optional[date] = None,
        expiration_date: Optional[date] = None,
        lot_number: Optional[str] = None,
        storage_location: Optional[str] = None,
        location_id: Optional[uuid.UUID] = None,
        order_item_id: Optional[uuid.UUID] = None,
    ) -> InventoryItem:
        """
        Receive new inventory into stock.
        
        Creates a new lot record for FIFO tracking.
        """
        inventory_id = uuid.uuid4()
        received_date = received_date or date.today()
        total_value = int(float(quantity) * unit_cost)
        
        # Calculate days until expiration
        days_until = None
        if expiration_date:
            days_until = (expiration_date - date.today()).days
        
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Get ingredient info
            result = await session.execute(
                text("SELECT name, shelf_life_days FROM ingredients WHERE id = :id"),
                {"id": ingredient_id}
            )
            ing = result.fetchone()
            ingredient_name = ing.name if ing else "Unknown"
            
            # If no expiration date provided, calculate from shelf life
            if not expiration_date and ing and ing.shelf_life_days:
                expiration_date = received_date + timedelta(days=ing.shelf_life_days)
                days_until = ing.shelf_life_days
            
            await session.execute(
                text("""
                    INSERT INTO food_inventory (
                        id, org_id, location_id, ingredient_id,
                        quantity_on_hand, unit,
                        lot_number, received_date, expiration_date, days_until_expiration,
                        unit_cost_at_receipt, total_value,
                        storage_location, status,
                        created_at
                    ) VALUES (
                        :id, :org_id, :location_id, :ingredient_id,
                        :quantity, :unit,
                        :lot, :received, :expires, :days,
                        :cost, :value,
                        :storage, 'available',
                        NOW()
                    )
                """),
                {
                    "id": inventory_id,
                    "org_id": org_id,
                    "location_id": location_id,
                    "ingredient_id": ingredient_id,
                    "quantity": quantity,
                    "unit": unit,
                    "lot": lot_number,
                    "received": received_date,
                    "expires": expiration_date,
                    "days": days_until,
                    "cost": unit_cost,
                    "value": total_value,
                    "storage": storage_location,
                }
            )
            await session.commit()
        
        # Log event
        await event_store.append(
            event_type="ops.inventory.received",
            payload={
                "inventory_id": str(inventory_id),
                "org_id": str(org_id),
                "ingredient_id": str(ingredient_id),
                "ingredient_name": ingredient_name,
                "quantity": str(quantity),
                "unit": unit,
                "unit_cost": unit_cost,
                "total_value": total_value,
                "lot_number": lot_number,
                "received_date": received_date.isoformat(),
                "expiration_date": expiration_date.isoformat() if expiration_date else None,
                "storage_location": storage_location,
            },
            org_id=org_id,
        )
        
        logger.info(f"Received inventory: {ingredient_name} x {quantity} {unit} ({inventory_id})")
        
        return InventoryItem(
            id=inventory_id,
            org_id=org_id,
            location_id=location_id,
            ingredient_id=ingredient_id,
            quantity_on_hand=quantity,
            unit=unit,
            lot_number=lot_number,
            received_date=received_date,
            expiration_date=expiration_date,
            days_until_expiration=days_until,
            unit_cost_at_receipt=unit_cost,
            total_value=total_value,
            storage_location=storage_location,
            status=InventoryStatus.AVAILABLE,
        )
    
    async def consume_inventory(
        self,
        org_id: uuid.UUID,
        ingredient_id: uuid.UUID,
        quantity: Decimal,
        unit: str,
        reason: str = "usage",
    ) -> Dict[str, Any]:
        """
        Consume inventory using FIFO.
        
        Automatically uses oldest available inventory first.
        """
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Get available inventory ordered by received date (FIFO)
            result = await session.execute(
                text("""
                    SELECT id, quantity_on_hand, unit_cost_at_receipt, lot_number, received_date
                    FROM food_inventory
                    WHERE org_id = :org_id
                    AND ingredient_id = :ingredient_id
                    AND status = 'available'
                    AND quantity_on_hand > 0
                    ORDER BY received_date ASC, created_at ASC
                """),
                {"org_id": org_id, "ingredient_id": ingredient_id}
            )
            
            lots = result.fetchall()
            remaining = float(quantity)
            consumed_lots = []
            total_cost = 0
            
            for lot in lots:
                if remaining <= 0:
                    break
                
                available = float(lot.quantity_on_hand)
                to_consume = min(available, remaining)
                
                new_qty = available - to_consume
                cost = int(to_consume * lot.unit_cost_at_receipt)
                total_cost += cost
                
                # Update lot
                if new_qty <= 0:
                    await session.execute(
                        text("""
                            UPDATE food_inventory
                            SET quantity_on_hand = 0, status = 'consumed', updated_at = NOW()
                            WHERE id = :id
                        """),
                        {"id": lot.id}
                    )
                else:
                    await session.execute(
                        text("""
                            UPDATE food_inventory
                            SET quantity_on_hand = :qty, 
                                total_value = :qty * unit_cost_at_receipt,
                                updated_at = NOW()
                            WHERE id = :id
                        """),
                        {"id": lot.id, "qty": new_qty}
                    )
                
                consumed_lots.append({
                    "lot_id": str(lot.id),
                    "lot_number": lot.lot_number,
                    "received_date": lot.received_date.isoformat(),
                    "quantity_consumed": to_consume,
                    "cost": cost,
                })
                
                remaining -= to_consume
            
            await session.commit()
            
            # Get ingredient name
            name_result = await session.execute(
                text("SELECT name FROM ingredients WHERE id = :id"),
                {"id": ingredient_id}
            )
            name_row = name_result.fetchone()
        
        # Log event
        await event_store.append(
            event_type="ops.inventory.consumed",
            payload={
                "org_id": str(org_id),
                "ingredient_id": str(ingredient_id),
                "ingredient_name": name_row.name if name_row else None,
                "quantity_requested": str(quantity),
                "quantity_consumed": str(float(quantity) - remaining),
                "unit": unit,
                "reason": reason,
                "lots_used": len(consumed_lots),
                "total_cost": total_cost,
                "fifo_enforced": True,
            },
            org_id=org_id,
        )
        
        return {
            "ingredient_id": str(ingredient_id),
            "quantity_consumed": float(quantity) - remaining,
            "quantity_short": remaining if remaining > 0 else 0,
            "lots_used": consumed_lots,
            "total_cost": total_cost,
            "fifo_enforced": True,
        }
    
    async def get_expiring_inventory(
        self,
        org_id: uuid.UUID,
        days_ahead: int = 7,
    ) -> List[ExpirationAlert]:
        """Get inventory expiring within specified days."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            cutoff_date = date.today() + timedelta(days=days_ahead)
            
            result = await session.execute(
                text("""
                    SELECT 
                        fi.id,
                        fi.quantity_on_hand,
                        fi.unit,
                        fi.expiration_date,
                        fi.total_value,
                        fi.storage_location,
                        i.name as ingredient_name
                    FROM food_inventory fi
                    JOIN ingredients i ON fi.ingredient_id = i.id
                    WHERE fi.org_id = :org_id
                    AND fi.status = 'available'
                    AND fi.expiration_date IS NOT NULL
                    AND fi.expiration_date <= :cutoff
                    AND fi.quantity_on_hand > 0
                    ORDER BY fi.expiration_date ASC
                """),
                {"org_id": org_id, "cutoff": cutoff_date}
            )
            
            alerts = []
            for row in result.fetchall():
                days_remaining = (row.expiration_date - date.today()).days
                
                if days_remaining <= 0:
                    urgency = "critical"
                elif days_remaining <= 2:
                    urgency = "warning"
                else:
                    urgency = "notice"
                
                alerts.append(ExpirationAlert(
                    inventory_id=row.id,
                    ingredient_name=row.ingredient_name,
                    quantity=row.quantity_on_hand,
                    unit=row.unit,
                    expiration_date=row.expiration_date,
                    days_remaining=days_remaining,
                    value=row.total_value,
                    storage_location=row.storage_location,
                    urgency=urgency,
                ))
            
            return alerts
    
    async def process_expired_inventory(
        self,
        org_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Process expired inventory - mark as expired and create waste records.
        
        Should be run daily.
        """
        from app.services.food_waste_service import food_waste_service, WasteType, WasteReason
        
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Find expired items
            result = await session.execute(
                text("""
                    SELECT 
                        fi.id,
                        fi.ingredient_id,
                        fi.quantity_on_hand,
                        fi.unit,
                        fi.total_value,
                        i.name
                    FROM food_inventory fi
                    JOIN ingredients i ON fi.ingredient_id = i.id
                    WHERE fi.org_id = :org_id
                    AND fi.status = 'available'
                    AND fi.expiration_date IS NOT NULL
                    AND fi.expiration_date < CURRENT_DATE
                    AND fi.quantity_on_hand > 0
                """),
                {"org_id": org_id}
            )
            
            expired_items = result.fetchall()
            processed = []
            total_waste = 0
            
            for item in expired_items:
                # Mark as expired
                await session.execute(
                    text("""
                        UPDATE food_inventory
                        SET status = 'expired', updated_at = NOW()
                        WHERE id = :id
                    """),
                    {"id": item.id}
                )
                
                # Create waste record
                await food_waste_service.log_waste(
                    org_id=org_id,
                    waste_type=WasteType.EXPIRED,
                    waste_reason=WasteReason.PAST_EXPIRATION,
                    quantity=item.quantity_on_hand,
                    unit=item.unit,
                    estimated_cost=item.total_value,
                    ingredient_id=item.ingredient_id,
                    inventory_id=item.id,
                    notes=f"Auto-expired: {item.name}",
                )
                
                processed.append({
                    "inventory_id": str(item.id),
                    "ingredient": item.name,
                    "quantity": float(item.quantity_on_hand),
                    "unit": item.unit,
                    "value": item.total_value,
                })
                total_waste += item.total_value
            
            await session.commit()
        
        if processed:
            await event_store.append(
                event_type="ops.inventory.expired_processed",
                payload={
                    "org_id": str(org_id),
                    "items_expired": len(processed),
                    "total_waste_value": total_waste,
                    "items": processed,
                },
                org_id=org_id,
            )
        
        return {
            "items_processed": len(processed),
            "total_waste_value": total_waste,
            "items": processed,
        }
    
    async def get_inventory_value(
        self,
        org_id: uuid.UUID,
        as_of_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get total inventory value, optionally as of a specific date."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            as_of = as_of_date or date.today()
            
            # Current inventory value by category
            result = await session.execute(
                text("""
                    SELECT 
                        i.category,
                        COALESCE(SUM(fi.total_value), 0) as value,
                        COUNT(DISTINCT fi.ingredient_id) as item_count
                    FROM food_inventory fi
                    JOIN ingredients i ON fi.ingredient_id = i.id
                    WHERE fi.org_id = :org_id
                    AND fi.status = 'available'
                    AND fi.received_date <= :as_of
                    GROUP BY i.category
                """),
                {"org_id": org_id, "as_of": as_of}
            )
            
            by_category = {}
            total_value = 0
            total_items = 0
            
            for row in result.fetchall():
                by_category[row.category] = {
                    "value": row.value,
                    "item_count": row.item_count,
                }
                total_value += row.value
                total_items += row.item_count
            
            # Value at risk (expiring in 3 days)
            risk_result = await session.execute(
                text("""
                    SELECT COALESCE(SUM(total_value), 0) as at_risk
                    FROM food_inventory
                    WHERE org_id = :org_id
                    AND status = 'available'
                    AND expiration_date IS NOT NULL
                    AND expiration_date <= CURRENT_DATE + INTERVAL '3 days'
                """),
                {"org_id": org_id}
            )
            at_risk = risk_result.fetchone().at_risk
            
            return {
                "org_id": str(org_id),
                "as_of_date": as_of.isoformat(),
                "total_value": total_value,
                "total_items": total_items,
                "by_category": by_category,
                "value_at_risk_3_days": at_risk,
            }
    
    async def get_low_stock_items(
        self,
        org_id: uuid.UUID,
    ) -> List[Dict[str, Any]]:
        """Get items below reorder point."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("""
                    SELECT 
                        i.id,
                        i.name,
                        i.category,
                        i.reorder_point,
                        i.par_level,
                        i.base_unit,
                        COALESCE(SUM(fi.quantity_on_hand), 0) as on_hand
                    FROM ingredients i
                    LEFT JOIN food_inventory fi ON i.id = fi.ingredient_id 
                        AND fi.status = 'available'
                        AND fi.org_id = :org_id
                    WHERE i.org_id = :org_id
                    AND i.status = 'active'
                    AND i.reorder_point IS NOT NULL
                    GROUP BY i.id, i.name, i.category, i.reorder_point, i.par_level, i.base_unit
                    HAVING COALESCE(SUM(fi.quantity_on_hand), 0) <= i.reorder_point
                    ORDER BY (COALESCE(SUM(fi.quantity_on_hand), 0) / i.reorder_point) ASC
                """),
                {"org_id": org_id}
            )
            
            low_stock = []
            for row in result.fetchall():
                needed = float(row.par_level - row.on_hand) if row.par_level else float(row.reorder_point)
                low_stock.append({
                    "ingredient_id": str(row.id),
                    "name": row.name,
                    "category": row.category,
                    "on_hand": float(row.on_hand),
                    "reorder_point": float(row.reorder_point),
                    "par_level": float(row.par_level) if row.par_level else None,
                    "unit": row.base_unit,
                    "quantity_needed": needed,
                    "urgency": "critical" if row.on_hand == 0 else "warning",
                })
            
            return low_stock


# Singleton instance
perishable_inventory_service = PerishableInventoryService()
