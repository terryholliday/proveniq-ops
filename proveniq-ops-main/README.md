# PROVENIQ Ops

**B2B Inventory & Operations Management Platform**

> Synthetic Precision — faster than human perception, anticipatory rather than reactive.

## Architecture

```
proveniq-ops/
├── backend/                 # FastAPI Python backend
│   ├── app/
│   │   ├── api/            # API route handlers
│   │   ├── core/           # Core configuration
│   │   ├── db/             # Database models & connection
│   │   ├── models/         # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   │   ├── bishop/     # Bishop FSM intelligence
│   │   │   ├── vendor/     # Vendor Bridge engine
│   │   │   └── mocks/      # Mock external systems
│   │   └── main.py
│   ├── requirements.txt
│   └── .env.example
├── mobile/                  # React Native (Expo) app
│   └── [future scope]
└── docs/
    └── schema.sql          # Authoritative DB schema
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI, Pydantic |
| Database | PostgreSQL (Supabase), SQLAlchemy async |
| Mobile | React Native (Expo), expo-camera |
| State | Zustand (mobile), FSM (Bishop) |

## Bishop AI

Bishop is a **deterministic Finite State Machine**, not a chatbot.

### States
- `IDLE` — Awaiting input
- `SCANNING` — Inventory capture in progress
- `ANALYZING_RISK` — ClaimsIQ risk evaluation
- `CHECKING_FUNDS` — Ledger balance verification
- `ORDER_QUEUED` — Order dispatched to vendor

### Behavior
- Emotionless, polite, hyper-competent
- Never verbose or speculative
- Always declarative and actionable

## Quick Start

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

## External System Mocks

| System | Purpose | Status |
|--------|---------|--------|
| Ledger | Cash & liquidity | Mocked |
| ClaimsIQ | Risk & liability | Mocked |
| Capital | Inventory financing | Future hook |

---

**PROVENIQ** — Operational Intelligence Layer
