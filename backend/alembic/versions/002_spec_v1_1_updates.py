"""Spec v1.1 updates - Auth, Evidence, Hash

Revision ID: 002_spec_v1_1
Revises: 001_initial
Create Date: 2024-12-19

Implements:
- Organizations table
- Updated lease statuses
- Updated inspection statuses with schema_version
- Inspection evidence table
- Magic tokens table
- Content hash support
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '002_spec_v1_1'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create new ENUM types
    op.execute("CREATE TYPE lease_status AS ENUM ('draft', 'pending', 'active', 'terminating', 'ended', 'disputed')")
    op.execute("ALTER TYPE inspectionstatus ADD VALUE IF NOT EXISTS 'signed'")
    op.execute("ALTER TYPE inspectionstatus ADD VALUE IF NOT EXISTS 'archived'")
    op.execute("ALTER TYPE inspectiontype ADD VALUE IF NOT EXISTS 'PERIODIC'")
    
    # Organizations table
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
    )
    
    # Add organization_id to users
    op.add_column('users', sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('users', sa.Column('firebase_uid', sa.String(128), nullable=True, unique=True))
    op.add_column('users', sa.Column('role', sa.String(50), nullable=True))
    op.create_foreign_key('fk_users_organization', 'users', 'organizations', ['organization_id'], ['id'])
    op.create_index('ix_users_firebase_uid', 'users', ['firebase_uid'])
    op.create_index('ix_users_organization', 'users', ['organization_id'])
    
    # Add organization_id to properties
    op.add_column('properties', sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_properties_organization', 'properties', 'organizations', ['organization_id'], ['id'])
    op.create_index('ix_properties_organization', 'properties', ['organization_id'])
    
    # Update leases table
    op.add_column('leases', sa.Column('status_new', postgresql.ENUM(
        'draft', 'pending', 'active', 'terminating', 'ended', 'disputed',
        name='lease_status', create_type=False
    ), nullable=True, default='draft'))
    op.add_column('leases', sa.Column('magic_token', sa.String(255), nullable=True, unique=True))
    op.add_column('leases', sa.Column('magic_token_expires_at', sa.DateTime(), nullable=True))
    
    # Migrate active boolean to status_new
    op.execute("""
        UPDATE leases 
        SET status_new = CASE 
            WHEN active = true THEN 'active'::lease_status
            ELSE 'ended'::lease_status
        END
    """)
    
    # Update inspections table
    op.add_column('inspections', sa.Column('schema_version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('inspections', sa.Column('supplemental_to_inspection_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('inspections', sa.Column('content_hash', sa.String(64), nullable=True))
    op.add_column('inspections', sa.Column('submitted_at', sa.DateTime(), nullable=True))
    op.create_foreign_key(
        'fk_inspections_supplemental', 'inspections', 'inspections',
        ['supplemental_to_inspection_id'], ['id']
    )
    
    # Inspection evidence table
    op.create_table(
        'inspection_evidence',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('inspection_item_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('inspection_items.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('storage_url', sa.String(500), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
    )
    
    # Magic tokens table
    op.create_table(
        'magic_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('lease_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('leases.id'), nullable=False, index=True),
        sa.Column('token', sa.String(255), nullable=False, unique=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
    )
    
    # Create indexes
    op.create_index('ix_leases_status', 'leases', ['status_new'])
    op.create_index('ix_inspections_status', 'inspections', ['status'])


def downgrade() -> None:
    # Drop new tables
    op.drop_table('magic_tokens')
    op.drop_table('inspection_evidence')
    
    # Remove new columns from inspections
    op.drop_constraint('fk_inspections_supplemental', 'inspections', type_='foreignkey')
    op.drop_column('inspections', 'submitted_at')
    op.drop_column('inspections', 'content_hash')
    op.drop_column('inspections', 'supplemental_to_inspection_id')
    op.drop_column('inspections', 'schema_version')
    
    # Remove new columns from leases
    op.drop_index('ix_leases_status', 'leases')
    op.drop_column('leases', 'magic_token_expires_at')
    op.drop_column('leases', 'magic_token')
    op.drop_column('leases', 'status_new')
    
    # Remove new columns from properties
    op.drop_index('ix_properties_organization', 'properties')
    op.drop_constraint('fk_properties_organization', 'properties', type_='foreignkey')
    op.drop_column('properties', 'organization_id')
    
    # Remove new columns from users
    op.drop_index('ix_users_organization', 'users')
    op.drop_index('ix_users_firebase_uid', 'users')
    op.drop_constraint('fk_users_organization', 'users', type_='foreignkey')
    op.drop_column('users', 'role')
    op.drop_column('users', 'firebase_uid')
    op.drop_column('users', 'organization_id')
    
    # Drop organizations table
    op.drop_table('organizations')
    
    # Drop new enum
    op.execute("DROP TYPE IF EXISTS lease_status")
