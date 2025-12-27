"""Operational Integrity Framework & Downstream Integration - Phase 3-4 & 4-5

Revision ID: 007_integrity_framework
Revises: 006_attestations
Create Date: 2024-12-26

Phase 3-4: OPS AS DE FACTO STANDARD
- Publish Proveniq Operational Integrity Framework
- Map events to insurance, audit, compliance concepts
- Goal: "We prefer Ops-based documentation"

Phase 4-5: REGULATORY & CAPITAL DEPENDENCE
- Capital systems require Ops truth
- Claims systems defer to Ops timelines
- Loss prevention provable through Ops
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '007_integrity_framework'
down_revision: Union[str, None] = '006_attestations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # EVENT_TAXONOMY - Maps Ops events to industry-standard concepts
    # Insurance, audit, compliance, regulatory mappings
    # =========================================================================
    op.create_table(
        'event_taxonomy',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ops_event_type', sa.String(100), nullable=False, unique=True),
        
        # Industry mappings
        sa.Column('insurance_category', sa.String(100), nullable=True),
        sa.Column('insurance_subcategory', sa.String(100), nullable=True),
        sa.Column('audit_classification', sa.String(100), nullable=True),
        sa.Column('compliance_domain', sa.String(100), nullable=True),
        sa.Column('regulatory_relevance', postgresql.ARRAY(sa.String(50)), nullable=True),
        
        # ISO/Standard mappings
        sa.Column('iso_category', sa.String(50), nullable=True),  # ISO 22000, ISO 9001, etc.
        sa.Column('haccp_relevance', sa.Boolean(), default=False),
        sa.Column('food_safety_category', sa.String(100), nullable=True),
        
        # Claims relevance
        sa.Column('claims_weight', sa.Numeric(5, 4), nullable=False, default=0.5),
        sa.Column('evidence_strength', sa.String(20), nullable=False, default='medium'),
        
        # Description for third parties
        sa.Column('plain_language_description', sa.Text(), nullable=False),
        sa.Column('insurance_description', sa.Text(), nullable=True),
        sa.Column('audit_description', sa.Text(), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        
        sa.CheckConstraint("evidence_strength IN ('weak', 'medium', 'strong', 'definitive')", name='evidence_strength_valid'),
    )
    
    op.create_index('idx_taxonomy_insurance', 'event_taxonomy', ['insurance_category'])
    op.create_index('idx_taxonomy_audit', 'event_taxonomy', ['audit_classification'])
    op.create_index('idx_taxonomy_compliance', 'event_taxonomy', ['compliance_domain'])

    # =========================================================================
    # DOWNSTREAM_INTEGRATIONS - Registered downstream systems
    # ClaimsIQ, Capital, Bids, external insurers, lenders
    # =========================================================================
    op.create_table(
        'downstream_integrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('integration_id', sa.String(64), nullable=False, unique=True),
        sa.Column('system_name', sa.String(100), nullable=False),
        sa.Column('system_type', sa.String(50), nullable=False),
        
        # Connection details
        sa.Column('api_endpoint', sa.String(500), nullable=True),
        sa.Column('webhook_url', sa.String(500), nullable=True),
        sa.Column('auth_type', sa.String(50), nullable=False, default='api_key'),
        
        # Data sharing configuration
        sa.Column('shared_event_types', postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.Column('trust_tier_threshold', sa.Integer(), nullable=True),
        sa.Column('attestation_required', sa.Boolean(), default=False),
        
        # Status
        sa.Column('status', sa.String(20), nullable=False, default='active'),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sync_frequency_minutes', sa.Integer(), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        
        sa.CheckConstraint("system_type IN ('claimsiq', 'capital', 'bids', 'insurer', 'lender', 'regulator', 'auditor')",
                          name='system_type_valid'),
        sa.CheckConstraint("auth_type IN ('api_key', 'oauth2', 'mtls', 'webhook_secret')", name='auth_type_valid'),
        sa.CheckConstraint("status IN ('active', 'inactive', 'pending', 'suspended')", name='integration_status_valid'),
    )
    
    op.create_index('idx_integrations_type', 'downstream_integrations', ['system_type'])
    op.create_index('idx_integrations_status', 'downstream_integrations', ['status'])

    # =========================================================================
    # DOWNSTREAM_REQUESTS - Requests from downstream systems
    # Audit trail of who accessed what Ops data
    # =========================================================================
    op.create_table(
        'downstream_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('integration_id', sa.String(64), nullable=False),
        sa.Column('request_type', sa.String(50), nullable=False),
        
        # Request details
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('time_range_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('time_range_end', sa.DateTime(timezone=True), nullable=True),
        
        # Response
        sa.Column('response_status', sa.String(20), nullable=False),
        sa.Column('events_returned', sa.Integer(), nullable=True),
        sa.Column('trust_tier_at_request', sa.Integer(), nullable=True),
        sa.Column('attestation_id', sa.String(64), nullable=True),
        
        # Audit
        sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        
        sa.CheckConstraint(
            "request_type IN ('timeline', 'attestation', 'trust_tier', 'evidence_pack', 'compliance_report', 'audit_export')",
            name='request_type_valid'
        ),
        sa.CheckConstraint("response_status IN ('success', 'denied', 'error', 'partial')", name='response_status_valid'),
    )
    
    op.create_index('idx_downstream_requests_integration', 'downstream_requests', ['integration_id'])
    op.create_index('idx_downstream_requests_asset', 'downstream_requests', ['asset_id'])
    op.create_index('idx_downstream_requests_time', 'downstream_requests', ['requested_at'])

    # =========================================================================
    # COMPLIANCE_REPORTS - Generated compliance/audit reports
    # =========================================================================
    op.create_table(
        'compliance_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('report_id', sa.String(64), nullable=False, unique=True),
        sa.Column('report_type', sa.String(50), nullable=False),
        
        # Scope
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('asset_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column('time_range_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('time_range_end', sa.DateTime(timezone=True), nullable=False),
        
        # Content
        sa.Column('report_data', postgresql.JSONB, nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        
        # Metrics
        sa.Column('total_events', sa.Integer(), nullable=False),
        sa.Column('anomalies_detected', sa.Integer(), nullable=False, default=0),
        sa.Column('attestations_issued', sa.Integer(), nullable=False, default=0),
        sa.Column('average_trust_tier', sa.Numeric(5, 2), nullable=True),
        
        # Signature
        sa.Column('report_hash', sa.String(128), nullable=False),
        sa.Column('signed_by_key_id', sa.String(64), nullable=True),
        sa.Column('signature', sa.Text(), nullable=True),
        
        # Metadata
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('generated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('requested_by_integration', sa.String(64), nullable=True),
        
        sa.CheckConstraint(
            "report_type IN ('operational_summary', 'compliance_audit', 'insurance_evidence', 'regulatory_filing', 'loss_prevention', 'incident_timeline')",
            name='report_type_valid'
        ),
    )
    
    op.create_index('idx_compliance_reports_org', 'compliance_reports', ['org_id'])
    op.create_index('idx_compliance_reports_type', 'compliance_reports', ['report_type'])
    op.create_index('idx_compliance_reports_generated', 'compliance_reports', ['generated_at'])

    # =========================================================================
    # FRAMEWORK_VERSIONS - Versioned Operational Integrity Framework
    # Published standards that downstream systems reference
    # =========================================================================
    op.create_table(
        'framework_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('version', sa.String(20), nullable=False, unique=True),
        sa.Column('name', sa.String(255), nullable=False),
        
        # Framework content
        sa.Column('schema_definition', postgresql.JSONB, nullable=False),
        sa.Column('event_types', postgresql.JSONB, nullable=False),
        sa.Column('trust_tier_requirements', postgresql.JSONB, nullable=False),
        sa.Column('attestation_rules', postgresql.JSONB, nullable=False),
        
        # Compatibility
        sa.Column('backward_compatible_with', postgresql.ARRAY(sa.String(20)), nullable=True),
        sa.Column('breaking_changes', postgresql.JSONB, nullable=True),
        
        # Lifecycle
        sa.Column('status', sa.String(20), nullable=False, default='draft'),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deprecated_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        
        sa.CheckConstraint("status IN ('draft', 'published', 'deprecated')", name='framework_status_valid'),
    )
    
    # Insert initial framework version
    op.execute("""
        INSERT INTO framework_versions (
            id, version, name, status,
            schema_definition, event_types, trust_tier_requirements, attestation_rules,
            published_at, created_at
        ) VALUES (
            gen_random_uuid(),
            '1.0.0',
            'PROVENIQ Operational Integrity Framework',
            'published',
            '{"version": "1.0.0", "standard": "proveniq-oif", "description": "Operational truth infrastructure standard"}',
            '{"categories": ["telemetry", "bishop", "shrinkage", "inventory", "vendor", "anomaly"]}',
            '{"bronze": {"min_score": 0.0}, "silver": {"min_score": 0.3, "min_days": 7}, "gold": {"min_score": 0.6, "min_days": 30}, "platinum": {"min_score": 0.85, "min_days": 90}}',
            '{"types": ["OPERATION_WITHIN_SPEC", "CONDITION_AT_TIME", "CONTINUITY_CONFIRMED"], "platinum_required": true, "expiration_required": true}',
            NOW(),
            NOW()
        )
    """)

    # =========================================================================
    # Insert default event taxonomy mappings
    # =========================================================================
    op.execute("""
        INSERT INTO event_taxonomy (id, ops_event_type, insurance_category, insurance_subcategory, audit_classification, compliance_domain, claims_weight, evidence_strength, plain_language_description, insurance_description) VALUES
        (gen_random_uuid(), 'ops.scan.initiated', 'Loss Prevention', 'Inventory Control', 'Operational', 'SOX', 0.3, 'medium', 'Inventory scan was started', 'Evidence of inventory monitoring activity'),
        (gen_random_uuid(), 'ops.scan.completed', 'Loss Prevention', 'Inventory Control', 'Operational', 'SOX', 0.5, 'strong', 'Inventory scan completed successfully', 'Documented inventory verification'),
        (gen_random_uuid(), 'ops.shrinkage.detected', 'Property Loss', 'Inventory Shrinkage', 'Financial', 'Insurance', 0.9, 'definitive', 'Inventory shrinkage was detected', 'Direct evidence of inventory loss requiring claim consideration'),
        (gen_random_uuid(), 'ops.shrinkage.classified', 'Property Loss', 'Inventory Shrinkage', 'Financial', 'Insurance', 0.85, 'strong', 'Shrinkage was classified by type', 'Categorized loss for claims processing'),
        (gen_random_uuid(), 'ops.order.created', 'Business Operations', 'Procurement', 'Operational', 'SOX', 0.4, 'medium', 'Purchase order was created', 'Evidence of operational activity'),
        (gen_random_uuid(), 'ops.order.fulfilled', 'Business Operations', 'Procurement', 'Operational', 'SOX', 0.5, 'strong', 'Order was fulfilled and received', 'Documented delivery receipt'),
        (gen_random_uuid(), 'ops.bishop.recommendation_generated', 'Loss Prevention', 'Risk Management', 'Advisory', 'Internal', 0.3, 'weak', 'AI system generated a recommendation', 'System-generated operational guidance'),
        (gen_random_uuid(), 'ops.bishop.recommendation_accepted', 'Loss Prevention', 'Risk Management', 'Decision', 'Internal', 0.6, 'strong', 'Human operator accepted AI recommendation', 'Documented human decision on AI guidance'),
        (gen_random_uuid(), 'ops.bishop.recommendation_rejected', 'Loss Prevention', 'Risk Management', 'Decision', 'Internal', 0.6, 'strong', 'Human operator rejected AI recommendation', 'Documented human override of AI guidance'),
        (gen_random_uuid(), 'ops.anomaly.detected', 'Loss Prevention', 'Risk Assessment', 'Exception', 'Compliance', 0.8, 'strong', 'Operational anomaly was detected', 'Evidence of deviation from normal operations'),
        (gen_random_uuid(), 'ops.temperature.recorded', 'Product Liability', 'Cold Chain', 'Compliance', 'FDA', 0.7, 'strong', 'Temperature reading was recorded', 'Cold chain compliance documentation'),
        (gen_random_uuid(), 'ops.receiving.completed', 'Business Operations', 'Inventory Receipt', 'Operational', 'SOX', 0.5, 'strong', 'Goods were received and logged', 'Chain of custody documentation')
    """)


def downgrade() -> None:
    op.drop_table('framework_versions')
    op.drop_table('compliance_reports')
    op.drop_table('downstream_requests')
    op.drop_table('downstream_integrations')
    op.drop_table('event_taxonomy')
