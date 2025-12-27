"""Food Management System - Cost, Waste, Vendors, Perishables

Revision ID: 008_food_management
Revises: 007_integrity_framework
Create Date: 2024-12-26

Restaurant success depends on:
- Food cost control (target 28-35% of revenue)
- Waste minimization
- Vendor management and price optimization
- Perishable inventory with FIFO enforcement
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '008_food_management'
down_revision: Union[str, None] = '007_integrity_framework'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # INGREDIENTS - Master ingredient catalog
    # =========================================================================
    op.create_table(
        'ingredients',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('subcategory', sa.String(100), nullable=True),
        
        # Unit of measure
        sa.Column('base_unit', sa.String(20), nullable=False),  # lb, oz, each, case, gal
        sa.Column('purchase_unit', sa.String(20), nullable=False),
        sa.Column('purchase_to_base_ratio', sa.Numeric(10, 4), nullable=False, default=1),
        
        # Current cost tracking
        sa.Column('current_cost_per_unit', sa.BigInteger(), nullable=False),  # cents
        sa.Column('cost_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('avg_cost_30d', sa.BigInteger(), nullable=True),
        sa.Column('avg_cost_90d', sa.BigInteger(), nullable=True),
        
        # Perishable info
        sa.Column('is_perishable', sa.Boolean(), default=True),
        sa.Column('shelf_life_days', sa.Integer(), nullable=True),
        sa.Column('requires_refrigeration', sa.Boolean(), default=False),
        sa.Column('requires_freezer', sa.Boolean(), default=False),
        
        # Par levels
        sa.Column('par_level', sa.Numeric(10, 2), nullable=True),
        sa.Column('reorder_point', sa.Numeric(10, 2), nullable=True),
        sa.Column('min_order_qty', sa.Numeric(10, 2), nullable=True),
        
        # Preferred vendor
        sa.Column('preferred_vendor_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        sa.Column('status', sa.String(20), nullable=False, default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        
        sa.CheckConstraint("category IN ('protein', 'produce', 'dairy', 'dry_goods', 'beverages', 'frozen', 'bakery', 'condiments', 'supplies')",
                          name='ingredient_category_valid'),
        sa.CheckConstraint("status IN ('active', 'inactive', 'discontinued')", name='ingredient_status_valid'),
    )
    
    op.create_index('idx_ingredients_org', 'ingredients', ['org_id'])
    op.create_index('idx_ingredients_category', 'ingredients', ['category'])
    op.create_index('idx_ingredients_name', 'ingredients', ['org_id', 'name'])

    # =========================================================================
    # INGREDIENT_COSTS - Historical cost tracking
    # =========================================================================
    op.create_table(
        'ingredient_costs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Cost data
        sa.Column('cost_per_unit', sa.BigInteger(), nullable=False),  # cents
        sa.Column('unit', sa.String(20), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        
        # Source
        sa.Column('source', sa.String(50), nullable=False),  # invoice, quote, manual, vendor_sync
        sa.Column('invoice_id', sa.String(100), nullable=True),
        
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        
        sa.CheckConstraint("source IN ('invoice', 'quote', 'manual', 'vendor_sync', 'delivery')", name='cost_source_valid'),
    )
    
    op.create_index('idx_ingredient_costs_ingredient', 'ingredient_costs', ['ingredient_id'])
    op.create_index('idx_ingredient_costs_date', 'ingredient_costs', ['effective_date'])
    op.create_index('idx_ingredient_costs_vendor', 'ingredient_costs', ['vendor_id'])

    # =========================================================================
    # MENU_ITEMS - Menu items with recipe costing
    # =========================================================================
    op.create_table(
        'menu_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('subcategory', sa.String(100), nullable=True),
        
        # Pricing
        sa.Column('menu_price', sa.BigInteger(), nullable=False),  # cents
        sa.Column('calculated_food_cost', sa.BigInteger(), nullable=True),  # cents
        sa.Column('food_cost_percentage', sa.Numeric(5, 2), nullable=True),
        sa.Column('target_food_cost_pct', sa.Numeric(5, 2), nullable=True, default=30),
        
        # Sales data
        sa.Column('avg_daily_sales', sa.Numeric(10, 2), nullable=True),
        sa.Column('last_sold_at', sa.DateTime(timezone=True), nullable=True),
        
        # Status
        sa.Column('status', sa.String(20), nullable=False, default='active'),
        sa.Column('is_seasonal', sa.Boolean(), default=False),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        
        sa.CheckConstraint("status IN ('active', 'inactive', 'seasonal', '86d')", name='menu_item_status_valid'),
    )
    
    op.create_index('idx_menu_items_org', 'menu_items', ['org_id'])
    op.create_index('idx_menu_items_category', 'menu_items', ['category'])

    # =========================================================================
    # RECIPES - Menu item ingredients (bill of materials)
    # =========================================================================
    op.create_table(
        'recipes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), nullable=False),
        
        # Quantity
        sa.Column('quantity', sa.Numeric(10, 4), nullable=False),
        sa.Column('unit', sa.String(20), nullable=False),
        sa.Column('waste_factor', sa.Numeric(5, 4), nullable=False, default=1.0),  # 1.1 = 10% waste
        
        # Calculated cost
        sa.Column('calculated_cost', sa.BigInteger(), nullable=True),  # cents
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        
        sa.UniqueConstraint('menu_item_id', 'ingredient_id', name='recipe_unique'),
    )
    
    op.create_index('idx_recipes_menu_item', 'recipes', ['menu_item_id'])
    op.create_index('idx_recipes_ingredient', 'recipes', ['ingredient_id'])

    # =========================================================================
    # FOOD_INVENTORY - Current inventory with expiration tracking
    # =========================================================================
    op.create_table(
        'food_inventory',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), nullable=False),
        
        # Quantity
        sa.Column('quantity_on_hand', sa.Numeric(10, 4), nullable=False),
        sa.Column('unit', sa.String(20), nullable=False),
        
        # Lot tracking (FIFO)
        sa.Column('lot_number', sa.String(100), nullable=True),
        sa.Column('received_date', sa.Date(), nullable=False),
        sa.Column('expiration_date', sa.Date(), nullable=True),
        sa.Column('days_until_expiration', sa.Integer(), nullable=True),
        
        # Cost at receipt
        sa.Column('unit_cost_at_receipt', sa.BigInteger(), nullable=False),  # cents
        sa.Column('total_value', sa.BigInteger(), nullable=False),  # cents
        
        # Storage
        sa.Column('storage_location', sa.String(100), nullable=True),  # walk-in, freezer, dry storage
        
        # Status
        sa.Column('status', sa.String(20), nullable=False, default='available'),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        
        sa.CheckConstraint("status IN ('available', 'reserved', 'expired', 'wasted', 'consumed')", name='inventory_status_valid'),
    )
    
    op.create_index('idx_food_inventory_org', 'food_inventory', ['org_id'])
    op.create_index('idx_food_inventory_ingredient', 'food_inventory', ['ingredient_id'])
    op.create_index('idx_food_inventory_expiration', 'food_inventory', ['expiration_date'])
    op.create_index('idx_food_inventory_status', 'food_inventory', ['status'])

    # =========================================================================
    # FOOD_WASTE - Waste tracking with categorization
    # =========================================================================
    op.create_table(
        'food_waste',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('inventory_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Waste details
        sa.Column('waste_type', sa.String(50), nullable=False),
        sa.Column('waste_reason', sa.String(100), nullable=False),
        sa.Column('quantity', sa.Numeric(10, 4), nullable=False),
        sa.Column('unit', sa.String(20), nullable=False),
        
        # Value
        sa.Column('estimated_cost', sa.BigInteger(), nullable=False),  # cents
        
        # Evidence
        sa.Column('photo_url', sa.String(500), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('recorded_by', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Timestamps
        sa.Column('waste_date', sa.Date(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        
        sa.CheckConstraint(
            "waste_type IN ('spoilage', 'expired', 'prep_waste', 'cooking_error', 'customer_return', 'overproduction', 'damaged', 'theft', 'unknown')",
            name='waste_type_valid'
        ),
        sa.CheckConstraint(
            "waste_reason IN ('past_expiration', 'temperature_abuse', 'improper_storage', 'over_prep', 'dropped', 'burnt', 'wrong_order', 'quality_issue', 'inventory_shrink', 'spillage', 'other')",
            name='waste_reason_valid'
        ),
    )
    
    op.create_index('idx_food_waste_org', 'food_waste', ['org_id'])
    op.create_index('idx_food_waste_date', 'food_waste', ['waste_date'])
    op.create_index('idx_food_waste_type', 'food_waste', ['waste_type'])
    op.create_index('idx_food_waste_ingredient', 'food_waste', ['ingredient_id'])

    # =========================================================================
    # INGREDIENT_VENDOR_PRODUCTS - Vendor-specific ingredient catalog
    # (Named to avoid conflict with vendor_products in 002_inventory_orders)
    # =========================================================================
    op.create_table(
        'ingredient_vendor_products',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Vendor product info
        sa.Column('vendor_sku', sa.String(100), nullable=False),
        sa.Column('vendor_product_name', sa.String(255), nullable=False),
        sa.Column('vendor_category', sa.String(100), nullable=True),
        
        # Pricing
        sa.Column('current_price', sa.BigInteger(), nullable=False),  # cents
        sa.Column('price_per_unit', sa.BigInteger(), nullable=False),  # cents per base unit
        sa.Column('pack_size', sa.String(50), nullable=True),
        sa.Column('unit', sa.String(20), nullable=False),
        
        # Availability
        sa.Column('is_available', sa.Boolean(), default=True),
        sa.Column('lead_time_days', sa.Integer(), nullable=True),
        sa.Column('min_order_qty', sa.Numeric(10, 2), nullable=True),
        
        # Last sync
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        
        sa.UniqueConstraint('vendor_id', 'vendor_sku', name='ingredient_vendor_product_unique'),
    )
    
    op.create_index('idx_ivp_vendor', 'ingredient_vendor_products', ['vendor_id'])
    op.create_index('idx_ivp_ingredient', 'ingredient_vendor_products', ['ingredient_id'])
    op.create_index('idx_ivp_sku', 'ingredient_vendor_products', ['vendor_sku'])

    # =========================================================================
    # FOOD_ORDERS - Purchase orders for food
    # =========================================================================
    op.create_table(
        'food_orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('order_number', sa.String(100), nullable=False),
        
        # Order details
        sa.Column('order_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, default='draft'),
        
        # Totals
        sa.Column('subtotal', sa.BigInteger(), nullable=False, default=0),  # cents
        sa.Column('tax', sa.BigInteger(), nullable=False, default=0),
        sa.Column('delivery_fee', sa.BigInteger(), nullable=False, default=0),
        sa.Column('total', sa.BigInteger(), nullable=False, default=0),
        
        # Dates
        sa.Column('order_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expected_delivery', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_delivery', sa.DateTime(timezone=True), nullable=True),
        
        # Bishop integration
        sa.Column('bishop_session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('auto_generated', sa.Boolean(), default=False),
        
        # Approval
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        
        sa.CheckConstraint("order_type IN ('regular', 'emergency', 'standing', 'special')", name='order_type_valid'),
        sa.CheckConstraint("status IN ('draft', 'pending_approval', 'approved', 'submitted', 'confirmed', 'shipped', 'delivered', 'cancelled', 'partial')", name='order_status_valid'),
    )
    
    op.create_index('idx_food_orders_org', 'food_orders', ['org_id'])
    op.create_index('idx_food_orders_vendor', 'food_orders', ['vendor_id'])
    op.create_index('idx_food_orders_status', 'food_orders', ['status'])
    op.create_index('idx_food_orders_date', 'food_orders', ['order_date'])

    # =========================================================================
    # FOOD_ORDER_ITEMS - Line items on purchase orders
    # =========================================================================
    op.create_table(
        'food_order_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('vendor_product_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Item details
        sa.Column('product_name', sa.String(255), nullable=False),
        sa.Column('vendor_sku', sa.String(100), nullable=True),
        sa.Column('quantity_ordered', sa.Numeric(10, 4), nullable=False),
        sa.Column('quantity_received', sa.Numeric(10, 4), nullable=True),
        sa.Column('unit', sa.String(20), nullable=False),
        
        # Pricing
        sa.Column('unit_price', sa.BigInteger(), nullable=False),  # cents
        sa.Column('line_total', sa.BigInteger(), nullable=False),  # cents
        
        # Receiving
        sa.Column('received_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('received_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('receiving_notes', sa.Text(), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    op.create_index('idx_food_order_items_order', 'food_order_items', ['order_id'])
    op.create_index('idx_food_order_items_ingredient', 'food_order_items', ['ingredient_id'])

    # =========================================================================
    # FOOD_COST_REPORTS - Daily/weekly food cost summaries
    # =========================================================================
    op.create_table(
        'food_cost_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_date', sa.Date(), nullable=False),
        sa.Column('report_type', sa.String(20), nullable=False),  # daily, weekly, monthly
        
        # Revenue (from POS integration)
        sa.Column('total_food_sales', sa.BigInteger(), nullable=True),  # cents
        
        # Costs
        sa.Column('beginning_inventory_value', sa.BigInteger(), nullable=True),
        sa.Column('purchases', sa.BigInteger(), nullable=True),
        sa.Column('ending_inventory_value', sa.BigInteger(), nullable=True),
        sa.Column('calculated_cogs', sa.BigInteger(), nullable=True),  # cost of goods sold
        
        # Waste
        sa.Column('total_waste_value', sa.BigInteger(), nullable=True),
        sa.Column('waste_by_type', postgresql.JSONB, nullable=True),
        
        # Metrics
        sa.Column('food_cost_percentage', sa.Numeric(5, 2), nullable=True),
        sa.Column('target_food_cost_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('variance_from_target', sa.Numeric(5, 2), nullable=True),
        
        # Alerts
        sa.Column('alerts', postgresql.JSONB, nullable=True),
        
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        
        sa.UniqueConstraint('org_id', 'report_date', 'report_type', name='food_cost_report_unique'),
        sa.CheckConstraint("report_type IN ('daily', 'weekly', 'monthly')", name='report_type_valid'),
    )
    
    op.create_index('idx_food_cost_reports_org', 'food_cost_reports', ['org_id'])
    op.create_index('idx_food_cost_reports_date', 'food_cost_reports', ['report_date'])


def downgrade() -> None:
    op.drop_table('food_cost_reports')
    op.drop_table('food_order_items')
    op.drop_table('food_orders')
    op.drop_table('ingredient_vendor_products')
    op.drop_table('food_waste')
    op.drop_table('food_inventory')
    op.drop_table('recipes')
    op.drop_table('menu_items')
    op.drop_table('ingredient_costs')
    op.drop_table('ingredients')
