-- PROVENIQ Ops — Postgres DDL (Gold Master)
-- Notes:
-- 1) event_store is append-only (no UPDATE/DELETE permitted by app role)
-- 2) projections are derived and rebuildable
-- 3) telemetry is ephemeral and partitioned
-- 4) evidence blobs are NOT stored here, only hashes + metadata

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ===== Event Store =====
CREATE TABLE IF NOT EXISTS event_store (
  event_id            UUID PRIMARY KEY,
  asset_id            UUID NOT NULL,
  entity_id           TEXT NOT NULL,

  aggregate_version   BIGINT NOT NULL,
  event_type          TEXT NOT NULL,
  emitter_class       TEXT NOT NULL CHECK (emitter_class IN ('HUMAN','SYSTEM','LEDGER_EXTERNAL')),
  emitter_id          TEXT NOT NULL,

  ts_utc              TIMESTAMPTZ NOT NULL,

  evidence_policy     TEXT NOT NULL CHECK (evidence_policy IN ('REQUIRED','INHERIT_LAST','WAIVER','OPTIONAL')),
  evidence_hash       TEXT NOT NULL,
  waiver_reason       TEXT NULL,

  payload_json        JSONB NOT NULL,

  prev_event_hash     TEXT NOT NULL,
  event_hash          TEXT NOT NULL,
  signature           TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_event_store_asset_version
  ON event_store(asset_id, aggregate_version);

CREATE INDEX IF NOT EXISTS ix_event_store_entity_asset
  ON event_store(entity_id, asset_id, aggregate_version);

-- ===== Projections (Derived) =====
CREATE TABLE IF NOT EXISTS asset_projection (
  asset_id            UUID PRIMARY KEY,
  entity_id           TEXT NOT NULL,

  aggregate_version   BIGINT NOT NULL,
  status              TEXT NOT NULL,
  condition           TEXT NOT NULL,
  location_zone       TEXT NULL,
  last_evidence_ts    TIMESTAMPTZ NULL,

  confidence_score    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
  confidence_source   TEXT NULL,
  requires_reverification BOOLEAN NOT NULL DEFAULT FALSE,

  ledger_ref_id       TEXT NULL,
  sync_status         TEXT NOT NULL DEFAULT 'UNENCUMBERED',
  retry_count         INT NOT NULL DEFAULT 0,

  chain_status        TEXT NOT NULL DEFAULT 'VALID',
  last_event_hash     TEXT NOT NULL,
  last_prev_hash      TEXT NOT NULL,

  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_asset_projection_entity
  ON asset_projection(entity_id);

-- ===== Evidence Index (metadata only) =====
CREATE TABLE IF NOT EXISTS evidence_objects (
  evidence_id         UUID PRIMARY KEY,
  entity_id           TEXT NOT NULL,
  sha256              TEXT NOT NULL UNIQUE,
  content_type        TEXT NOT NULL,
  byte_size           BIGINT NOT NULL,
  storage_key         TEXT NOT NULL, -- S3 key or similar
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===== Idempotency =====
CREATE TABLE IF NOT EXISTS idempotency_keys (
  entity_id           TEXT NOT NULL,
  idempotency_key     TEXT NOT NULL,
  request_hash        TEXT NOT NULL,
  response_json       JSONB NOT NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(entity_id, idempotency_key)
);

-- ===== Outbox (webhooks) =====
CREATE TABLE IF NOT EXISTS outbox_webhooks (
  outbox_id           UUID PRIMARY KEY,
  entity_id           TEXT NOT NULL,
  topic               TEXT NOT NULL,
  payload_json        JSONB NOT NULL,
  attempts            INT NOT NULL DEFAULT 0,
  next_attempt_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  status              TEXT NOT NULL DEFAULT 'PENDING', -- PENDING|SENT|FAILED
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_outbox_pending
  ON outbox_webhooks(status, next_attempt_at);

-- ===== Ledger Sync State =====
CREATE TABLE IF NOT EXISTS ledger_sync_state (
  asset_id            UUID PRIMARY KEY,
  ledger_ref_id       TEXT NOT NULL,
  locked_at           TIMESTAMPTZ NOT NULL,
  retry_count         INT NOT NULL DEFAULT 0,
  last_polled_at      TIMESTAMPTZ NULL
);

-- ===== Telemetry =====
-- Use daily partitions in production (native partitioning). Minimal table here.
CREATE TABLE IF NOT EXISTS telemetry_raw (
  entity_id           TEXT NOT NULL,
  asset_id            UUID NOT NULL,
  ts_utc              TIMESTAMPTZ NOT NULL,
  sensor_type         TEXT NOT NULL,
  value_num           DOUBLE PRECISION NULL,
  value_json          JSONB NULL,
  PRIMARY KEY(entity_id, asset_id, ts_utc, sensor_type)
);

CREATE TABLE IF NOT EXISTS telemetry_agg_1m (
  entity_id           TEXT NOT NULL,
  asset_id            UUID NOT NULL,
  bucket_utc          TIMESTAMPTZ NOT NULL,
  sensor_type         TEXT NOT NULL,
  avg_value           DOUBLE PRECISION NULL,
  min_value           DOUBLE PRECISION NULL,
  max_value           DOUBLE PRECISION NULL,
  sample_count        INT NOT NULL,
  anomaly_flags       JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY(entity_id, asset_id, bucket_utc, sensor_type)
);

CREATE TABLE IF NOT EXISTS telemetry_agg_15m (
  entity_id           TEXT NOT NULL,
  asset_id            UUID NOT NULL,
  bucket_utc          TIMESTAMPTZ NOT NULL,
  sensor_type         TEXT NOT NULL,
  avg_value           DOUBLE PRECISION NULL,
  min_value           DOUBLE PRECISION NULL,
  max_value           DOUBLE PRECISION NULL,
  sample_count        INT NOT NULL,
  anomaly_flags       JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY(entity_id, asset_id, bucket_utc, sensor_type)
);
