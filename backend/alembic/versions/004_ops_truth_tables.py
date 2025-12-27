from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004_ops_truth_tables"
down_revision: Union[str, None] = "003_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_store",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("aggregate_version", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column(
            "emitter_class",
            sa.Text(),
            nullable=False,
        ),
        sa.Column("emitter_id", sa.Text(), nullable=False),
        sa.Column("ts_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_policy", sa.Text(), nullable=False),
        sa.Column("evidence_hash", sa.Text(), nullable=False),
        sa.Column("waiver_reason", sa.Text(), nullable=True),
        sa.Column("payload_json", postgresql.JSONB, nullable=False),
        sa.Column("prev_event_hash", sa.Text(), nullable=False),
        sa.Column("event_hash", sa.Text(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.CheckConstraint("emitter_class IN ('HUMAN','SYSTEM','LEDGER_EXTERNAL')"),
        sa.CheckConstraint("evidence_policy IN ('REQUIRED','INHERIT_LAST','WAIVER','OPTIONAL')"),
    )
    op.create_index("ux_event_store_asset_version", "event_store", ["asset_id", "aggregate_version"], unique=True)
    op.create_index("ix_event_store_entity_asset", "event_store", ["entity_id", "asset_id", "aggregate_version"], unique=False)

    op.create_table(
        "asset_projection",
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("aggregate_version", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("condition", sa.Text(), nullable=False),
        sa.Column("location_zone", sa.Text(), nullable=True),
        sa.Column("last_evidence_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("confidence_source", sa.Text(), nullable=True),
        sa.Column("requires_reverification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ledger_ref_id", sa.Text(), nullable=True),
        sa.Column("sync_status", sa.Text(), nullable=False, server_default=sa.text("'UNENCUMBERED'")),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("chain_status", sa.Text(), nullable=False, server_default=sa.text("'VALID'")),
        sa.Column("last_event_hash", sa.Text(), nullable=False),
        sa.Column("last_prev_hash", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_asset_projection_entity", "asset_projection", ["entity_id"], unique=False)

    op.create_table(
        "evidence_objects",
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False, unique=True),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("response_json", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("entity_id", "idempotency_key"),
    )

    op.create_table(
        "outbox_webhooks",
        sa.Column("outbox_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_outbox_pending", "outbox_webhooks", ["status", "next_attempt_at"], unique=False)

    op.create_table(
        "ledger_sync_state",
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ledger_ref_id", sa.Text(), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "telemetry_raw",
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ts_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sensor_type", sa.Text(), nullable=False),
        sa.Column("value_num", sa.Float(), nullable=True),
        sa.Column("value_json", postgresql.JSONB, nullable=True),
        sa.PrimaryKeyConstraint("entity_id", "asset_id", "ts_utc", "sensor_type"),
    )

    op.create_table(
        "telemetry_agg_1m",
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bucket_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sensor_type", sa.Text(), nullable=False),
        sa.Column("avg_value", sa.Float(), nullable=True),
        sa.Column("min_value", sa.Float(), nullable=True),
        sa.Column("max_value", sa.Float(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("anomaly_flags", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("entity_id", "asset_id", "bucket_utc", "sensor_type"),
    )

    op.create_table(
        "telemetry_agg_15m",
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bucket_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sensor_type", sa.Text(), nullable=False),
        sa.Column("avg_value", sa.Float(), nullable=True),
        sa.Column("min_value", sa.Float(), nullable=True),
        sa.Column("max_value", sa.Float(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("anomaly_flags", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("entity_id", "asset_id", "bucket_utc", "sensor_type"),
    )


def downgrade() -> None:
    op.drop_table("telemetry_agg_15m")
    op.drop_table("telemetry_agg_1m")
    op.drop_table("telemetry_raw")
    op.drop_table("ledger_sync_state")
    op.drop_index("ix_outbox_pending", table_name="outbox_webhooks")
    op.drop_table("outbox_webhooks")
    op.drop_table("idempotency_keys")
    op.drop_table("evidence_objects")
    op.drop_index("ix_asset_projection_entity", table_name="asset_projection")
    op.drop_table("asset_projection")
    op.drop_index("ix_event_store_entity_asset", table_name="event_store")
    op.drop_index("ux_event_store_asset_version", table_name="event_store")
    op.drop_table("event_store")
