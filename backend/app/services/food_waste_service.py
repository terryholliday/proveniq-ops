"""
PROVENIQ Ops - Food Waste Tracking Service

Industry benchmarks:
- Restaurant waste target: under 4-5% of food purchases
- Pre-consumer waste: prep waste, spoilage, overproduction
- Post-consumer waste: plate waste, returns

This service:
- Logs waste events with categorization
- Calculates waste costs and percentages
- Identifies patterns (what, when, why)
- Provides actionable insights to reduce waste
"""

import uuid
import json
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import logging

from app.db.session import async_session_maker
from app.services.events.store import event_store

logger = logging.getLogger(__name__)


class WasteType(str, Enum):
    """Types of food waste."""
    SPOILAGE = "spoilage"
    EXPIRED = "expired"
    PREP_WASTE = "prep_waste"
    COOKING_ERROR = "cooking_error"
    CUSTOMER_RETURN = "customer_return"
    OVERPRODUCTION = "overproduction"
    DAMAGED = "damaged"
    THEFT = "theft"
    UNKNOWN = "unknown"


class WasteReason(str, Enum):
    """Specific reasons for waste."""
    PAST_EXPIRATION = "past_expiration"
    TEMPERATURE_ABUSE = "temperature_abuse"
    IMPROPER_STORAGE = "improper_storage"
    OVER_PREP = "over_prep"
    DROPPED = "dropped"
    BURNT = "burnt"
    WRONG_ORDER = "wrong_order"
    QUALITY_ISSUE = "quality_issue"
    INVENTORY_SHRINK = "inventory_shrink"
    SPILLAGE = "spillage"
    OTHER = "other"


class WasteEntry(BaseModel):
    """A single waste event."""
    id: Optional[uuid.UUID] = None
    org_id: uuid.UUID
    ingredient_id: Optional[uuid.UUID] = None
    menu_item_id: Optional[uuid.UUID] = None
    inventory_id: Optional[uuid.UUID] = None
    
    waste_type: WasteType
    waste_reason: WasteReason
    quantity: Decimal
    unit: str
    estimated_cost: int  # cents
    
    photo_url: Optional[str] = None
    notes: Optional[str] = None
    recorded_by: Optional[uuid.UUID] = None
    waste_date: date


class WasteSummary(BaseModel):
    """Waste summary for a period."""
    org_id: uuid.UUID
    start_date: date
    end_date: date
    
    total_waste_cost: int
    total_entries: int
    
    by_type: Dict[str, int]
    by_reason: Dict[str, int]
    by_ingredient: List[Dict[str, Any]]
    
    daily_average: int
    trend: str


class FoodWasteService:
    """
    Service for food waste tracking.
    
    MOAT PRINCIPLE:
    - Waste data creates accountability
    - Pattern recognition reduces future waste
    - Evidence trail for insurance claims on spoilage
    - Links to inventory and vendor quality
    """
    
    async def log_waste(
        self,
        org_id: uuid.UUID,
        waste_type: WasteType,
        waste_reason: WasteReason,
        quantity: Decimal,
        unit: str,
        estimated_cost: int,
        waste_date: Optional[date] = None,
        ingredient_id: Optional[uuid.UUID] = None,
        menu_item_id: Optional[uuid.UUID] = None,
        inventory_id: Optional[uuid.UUID] = None,
        photo_url: Optional[str] = None,
        notes: Optional[str] = None,
        recorded_by: Optional[uuid.UUID] = None,
    ) -> WasteEntry:
        """
        Log a food waste event.
        
        Every waste entry creates an immutable record for:
        - Cost tracking
        - Pattern analysis
        - Insurance claims
        - Vendor quality issues
        """
        waste_id = uuid.uuid4()
        waste_date = waste_date or date.today()
        
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Get ingredient name if provided
            ingredient_name = None
            if ingredient_id:
                result = await session.execute(
                    text("SELECT name FROM ingredients WHERE id = :id"),
                    {"id": ingredient_id}
                )
                row = result.fetchone()
                ingredient_name = row.name if row else None
            
            # Get menu item name if provided
            menu_item_name = None
            if menu_item_id:
                result = await session.execute(
                    text("SELECT name FROM menu_items WHERE id = :id"),
                    {"id": menu_item_id}
                )
                row = result.fetchone()
                menu_item_name = row.name if row else None
            
            await session.execute(
                text("""
                    INSERT INTO food_waste (
                        id, org_id, ingredient_id, menu_item_id, inventory_id,
                        waste_type, waste_reason, quantity, unit, estimated_cost,
                        photo_url, notes, recorded_by, waste_date, recorded_at
                    ) VALUES (
                        :id, :org_id, :ingredient_id, :menu_item_id, :inventory_id,
                        :waste_type, :waste_reason, :quantity, :unit, :cost,
                        :photo, :notes, :recorded_by, :waste_date, NOW()
                    )
                """),
                {
                    "id": waste_id,
                    "org_id": org_id,
                    "ingredient_id": ingredient_id,
                    "menu_item_id": menu_item_id,
                    "inventory_id": inventory_id,
                    "waste_type": waste_type.value,
                    "waste_reason": waste_reason.value,
                    "quantity": quantity,
                    "unit": unit,
                    "cost": estimated_cost,
                    "photo": photo_url,
                    "notes": notes,
                    "recorded_by": recorded_by,
                    "waste_date": waste_date,
                }
            )
            
            # If linked to inventory, update inventory status
            if inventory_id:
                await session.execute(
                    text("""
                        UPDATE food_inventory
                        SET status = 'wasted', quantity_on_hand = quantity_on_hand - :qty, updated_at = NOW()
                        WHERE id = :id
                    """),
                    {"id": inventory_id, "qty": quantity}
                )
            
            await session.commit()
        
        # Log event for forensics
        await event_store.append(
            event_type="ops.waste.logged",
            payload={
                "waste_id": str(waste_id),
                "org_id": str(org_id),
                "waste_type": waste_type.value,
                "waste_reason": waste_reason.value,
                "ingredient_id": str(ingredient_id) if ingredient_id else None,
                "ingredient_name": ingredient_name,
                "menu_item_id": str(menu_item_id) if menu_item_id else None,
                "menu_item_name": menu_item_name,
                "quantity": str(quantity),
                "unit": unit,
                "estimated_cost": estimated_cost,
                "waste_date": waste_date.isoformat(),
                "has_photo": photo_url is not None,
            },
            org_id=org_id,
        )
        
        logger.info(f"Logged waste: {waste_type.value} - ${estimated_cost/100:.2f} ({waste_id})")
        
        return WasteEntry(
            id=waste_id,
            org_id=org_id,
            ingredient_id=ingredient_id,
            menu_item_id=menu_item_id,
            inventory_id=inventory_id,
            waste_type=waste_type,
            waste_reason=waste_reason,
            quantity=quantity,
            unit=unit,
            estimated_cost=estimated_cost,
            photo_url=photo_url,
            notes=notes,
            recorded_by=recorded_by,
            waste_date=waste_date,
        )
    
    async def get_waste_summary(
        self,
        org_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> WasteSummary:
        """Get waste summary for a period."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            # Total waste
            total_result = await session.execute(
                text("""
                    SELECT 
                        COALESCE(SUM(estimated_cost), 0) as total_cost,
                        COUNT(*) as total_entries
                    FROM food_waste
                    WHERE org_id = :org_id
                    AND waste_date BETWEEN :start AND :end
                """),
                {"org_id": org_id, "start": start_date, "end": end_date}
            )
            total_row = total_result.fetchone()
            
            # By type
            type_result = await session.execute(
                text("""
                    SELECT waste_type, COALESCE(SUM(estimated_cost), 0) as cost
                    FROM food_waste
                    WHERE org_id = :org_id
                    AND waste_date BETWEEN :start AND :end
                    GROUP BY waste_type
                """),
                {"org_id": org_id, "start": start_date, "end": end_date}
            )
            by_type = {row.waste_type: row.cost for row in type_result.fetchall()}
            
            # By reason
            reason_result = await session.execute(
                text("""
                    SELECT waste_reason, COALESCE(SUM(estimated_cost), 0) as cost
                    FROM food_waste
                    WHERE org_id = :org_id
                    AND waste_date BETWEEN :start AND :end
                    GROUP BY waste_reason
                """),
                {"org_id": org_id, "start": start_date, "end": end_date}
            )
            by_reason = {row.waste_reason: row.cost for row in reason_result.fetchall()}
            
            # By ingredient (top 10)
            ingredient_result = await session.execute(
                text("""
                    SELECT 
                        i.name,
                        COALESCE(SUM(w.estimated_cost), 0) as cost,
                        COUNT(*) as entries
                    FROM food_waste w
                    JOIN ingredients i ON w.ingredient_id = i.id
                    WHERE w.org_id = :org_id
                    AND w.waste_date BETWEEN :start AND :end
                    GROUP BY i.name
                    ORDER BY cost DESC
                    LIMIT 10
                """),
                {"org_id": org_id, "start": start_date, "end": end_date}
            )
            by_ingredient = [
                {"name": row.name, "cost": row.cost, "entries": row.entries}
                for row in ingredient_result.fetchall()
            ]
            
            # Calculate daily average
            days = (end_date - start_date).days + 1
            daily_avg = total_row.total_cost // days if days > 0 else 0
            
            # Calculate trend
            trend = await self._calculate_waste_trend(org_id, start_date, end_date)
            
            return WasteSummary(
                org_id=org_id,
                start_date=start_date,
                end_date=end_date,
                total_waste_cost=total_row.total_cost,
                total_entries=total_row.total_entries,
                by_type=by_type,
                by_reason=by_reason,
                by_ingredient=by_ingredient,
                daily_average=daily_avg,
                trend=trend,
            )
    
    async def _calculate_waste_trend(
        self,
        org_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> str:
        """Calculate waste trend vs previous period."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            days = (end_date - start_date).days + 1
            prev_start = start_date - timedelta(days=days)
            prev_end = start_date - timedelta(days=1)
            
            # Current period
            current_result = await session.execute(
                text("""
                    SELECT COALESCE(SUM(estimated_cost), 0) as total
                    FROM food_waste
                    WHERE org_id = :org_id
                    AND waste_date BETWEEN :start AND :end
                """),
                {"org_id": org_id, "start": start_date, "end": end_date}
            )
            current = current_result.fetchone().total
            
            # Previous period
            prev_result = await session.execute(
                text("""
                    SELECT COALESCE(SUM(estimated_cost), 0) as total
                    FROM food_waste
                    WHERE org_id = :org_id
                    AND waste_date BETWEEN :start AND :end
                """),
                {"org_id": org_id, "start": prev_start, "end": prev_end}
            )
            previous = prev_result.fetchone().total
            
            if previous == 0:
                return "stable" if current == 0 else "increasing"
            
            change_pct = (current - previous) / previous * 100
            
            if change_pct > 10:
                return "increasing"
            elif change_pct < -10:
                return "decreasing"
            return "stable"
    
    async def get_waste_patterns(
        self,
        org_id: uuid.UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Identify waste patterns for actionable insights."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            start_date = date.today() - timedelta(days=days)
            
            # Day of week pattern
            dow_result = await session.execute(
                text("""
                    SELECT 
                        EXTRACT(DOW FROM waste_date) as day_of_week,
                        COALESCE(SUM(estimated_cost), 0) as cost
                    FROM food_waste
                    WHERE org_id = :org_id
                    AND waste_date >= :start
                    GROUP BY EXTRACT(DOW FROM waste_date)
                    ORDER BY day_of_week
                """),
                {"org_id": org_id, "start": start_date}
            )
            dow_pattern = {
                int(row.day_of_week): row.cost
                for row in dow_result.fetchall()
            }
            
            # Time of day pattern (if we track that)
            # For now, aggregate by waste type and reason combos
            pattern_result = await session.execute(
                text("""
                    SELECT 
                        waste_type,
                        waste_reason,
                        COALESCE(SUM(estimated_cost), 0) as cost,
                        COUNT(*) as occurrences
                    FROM food_waste
                    WHERE org_id = :org_id
                    AND waste_date >= :start
                    GROUP BY waste_type, waste_reason
                    ORDER BY cost DESC
                    LIMIT 10
                """),
                {"org_id": org_id, "start": start_date}
            )
            
            top_patterns = [
                {
                    "type": row.waste_type,
                    "reason": row.waste_reason,
                    "cost": row.cost,
                    "occurrences": row.occurrences,
                }
                for row in pattern_result.fetchall()
            ]
            
            # Repeat offenders (same ingredient wasted multiple times)
            repeat_result = await session.execute(
                text("""
                    SELECT 
                        i.name,
                        COUNT(*) as waste_count,
                        COALESCE(SUM(w.estimated_cost), 0) as total_cost
                    FROM food_waste w
                    JOIN ingredients i ON w.ingredient_id = i.id
                    WHERE w.org_id = :org_id
                    AND w.waste_date >= :start
                    GROUP BY i.name
                    HAVING COUNT(*) > 2
                    ORDER BY waste_count DESC
                    LIMIT 5
                """),
                {"org_id": org_id, "start": start_date}
            )
            
            repeat_offenders = [
                {"ingredient": row.name, "count": row.waste_count, "cost": row.total_cost}
                for row in repeat_result.fetchall()
            ]
            
            # Generate insights
            insights = self._generate_insights(top_patterns, repeat_offenders, dow_pattern)
            
            return {
                "period_days": days,
                "day_of_week_pattern": dow_pattern,
                "top_waste_patterns": top_patterns,
                "repeat_offenders": repeat_offenders,
                "insights": insights,
            }
    
    def _generate_insights(
        self,
        patterns: List[Dict],
        repeats: List[Dict],
        dow: Dict[int, int],
    ) -> List[str]:
        """Generate actionable insights from waste patterns."""
        insights = []
        
        # Check for spoilage/expiration issues
        spoilage_cost = sum(
            p["cost"] for p in patterns
            if p["type"] in ("spoilage", "expired")
        )
        if spoilage_cost > 0:
            insights.append(
                f"Spoilage and expiration account for ${spoilage_cost/100:.2f}. "
                "Review FIFO practices and par levels."
            )
        
        # Check for prep waste
        prep_patterns = [p for p in patterns if p["type"] == "prep_waste"]
        if prep_patterns:
            total_prep = sum(p["cost"] for p in prep_patterns)
            insights.append(
                f"Prep waste totals ${total_prep/100:.2f}. "
                "Consider batch size adjustments."
            )
        
        # Check for repeat offenders
        if repeats:
            top_repeat = repeats[0]
            insights.append(
                f"{top_repeat['ingredient']} was wasted {top_repeat['count']} times "
                f"(${top_repeat['cost']/100:.2f}). Reduce par level or find alternative vendor."
            )
        
        # Check day of week patterns
        if dow:
            max_day = max(dow, key=dow.get)
            day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
            insights.append(
                f"Highest waste on {day_names[max_day]}. "
                "Review delivery schedule and prep planning."
            )
        
        return insights
    
    async def get_waste_for_claims(
        self,
        org_id: uuid.UUID,
        start_date: date,
        end_date: date,
        waste_types: Optional[List[WasteType]] = None,
    ) -> Dict[str, Any]:
        """
        Get waste data formatted for insurance claims.
        
        Only spoilage, expired, and damaged waste typically qualifies for claims.
        """
        claimable_types = waste_types or [
            WasteType.SPOILAGE,
            WasteType.EXPIRED,
            WasteType.DAMAGED,
        ]
        
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(
                text("""
                    SELECT 
                        w.id,
                        w.waste_date,
                        w.waste_type,
                        w.waste_reason,
                        w.quantity,
                        w.unit,
                        w.estimated_cost,
                        w.photo_url,
                        w.notes,
                        i.name as ingredient_name,
                        w.recorded_at
                    FROM food_waste w
                    LEFT JOIN ingredients i ON w.ingredient_id = i.id
                    WHERE w.org_id = :org_id
                    AND w.waste_date BETWEEN :start AND :end
                    AND w.waste_type = ANY(:types)
                    ORDER BY w.waste_date, w.recorded_at
                """),
                {
                    "org_id": org_id,
                    "start": start_date,
                    "end": end_date,
                    "types": [t.value for t in claimable_types],
                }
            )
            
            entries = []
            total_cost = 0
            
            for row in result.fetchall():
                entries.append({
                    "waste_id": str(row.id),
                    "date": row.waste_date.isoformat(),
                    "type": row.waste_type,
                    "reason": row.waste_reason,
                    "item": row.ingredient_name or "Unknown",
                    "quantity": f"{row.quantity} {row.unit}",
                    "cost": row.estimated_cost,
                    "has_photo": row.photo_url is not None,
                    "photo_url": row.photo_url,
                    "notes": row.notes,
                    "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
                })
                total_cost += row.estimated_cost
            
            return {
                "org_id": str(org_id),
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "claimable_waste_types": [t.value for t in claimable_types],
                "total_claimable_cost": total_cost,
                "entry_count": len(entries),
                "entries": entries,
                "disclaimer": (
                    "This report documents recorded food waste events. "
                    "Actual claim eligibility subject to policy terms."
                ),
            }


# Singleton instance
food_waste_service = FoodWasteService()
