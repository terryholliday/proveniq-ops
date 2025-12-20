"""Inventory & Orders Tables

Revision ID: 002_inventory
Revises: 001_bishop
Create Date: 2024-12-20

Implements:
- Vendors table
- Products table  
- Vendor-Product mappings
- Inventory snapshots
- Orders and order items
- Consumption events
- Usage statistics
- Vendor lead times
- Stockout alerts
- Bishop state log
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '002_inventory'
down_revision: Union[str, None] = '001_bishop'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Vendors table
    op.create_table(
        'vendors',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('api_endpoint', sa.String(512), nullable=True),
        sa.Column('priority_level', sa.Integer(), nullable=False, default=1),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint('priority_level > 0', name='vendors_priority_positive'),
    )
    op.create_index('idx_vendors_priority', 'vendors', ['priority_level'], postgresql_where=sa.text('is_active = true'))

    # Products table
    op.create_table(
        'products',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('barcode', sa.String(100), unique=True, nullable=True),
        sa.Column('par_level', sa.Integer(), nullable=False, default=0),
        sa.Column('risk_category', sa.String(50), nullable=False, default='standard'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint('par_level >= 0', name='products_par_non_negative'),
        sa.CheckConstraint("risk_category IN ('standard', 'perishable', 'hazardous', 'controlled')", 
                          name='products_risk_valid'),
    )
    op.create_index('idx_products_barcode', 'products', ['barcode'], postgresql_where=sa.text('barcode IS NOT NULL'))
    op.create_index('idx_products_risk', 'products', ['risk_category'])

    # Vendor Products table (SKU mapping)
    op.create_table(
        'vendor_products',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vendor_sku', sa.String(100), nullable=False),
        sa.Column('current_price', sa.Numeric(12, 4), nullable=False),
        sa.Column('stock_available', sa.Integer(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint('current_price > 0', name='vendor_products_price_positive'),
        sa.CheckConstraint('stock_available IS NULL OR stock_available >= 0', 
                          name='vendor_products_stock_non_negative'),
        sa.UniqueConstraint('vendor_id', 'product_id'),
        sa.UniqueConstraint('vendor_id', 'vendor_sku'),
    )
    op.create_index('idx_vendor_products_vendor', 'vendor_products', ['vendor_id'])
    op.create_index('idx_vendor_products_product', 'vendor_products', ['product_id'])

    # Inventory Snapshots table
    op.create_table(
        'inventory_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('product_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('confidence_score', sa.Numeric(5, 4), nullable=True),
        sa.Column('scanned_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('scanned_by', sa.String(100), nullable=False, default='bishop'),
        sa.Column('scan_method', sa.String(50), nullable=False, default='manual'),
        sa.Column('location_tag', sa.String(255), nullable=True),
        sa.CheckConstraint('quantity >= 0', name='snapshots_quantity_non_negative'),
        sa.CheckConstraint('confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)',
                          name='snapshots_confidence_range'),
        sa.CheckConstraint("scan_method IN ('manual', 'barcode', 'silhouette', 'volumetric')",
                          name='snapshots_method_valid'),
    )
    op.create_index('idx_snapshots_product', 'inventory_snapshots', ['product_id'])
    op.create_index('idx_snapshots_scanned_at', 'inventory_snapshots', ['scanned_at'])
    op.create_index('idx_snapshots_scanned_by', 'inventory_snapshots', ['scanned_by'])

    # Orders table
    op.create_table(
        'orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('vendors.id'), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, default='queued'),
        sa.Column('total_amount', sa.Numeric(12, 4), nullable=True),
        sa.Column('blocked_reason', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('queued', 'submitted', 'confirmed', 'delivered', 'cancelled', 'blocked')",
                          name='orders_status_valid'),
    )
    op.create_index('idx_orders_status', 'orders', ['status'])
    op.create_index('idx_orders_vendor', 'orders', ['vendor_id'])

    # Order Items table
    op.create_table(
        'order_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('order_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('products.id'), nullable=False),
        sa.Column('vendor_product_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('vendor_products.id'), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(12, 4), nullable=False),
        sa.CheckConstraint('quantity > 0', name='order_items_quantity_positive'),
    )
    op.create_index('idx_order_items_order', 'order_items', ['order_id'])

    # Consumption Events table
    op.create_table(
        'consumption_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('product_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('qty_delta', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False, default='consumption'),
        sa.Column('location_id', sa.String(100), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('recorded_by', sa.String(100), nullable=False, default='bishop'),
        sa.CheckConstraint("event_type IN ('consumption', 'receiving', 'adjustment', 'transfer', 'spoilage')",
                          name='consumption_event_type_valid'),
    )
    op.create_index('idx_consumption_product', 'consumption_events', ['product_id'])
    op.create_index('idx_consumption_recorded', 'consumption_events', ['recorded_at'])
    op.create_index('idx_consumption_type', 'consumption_events', ['event_type'])

    # Usage Statistics table
    op.create_table(
        'usage_statistics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('product_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('avg_daily_burn_7d', sa.Numeric(12, 4), nullable=False, default=0),
        sa.Column('avg_daily_burn_30d', sa.Numeric(12, 4), nullable=False, default=0),
        sa.Column('avg_daily_burn_90d', sa.Numeric(12, 4), nullable=False, default=0),
        sa.Column('variance_coefficient', sa.Numeric(8, 4), nullable=False, default=0),
        sa.Column('last_calculated', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_usage_product', 'usage_statistics', ['product_id'])

    # Vendor Lead Times table
    op.create_table(
        'vendor_lead_times',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('product_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('avg_lead_time_hours', sa.Integer(), nullable=False, default=48),
        sa.Column('reliability_score', sa.Numeric(5, 4), nullable=False, default=1.0),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('product_id', 'vendor_id'),
        sa.CheckConstraint('avg_lead_time_hours >= 0', name='lead_time_non_negative'),
        sa.CheckConstraint('reliability_score >= 0 AND reliability_score <= 1', name='reliability_score_range'),
    )
    op.create_index('idx_lead_time_product', 'vendor_lead_times', ['product_id'])
    op.create_index('idx_lead_time_vendor', 'vendor_lead_times', ['vendor_id'])

    # Stockout Alerts table
    op.create_table(
        'stockout_alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('product_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('alert_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('projected_hours_to_stockout', sa.Numeric(10, 2), nullable=False),
        sa.Column('confidence', sa.Numeric(5, 4), nullable=False),
        sa.Column('recommended_vendor_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('vendors.id'), nullable=True),
        sa.Column('recommended_qty', sa.Integer(), nullable=True),
        sa.Column('estimated_cost', sa.Numeric(12, 4), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.String(100), nullable=True),
        sa.CheckConstraint("alert_type IN ('PREDICTIVE_STOCKOUT', 'WARNING', 'CRITICAL')",
                          name='alert_type_valid'),
        sa.CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')",
                          name='alert_severity_valid'),
        sa.CheckConstraint("status IN ('active', 'acknowledged', 'resolved', 'expired')",
                          name='alert_status_valid'),
    )
    op.create_index('idx_stockout_product', 'stockout_alerts', ['product_id'])
    op.create_index('idx_stockout_status', 'stockout_alerts', ['status'])
    op.create_index('idx_stockout_severity', 'stockout_alerts', ['severity'])
    op.create_index('idx_stockout_created', 'stockout_alerts', ['created_at'])

    # Bishop State Log table
    op.create_table(
        'bishop_state_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('previous_state', sa.String(50), nullable=True),
        sa.Column('current_state', sa.String(50), nullable=False),
        sa.Column('trigger_event', sa.String(100), nullable=False),
        sa.Column('context_data', postgresql.JSONB, nullable=True),
        sa.Column('output_message', sa.Text(), nullable=True),
        sa.Column('logged_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("current_state IN ('IDLE', 'SCANNING', 'ANALYZING_RISK', 'CHECKING_FUNDS', 'ORDER_QUEUED')",
                          name='bishop_state_valid'),
    )
    op.create_index('idx_bishop_log_state', 'bishop_state_log', ['current_state'])
    op.create_index('idx_bishop_log_time', 'bishop_state_log', ['logged_at'])


def downgrade() -> None:
    op.drop_table('bishop_state_log')
    op.drop_table('stockout_alerts')
    op.drop_table('vendor_lead_times')
    op.drop_table('usage_statistics')
    op.drop_table('consumption_events')
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_table('inventory_snapshots')
    op.drop_table('vendor_products')
    op.drop_table('products')
    op.drop_table('vendors')
