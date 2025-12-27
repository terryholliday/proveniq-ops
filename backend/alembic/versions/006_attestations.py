"""Attestations - Phase 2-3

Revision ID: 006_attestations
Revises: 005_trust_tiers
Create Date: 2024-12-26

Implements:
- ops_attestations: Issued attestations (cryptographically signed)
- attestation_keys: Key management for signing
- attestation_requests: Pending attestation requests

GOVERNANCE (BINDING):
- Attestations state what can be PROVEN, not what is PROMISED
- Only PLATINUM tier assets are eligible
- Attestations are time-bound and expire (never perpetual)
- Verifiable without Proveniq authentication
- 3 types only: OPERATION_WITHIN_SPEC, CONDITION_AT_TIME, CONTINUITY_CONFIRMED
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '006_attestations'
down_revision: Union[str, None] = '005_trust_tiers'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # ATTESTATION_KEYS - Key management for signing attestations
    # Versioned and auditable
    # =========================================================================
    op.create_table(
        'attestation_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('key_id', sa.String(64), nullable=False, unique=True),
        sa.Column('version', sa.Integer(), nullable=False),
        
        # Key material (encrypted at rest)
        sa.Column('public_key_pem', sa.Text(), nullable=False),
        sa.Column('private_key_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('key_algorithm', sa.String(50), nullable=False, default='Ed25519'),
        
        # Lifecycle
        sa.Column('status', sa.String(20), nullable=False, default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rotated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        
        # Governance
        sa.Column('rotation_reason', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(255), nullable=False),
        
        sa.CheckConstraint("status IN ('pending', 'active', 'rotated', 'revoked')", name='key_status_valid'),
        sa.CheckConstraint("key_algorithm IN ('Ed25519', 'ECDSA_P256', 'RSA_4096')", name='key_algorithm_valid'),
    )
    
    op.create_index('idx_attestation_keys_status', 'attestation_keys', ['status'])
    op.create_index('idx_attestation_keys_version', 'attestation_keys', ['version'])

    # =========================================================================
    # OPS_ATTESTATIONS - Issued attestations
    # Cryptographically signed, time-bound, evidence-backed
    # =========================================================================
    op.create_table(
        'ops_attestations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        
        # UUIDv7 for time-sortable IDs
        sa.Column('attestation_id', sa.String(36), nullable=False, unique=True),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        
        # Attestation type (AUTHORITATIVE - no custom types)
        sa.Column('attestation_type', sa.String(50), nullable=False),
        
        # Time window (attestations are ALWAYS time-bound)
        sa.Column('time_window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('time_window_end', sa.DateTime(timezone=True), nullable=False),
        
        # Declared parameters (what was observed)
        sa.Column('declared_parameters', postgresql.JSONB, nullable=False),
        
        # Confidence and evidence
        sa.Column('confidence_score', sa.Numeric(5, 4), nullable=False),
        sa.Column('evidence_event_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column('evidence_count', sa.Integer(), nullable=False),
        sa.Column('evidence_digest', sa.String(128), nullable=False),  # SHA-512 of evidence
        
        # Trust tier at issuance (must be PLATINUM)
        sa.Column('trust_tier_at_issuance', sa.Integer(), nullable=False),
        
        # Cryptographic signature
        sa.Column('issuer_key_id', sa.String(64), nullable=False),
        sa.Column('issuer_signature', sa.Text(), nullable=False),
        sa.Column('signature_algorithm', sa.String(50), nullable=False),
        
        # Lifecycle
        sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='valid'),
        
        # Verification metadata
        sa.Column('verification_url', sa.String(500), nullable=True),
        sa.Column('verification_count', sa.Integer(), nullable=False, default=0),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        
        sa.CheckConstraint(
            "attestation_type IN ('OPERATION_WITHIN_SPEC', 'CONDITION_AT_TIME', 'CONTINUITY_CONFIRMED')",
            name='attestation_type_valid'
        ),
        sa.CheckConstraint("status IN ('valid', 'expired', 'superseded')", name='attestation_status_valid'),
        sa.CheckConstraint('trust_tier_at_issuance = 4', name='platinum_required'),  # PLATINUM = 4
        sa.CheckConstraint('confidence_score >= 0 AND confidence_score <= 1', name='confidence_range'),
        sa.CheckConstraint('time_window_end > time_window_start', name='valid_time_window'),
        sa.CheckConstraint('expires_at > issued_at', name='valid_expiry'),
    )
    
    op.create_index('idx_attestations_asset', 'ops_attestations', ['asset_id'])
    op.create_index('idx_attestations_org', 'ops_attestations', ['org_id'])
    op.create_index('idx_attestations_type', 'ops_attestations', ['attestation_type'])
    op.create_index('idx_attestations_status', 'ops_attestations', ['status'])
    op.create_index('idx_attestations_issued', 'ops_attestations', ['issued_at'])
    op.create_index('idx_attestations_expires', 'ops_attestations', ['expires_at'])
    op.create_index('idx_attestations_key', 'ops_attestations', ['issuer_key_id'])

    # =========================================================================
    # ATTESTATION_REQUESTS - Pending attestation requests
    # Tracks eligibility checks and failures
    # =========================================================================
    op.create_table(
        'attestation_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('requested_by', postgresql.UUID(as_uuid=True), nullable=False),
        
        # Request details
        sa.Column('attestation_type', sa.String(50), nullable=False),
        sa.Column('time_window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('time_window_end', sa.DateTime(timezone=True), nullable=False),
        
        # Eligibility check results
        sa.Column('eligibility_status', sa.String(20), nullable=False),
        sa.Column('eligibility_checks', postgresql.JSONB, nullable=False),
        sa.Column('failed_checks', postgresql.ARRAY(sa.String(100)), nullable=True),
        
        # Outcome
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('attestation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        
        sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.CheckConstraint(
            "attestation_type IN ('OPERATION_WITHIN_SPEC', 'CONDITION_AT_TIME', 'CONTINUITY_CONFIRMED')",
            name='request_type_valid'
        ),
        sa.CheckConstraint("eligibility_status IN ('eligible', 'ineligible', 'pending')", name='eligibility_status_valid'),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'failed')", name='request_status_valid'),
    )
    
    op.create_index('idx_attest_requests_asset', 'attestation_requests', ['asset_id'])
    op.create_index('idx_attest_requests_org', 'attestation_requests', ['org_id'])
    op.create_index('idx_attest_requests_status', 'attestation_requests', ['status'])


def downgrade() -> None:
    op.drop_table('attestation_requests')
    op.drop_table('ops_attestations')
    op.drop_table('attestation_keys')
