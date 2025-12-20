# PROVENIQ Ops — Technical Specification (v1.1)

**Product Name:** PROVENIQ Ops  
**Internal Codename:** "Landlord Vector"  
**Goal:** Zero-CAC tenant acquisition via free B2B landlord tools  
**Status:** LOCKED (Ready for Engineering)

---

## 1. Tech Stack & Architecture

| Layer | Technology | Notes |
|-------|------------|-------|
| **Backend** | FastAPI (Python 3.10+) | Async-first |
| **Database** | PostgreSQL (Cloud SQL) | SQLAlchemy 2.0 (Async) |
| **Driver** | `asyncpg` | **CRITICAL:** Prevents event loop blocking |
| **Auth** | Firebase Auth + `firebase-admin` SDK | Server-side verification |
| **Storage** | Google Cloud Storage / S3 | Presigned URLs |
| **Frontend** | React Native (Tenant) / React Admin (Landlord) | — |

### Auth Policy (P0 - CRITICAL)

> **The API never mints JWTs. It verifies Magic Links/Credentials and issues Firebase Custom Tokens. The Client SDK exchanges these for JWTs.**

---

## 2. Core Feature Set

### A. Authentication & Security (P0 - Critical)

#### JWT Enforcement
Middleware must verify Firebase JWT on every protected request.

#### RBAC & Ownership Guardrails

| Role | Access Scope |
|------|--------------|
| `LANDLORD_ADMIN` | Strictly scoped to properties within their `organization_id` |
| `TENANT` | Strictly scoped to inspections linked to their active lease |

**Rule:** No cross-tenant or cross-landlord reads are permitted under any circumstance.

#### Magic Link Handshake

```
Endpoint: /auth/exchange-token
Logic: Verifies magic token string 
       → Returns Firebase Custom Token 
       → Client completes auth with Firebase
```

---

### B. Landlord Endpoints (`/landlord`)

| Feature | Endpoint | Method | Notes |
|---------|----------|--------|-------|
| **Properties** | `/properties` | GET/POST | Create/List buildings |
| **Units** | `/properties/{id}/units` | POST | Bulk create units supported |
| **Tenant CSV Upload** | `/upload-tenants` | POST | Idempotency Required. Matches on `email + unit_id` |
| **Lease Management** | `/leases` | POST | Links Tenant to Unit. Sets state to `DRAFT` |
| **Invite Tenant** | `/leases/{id}/invite` | POST | Generates magic link (`proveniq://auth?token=...`) + email |
| **Checklist Config** | `/properties/{id}/checklist` | PUT | Define default rooms/items for new inspections |

---

### C. Tenant Endpoints (`/tenant`)

| Feature | Endpoint | Method | Notes |
|---------|----------|--------|-------|
| **List Inspections** | `/inspections` | GET | Filter by status |
| **Start Inspection** | `/inspections` | POST | Creates `DRAFT`. Blocking UX: Tenant cannot skip "Move-In" unless disabled by landlord |
| **Upload Evidence** | `/inspections/{id}/evidence` | POST | Request Presigned Upload URL (PUT) |
| **Confirm Evidence** | `/inspections/{id}/evidence/confirm` | POST | **Required.** Validate upload existence, size, MIME. Compute hash. Link to Item |
| **Submit Inspection** | `/inspections/{id}/submit` | POST | Locks inspection, calculates hash, transitions to `SUBMITTED` |
| **Maintenance** | `/maintenance` | GET/POST | Create ticket. Optional: Link to `inventory_item` |

---

## 3. Data Model & State Machines (The "Legal Anchor")

### A. Lease Lifecycle

```typescript
enum LeaseStatus {
  DRAFT       = "draft",       // Created, tenant not invited
  PENDING     = "pending",     // Invite sent
  ACTIVE      = "active",      // Tenant moved in
  TERMINATING = "terminating", // Move-out notice given
  ENDED       = "ended",       // Move-out inspection SIGNED or landlord-forced termination
  DISPUTED    = "disputed"     // Deposit withheld/contested
}
```

**State Transitions:**
```
DRAFT → PENDING → ACTIVE → TERMINATING → ENDED
                    ↓                        ↓
                DISPUTED ←───────────────────┘
```

---

### B. Inspection Lifecycle & Versioning

```typescript
enum InspectionStatus {
  DRAFT     = "draft",     // Tenant adding photos/notes
  SUBMITTED = "submitted", // Locked by Tenant, waiting for Landlord
  REVIEWED  = "reviewed",  // (Optional) Landlord acknowledged without objection
  SIGNED    = "signed",    // Final state. Cryptographically finalized.
  ARCHIVED  = "archived"   // Superseded (only if correction required)
}
```

**State Transitions:**
```
DRAFT → SUBMITTED → REVIEWED → SIGNED
                        ↓
                    ARCHIVED (if correction needed)
```

#### Schema Requirements

| Field | Type | Notes |
|-------|------|-------|
| `type` | ENUM | `MOVE_IN` \| `MOVE_OUT` \| `PERIODIC` |
| `schema_version` | INT NOT NULL DEFAULT 1 | Handles future checklist/hash logic changes |
| `supplemental_to_inspection_id` | UUID (Nullable) | Points to parent if this is a correction |

---

### C. The Hash Scope (Canonical Definition)

> **Strict adherence required to prevent hash drift.**

The `content_hash` SHALL be calculated from a canonical, ordered JSON structure including:

```json
{
  "inspection_id": "uuid",
  "lease_id": "uuid",
  "inspection_type": "MOVE_IN|MOVE_OUT|PERIODIC",
  "schema_version": 1,
  "items": [
    {
      "room_name": "string",
      "item_name": "string",
      "condition": "GOOD|FAIR|DAMAGED|MISSING",
      "notes": "string",
      "evidence": [
        {
          "url": "string",
          "hash": "sha256",
          "mime_type": "string",
          "timestamp": "ISO8601"
        }
      ]
    }
  ],
  "submitted_at": "ISO8601"
}
```

**Rule:** Any change to this structure invalidates the hash and requires a new inspection record.

---

## 4. The "Trojan Horse" Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. INGESTION                                                     │
│    Landlord uploads CSV → System creates Unit/Tenant/Lease       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. ACTIVATION                                                    │
│    Landlord invites → Tenant receives Magic Link                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. CAPTURE (BLOCKING)                                            │
│    Tenant logs in → App enforces "Move-In Inspection Required"   │
│    By default, tenants cannot dismiss this screen                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. EVIDENCE                                                      │
│    App gets Presigned URL → Uploads to Cloud                     │
│    App calls POST .../evidence/confirm                           │
│    API validates & links evidence to inspection item             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. LOCK                                                          │
│    Tenant clicks "Sign"                                          │
│    API calculates content_hash                                   │
│    State → SUBMITTED                                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. CONVERSION                                                    │
│    App displays: "Condition Report Secure. Protect your items?"  │
│    → Triggers PROVENIQ Home Onboarding                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Implementation Roadmap

### Phase 1: The Trust Core (Critical Path)

| Priority | Feature | Description |
|----------|---------|-------------|
| P0 | **Inspection Locking + Hash Contract** | Implement the Canonical Hash logic first |
| P0 | **Auth & Roles** | Implement Firebase Admin middleware + Custom Token exchange |
| P0 | **Image Pipeline** | Presigned URLs + Confirmation Endpoint |
| P0 | **Invite System** | Magic Link logic |

### Phase 2: The Activation Engine (Public Launch)

| Priority | Feature | Description |
|----------|---------|-------------|
| P1 | **Tenant Mobile App** | React Native MVP |
| P1 | **Lease-Scoped Diff Engine** | Logic to compare `MOVE_IN` vs `MOVE_OUT` for same `lease_id` |
| P1 | **PROVENIQ Home Webhook** | The business logic trigger |

### Phase 3: Scale & Monetization

| Priority | Feature | Description |
|----------|---------|-------------|
| P2 | **Organizations** | Enable multi-agent access |
| P2 | **Stripe Integration** | Billing |
| P2 | **Ledger Integration** | Write `content_hash` to blockchain |

---

## 6. SQL DDL (Updated Schema)

```sql
-- Enums
CREATE TYPE lease_status AS ENUM (
  'draft', 'pending', 'active', 'terminating', 'ended', 'disputed'
);

CREATE TYPE inspection_type AS ENUM (
  'MOVE_IN', 'MOVE_OUT', 'PERIODIC'
);

CREATE TYPE inspection_status AS ENUM (
  'draft', 'submitted', 'reviewed', 'signed', 'archived'
);

CREATE TYPE item_condition AS ENUM (
  'GOOD', 'FAIR', 'DAMAGED', 'MISSING'
);

-- Organizations (for multi-landlord support)
CREATE TABLE organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users (Landlords & Tenants)
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  firebase_uid VARCHAR(128) UNIQUE,
  organization_id UUID REFERENCES organizations(id),
  email VARCHAR(255) NOT NULL UNIQUE,
  role VARCHAR(50) NOT NULL CHECK (role IN ('LANDLORD_ADMIN', 'TENANT', 'LANDLORD_AGENT')),
  full_name VARCHAR(255),
  phone VARCHAR(50),
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Properties
CREATE TABLE properties (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  landlord_id UUID NOT NULL REFERENCES users(id),
  name VARCHAR(255),
  address VARCHAR(500) NOT NULL,
  city VARCHAR(100) NOT NULL,
  state VARCHAR(50) NOT NULL,
  zip_code VARCHAR(20) NOT NULL,
  default_checklist JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Units
CREATE TABLE units (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  unit_number VARCHAR(50) NOT NULL,
  status VARCHAR(20) DEFAULT 'VACANT',
  bedrooms INT,
  bathrooms FLOAT,
  square_feet INT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (property_id, unit_number)
);

-- Leases (Updated with new statuses)
CREATE TABLE leases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  unit_id UUID NOT NULL REFERENCES units(id) ON DELETE CASCADE,
  tenant_id UUID NOT NULL REFERENCES users(id),
  status lease_status NOT NULL DEFAULT 'draft',
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  security_deposit_cents INT,
  magic_token VARCHAR(255) UNIQUE,
  magic_token_expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Inspections (Updated with hash + versioning)
CREATE TABLE inspections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lease_id UUID NOT NULL REFERENCES leases(id) ON DELETE CASCADE,
  type inspection_type NOT NULL,
  status inspection_status NOT NULL DEFAULT 'draft',
  schema_version INT NOT NULL DEFAULT 1,
  supplemental_to_inspection_id UUID REFERENCES inspections(id),
  content_hash VARCHAR(64),  -- SHA-256 hex
  signed_at TIMESTAMPTZ,
  signature_hash VARCHAR(255),
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  submitted_at TIMESTAMPTZ
);

-- Inspection Items
CREATE TABLE inspection_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inspection_id UUID NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
  room_name VARCHAR(100) NOT NULL,
  item_name VARCHAR(255),
  condition item_condition NOT NULL DEFAULT 'GOOD',
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Inspection Evidence (NEW - explicit evidence tracking)
CREATE TABLE inspection_evidence (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inspection_item_id UUID NOT NULL REFERENCES inspection_items(id) ON DELETE CASCADE,
  storage_url VARCHAR(500) NOT NULL,
  file_hash VARCHAR(64) NOT NULL,  -- SHA-256 of file content
  mime_type VARCHAR(100) NOT NULL,
  file_size_bytes BIGINT NOT NULL,
  uploaded_at TIMESTAMPTZ DEFAULT NOW(),
  confirmed_at TIMESTAMPTZ  -- NULL until confirmation endpoint called
);

-- Magic Link Tokens
CREATE TABLE magic_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lease_id UUID NOT NULL REFERENCES leases(id),
  token VARCHAR(255) NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX ix_users_firebase_uid ON users(firebase_uid);
CREATE INDEX ix_users_organization ON users(organization_id);
CREATE INDEX ix_properties_organization ON properties(organization_id);
CREATE INDEX ix_leases_tenant ON leases(tenant_id);
CREATE INDEX ix_leases_status ON leases(status);
CREATE INDEX ix_inspections_lease ON inspections(lease_id);
CREATE INDEX ix_inspections_status ON inspections(status);
```

---

## 7. API Contracts

### A. Magic Link Exchange

```http
POST /auth/exchange-token
Content-Type: application/json

{
  "magic_token": "abc123..."
}
```

**Response (Success):**
```json
{
  "firebase_custom_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "lease_id": "uuid",
  "tenant_id": "uuid"
}
```

### B. Evidence Upload Flow

**Step 1: Request Presigned URL**
```http
POST /tenant/inspections/{inspection_id}/evidence
Authorization: Bearer {firebase_jwt}

{
  "inspection_item_id": "uuid",
  "file_name": "kitchen_fridge.jpg",
  "content_type": "image/jpeg",
  "file_size_bytes": 2048576
}
```

**Response:**
```json
{
  "evidence_id": "uuid",
  "upload_url": "https://storage.googleapis.com/...",
  "expires_in_seconds": 3600
}
```

**Step 2: Client uploads to presigned URL (PUT)**

**Step 3: Confirm Upload**
```http
POST /tenant/inspections/{inspection_id}/evidence/confirm
Authorization: Bearer {firebase_jwt}

{
  "evidence_id": "uuid"
}
```

**Response:**
```json
{
  "confirmed": true,
  "file_hash": "sha256:abc123...",
  "mime_type": "image/jpeg"
}
```

### C. Submit Inspection (Locking)

```http
POST /tenant/inspections/{inspection_id}/submit
Authorization: Bearer {firebase_jwt}

{
  "signature_hash": "user_provided_signature_hash"
}
```

**Response:**
```json
{
  "inspection_id": "uuid",
  "status": "submitted",
  "content_hash": "sha256:def456...",
  "submitted_at": "2024-12-19T12:00:00Z"
}
```

---

## 8. Legal & Privacy Directives

### Disclaimer
PROVENIQ does not provide insurance, escrow, or financial guarantees. The system provides evidence and documentation only.

### Naming
Feature is **"Deposit Evidence Package"**, not "Shield."

### Data Custody

| Data Type | Owner | Custodian |
|-----------|-------|-----------|
| Property Data | Landlord | PROVENIQ |
| Personal Property Evidence | Tenant | PROVENIQ |

### Immutability Rule
`SIGNED` inspections are **read-only**. Corrections require a new supplemental inspection record linked via `supplemental_to_inspection_id`.

---

## 9. Observability Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| `inspection_submit_latency_ms` | Time from submit request to hash calculation complete | < 500ms |
| `evidence_confirm_rate` | % of uploaded evidence that gets confirmed | > 95% |
| `magic_link_conversion_rate` | % of sent invites that complete auth | > 60% |
| `move_in_completion_rate` | % of tenants completing move-in inspection | > 80% |
| `home_conversion_rate` | % of tenants who onboard to PROVENIQ Home | > 25% |

---

**END OF SPECIFICATION**
