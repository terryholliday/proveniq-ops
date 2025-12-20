"""BISHOP Module - Restaurant/Retail Inventory

Revision ID: 003_bishop
Revises: 002_spec_v1_1
Create Date: 2024-12-19

Implements:
- BISHOP locations (restaurants, retail, warehouses)
- Shelves and inventory items
- AI-powered shelf scans
- Shrinkage tracking and reporting
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_bishop'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table first (required for FKs)
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('firebase_uid', sa.String(128), unique=True, nullable=False, index=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('role', sa.String(50), nullable=False, default='operator'),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create ENUM types
    op.execute("""
        CREATE TYPE bishop_location_type AS ENUM ('RESTAURANT', 'RETAIL', 'WAREHOUSE', 'KITCHEN')
    """)
    op.execute("""
        CREATE TYPE bishop_scan_status AS ENUM (
            'IDLE', 'SCANNING', 'ANALYZING_RISK', 'CHECKING_FUNDS', 
            'ORDER_QUEUED', 'COMPLETED', 'FAILED'
        )
    """)
    op.execute("""
        CREATE TYPE shrinkage_type AS ENUM (
            'THEFT', 'SPOILAGE', 'DAMAGE', 'ADMIN_ERROR', 'VENDOR_ERROR', 'UNKNOWN'
        )
    """)

    # BISHOP Locations table
    op.create_table(
        'bishop_locations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('location_type', postgresql.ENUM(
            'RESTAURANT', 'RETAIL', 'WAREHOUSE', 'KITCHEN',
            name='bishop_location_type', create_type=False
        ), nullable=False, default='RESTAURANT'),
        sa.Column('address', sa.String(500), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(50), nullable=True),
        sa.Column('zip_code', sa.String(20), nullable=True),
        sa.Column('vendor_config', postgresql.JSONB, nullable=True),
        sa.Column('daily_order_limit', sa.Float(), nullable=True),
        sa.Column('auto_order_enabled', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # BISHOP Shelves table
    op.create_table(
        'bishop_shelves',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('location_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('bishop_locations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('shelf_code', sa.String(50), nullable=True),
        sa.Column('zone', sa.String(100), nullable=True),
        sa.Column('expected_inventory', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
    )

    # BISHOP Items table
    op.create_table(
        'bishop_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('shelf_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('bishop_shelves.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('sku', sa.String(100), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('quantity_on_hand', sa.Integer(), default=0),
        sa.Column('quantity_unit', sa.String(50), nullable=True),
        sa.Column('par_level', sa.Integer(), nullable=True),
        sa.Column('reorder_point', sa.Integer(), nullable=True),
        sa.Column('vendor_sku', sa.String(100), nullable=True),
        sa.Column('vendor_name', sa.String(255), nullable=True),
        sa.Column('unit_cost', sa.Float(), nullable=True),
        sa.Column('is_perishable', sa.Boolean(), default=False),
        sa.Column('shelf_life_days', sa.Integer(), nullable=True),
        sa.Column('last_scanned_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # BISHOP Scans table
    op.create_table(
        'bishop_scans',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('location_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('bishop_locations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('shelf_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('bishop_shelves.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('scanned_by_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', postgresql.ENUM(
            'IDLE', 'SCANNING', 'ANALYZING_RISK', 'CHECKING_FUNDS',
            'ORDER_QUEUED', 'COMPLETED', 'FAILED',
            name='bishop_scan_status', create_type=False
        ), nullable=False, default='IDLE'),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('image_hash', sa.String(128), nullable=True),
        sa.Column('ai_detected_items', postgresql.JSONB, nullable=True),
        sa.Column('discrepancies', postgresql.JSONB, nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('suggested_order', postgresql.JSONB, nullable=True),
        sa.Column('order_total', sa.Float(), nullable=True),
        sa.Column('order_approved', sa.Boolean(), nullable=True),
        sa.Column('order_approved_by_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('started_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )

    # Shrinkage Events table
    op.create_table(
        'shrinkage_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('location_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('bishop_locations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('item_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('bishop_items.id', ondelete='SET NULL'), nullable=True),
        sa.Column('scan_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('bishop_scans.id', ondelete='SET NULL'), nullable=True),
        sa.Column('shrinkage_type', postgresql.ENUM(
            'THEFT', 'SPOILAGE', 'DAMAGE', 'ADMIN_ERROR', 'VENDOR_ERROR', 'UNKNOWN',
            name='shrinkage_type', create_type=False
        ), nullable=False, default='UNKNOWN'),
        sa.Column('sku', sa.String(100), nullable=True),
        sa.Column('item_name', sa.String(255), nullable=True),
        sa.Column('quantity_lost', sa.Integer(), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=True),
        sa.Column('total_loss_value', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('evidence_url', sa.String(500), nullable=True),
        sa.Column('detected_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('resolved', sa.Boolean(), default=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
    )

    # Add relationship column to users for bishop_locations
    # (The relationship is already defined via owner_id FK above)

    # Create indexes for common queries
    op.create_index('ix_bishop_scans_status', 'bishop_scans', ['status'])
    op.create_index('ix_shrinkage_events_type', 'shrinkage_events', ['shrinkage_type'])
    op.create_index('ix_shrinkage_events_detected', 'shrinkage_events', ['detected_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_shrinkage_events_detected', 'shrinkage_events')
    op.drop_index('ix_shrinkage_events_type', 'shrinkage_events')
    op.drop_index('ix_bishop_scans_status', 'bishop_scans')

    # Drop tables in reverse order
    op.drop_table('shrinkage_events')
    op.drop_table('bishop_scans')
    op.drop_table('bishop_items')
    op.drop_table('bishop_shelves')
    op.drop_table('bishop_locations')

    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS shrinkage_type")
    op.execute("DROP TYPE IF EXISTS bishop_scan_status")
    op.execute("DROP TYPE IF EXISTS bishop_location_type")

    # Drop users table
    op.drop_table('users')
