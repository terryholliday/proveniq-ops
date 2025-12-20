# PROVENIQ Ops — Feature Alignment v2.0

**Status:** Implementation Tracking  
**Date:** December 2024  
**Master Plan:** `MASTER_PLAN_V2.md`  
**Total Features:** 118

---

## Progress Summary

| Section | Total | ✅ Done | 🟡 Partial | ❌ Not Started |
|---------|-------|---------|------------|----------------|
| I. Inventory Measurement & Vision | 17 | 0 | 2 | 15 |
| II. Inventory Flow & Operations | 17 | 0 | 1 | 16 |
| III. Bishop Intelligence | 12 | 1 | 0 | 11 |
| IV. Financial Intelligence | 10 | 0 | 0 | 10 |
| V. Vendor Intelligence | 6 | 0 | 1 | 5 |
| VI. Decision Intelligence | 10 | 1 | 0 | 9 |
| VII. Human Performance | 6 | 0 | 0 | 6 |
| VIII. Audit & Compliance | 7 | 0 | 0 | 7 |
| IX. Ecosystem Bridges | 12 | 0 | 0 | 12 |
| X. User Experience | 7 | 2 | 1 | 4 |
| XI. Governance | 7 | 2 | 1 | 4 |
| XII. Platform Enablers | 7 | 3 | 2 | 2 |
| **TOTAL** | **118** | **9** | **8** | **101** |

**Overall Progress:** ~14% (17/118 features started)

---

## I. OPERATIONAL INTELLIGENCE CORE (The Nervous System)

### A. Inventory Measurement & Truth

| # | Feature | Status | Implementation |
|---|---------|--------|----------------|
| 1 | Discrete item tracking (unit/each) | 🟡 | Barcode scanner exists, no DB |
| 2 | Bulk inventory tracking (weight/volume) | ❌ | |
| 3 | Base-unit normalization (g/ml/each) | ❌ | |
| 4 | Handling units abstraction (bag/case/cambro) | ❌ | |
| 5 | Partial container handling | ❌ | |
| 6 | Measurement confidence scoring | ❌ | |
| 7 | Confidence-aware EOH | ❌ | |
| 8 | Multi-method measurement | ❌ | |
| 9 | Forced re-verification rules | ❌ | |

### B. Vision-Assisted Inventory (Safe AI)

| # | Feature | Status | Implementation |
|---|---------|--------|----------------|
| 1 | Container classification | ❌ | |
| 2 | Fill-level estimation (ratio) | ❌ | |
| 3 | OCR for labels | ❌ | |
| 4 | Item hint extraction | ❌ | |
| 5 | Density-gated volume→mass | ❌ | |
| 6 | Component confidence tracking | ❌ | |
| 7 | Vision observation-only | ✅ | Design enforced |
| 8 | Photo evidence storage | 🟡 | Camera exists, storage not connected |

---

## II. INVENTORY FLOW & OPERATIONS

### Receiving & Reconciliation

| Feature | Status | Notes |
|---------|--------|-------|
| **Scan-at-dock receiving** | ❌ Not Started | |
| **PO auto-reconciliation** | ❌ Not Started | |
| **Short/overage/substitution detection** | ❌ Not Started | |
| **Damage flagging** | ❌ Not Started | |
| **Adjustment proposals** | ❌ Not Started | Approval-gated |
| **Vendor dispute evidence** | ❌ Not Started | |

### Expiration & Waste

| Feature | Status | Notes |
|---------|--------|-------|
| **Lot & expiration tracking** | ❌ Not Started | |
| **24/48/72h expiration windows** | ❌ Not Started | |
| **Expiration Cascade Planner** | ❌ Not Started | Discount/Transfer/Donate/Dispose |
| **Waste reason capture** | ❌ Not Started | |
| **Waste autopsy protocol** | ❌ Not Started | |
| **Compliance-aware donation** | ❌ Not Started | |

### Transfers & Network

| Feature | Status | Notes |
|---------|--------|-------|
| **Inter-location visibility** | 🟡 Partial | Multi-location auth exists |
| **Imbalance detection** | ❌ Not Started | |
| **Transfer cost modeling** | ❌ Not Started | |
| **Transfer proposals** | ❌ Not Started | |
| **Network optimization** | ❌ Not Started | |

---

## III. PREDICTIVE & PREVENTIVE INTELLIGENCE (BISHOP CORE)

### Demand & Stockout Intelligence

| Feature | Status | Notes |
|---------|--------|-------|
| **Real-time burn-rate detection** | ❌ Not Started | |
| **Historical usage modeling** | ❌ Not Started | 7/30/90d |
| **Seasonality-aware forecasting** | ❌ Not Started | |
| **Confidence-aware stockout prediction** | ❌ Not Started | |
| **Safety stock enforcement** | ❌ Not Started | |
| **Predictive stockout alerts** | ❌ Not Started | |
| **One-tap emergency reorder** | ❌ Not Started | Policy-gated |

### Loss Prevention (Passive)

| Feature | Status | Notes |
|---------|--------|-------|
| **Ghost inventory detection** | ❌ Not Started | |
| **Scan anomaly detection** | ❌ Not Started | Odd hours/spikes/repeats |
| **Shrinkage trend detection** | ❌ Not Started | |
| **Chain-of-custody tracking** | ❌ Not Started | High-risk items |

---

## IV. FINANCIAL & PROFITABILITY INTELLIGENCE

### Cost & Margin Control

| Feature | Status | Notes |
|---------|--------|-------|
| **Cost-per-serving calculation** | ❌ Not Started | |
| **Recipe-to-inventory linking** | ❌ Not Started | |
| **Real-time margin tracking** | ❌ Not Started | |
| **Margin compression alerts** | ❌ Not Started | |
| **Menu profitability insights** | ❌ Not Started | |

### Cash-Aware Operations

| Feature | Status | Notes |
|---------|--------|-------|
| **Ledger-integrated liquidity** | ❌ Not Started | Hook to PROVENIQ Ledger |
| **Cash-flow–aware ordering** | ❌ Not Started | |
| **Deferrable vs critical classification** | ❌ Not Started | |
| **True Cost of Delay modeling** | ❌ Not Started | |
| **Order timing optimization** | ❌ Not Started | |

---

## V. VENDOR INTELLIGENCE

| Feature | Status | Notes |
|---------|--------|-------|
| **Vendor price monitoring** | ❌ Not Started | |
| **Cross-vendor SKU normalization** | ❌ Not Started | |
| **Vendor price delta alerts** | ❌ Not Started | |
| **Vendor reliability scoring** | ❌ Not Started | On-time/fill/substitution/volatility |
| **Vendor switch recommendations** | ❌ Not Started | Approval-gated |
| **Contract lock enforcement** | ❌ Not Started | |
| **Vendor account storage** | 🟡 Partial | Onboarding collects, backend not connected |

---

## VI. DECISION INTELLIGENCE (THE MOAT)

### Bishop Decision System

| Feature | Status | Notes |
|---------|--------|-------|
| **Bishop FSM** | ✅ Built | IDLE→SCANNING→ANALYZING→CHECKING→QUEUED |
| **Unified Decision DAG** | ❌ Not Started | Enforced execution order |
| **Policy gates** | ❌ Not Started | Liquidity/criticality/approvals |
| **Proposal-only generation** | ❌ Not Started | No silent execution |
| **Explicit approval tokens** | ❌ Not Started | |
| **Immutable decision trace IDs** | ❌ Not Started | |

### Advanced Decision Tools

| Feature | Status | Notes |
|---------|--------|-------|
| **What-If Scenario Simulator** | ❌ Not Started | |
| **Decision Memory** | ❌ Not Started | "What happened last time" |
| **Explain-This engine** | ❌ Not Started | |
| **Alternative-path comparison** | ❌ Not Started | |
| **Confidence-aware recommendations** | ❌ Not Started | |

---

## VII. HUMAN PERFORMANCE & OPERATIONS INSIGHT

| Feature | Status | Notes |
|---------|--------|-------|
| **Skill drift detection** | ❌ Not Started | By role/shift |
| **Shift-level performance** | ❌ Not Started | |
| **Receiving accuracy trends** | ❌ Not Started | |
| **Counting variance trends** | ❌ Not Started | |
| **Training recommendation signals** | ❌ Not Started | |

---

## VIII. AUDIT, COMPLIANCE & TRUST

| Feature | Status | Notes |
|---------|--------|-------|
| **Invisible audit readiness** | ❌ Not Started | |
| **Evidence completeness checks** | ❌ Not Started | |
| **Missing documentation detection** | ❌ Not Started | |
| **Approval & execution trails** | ❌ Not Started | |
| **Inventory as insurance evidence** | ❌ Not Started | |
| **Claim-ready evidence packets** | ❌ Not Started | Link to ClaimsIQ |
| **Vendor dispute documentation** | ❌ Not Started | |

---

## IX. ECOSYSTEM BRIDGES (THE FLYWHEEL)

### A. OPS ⇄ CLAIMSIQ (Loss → Recovery)

| # | Feature | Status | Implementation |
|---|---------|--------|----------------|
| 1 | Loss-to-Claim auto-packaging | ❌ | |
| 2 | Coverage-aware Ops alerts | ❌ | |
| 3 | Required evidence prompts before disposal | ❌ | |
| 4 | Claim outcome feedback into Ops rules | ❌ | |

### B. OPS ⇄ BIDS (Excess → Liquidity)

| # | Feature | Status | Implementation |
|---|---------|--------|----------------|
| 1 | Salvage readiness scoring | ❌ | |
| 2 | Condition grading & resale valuation | ❌ | |
| 3 | Liquidation path optimization | ❌ | Transfer→Discount→Donate→Auction |
| 4 | One-tap auction listing from Ops | ❌ | |

### C. OPS ⇄ CAPITAL (Inventory → Cash)

| # | Feature | Status | Implementation |
|---|---------|--------|----------------|
| 1 | Inventory-backed liquidity signals | ❌ | |
| 2 | Asset-quality scoring for lending | ❌ | |
| 3 | Credit constraint feedback into ordering | ❌ | |
| 4 | Liquidation → Ledger auto-settlement | ❌ | |

---

## X. USER EXPERIENCE & OPERATOR TRUST

| Feature | Status | Notes |
|---------|--------|-------|
| **Guided bulk-count flows** | ❌ Not Started | |
| **Photo-first inventory capture** | 🟡 Partial | Camera exists |
| **Confidence transparency** | ❌ Not Started | Never hidden |
| **Calm Mode vs Crisis Mode UI** | ❌ Not Started | |
| **One-tap emergency actions** | ❌ Not Started | |
| **Minimal data entry** | ✅ Built | Barcode-first design |
| **"Tell me what you see"** | ❌ Not Started | AI-assisted entry |

---

## XI. GOVERNANCE & SAFETY (NON-NEGOTIABLE)

| Feature | Status | Notes |
|---------|--------|-------|
| **No execution without approval** | 🟡 Partial | Role system designed, not enforced |
| **No AI hallucinated quantities** | ✅ Design | Vision is observation-only |
| **No silent assumptions** | ❌ Not Started | Needs explicit confirmation |
| **No confidence masking** | ❌ Not Started | Always show uncertainty |
| **Deterministic outputs only** | ✅ Built | Bishop FSM is deterministic |
| **Immutable logs** | ❌ Not Started | |
| **Reproducible decisions** | ❌ Not Started | |

---

## XII. TECHNICAL PLATFORM (ENABLERS)

| Feature | Status | Notes |
|---------|--------|-------|
| **Multi-tenant architecture** | 🟡 Partial | Auth/org structure exists |
| **Location-aware policies** | 🟡 Partial | Location selection exists |
| **Strict typing (Pydantic)** | ✅ Built | Backend uses Pydantic |
| **Versioned data contracts** | ❌ Not Started | |
| **DAG-enforced execution** | ❌ Not Started | |
| **API-first, headless-ready** | ✅ Built | FastAPI backend |
| **Event-driven orchestration** | ❌ Not Started | |

---

## WHAT'S BUILT (Current State)

### Backend (proveniq-ops/backend)
- ✅ FastAPI scaffolding
- ✅ Bishop FSM service (state machine)
- ✅ Scan service (mock vision)
- ✅ Vendor service (SYSCO/US Foods mock)
- ✅ Shrinkage service (detection/classification)
- ✅ Pydantic schemas
- ✅ SQLAlchemy models
- ✅ Alembic migration

### Mobile App (proveniq-ops/mobile)
- ✅ Expo/React Native shell
- ✅ Zustand state management
- ✅ Barcode scanner (expo-camera)
- ✅ Bishop FSM display
- ✅ Auth flow (login/logout)
- ✅ Location selection
- ✅ Business type selection
- ✅ 7-step onboarding flow
- ✅ FAQ screen
- ✅ Settings screen
- ✅ Theme system

### Documentation
- ✅ User Guide
- ✅ FAQ content
- ✅ Technical spec (needs update)

---

## RECOMMENDED ROADMAP

### Phase 1: Foundation (Current → Q1)
**Goal:** Working inventory scan with persistence

1. Connect scanner to backend API
2. Implement item CRUD
3. Basic inventory list/search
4. Par level storage
5. Simple below-par alerts

### Phase 2: Vendor Integration (Q1)
**Goal:** Working orders to real vendors

1. SYSCO API integration
2. US Foods API integration
3. Order creation flow
4. Approval workflow (role-based)
5. Order history

### Phase 3: Bishop Intelligence (Q2)
**Goal:** Predictive ordering, shrinkage detection

1. Burn-rate calculation
2. Stockout prediction
3. Reorder recommendations
4. Shrinkage reporting
5. Decision trace logging

### Phase 4: Decision DAG (Q2-Q3)
**Goal:** The Moat - Policy-enforced decisions

1. DAG execution engine
2. Policy gates (liquidity, criticality)
3. Approval tokens
4. What-If simulator
5. Explain-This engine

### Phase 5: Ecosystem (Q3-Q4)
**Goal:** Network effects

1. PROVENIQ Ledger integration
2. ClaimsIQ integration
3. Peer benchmarking
4. Multi-location optimization

---

## IMMEDIATE NEXT STEPS

1. **Connect mobile → backend** — API calls for scan data
2. **Implement item persistence** — Store scanned items
3. **Build inventory list screen** — View all items
4. **Add par level input** — Set reorder points
5. **Create order draft flow** — Generate orders from below-par items

---

**Key Insight:** The mobile shell and Bishop FSM are built. The gap is **data persistence and vendor API integration**. Once items persist and orders flow to vendors, the intelligence layer can be layered on top.

---

*This document should be updated as features are completed.*
