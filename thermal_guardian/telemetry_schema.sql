-- Thermal Guardian Telemetry Schema (Postgres)
-- NOTE: Telemetry is EPHEMERAL and NON-AUTHORITATIVE.
-- Recommended sampling:
--   temp: 30-60s, door: event-driven, power: 5-15s
-- Retention policy (enforced by jobs, not constraints):
--   telemetry_raw: keep 24h
--   telemetry_agg_1m: keep 7d
--   telemetry_agg_15m: keep 30d
--   >30d purge (hard delete)

-- Canonical signals (normalized):
--   sensor_type in ('temp_c','door_open','power_w','compressor_on')
--   value_num used for numeric signals; value_json optional metadata

CREATE TABLE IF NOT EXISTS telemetry_raw (
  entity_id     TEXT NOT NULL,
  asset_id      UUID NOT NULL,
  ts_utc        TIMESTAMPTZ NOT NULL,
  sensor_type   TEXT NOT NULL CHECK (sensor_type IN ('temp_c','door_open','power_w','compressor_on')),
  value_num     DOUBLE PRECISION NULL,
  value_json    JSONB NULL,
  PRIMARY KEY(entity_id, asset_id, ts_utc, sensor_type)
);

-- Helpful indexes for range scans by time and sensor
CREATE INDEX IF NOT EXISTS ix_tr_asset_sensor_time
  ON telemetry_raw(asset_id, sensor_type, ts_utc DESC);

CREATE INDEX IF NOT EXISTS ix_tr_entity_time
  ON telemetry_raw(entity_id, ts_utc DESC);

-- Aggregations at 1-minute buckets
CREATE TABLE IF NOT EXISTS telemetry_agg_1m (
  entity_id     TEXT NOT NULL,
  asset_id      UUID NOT NULL,
  bucket_utc    TIMESTAMPTZ NOT NULL, -- floor to minute
  sensor_type   TEXT NOT NULL CHECK (sensor_type IN ('temp_c','power_w')),
  avg_value     DOUBLE PRECISION NULL,
  min_value     DOUBLE PRECISION NULL,
  max_value     DOUBLE PRECISION NULL,
  sample_count  INT NOT NULL,
  anomaly_flags JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY(entity_id, asset_id, bucket_utc, sensor_type)
);

CREATE INDEX IF NOT EXISTS ix_ta1_asset_sensor_bucket
  ON telemetry_agg_1m(asset_id, sensor_type, bucket_utc DESC);

-- Aggregations at 15-minute buckets (from 1m)
CREATE TABLE IF NOT EXISTS telemetry_agg_15m (
  entity_id     TEXT NOT NULL,
  asset_id      UUID NOT NULL,
  bucket_utc    TIMESTAMPTZ NOT NULL, -- floor to 15 minutes
  sensor_type   TEXT NOT NULL CHECK (sensor_type IN ('temp_c','power_w')),
  avg_value     DOUBLE PRECISION NULL,
  min_value     DOUBLE PRECISION NULL,
  max_value     DOUBLE PRECISION NULL,
  sample_count  INT NOT NULL,
  anomaly_flags JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY(entity_id, asset_id, bucket_utc, sensor_type)
);

CREATE INDEX IF NOT EXISTS ix_ta15_asset_sensor_bucket
  ON telemetry_agg_15m(asset_id, sensor_type, bucket_utc DESC);

-- Door open is best stored as edge events; keep raw door_open in telemetry_raw as 0/1.
-- Optional: door episodes table built by worker (derived)
CREATE TABLE IF NOT EXISTS door_episodes (
  entity_id     TEXT NOT NULL,
  asset_id      UUID NOT NULL,
  open_ts       TIMESTAMPTZ NOT NULL,
  close_ts      TIMESTAMPTZ NOT NULL,
  open_seconds  INT NOT NULL,
  PRIMARY KEY(entity_id, asset_id, open_ts)
);

CREATE INDEX IF NOT EXISTS ix_door_episodes_asset_time
  ON door_episodes(asset_id, open_ts DESC);

-- Optional: learned baselines (derived, recalculated)
CREATE TABLE IF NOT EXISTS thermal_baselines (
  entity_id       TEXT NOT NULL,
  asset_id        UUID NOT NULL,
  baseline_start  TIMESTAMPTZ NOT NULL,
  baseline_end    TIMESTAMPTZ NOT NULL,
  tset_c_median   DOUBLE PRECISION NOT NULL,
  recovery_slope_c_per_min_median DOUBLE PRECISION NOT NULL,
  recovery_slope_c_per_min_p90    DOUBLE PRECISION NOT NULL,
  duty_cycle_median DOUBLE PRECISION NULL,
  cycles_per_hour_median DOUBLE PRECISION NULL,
  temp_stddev_24h_median DOUBLE PRECISION NOT NULL,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(entity_id, asset_id)
);

CREATE INDEX IF NOT EXISTS ix_thermal_baselines_asset
  ON thermal_baselines(asset_id);
