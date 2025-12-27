"""Trust Tiers & Credibility Stack - Phase 1-2

Revision ID: 005_trust_tiers
Revises: 004_event_store
Create Date: 2024-12-26

Implements:
- asset_trust_tiers: Current trust tier per asset (BRONZE/SILVER/GOLD/PLATINUM)
- trust_tier_history: Audit trail of tier changes
- trust_tier_drivers: Cached driver calculations per asset
- security_waivers: Active waivers that cap trust tier

Trust Tiers are:
- Per asset, NOT per account
- Derived from behavior over time
- Earned, not purchased
- Orthogonal to billing plans
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '005_trust_tiers'
down_revision: Union[str, None] = '004_event_store'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # ASSET_TRUST_TIERS - Current trust tier per asset
    # Trust is EARNED over time, never purchased or manually set
    # =========================================================================
    op.create_table(
        'asset_trust_tiers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        
        # Current tier (1=BRONZE, 2=SILVER, 3=GOLD, 4=PLATINUM)
        sa.Column('tier', sa.Integer(), nullable=False, default=1),
        sa.Column('tier_name', sa.String(20), nullable=False, default='BRONZE'),
        
        # Driver scores (all 0.0-1.0)
        sa.Column('evidence_quality_score', sa.Numeric(5, 4), nullable=False, default=0),
        sa.Column('telemetry_continuity_score', sa.Numeric(5, 4), nullable=False, default=0),
        sa.Column('human_discipline_score', sa.Numeric(5, 4), nullable=False, default=0),
        sa.Column('time_in_system_score', sa.Numeric(5, 4), nullable=False, default=0),
        sa.Column('integrity_score', sa.Numeric(5, 4), nullable=False, default=0),
        
        # Composite score (weighted average of drivers)
        sa.Column('composite_score', sa.Numeric(5, 4), nullable=False, default=0),
        
        # Tier explanation (plain language, no jargon)
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('upgrade_path', sa.Text(), nullable=True),  # What would increase tier
        sa.Column('risk_factors', sa.Text(), nullable=True),   # What could decrease tier
        
        # Caps and constraints
        sa.Column('tier_cap', sa.Integer(), nullable=True),  # Max tier due to waivers/flags
        sa.Column('tier_cap_reason', sa.String(255), nullable=True),
        
        # Time tracking
        sa.Column('first_event_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_event_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('days_in_system', sa.Integer(), nullable=False, default=0),
        
        # Calculation metadata
        sa.Column('last_calculated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('calculation_version', sa.String(20), nullable=False, default='1.0.0'),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        
        sa.CheckConstraint('tier >= 1 AND tier <= 4', name='trust_tier_range'),
        sa.CheckConstraint("tier_name IN ('BRONZE', 'SILVER', 'GOLD', 'PLATINUM')", name='trust_tier_name_valid'),
        sa.CheckConstraint('evidence_quality_score >= 0 AND evidence_quality_score <= 1', name='evidence_score_range'),
        sa.CheckConstraint('telemetry_continuity_score >= 0 AND telemetry_continuity_score <= 1', name='telemetry_score_range'),
        sa.CheckConstraint('human_discipline_score >= 0 AND human_discipline_score <= 1', name='discipline_score_range'),
        sa.CheckConstraint('time_in_system_score >= 0 AND time_in_system_score <= 1', name='time_score_range'),
        sa.CheckConstraint('integrity_score >= 0 AND integrity_score <= 1', name='integrity_score_range'),
        sa.CheckConstraint('composite_score >= 0 AND composite_score <= 1', name='composite_score_range'),
    )
    
    op.create_index('idx_trust_tiers_asset', 'asset_trust_tiers', ['asset_id'])
    op.create_index('idx_trust_tiers_org', 'asset_trust_tiers', ['org_id'])
    op.create_index('idx_trust_tiers_tier', 'asset_trust_tiers', ['tier'])
    op.create_index('idx_trust_tiers_composite', 'asset_trust_tiers', ['composite_score'])

    # =========================================================================
    # TRUST_TIER_HISTORY - Audit trail of tier changes
    # Never delete - this is the credibility audit trail
    # =========================================================================
    op.create_table(
        'trust_tier_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        
        # Tier change
        sa.Column('previous_tier', sa.Integer(), nullable=True),
        sa.Column('new_tier', sa.Integer(), nullable=False),
        sa.Column('previous_tier_name', sa.String(20), nullable=True),
        sa.Column('new_tier_name', sa.String(20), nullable=False),
        
        # What caused the change
        sa.Column('change_type', sa.String(50), nullable=False),  # upgrade, downgrade, initial, recalculation
        sa.Column('change_reason', sa.Text(), nullable=False),
        
        # Driver scores at time of change
        sa.Column('evidence_quality_score', sa.Numeric(5, 4), nullable=False),
        sa.Column('telemetry_continuity_score', sa.Numeric(5, 4), nullable=False),
        sa.Column('human_discipline_score', sa.Numeric(5, 4), nullable=False),
        sa.Column('time_in_system_score', sa.Numeric(5, 4), nullable=False),
        sa.Column('integrity_score', sa.Numeric(5, 4), nullable=False),
        sa.Column('composite_score', sa.Numeric(5, 4), nullable=False),
        
        # Trigger event (if applicable)
        sa.Column('triggered_by_event_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('triggered_by_event_type', sa.String(100), nullable=True),
        
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        
        sa.CheckConstraint("change_type IN ('initial', 'upgrade', 'downgrade', 'recalculation', 'cap_applied', 'cap_removed')",
                          name='change_type_valid'),
    )
    
    op.create_index('idx_tier_history_asset', 'trust_tier_history', ['asset_id'])
    op.create_index('idx_tier_history_org', 'trust_tier_history', ['org_id'])
    op.create_index('idx_tier_history_recorded', 'trust_tier_history', ['recorded_at'])
    op.create_index('idx_tier_history_change_type', 'trust_tier_history', ['change_type'])

    # =========================================================================
    # SECURITY_WAIVERS - Active waivers that cap trust tier
    # Waivers impose tier caps until resolved
    # =========================================================================
    op.create_table(
        'security_waivers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        
        # Waiver details
        sa.Column('waiver_type', sa.String(100), nullable=False),
        sa.Column('waiver_reason', sa.Text(), nullable=False),
        sa.Column('tier_cap', sa.Integer(), nullable=False),  # Max tier allowed while waiver active
        
        # Time bounds
        sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        
        # Status
        sa.Column('status', sa.String(20), nullable=False, default='active'),
        sa.Column('resolution_type', sa.String(50), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        
        sa.CheckConstraint('tier_cap >= 1 AND tier_cap <= 4', name='waiver_tier_cap_range'),
        sa.CheckConstraint("status IN ('active', 'expired', 'resolved', 'overridden')", name='waiver_status_valid'),
        sa.CheckConstraint("waiver_type IN ('sensor_unverified', 'telemetry_gap', 'integrity_flag', 'manual_override', 'ledger_pending', 'evidence_missing')",
                          name='waiver_type_valid'),
    )
    
    op.create_index('idx_waivers_asset', 'security_waivers', ['asset_id'])
    op.create_index('idx_waivers_org', 'security_waivers', ['org_id'])
    op.create_index('idx_waivers_status', 'security_waivers', ['status'])
    op.create_index('idx_waivers_expires', 'security_waivers', ['expires_at'])
    op.create_index('idx_waivers_active', 'security_waivers', ['asset_id', 'status'],
                    postgresql_where=sa.text("status = 'active'"))

    # =========================================================================
    # TRUST_TIER_THRESHOLDS - Configurable thresholds per tier
    # Versioned for governance compliance
    # =========================================================================
    op.create_table(
        'trust_tier_thresholds',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('effective_until', sa.DateTime(timezone=True), nullable=True),
        
        # Thresholds for each tier (composite score required)
        sa.Column('bronze_min', sa.Numeric(5, 4), nullable=False, default=0.0),
        sa.Column('silver_min', sa.Numeric(5, 4), nullable=False, default=0.3),
        sa.Column('gold_min', sa.Numeric(5, 4), nullable=False, default=0.6),
        sa.Column('platinum_min', sa.Numeric(5, 4), nullable=False, default=0.85),
        
        # Driver weights (must sum to 1.0)
        sa.Column('evidence_weight', sa.Numeric(5, 4), nullable=False, default=0.25),
        sa.Column('telemetry_weight', sa.Numeric(5, 4), nullable=False, default=0.25),
        sa.Column('discipline_weight', sa.Numeric(5, 4), nullable=False, default=0.20),
        sa.Column('time_weight', sa.Numeric(5, 4), nullable=False, default=0.15),
        sa.Column('integrity_weight', sa.Numeric(5, 4), nullable=False, default=0.15),
        
        # Minimum time-in-system requirements (days)
        sa.Column('silver_min_days', sa.Integer(), nullable=False, default=7),
        sa.Column('gold_min_days', sa.Integer(), nullable=False, default=30),
        sa.Column('platinum_min_days', sa.Integer(), nullable=False, default=90),
        
        # Governance metadata
        sa.Column('change_reason', sa.Text(), nullable=True),
        sa.Column('approved_by', sa.String(255), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        
        sa.UniqueConstraint('version'),
    )
    
    # Insert default thresholds (v1.0.0)
    op.execute("""
        INSERT INTO trust_tier_thresholds (
            id, version, effective_from,
            bronze_min, silver_min, gold_min, platinum_min,
            evidence_weight, telemetry_weight, discipline_weight, time_weight, integrity_weight,
            silver_min_days, gold_min_days, platinum_min_days,
            change_reason, approved_by, created_at
        ) VALUES (
            gen_random_uuid(), '1.0.0', NOW(),
            0.0, 0.30, 0.60, 0.85,
            0.25, 0.25, 0.20, 0.15, 0.15,
            7, 30, 90,
            'Initial governance-compliant thresholds', 'SYSTEM',
            NOW()
        )
    """)


def downgrade() -> None:
    op.drop_table('trust_tier_thresholds')
    op.drop_table('security_waivers')
    op.drop_table('trust_tier_history')
    op.drop_table('asset_trust_tiers')
