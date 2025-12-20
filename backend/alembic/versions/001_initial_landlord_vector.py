"""Initial Landlord Vector schema

Revision ID: 001_initial
Revises: 
Create Date: 2024-12-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ENUM types
    op.execute("CREATE TYPE unitstatus AS ENUM ('VACANT', 'OCCUPIED')")
    op.execute("CREATE TYPE inspectiontype AS ENUM ('MOVE_IN', 'MOVE_OUT')")
    op.execute("CREATE TYPE inspectionstatus AS ENUM ('DRAFT', 'SUBMITTED', 'REVIEWED')")
    op.execute("CREATE TYPE itemcondition AS ENUM ('GOOD', 'FAIR', 'DAMAGED', 'MISSING')")
    op.execute("CREATE TYPE maintenancepriority AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'EMERGENCY')")
    op.execute("CREATE TYPE maintenancestatus AS ENUM ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CANCELLED')")
    
    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=True),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_verified', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Properties table
    op.create_table(
        'properties',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('landlord_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('address', sa.String(500), nullable=False),
        sa.Column('city', sa.String(100), nullable=False),
        sa.Column('state', sa.String(50), nullable=False),
        sa.Column('zip_code', sa.String(20), nullable=False),
        sa.Column('default_checklist', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Units table
    op.create_table(
        'units',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('property_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('properties.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('unit_number', sa.String(50), nullable=False),
        sa.Column('status', postgresql.ENUM('VACANT', 'OCCUPIED', name='unitstatus', create_type=False), default='VACANT', nullable=False),
        sa.Column('bedrooms', sa.Integer(), nullable=True),
        sa.Column('bathrooms', sa.Float(), nullable=True),
        sa.Column('square_feet', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
    )
    
    # Inventory Items table
    op.create_table(
        'inventory_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('units.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('brand', sa.String(100), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('serial_number', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('purchase_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('current_value', sa.Numeric(12, 2), nullable=True),
        sa.Column('purchase_date', sa.Date(), nullable=True),
        sa.Column('warranty_expiry', sa.Date(), nullable=True),
        sa.Column('warranty_document_url', sa.String(500), nullable=True),
        sa.Column('photo_urls', postgresql.JSONB(), nullable=True),
        sa.Column('documents', postgresql.JSONB(), nullable=True),
        sa.Column('ai_metadata', postgresql.JSONB(), nullable=True),
        sa.Column('room', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Leases table
    op.create_table(
        'leases',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('units.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('active', sa.Boolean(), default=True),
        sa.Column('security_deposit_amount', sa.Integer(), nullable=True),
        sa.Column('security_deposit_status', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Inspections table
    op.create_table(
        'inspections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('lease_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('leases.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('type', postgresql.ENUM('MOVE_IN', 'MOVE_OUT', name='inspectiontype', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('DRAFT', 'SUBMITTED', 'REVIEWED', name='inspectionstatus', create_type=False), default='DRAFT', nullable=False),
        sa.Column('signed_at', sa.DateTime(), nullable=True),
        sa.Column('signature_hash', sa.String(255), nullable=True),
        sa.Column('checklists', postgresql.JSONB(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Inspection Items table
    op.create_table(
        'inspection_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('inspection_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inspections.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory_items.id', ondelete='SET NULL'), nullable=True),
        sa.Column('room_name', sa.String(100), nullable=False),
        sa.Column('item_name', sa.String(255), nullable=True),
        sa.Column('condition', postgresql.ENUM('GOOD', 'FAIR', 'DAMAGED', 'MISSING', name='itemcondition', create_type=False), default='GOOD', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('photo_urls', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
    )
    
    # Maintenance Requests table
    op.create_table(
        'maintenance_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('units.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory_items.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('priority', postgresql.ENUM('LOW', 'MEDIUM', 'HIGH', 'EMERGENCY', name='maintenancepriority', create_type=False), default='MEDIUM', nullable=False),
        sa.Column('status', postgresql.ENUM('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CANCELLED', name='maintenancestatus', create_type=False), default='OPEN', nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create indexes
    op.create_index('ix_properties_landlord_address', 'properties', ['landlord_id', 'address'])
    op.create_index('ix_units_property_number', 'units', ['property_id', 'unit_number'])
    op.create_index('ix_leases_active', 'leases', ['tenant_id', 'active'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('maintenance_requests')
    op.drop_table('inspection_items')
    op.drop_table('inspections')
    op.drop_table('leases')
    op.drop_table('inventory_items')
    op.drop_table('units')
    op.drop_table('properties')
    op.drop_table('users')
    
    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS maintenancestatus")
    op.execute("DROP TYPE IF EXISTS maintenancepriority")
    op.execute("DROP TYPE IF EXISTS itemcondition")
    op.execute("DROP TYPE IF EXISTS inspectionstatus")
    op.execute("DROP TYPE IF EXISTS inspectiontype")
    op.execute("DROP TYPE IF EXISTS unitstatus")
