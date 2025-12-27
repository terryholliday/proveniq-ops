"""Event Store & Decision Traces - Phase 0-1 Data Gravity

Revision ID: 004_event_store
Revises: 003_users
Create Date: 2024-12-26

Implements:
- ops_events: Immutable append-only event store (DATA GRAVITY)
- decision_traces: Persistent decision history (FORENSIC RECONSTRUCTION)
- trace_events: Individual events within a trace
- operational_baselines: Earned baselines over time (CANNOT BE IMPORTED)
- anomaly_contexts: Links anomalies to prior operational context
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '004_event_store'
down_revision: Union[str, None] = '003_users'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # OPS_EVENTS - Immutable append-only event store
    # This is the DATA GRAVITY table. Never delete. Never update.
    # =========================================================================
    op.create_table(
        'ops_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('wallet_id', sa.String(255), nullable=True),  # Pseudonymous identifier
        sa.Column('correlation_id', sa.String(255), nullable=True),
        sa.Column('idempotency_key', sa.String(255), nullable=True, unique=True),
        sa.Column('version', sa.String(20), nullable=False, default='1.0'),
        sa.Column('source_app', sa.String(50), nullable=False, default='OPS'),
        
        # Payload stored as JSONB for queryability
        sa.Column('payload', postgresql.JSONB, nullable=False, default={}),
        
        # Hash for integrity verification
        sa.Column('payload_hash', sa.String(64), nullable=False),
        
        # Ledger sync status
        sa.Column('ledger_synced', sa.Boolean(), nullable=False, default=False),
        sa.Column('ledger_event_id', sa.String(255), nullable=True),
        sa.Column('ledger_synced_at', sa.DateTime(timezone=True), nullable=True),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # Indexes for common queries
    op.create_index('idx_ops_events_type', 'ops_events', ['event_type'])
    op.create_index('idx_ops_events_timestamp', 'ops_events', ['timestamp'])
    op.create_index('idx_ops_events_correlation', 'ops_events', ['correlation_id'])
    op.create_index('idx_ops_events_wallet', 'ops_events', ['wallet_id'])
    op.create_index('idx_ops_events_ledger_sync', 'ops_events', ['ledger_synced'], 
                    postgresql_where=sa.text('ledger_synced = false'))
    
    # GIN index for JSONB payload queries
    op.execute('CREATE INDEX idx_ops_events_payload ON ops_events USING GIN (payload)')

    # =========================================================================
    # DECISION_TRACES - Persistent decision history
    # Enables "What happened last time" and forensic reconstruction
    # =========================================================================
    op.create_table(
        'decision_traces',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('dag_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('dag_name', sa.String(255), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        
        # Timing
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        
        # Context snapshots (JSONB for queryability)
        sa.Column('initial_context', postgresql.JSONB, nullable=False, default={}),
        sa.Column('final_context', postgresql.JSONB, nullable=False, default={}),
        
        # Outcome
        sa.Column('status', sa.String(50), nullable=False, default='pending'),
        sa.Column('error', sa.Text(), nullable=True),
        
        # Full trace serialization for replay
        sa.Column('trace_json', postgresql.JSONB, nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        
        sa.CheckConstraint("status IN ('pending', 'passed', 'failed', 'blocked')",
                          name='decision_traces_status_valid'),
    )
    
    op.create_index('idx_decision_traces_dag', 'decision_traces', ['dag_id'])
    op.create_index('idx_decision_traces_org', 'decision_traces', ['org_id'])
    op.create_index('idx_decision_traces_status', 'decision_traces', ['status'])
    op.create_index('idx_decision_traces_started', 'decision_traces', ['started_at'])
    
    # GIN indexes for context search
    op.execute('CREATE INDEX idx_decision_traces_initial_ctx ON decision_traces USING GIN (initial_context)')
    op.execute('CREATE INDEX idx_decision_traces_final_ctx ON decision_traces USING GIN (final_context)')

    # =========================================================================
    # TRACE_EVENTS - Individual events within a decision trace
    # =========================================================================
    op.create_table(
        'trace_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('trace_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('decision_traces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('node_id', sa.String(100), nullable=True),
        sa.Column('gate_id', sa.String(100), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('details', postgresql.JSONB, nullable=False, default={}),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    op.create_index('idx_trace_events_trace', 'trace_events', ['trace_id'])
    op.create_index('idx_trace_events_type', 'trace_events', ['event_type'])
    op.create_index('idx_trace_events_node', 'trace_events', ['node_id'])

    # =========================================================================
    # OPERATIONAL_BASELINES - Earned baselines (DATA GRAVITY)
    # These are EARNED over time, never imported. This is the moat.
    # =========================================================================
    op.create_table(
        'operational_baselines',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Baseline type
        sa.Column('baseline_type', sa.String(50), nullable=False),
        
        # Time window this baseline covers
        sa.Column('window_days', sa.Integer(), nullable=False),  # 7, 30, 90
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        
        # Statistical measures (earned from data, not imported)
        sa.Column('mean_value', sa.Numeric(18, 6), nullable=False),
        sa.Column('std_dev', sa.Numeric(18, 6), nullable=False),
        sa.Column('min_value', sa.Numeric(18, 6), nullable=False),
        sa.Column('max_value', sa.Numeric(18, 6), nullable=False),
        sa.Column('median_value', sa.Numeric(18, 6), nullable=False),
        sa.Column('sample_count', sa.Integer(), nullable=False),
        
        # Confidence in this baseline (increases with more data)
        sa.Column('confidence_score', sa.Numeric(5, 4), nullable=False),
        
        # Percentile thresholds for anomaly detection
        sa.Column('p05', sa.Numeric(18, 6), nullable=True),  # 5th percentile
        sa.Column('p25', sa.Numeric(18, 6), nullable=True),  # 25th percentile
        sa.Column('p75', sa.Numeric(18, 6), nullable=True),  # 75th percentile
        sa.Column('p95', sa.Numeric(18, 6), nullable=True),  # 95th percentile
        
        sa.Column('calculated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        
        sa.CheckConstraint("baseline_type IN ('daily_consumption', 'weekly_orders', 'shrinkage_rate', 'delivery_time', 'price_variance', 'scan_frequency')",
                          name='baselines_type_valid'),
        sa.CheckConstraint('window_days IN (7, 30, 90)', name='baselines_window_valid'),
        sa.CheckConstraint('confidence_score >= 0 AND confidence_score <= 1', name='baselines_confidence_range'),
    )
    
    op.create_index('idx_baselines_org', 'operational_baselines', ['org_id'])
    op.create_index('idx_baselines_product', 'operational_baselines', ['product_id'])
    op.create_index('idx_baselines_location', 'operational_baselines', ['location_id'])
    op.create_index('idx_baselines_type_window', 'operational_baselines', ['baseline_type', 'window_days'])
    
    # Unique constraint: one baseline per org/location/product/type/window
    op.create_unique_constraint(
        'uq_baselines_scope',
        'operational_baselines',
        ['org_id', 'location_id', 'product_id', 'baseline_type', 'window_days']
    )

    # =========================================================================
    # ANOMALY_CONTEXTS - Links anomalies to prior operational context
    # This is what makes forensic reconstruction possible
    # =========================================================================
    op.create_table(
        'anomaly_contexts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        
        # What anomaly was detected
        sa.Column('anomaly_type', sa.String(100), nullable=False),
        sa.Column('anomaly_severity', sa.String(20), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        
        # The anomalous value vs expected
        sa.Column('observed_value', sa.Numeric(18, 6), nullable=False),
        sa.Column('expected_value', sa.Numeric(18, 6), nullable=False),
        sa.Column('deviation_sigma', sa.Numeric(8, 4), nullable=False),  # Standard deviations from mean
        
        # Link to the baseline used for detection
        sa.Column('baseline_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('operational_baselines.id'), nullable=True),
        
        # Entity references
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Prior context snapshot (what led up to this anomaly)
        sa.Column('prior_events', postgresql.JSONB, nullable=False, default=[]),  # Last N events before anomaly
        sa.Column('prior_context', postgresql.JSONB, nullable=False, default={}),  # State at time of anomaly
        
        # Related events (linked after detection)
        sa.Column('related_event_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        
        # Resolution
        sa.Column('status', sa.String(50), nullable=False, default='detected'),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_type', sa.String(100), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Link to shrinkage if applicable
        sa.Column('shrinkage_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Link to decision trace if this triggered a decision
        sa.Column('decision_trace_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('decision_traces.id'), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        
        sa.CheckConstraint("anomaly_type IN ('consumption_spike', 'consumption_drop', 'price_anomaly', 'shrinkage_detected', 'delivery_delay', 'scan_gap', 'order_anomaly')",
                          name='anomaly_type_valid'),
        sa.CheckConstraint("anomaly_severity IN ('low', 'medium', 'high', 'critical')",
                          name='anomaly_severity_valid'),
        sa.CheckConstraint("status IN ('detected', 'investigating', 'confirmed', 'false_positive', 'resolved')",
                          name='anomaly_status_valid'),
    )
    
    op.create_index('idx_anomaly_org', 'anomaly_contexts', ['org_id'])
    op.create_index('idx_anomaly_type', 'anomaly_contexts', ['anomaly_type'])
    op.create_index('idx_anomaly_severity', 'anomaly_contexts', ['anomaly_severity'])
    op.create_index('idx_anomaly_detected', 'anomaly_contexts', ['detected_at'])
    op.create_index('idx_anomaly_status', 'anomaly_contexts', ['status'])
    op.create_index('idx_anomaly_product', 'anomaly_contexts', ['product_id'])
    
    # GIN index for prior events search
    op.execute('CREATE INDEX idx_anomaly_prior_events ON anomaly_contexts USING GIN (prior_events)')


def downgrade() -> None:
    op.drop_table('anomaly_contexts')
    op.drop_table('operational_baselines')
    op.drop_table('trace_events')
    op.drop_table('decision_traces')
    op.drop_table('ops_events')
