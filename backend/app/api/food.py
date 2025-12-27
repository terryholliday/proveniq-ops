"""
PROVENIQ Ops - Food Management API Routes
Ingredients, Menu Items, Recipes, Waste Tracking, Food Orders

Restaurant food cost control (target 28-35% of revenue)
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.schemas import (
    IngredientCreate,
    IngredientRead,
    IngredientCategory,
    MenuItemCreate,
    MenuItemRead,
    RecipeCreate,
    RecipeRead,
    FoodWasteCreate,
    FoodWasteRead,
    FoodOrderCreate,
    FoodOrderRead,
    FoodOrderStatus,
    FoodCostReportRead,
)

router = APIRouter(prefix="/food", tags=["Food Management"])


# =============================================================================
# INGREDIENTS
# =============================================================================

@router.get("/ingredients", response_model=list[IngredientRead])
async def list_ingredients(
    org_id: uuid.UUID,
    category: Optional[IngredientCategory] = None,
    is_perishable: Optional[bool] = None,
    below_par: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[IngredientRead]:
    """
    List ingredients for an organization.
    
    Filters:
    - category: Filter by ingredient category
    - is_perishable: Filter perishable items only
    - below_par: Show only items below par level (needs inventory check)
    """
    query = select_ingredient_table().where(col_org_id() == org_id)
    
    if category:
        query = query.where(col_category() == category.value)
    if is_perishable is not None:
        query = query.where(col_is_perishable() == is_perishable)
    
    query = query.order_by(col_name())
    
    result = await db.execute(query)
    ingredients = result.mappings().all()
    
    return [IngredientRead(**dict(i)) for i in ingredients]


@router.post("/ingredients", response_model=IngredientRead, status_code=status.HTTP_201_CREATED)
async def create_ingredient(
    ingredient: IngredientCreate,
    db: AsyncSession = Depends(get_db),
) -> IngredientRead:
    """Create a new ingredient in the catalog."""
    from sqlalchemy import text
    
    ingredient_id = uuid.uuid4()
    now = datetime.utcnow()
    
    query = text("""
        INSERT INTO ingredients (
            id, org_id, name, category, subcategory, base_unit, purchase_unit,
            purchase_to_base_ratio, current_cost_per_unit, is_perishable,
            shelf_life_days, requires_refrigeration, requires_freezer,
            par_level, reorder_point, min_order_qty, preferred_vendor_id,
            status, created_at, updated_at
        ) VALUES (
            :id, :org_id, :name, :category, :subcategory, :base_unit, :purchase_unit,
            :purchase_to_base_ratio, :current_cost_per_unit, :is_perishable,
            :shelf_life_days, :requires_refrigeration, :requires_freezer,
            :par_level, :reorder_point, :min_order_qty, :preferred_vendor_id,
            :status, :created_at, :updated_at
        )
        RETURNING *
    """)
    
    result = await db.execute(query, {
        "id": ingredient_id,
        "org_id": ingredient.org_id,
        "name": ingredient.name,
        "category": ingredient.category.value,
        "subcategory": ingredient.subcategory,
        "base_unit": ingredient.base_unit,
        "purchase_unit": ingredient.purchase_unit,
        "purchase_to_base_ratio": ingredient.purchase_to_base_ratio,
        "current_cost_per_unit": ingredient.current_cost_cents,
        "is_perishable": ingredient.is_perishable,
        "shelf_life_days": ingredient.shelf_life_days,
        "requires_refrigeration": ingredient.requires_refrigeration,
        "requires_freezer": ingredient.requires_freezer,
        "par_level": ingredient.par_level,
        "reorder_point": ingredient.reorder_point,
        "min_order_qty": ingredient.min_order_qty,
        "preferred_vendor_id": ingredient.preferred_vendor_id,
        "status": ingredient.status.value,
        "created_at": now,
        "updated_at": now,
    })
    
    row = result.mappings().first()
    await db.commit()
    
    return IngredientRead(
        id=row["id"],
        org_id=row["org_id"],
        name=row["name"],
        category=row["category"],
        subcategory=row["subcategory"],
        base_unit=row["base_unit"],
        purchase_unit=row["purchase_unit"],
        purchase_to_base_ratio=row["purchase_to_base_ratio"],
        current_cost_cents=row["current_cost_per_unit"],
        is_perishable=row["is_perishable"],
        shelf_life_days=row["shelf_life_days"],
        requires_refrigeration=row["requires_refrigeration"],
        requires_freezer=row["requires_freezer"],
        par_level=row["par_level"],
        reorder_point=row["reorder_point"],
        min_order_qty=row["min_order_qty"],
        preferred_vendor_id=row["preferred_vendor_id"],
        status=row["status"],
        cost_updated_at=row.get("cost_updated_at"),
        avg_cost_30d=row.get("avg_cost_30d"),
        avg_cost_90d=row.get("avg_cost_90d"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("/ingredients/{ingredient_id}", response_model=IngredientRead)
async def get_ingredient(
    ingredient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> IngredientRead:
    """Get a specific ingredient by ID."""
    from sqlalchemy import text
    
    query = text("SELECT * FROM ingredients WHERE id = :id")
    result = await db.execute(query, {"id": ingredient_id})
    row = result.mappings().first()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient {ingredient_id} not found",
        )
    
    return IngredientRead(
        id=row["id"],
        org_id=row["org_id"],
        name=row["name"],
        category=row["category"],
        subcategory=row["subcategory"],
        base_unit=row["base_unit"],
        purchase_unit=row["purchase_unit"],
        purchase_to_base_ratio=row["purchase_to_base_ratio"],
        current_cost_cents=row["current_cost_per_unit"],
        is_perishable=row["is_perishable"],
        shelf_life_days=row["shelf_life_days"],
        requires_refrigeration=row["requires_refrigeration"],
        requires_freezer=row["requires_freezer"],
        par_level=row["par_level"],
        reorder_point=row["reorder_point"],
        min_order_qty=row["min_order_qty"],
        preferred_vendor_id=row["preferred_vendor_id"],
        status=row["status"],
        cost_updated_at=row.get("cost_updated_at"),
        avg_cost_30d=row.get("avg_cost_30d"),
        avg_cost_90d=row.get("avg_cost_90d"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# =============================================================================
# MENU ITEMS
# =============================================================================

@router.get("/menu-items", response_model=list[MenuItemRead])
async def list_menu_items(
    org_id: uuid.UUID,
    category: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> list[MenuItemRead]:
    """List menu items for an organization."""
    from sqlalchemy import text
    
    query_str = "SELECT * FROM menu_items WHERE org_id = :org_id"
    params = {"org_id": org_id}
    
    if category:
        query_str += " AND category = :category"
        params["category"] = category
    if status_filter:
        query_str += " AND status = :status"
        params["status"] = status_filter
    
    query_str += " ORDER BY name"
    
    result = await db.execute(text(query_str), params)
    rows = result.mappings().all()
    
    return [MenuItemRead(
        id=r["id"],
        org_id=r["org_id"],
        name=r["name"],
        category=r["category"],
        subcategory=r["subcategory"],
        menu_price_cents=r["menu_price"],
        target_food_cost_pct=r["target_food_cost_pct"],
        status=r["status"],
        is_seasonal=r["is_seasonal"],
        calculated_food_cost_cents=r.get("calculated_food_cost"),
        food_cost_percentage=r.get("food_cost_percentage"),
        avg_daily_sales=r.get("avg_daily_sales"),
        last_sold_at=r.get("last_sold_at"),
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    ) for r in rows]


@router.post("/menu-items", response_model=MenuItemRead, status_code=status.HTTP_201_CREATED)
async def create_menu_item(
    menu_item: MenuItemCreate,
    db: AsyncSession = Depends(get_db),
) -> MenuItemRead:
    """Create a new menu item."""
    from sqlalchemy import text
    
    item_id = uuid.uuid4()
    now = datetime.utcnow()
    
    query = text("""
        INSERT INTO menu_items (
            id, org_id, name, category, subcategory, menu_price,
            target_food_cost_pct, status, is_seasonal, created_at, updated_at
        ) VALUES (
            :id, :org_id, :name, :category, :subcategory, :menu_price,
            :target_food_cost_pct, :status, :is_seasonal, :created_at, :updated_at
        )
        RETURNING *
    """)
    
    result = await db.execute(query, {
        "id": item_id,
        "org_id": menu_item.org_id,
        "name": menu_item.name,
        "category": menu_item.category,
        "subcategory": menu_item.subcategory,
        "menu_price": menu_item.menu_price_cents,
        "target_food_cost_pct": menu_item.target_food_cost_pct,
        "status": menu_item.status.value,
        "is_seasonal": menu_item.is_seasonal,
        "created_at": now,
        "updated_at": now,
    })
    
    row = result.mappings().first()
    await db.commit()
    
    return MenuItemRead(
        id=row["id"],
        org_id=row["org_id"],
        name=row["name"],
        category=row["category"],
        subcategory=row["subcategory"],
        menu_price_cents=row["menu_price"],
        target_food_cost_pct=row["target_food_cost_pct"],
        status=row["status"],
        is_seasonal=row["is_seasonal"],
        calculated_food_cost_cents=row.get("calculated_food_cost"),
        food_cost_percentage=row.get("food_cost_percentage"),
        avg_daily_sales=row.get("avg_daily_sales"),
        last_sold_at=row.get("last_sold_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("/menu-items/{item_id}/cost-breakdown")
async def get_menu_item_cost_breakdown(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get detailed cost breakdown for a menu item.
    
    Shows each ingredient, quantity, cost, and total food cost percentage.
    Critical for maintaining target 28-35% food cost.
    """
    from sqlalchemy import text
    
    # Get menu item
    item_query = text("SELECT * FROM menu_items WHERE id = :id")
    item_result = await db.execute(item_query, {"id": item_id})
    item = item_result.mappings().first()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Menu item {item_id} not found",
        )
    
    # Get recipe ingredients with costs
    recipe_query = text("""
        SELECT r.*, i.name as ingredient_name, i.current_cost_per_unit, i.base_unit
        FROM recipes r
        JOIN ingredients i ON r.ingredient_id = i.id
        WHERE r.menu_item_id = :menu_item_id
    """)
    recipe_result = await db.execute(recipe_query, {"menu_item_id": item_id})
    recipes = recipe_result.mappings().all()
    
    ingredients_breakdown = []
    total_cost_cents = 0
    
    for r in recipes:
        ingredient_cost = int(float(r["quantity"]) * float(r["waste_factor"]) * r["current_cost_per_unit"])
        total_cost_cents += ingredient_cost
        
        ingredients_breakdown.append({
            "ingredient_id": str(r["ingredient_id"]),
            "ingredient_name": r["ingredient_name"],
            "quantity": float(r["quantity"]),
            "unit": r["unit"],
            "waste_factor": float(r["waste_factor"]),
            "unit_cost_cents": r["current_cost_per_unit"],
            "line_cost_cents": ingredient_cost,
        })
    
    menu_price = item["menu_price"]
    food_cost_pct = (total_cost_cents / menu_price * 100) if menu_price > 0 else 0
    target_pct = float(item["target_food_cost_pct"] or 30)
    variance = food_cost_pct - target_pct
    
    return {
        "menu_item_id": str(item_id),
        "menu_item_name": item["name"],
        "menu_price_cents": menu_price,
        "total_food_cost_cents": total_cost_cents,
        "food_cost_percentage": round(food_cost_pct, 2),
        "target_food_cost_pct": target_pct,
        "variance_from_target": round(variance, 2),
        "status": "ON_TARGET" if abs(variance) <= 3 else ("OVER_TARGET" if variance > 0 else "UNDER_TARGET"),
        "ingredients": ingredients_breakdown,
    }


# =============================================================================
# RECIPES
# =============================================================================

@router.post("/recipes", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    recipe: RecipeCreate,
    db: AsyncSession = Depends(get_db),
) -> RecipeRead:
    """Add an ingredient to a menu item's recipe."""
    from sqlalchemy import text
    
    recipe_id = uuid.uuid4()
    now = datetime.utcnow()
    
    # Get ingredient cost for calculation
    ing_query = text("SELECT current_cost_per_unit FROM ingredients WHERE id = :id")
    ing_result = await db.execute(ing_query, {"id": recipe.ingredient_id})
    ing = ing_result.mappings().first()
    
    if not ing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient {recipe.ingredient_id} not found",
        )
    
    calculated_cost = int(float(recipe.quantity) * float(recipe.waste_factor) * ing["current_cost_per_unit"])
    
    query = text("""
        INSERT INTO recipes (
            id, menu_item_id, ingredient_id, quantity, unit, waste_factor,
            calculated_cost, created_at, updated_at
        ) VALUES (
            :id, :menu_item_id, :ingredient_id, :quantity, :unit, :waste_factor,
            :calculated_cost, :created_at, :updated_at
        )
        RETURNING *
    """)
    
    result = await db.execute(query, {
        "id": recipe_id,
        "menu_item_id": recipe.menu_item_id,
        "ingredient_id": recipe.ingredient_id,
        "quantity": recipe.quantity,
        "unit": recipe.unit,
        "waste_factor": recipe.waste_factor,
        "calculated_cost": calculated_cost,
        "created_at": now,
        "updated_at": now,
    })
    
    row = result.mappings().first()
    await db.commit()
    
    return RecipeRead(
        id=row["id"],
        menu_item_id=row["menu_item_id"],
        ingredient_id=row["ingredient_id"],
        quantity=row["quantity"],
        unit=row["unit"],
        waste_factor=row["waste_factor"],
        calculated_cost_cents=row["calculated_cost"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# =============================================================================
# FOOD WASTE
# =============================================================================

@router.post("/waste", response_model=FoodWasteRead, status_code=status.HTTP_201_CREATED)
async def record_food_waste(
    waste: FoodWasteCreate,
    db: AsyncSession = Depends(get_db),
) -> FoodWasteRead:
    """
    Record a food waste event.
    
    Critical for:
    - Tracking shrinkage and loss
    - Identifying patterns (spoilage vs theft vs prep waste)
    - Insurance claims with ClaimsIQ
    """
    from sqlalchemy import text
    
    waste_id = uuid.uuid4()
    now = datetime.utcnow()
    today = date.today()
    
    query = text("""
        INSERT INTO food_waste (
            id, org_id, ingredient_id, menu_item_id, inventory_id,
            waste_type, waste_reason, quantity, unit, estimated_cost,
            photo_url, notes, recorded_by, waste_date, recorded_at
        ) VALUES (
            :id, :org_id, :ingredient_id, :menu_item_id, :inventory_id,
            :waste_type, :waste_reason, :quantity, :unit, :estimated_cost,
            :photo_url, :notes, :recorded_by, :waste_date, :recorded_at
        )
        RETURNING *
    """)
    
    result = await db.execute(query, {
        "id": waste_id,
        "org_id": waste.org_id,
        "ingredient_id": waste.ingredient_id,
        "menu_item_id": waste.menu_item_id,
        "inventory_id": waste.inventory_id,
        "waste_type": waste.waste_type.value,
        "waste_reason": waste.waste_reason.value,
        "quantity": waste.quantity,
        "unit": waste.unit,
        "estimated_cost": waste.estimated_cost_cents,
        "photo_url": waste.photo_url,
        "notes": waste.notes,
        "recorded_by": waste.recorded_by,
        "waste_date": today,
        "recorded_at": now,
    })
    
    row = result.mappings().first()
    await db.commit()
    
    return FoodWasteRead(
        id=row["id"],
        org_id=row["org_id"],
        ingredient_id=row["ingredient_id"],
        menu_item_id=row["menu_item_id"],
        inventory_id=row["inventory_id"],
        waste_type=row["waste_type"],
        waste_reason=row["waste_reason"],
        quantity=row["quantity"],
        unit=row["unit"],
        estimated_cost_cents=row["estimated_cost"],
        photo_url=row["photo_url"],
        notes=row["notes"],
        recorded_by=row["recorded_by"],
        waste_date=row["waste_date"],
        recorded_at=row["recorded_at"],
    )


@router.get("/waste/summary")
async def get_waste_summary(
    org_id: uuid.UUID,
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get waste summary for a date range.
    
    Returns breakdown by type, reason, and total cost.
    """
    from sqlalchemy import text
    
    query = text("""
        SELECT 
            waste_type,
            waste_reason,
            COUNT(*) as count,
            SUM(estimated_cost) as total_cost_cents,
            SUM(quantity) as total_quantity
        FROM food_waste
        WHERE org_id = :org_id
          AND waste_date >= :start_date
          AND waste_date <= :end_date
        GROUP BY waste_type, waste_reason
        ORDER BY total_cost_cents DESC
    """)
    
    result = await db.execute(query, {
        "org_id": org_id,
        "start_date": start_date,
        "end_date": end_date,
    })
    rows = result.mappings().all()
    
    total_cost = sum(r["total_cost_cents"] or 0 for r in rows)
    total_events = sum(r["count"] for r in rows)
    
    by_type = {}
    by_reason = {}
    
    for r in rows:
        wt = r["waste_type"]
        wr = r["waste_reason"]
        cost = r["total_cost_cents"] or 0
        
        by_type[wt] = by_type.get(wt, 0) + cost
        by_reason[wr] = by_reason.get(wr, 0) + cost
    
    return {
        "org_id": str(org_id),
        "period": {"start": str(start_date), "end": str(end_date)},
        "total_waste_events": total_events,
        "total_waste_cost_cents": total_cost,
        "by_type": by_type,
        "by_reason": by_reason,
        "details": [dict(r) for r in rows],
    }


# =============================================================================
# FOOD ORDERS
# =============================================================================

@router.post("/orders", response_model=FoodOrderRead, status_code=status.HTTP_201_CREATED)
async def create_food_order(
    order: FoodOrderCreate,
    db: AsyncSession = Depends(get_db),
) -> FoodOrderRead:
    """
    Create a food purchase order.
    
    Can be auto-generated by Bishop or manually created.
    """
    from sqlalchemy import text
    
    order_id = uuid.uuid4()
    now = datetime.utcnow()
    order_number = f"FO-{now.strftime('%Y%m%d')}-{str(order_id)[:8].upper()}"
    
    # Calculate totals
    subtotal = sum(
        int(float(item.quantity_ordered) * item.unit_price_cents)
        for item in order.items
    )
    
    # Create order
    order_query = text("""
        INSERT INTO food_orders (
            id, org_id, vendor_id, order_number, order_type, status,
            subtotal, tax, delivery_fee, total, order_date, expected_delivery,
            bishop_session_id, auto_generated, created_at, updated_at
        ) VALUES (
            :id, :org_id, :vendor_id, :order_number, :order_type, :status,
            :subtotal, :tax, :delivery_fee, :total, :order_date, :expected_delivery,
            :bishop_session_id, :auto_generated, :created_at, :updated_at
        )
        RETURNING *
    """)
    
    order_result = await db.execute(order_query, {
        "id": order_id,
        "org_id": order.org_id,
        "vendor_id": order.vendor_id,
        "order_number": order_number,
        "order_type": order.order_type.value,
        "status": FoodOrderStatus.DRAFT.value,
        "subtotal": subtotal,
        "tax": 0,
        "delivery_fee": 0,
        "total": subtotal,
        "order_date": now,
        "expected_delivery": order.expected_delivery,
        "bishop_session_id": order.bishop_session_id,
        "auto_generated": order.auto_generated,
        "created_at": now,
        "updated_at": now,
    })
    
    order_row = order_result.mappings().first()
    
    # Create order items
    items_created = []
    for item in order.items:
        item_id = uuid.uuid4()
        line_total = int(float(item.quantity_ordered) * item.unit_price_cents)
        
        item_query = text("""
            INSERT INTO food_order_items (
                id, order_id, ingredient_id, vendor_product_id, product_name,
                vendor_sku, quantity_ordered, unit, unit_price, line_total, created_at
            ) VALUES (
                :id, :order_id, :ingredient_id, :vendor_product_id, :product_name,
                :vendor_sku, :quantity_ordered, :unit, :unit_price, :line_total, :created_at
            )
            RETURNING *
        """)
        
        item_result = await db.execute(item_query, {
            "id": item_id,
            "order_id": order_id,
            "ingredient_id": item.ingredient_id,
            "vendor_product_id": item.vendor_product_id,
            "product_name": item.product_name,
            "vendor_sku": item.vendor_sku,
            "quantity_ordered": item.quantity_ordered,
            "unit": item.unit,
            "unit_price": item.unit_price_cents,
            "line_total": line_total,
            "created_at": now,
        })
        
        item_row = item_result.mappings().first()
        items_created.append(item_row)
    
    await db.commit()
    
    return FoodOrderRead(
        id=order_row["id"],
        org_id=order_row["org_id"],
        vendor_id=order_row["vendor_id"],
        order_number=order_row["order_number"],
        order_type=order_row["order_type"],
        status=order_row["status"],
        subtotal_cents=order_row["subtotal"],
        tax_cents=order_row["tax"],
        delivery_fee_cents=order_row["delivery_fee"],
        total_cents=order_row["total"],
        order_date=order_row["order_date"],
        expected_delivery=order_row["expected_delivery"],
        actual_delivery=order_row.get("actual_delivery"),
        bishop_session_id=order_row["bishop_session_id"],
        auto_generated=order_row["auto_generated"],
        approved_by=order_row.get("approved_by"),
        approved_at=order_row.get("approved_at"),
        created_at=order_row["created_at"],
        updated_at=order_row["updated_at"],
        items=[],  # Would need to map items
    )


@router.get("/orders", response_model=list[FoodOrderRead])
async def list_food_orders(
    org_id: uuid.UUID,
    status_filter: Optional[FoodOrderStatus] = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[FoodOrderRead]:
    """List food orders for an organization."""
    from sqlalchemy import text
    
    query_str = "SELECT * FROM food_orders WHERE org_id = :org_id"
    params = {"org_id": org_id}
    
    if status_filter:
        query_str += " AND status = :status"
        params["status"] = status_filter.value
    
    query_str += " ORDER BY created_at DESC LIMIT :limit"
    params["limit"] = limit
    
    result = await db.execute(text(query_str), params)
    rows = result.mappings().all()
    
    return [FoodOrderRead(
        id=r["id"],
        org_id=r["org_id"],
        vendor_id=r["vendor_id"],
        order_number=r["order_number"],
        order_type=r["order_type"],
        status=r["status"],
        subtotal_cents=r["subtotal"],
        tax_cents=r["tax"],
        delivery_fee_cents=r["delivery_fee"],
        total_cents=r["total"],
        order_date=r["order_date"],
        expected_delivery=r["expected_delivery"],
        actual_delivery=r.get("actual_delivery"),
        bishop_session_id=r["bishop_session_id"],
        auto_generated=r["auto_generated"],
        approved_by=r.get("approved_by"),
        approved_at=r.get("approved_at"),
        created_at=r["created_at"],
        updated_at=r["updated_at"],
        items=[],
    ) for r in rows]


@router.patch("/orders/{order_id}/approve")
async def approve_food_order(
    order_id: uuid.UUID,
    approved_by: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Approve a food order for submission to vendor."""
    from sqlalchemy import text
    
    now = datetime.utcnow()
    
    query = text("""
        UPDATE food_orders
        SET status = :status, approved_by = :approved_by, approved_at = :approved_at, updated_at = :updated_at
        WHERE id = :id AND status = 'draft'
        RETURNING *
    """)
    
    result = await db.execute(query, {
        "id": order_id,
        "status": FoodOrderStatus.APPROVED.value,
        "approved_by": approved_by,
        "approved_at": now,
        "updated_at": now,
    })
    
    row = result.mappings().first()
    await db.commit()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found or not in draft status",
        )
    
    return {
        "order_id": str(order_id),
        "status": FoodOrderStatus.APPROVED.value,
        "approved_by": str(approved_by),
        "approved_at": now.isoformat(),
        "message": "Order approved. Ready for submission to vendor.",
    }


# =============================================================================
# FOOD COST REPORTS
# =============================================================================

@router.get("/reports/food-cost")
async def get_food_cost_report(
    org_id: uuid.UUID,
    report_date: date,
    report_type: str = "daily",
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get food cost report for a specific date.
    
    Target: 28-35% food cost ratio.
    """
    from sqlalchemy import text
    
    query = text("""
        SELECT * FROM food_cost_reports
        WHERE org_id = :org_id AND report_date = :report_date AND report_type = :report_type
    """)
    
    result = await db.execute(query, {
        "org_id": org_id,
        "report_date": report_date,
        "report_type": report_type,
    })
    
    row = result.mappings().first()
    
    if not row:
        return {
            "org_id": str(org_id),
            "report_date": str(report_date),
            "report_type": report_type,
            "message": "No report found for this date. Report may not have been generated yet.",
            "data": None,
        }
    
    return {
        "id": str(row["id"]),
        "org_id": str(row["org_id"]),
        "report_date": str(row["report_date"]),
        "report_type": row["report_type"],
        "total_food_sales_cents": row["total_food_sales"],
        "beginning_inventory_value_cents": row["beginning_inventory_value"],
        "purchases_cents": row["purchases"],
        "ending_inventory_value_cents": row["ending_inventory_value"],
        "calculated_cogs_cents": row["calculated_cogs"],
        "total_waste_value_cents": row["total_waste_value"],
        "waste_by_type": row["waste_by_type"],
        "food_cost_percentage": float(row["food_cost_percentage"]) if row["food_cost_percentage"] else None,
        "target_food_cost_pct": float(row["target_food_cost_pct"]) if row["target_food_cost_pct"] else 30.0,
        "variance_from_target": float(row["variance_from_target"]) if row["variance_from_target"] else None,
        "alerts": row["alerts"],
        "generated_at": row["generated_at"].isoformat() if row["generated_at"] else None,
    }


# =============================================================================
# HELPER FUNCTIONS (raw SQL to avoid ORM complexity)
# =============================================================================

def select_ingredient_table():
    from sqlalchemy import text
    return text("SELECT * FROM ingredients")

def col_org_id():
    return "org_id"

def col_category():
    return "category"

def col_is_perishable():
    return "is_perishable"

def col_name():
    return "name"
