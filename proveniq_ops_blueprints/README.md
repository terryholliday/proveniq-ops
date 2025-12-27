# PROVENIQ Ops — Code-Grade Blueprints (Gold Master)

Version: V1.3.1 (Blueprint Pack)
Date: 2025-12-26
Owner: Terry

This pack turns the V1.3.1 Gold Master spec into implementation-ready engineering artifacts:
- Service boundaries
- Data model (Postgres)
- Event store & projections
- Telemetry store & downsampling
- Evidence store contract
- Ledger polling contract + sweeper
- Bishop recommendation loop
- Cryptographic integrity (hash chain + signatures)
- RBAC enforcement at the **event layer**
- Idempotency for `/events`
- Outbox + webhook delivery guarantees
- Threat model & incident playbooks
- OpenAPI skeleton + JSON Schemas
- CI guardrails (lint/test/migrate)

---

## 0) Non-Negotiables (Build Constraints)

### Scope Guard
PROVENIQ Ops MUST NOT implement:
- currency math, pricing, valuation
- payments/settlement/treasury
- GL/accounting
- claims adjudication
- auctions/bidding
- loan origination/repayment math

Ops MAY store opaque financial references:
- `ledger_ref_id`
- `sync_status`
- `finance_lock_status` (flags only)

### Truth Model
- **Event Store** is the only source of truth (append-only).
- **Projections** are derived and rebuildable.
- **Telemetry** is non-authoritative and must never reconstruct truth.
- **Evidence** required by policy per event.

### Crypto Integrity
- canonical JSON serialization
- `event_hash = sha256(canonical_payload + prev_hash + evidence_hash)`
- Ed25519 signature per event
- chain break => `CORRUPTED` + read-only

---

## 1) Reference Architecture

### Services (minimal, production-safe)
1. **ops-api** (FastAPI)
   - AuthN/AuthZ
   - Commands: append events
   - Queries: projections / lineage
2. **ops-worker**
   - Projection builder (CQRS read model)
   - Webhook outbox dispatcher
   - Ledger reconciliation sweeper
   - Telemetry downsampling jobs
3. **telemetry-ingest** (optional split; can live in ops-api initially)
   - High frequency ingest endpoint (writes to telemetry tables only)
4. **bishop** (system actor; can run inside ops-worker initially)
   - Reads telemetry + projections
   - Emits recommendation events only

### Data Stores
- Postgres (authoritative): event_store, projections, outbox, evidence_index
- Postgres (same instance OK): telemetry tables + downsample tables (partitioned)
- Object storage (S3-compatible): evidence blobs
- Redis (optional): idempotency cache + rate limiting
- Message bus (optional): outbox to Kafka/NATS (can start with DB outbox + HTTP delivery)

---

## 2) Repo Layout (Scaffold)

```
proveniq-ops/
  apps/
    ops_api/
      main.py
      routers/
      auth/
      domain/
      projections/
      crypto/
      storage/
    ops_worker/
      worker.py
      jobs/
      projections.py
      ledger_sweeper.py
      telemetry_downsample.py
      outbox_dispatcher.py
      bishop.py
  contracts/
    openapi.yaml
    event_types.json
    rbac.yaml
    json_schemas/
      base_event.schema.json
      asset_loss_reported.schema.json
      recommendation_accepted.schema.json
      security_waiver_granted.schema.json
    mermaid/
      telemetry_bishop_event_flow.mmd
  db/
    schema.sql
    migrations/  (alembic)
  infra/
    docker-compose.yml
    Dockerfile.ops_api
    Dockerfile.ops_worker
  ci/
    github-actions.yml
  README.md
```

---

## 3) Implementation Spec: Core Tables

See `db/schema.sql` for exact DDL.

### Tables (authoritative)
- `event_store` (append-only)
- `asset_projection` (current state)
- `asset_lineage_index` (optional helper for pagination)
- `evidence_objects` (metadata + hashes only, no blobs)
- `telemetry_raw` (partitioned by day)
- `telemetry_agg_1m`, `telemetry_agg_15m`
- `idempotency_keys`
- `outbox_webhooks`
- `ledger_sync_state`
- `security_incidents` (optional but recommended)

---

## 4) Command Path: POST /v1/ops/assets/{id}/events

### Steps (server MUST enforce)
1. AuthN -> derive `entity_id` from token (never trust header)
2. Validate event_type in registry
3. Validate emitter class + RBAC (role -> allowed event)
4. Validate evidence policy
5. Validate optimistic concurrency (`If-Match` == current aggregate_version)
6. Enforce idempotency (Idempotency-Key)
7. Build canonical payload
8. Compute event_hash with prev_hash + evidence_hash
9. Sign event (Ed25519)
10. Append to `event_store`
11. Update projections (sync or async)
12. Insert outbox webhook records (same tx)
13. Return response with new version + event_hash

---

## 5) Ledger Reconciliation Sweeper (bounded)

See `apps/ops_worker/jobs/ledger_sweeper.py` skeleton.

Rules:
- scan assets with `sync_status = WAITING_FOR_LEDGER` and `locked_at < now()-1h`
- poll `GET /ledger/v1/status/{ledger_ref_id}` every 15m
- max 5 attempts
- verify ledger signature
- emit `LOSS_AUTHORIZED | LOSS_DENIED` (as LEDGER_EXTERNAL) only if verified, else `LEDGER_SYNC_FAILED`

---

## 6) Telemetry Policy Implementation

### Retention
- Raw: keep 24h
- 1m aggregates: keep 7d
- 15m aggregates: keep 30d
- purge >30d

### Downsampling
- aggregates store avg/min/max/count + anomaly flags
- never becomes an Ops truth event without a human/system acceptance event

---

## 7) Bishop Action Loop

Bishop produces:
- `RECOMMENDATION_EMITTED` (SYSTEM:bishop)
A human/authorized system produces:
- `RECOMMENDATION_ACCEPTED` or `RECOMMENDATION_REJECTED`

Bishop must never write material events.

---

## 8) CI Guardrails (must pass)
- formatting + lint (ruff/black)
- typecheck (mypy)
- unit tests
- migration checks
- contract checks:
  - event_type registry enumerations match schemas
  - RBAC matrix contains all event types
  - OpenAPI validates

---

## 9) How to Use This Pack
1. Start from the DDL in `db/schema.sql`
2. Implement event append path with strict validators
3. Implement worker jobs: projections, outbox dispatch, sweeper, downsample
4. Lock CI to fail on any missing policy checks
