# PROVENIQ Ops — Master Plan v2.0

**Status:** Canonical  
**Date:** December 2024

---

## Architecture Overview

```
                          ┌─────────────────────────┐
                          │        USERS / OPS       │
                          │  (Scanning, Receiving,   │
                          │   Counting, Decisions)   │
                          └─────────────┬───────────┘
                                        │
                                        ▼
                         ┌──────────────────────────┐
                         │      PROVENIQ OPS         │
                         │  Inventory Truth Engine   │
                         │  • Measurement            │
                         │  • Vision (Obs Only)      │
                         │  • Waste / Transfers      │
                         │  • Evidence Capture       │
                         └─────────────┬────────────┘
                                       │
                                       ▼
                         ┌──────────────────────────┐
                         │        BISHOP             │
                         │  Decision Intelligence    │
                         │  • Forecasting            │
                         │  • Policy Gates           │
                         │  • Proposals              │
                         │  • Decision Memory        │
                         └───────┬───────┬──────────┘
                                 │       │
         ┌───────────────────────┘       └─────────────────────────┐
         ▼                                                         ▼
┌───────────────────────┐                             ┌───────────────────────┐
│     PROVENIQ BIDS     │                             │   PROVENIQ CLAIMSIQ   │
│  Excess → Liquidity   │                             │  Loss → Recovery      │
│  • Salvage Listings   │                             │  • Claim Packaging    │
│  • Auctions           │                             │  • Coverage Logic     │
│  • Recovery Value     │                             │  • Evidence Scoring   │
└───────────┬───────────┘                             └───────────┬───────────┘
            │                                                     │
            └───────────────┬─────────────────────────────────────┘
                            ▼
                    ┌──────────────────────────────────────────────┐
                    │            PROVENIQ CAPITAL                   │
                    │  Liquidity, Credit, Settlement, Ledger        │
                    │  • Cash Constraints                           │
                    │  • Asset Quality Scoring                      │
                    │  • Liquidation Settlement                     │
                    └──────────────────────────────────────────────┘
```

**The One Line:**
> Ops creates truth. Bishop creates intelligence. ClaimsIQ recovers losses. Bids unlocks dead capital. Capital controls the bloodstream.

---

## I. OPERATIONAL INTELLIGENCE CORE (The Nervous System)

### A. Inventory Measurement & Truth

| # | Feature | Description |
|---|---------|-------------|
| 1 | Discrete item tracking | Unit/each based |
| 2 | Bulk inventory tracking | Weight, volume, container-based |
| 3 | Base-unit normalization | g / ml / each |
| 4 | Handling units abstraction | bag, case, cambro, pan |
| 5 | Partial container handling | Ratio, weigh, volume |
| 6 | Measurement confidence scoring | Method-aware |
| 7 | Confidence-aware EOH | Effective On-Hand calculation |
| 8 | Multi-method measurement | Count × standard, net weight (tare-aware), vision-assisted volume, recipe-based depletion |
| 9 | Forced re-verification rules | Policy + confidence driven |

### B. Vision-Assisted Inventory (Safe AI)

| # | Feature | Description |
|---|---------|-------------|
| 1 | Container classification | Cambro, Lexan, hotel pans |
| 2 | Fill-level estimation | Ratio only |
| 3 | OCR for labels | Printed & handwritten |
| 4 | Item hint extraction | Non-authoritative |
| 5 | Density-gated conversion | Volume → mass |
| 6 | Component confidence tracking | Container, fill, OCR, identity, density |
| 7 | Vision observation-only | Never executes actions |
| 8 | Photo evidence storage | Audit, claims, disputes |

---

## II. INVENTORY FLOW & OPERATIONS (OPS)

### A. Receiving & Reconciliation

| # | Feature | Description |
|---|---------|-------------|
| 1 | Scan-at-dock receiving | |
| 2 | PO auto-reconciliation | |
| 3 | Short/overage/substitution detection | |
| 4 | Damage flagging | |
| 5 | Adjustment proposals | Approval-gated |
| 6 | Vendor dispute evidence capture | |

### B. Expiration, Waste & Loss

| # | Feature | Description |
|---|---------|-------------|
| 1 | Lot & expiration tracking | |
| 2 | 24/48/72 hour expiration windows | |
| 3 | Expiration Cascade Planner | Discount → Transfer → Donation → Disposal |
| 4 | Waste reason capture | |
| 5 | Waste autopsy protocol | Why loss occurred |
| 6 | Compliance-aware donation handling | |

### C. Transfers & Network Inventory

| # | Feature | Description |
|---|---------|-------------|
| 1 | Inter-location inventory visibility | |
| 2 | Multi-location imbalance detection | |
| 3 | Transfer cost modeling | |
| 4 | Transfer proposals | Approval-gated |
| 5 | Network-level stock optimization | |

---

## III. BISHOP — Predictive & Preventive Intelligence (The Brain)

### A. Demand & Stockout Intelligence

| # | Feature | Description |
|---|---------|-------------|
| 1 | Real-time burn-rate detection | |
| 2 | Historical usage modeling | 7/30/90 day |
| 3 | Seasonality-aware forecasting | |
| 4 | Confidence-aware stockout prediction | |
| 5 | Safety stock enforcement | |
| 6 | Predictive stockout alerts | |
| 7 | One-tap emergency reorder | Policy-gated |

### B. Passive Loss Prevention

| # | Feature | Description |
|---|---------|-------------|
| 1 | Ghost inventory detection | |
| 2 | Scan anomaly detection | Odd hours, sudden spikes, repeated scans |
| 3 | Shrinkage trend detection | |
| 4 | Chain-of-custody tracking | High-risk items |
| 5 | No-surveillance, no-blame design | |

---

## IV. FINANCIAL & PROFITABILITY INTELLIGENCE (OPS ⇄ CAPITAL)

### A. Cost & Margin Control

| # | Feature | Description |
|---|---------|-------------|
| 1 | Cost-per-serving calculation | |
| 2 | Recipe-to-inventory linkage | |
| 3 | Real-time margin tracking | |
| 4 | Margin compression alerts | |
| 5 | Menu profitability intelligence | |

### B. Cash-Aware Operations

| # | Feature | Description |
|---|---------|-------------|
| 1 | Ledger-integrated liquidity snapshot | Via Capital |
| 2 | Cash-flow–aware ordering | |
| 3 | Deferrable vs critical order classification | |
| 4 | True Cost of Delay modeling | |
| 5 | Order timing optimization | |

---

## V. VENDOR INTELLIGENCE (OPS ⇄ BIDS / CLAIMSIQ)

| # | Feature | Description |
|---|---------|-------------|
| 1 | Vendor price monitoring | |
| 2 | Cross-vendor SKU normalization | |
| 3 | Vendor price delta alerts | |
| 4 | Vendor reliability scoring | On-time, fill accuracy, substitution frequency, price volatility |
| 5 | Vendor switch recommendations | Approval-gated |
| 6 | Contract lock & constraint enforcement | |

---

## VI. DECISION INTELLIGENCE (THE MOAT)

### A. Bishop Decision System

| # | Feature | Description |
|---|---------|-------------|
| 1 | Unified Decision DAG | Enforced |
| 2 | Policy gates | Liquidity, criticality, approvals |
| 3 | Proposal-only generation | No silent execution |
| 4 | Explicit approval tokens | |
| 5 | Immutable decision trace IDs | |

### B. Advanced Decision Tools

| # | Feature | Description |
|---|---------|-------------|
| 1 | What-If Scenario Simulator | |
| 2 | Decision Memory | "What happened last time" |
| 3 | Explain-This engine | For every recommendation |
| 4 | Alternative-path comparison | |
| 5 | Confidence-aware recommendations | |

---

## VII. HUMAN PERFORMANCE & OPERATIONS INSIGHT

| # | Feature | Description |
|---|---------|-------------|
| 1 | Skill drift detection | By role/shift |
| 2 | Shift-level performance intelligence | |
| 3 | Receiving accuracy trends | |
| 4 | Counting variance trends | |
| 5 | Training recommendation signals | |
| 6 | No individual blame or surveillance framing | |

---

## VIII. AUDIT, COMPLIANCE & TRUST (OPS ⇄ CLAIMSIQ)

| # | Feature | Description |
|---|---------|-------------|
| 1 | Invisible audit readiness | |
| 2 | Continuous evidence completeness checks | |
| 3 | Missing documentation detection | |
| 4 | Approval & execution audit trails | |
| 5 | Inventory-as-insurance-evidence | |
| 6 | Claim-ready evidence packets | |
| 7 | Vendor dispute documentation | |

---

## IX. ECOSYSTEM BRIDGES (THE FLYWHEEL)

### A. OPS ⇄ CLAIMSIQ (Loss → Recovery)

| # | Feature | Description |
|---|---------|-------------|
| 1 | Loss-to-Claim auto-packaging | |
| 2 | Coverage-aware Ops alerts | |
| 3 | Required evidence prompts before disposal | |
| 4 | Claim outcome feedback into Ops handling rules | |

### B. OPS ⇄ BIDS (Excess → Liquidity)

| # | Feature | Description |
|---|---------|-------------|
| 1 | Salvage readiness scoring | |
| 2 | Condition grading & resale valuation | |
| 3 | Liquidation path optimization | Transfer → Discount → Donate → Auction |
| 4 | One-tap auction listing from Ops | |

### C. OPS ⇄ CAPITAL (Inventory → Cash)

| # | Feature | Description |
|---|---------|-------------|
| 1 | Inventory-backed liquidity signals | |
| 2 | Asset-quality scoring for lending | |
| 3 | Credit constraint feedback into ordering | |
| 4 | Liquidation → Ledger auto-settlement | |

---

## X. USER EXPERIENCE & OPERATOR TRUST

| # | Feature | Description |
|---|---------|-------------|
| 1 | Guided bulk-count flows | |
| 2 | Photo-first inventory capture | |
| 3 | Confidence transparency | Never hidden |
| 4 | Calm Mode vs Crisis Mode UI | |
| 5 | One-tap emergency actions | |
| 6 | Minimal data entry philosophy | |
| 7 | "Tell me what you see — Bishop does the math" | |

---

## XI. GOVERNANCE & SAFETY (NON-NEGOTIABLE)

| # | Rule | Enforcement |
|---|------|-------------|
| 1 | No execution without approval | Hard gate |
| 2 | No hallucinated quantities | Vision observation-only |
| 3 | No silent assumptions | Explicit confirmation required |
| 4 | No confidence masking | Always show uncertainty |
| 5 | Deterministic outputs only | No randomness |
| 6 | Immutable logs | Append-only |
| 7 | Reproducible decisions | Same input → same output |

---

## XII. PLATFORM & ENABLERS

| # | Feature | Description |
|---|---------|-------------|
| 1 | Multi-tenant architecture | |
| 2 | Location-aware policies | |
| 3 | Strict typing | Schema-first (Pydantic) |
| 4 | Versioned data contracts | |
| 5 | DAG-enforced execution order | |
| 6 | API-first, headless-ready | |
| 7 | Event-driven orchestration | |

---

## Feature Count Summary

| Section | Features |
|---------|----------|
| I. Inventory Measurement & Vision | 17 |
| II. Inventory Flow & Operations | 17 |
| III. Bishop Intelligence | 12 |
| IV. Financial Intelligence | 10 |
| V. Vendor Intelligence | 6 |
| VI. Decision Intelligence | 10 |
| VII. Human Performance | 6 |
| VIII. Audit & Compliance | 7 |
| IX. Ecosystem Bridges | 12 |
| X. User Experience | 7 |
| XI. Governance & Safety | 7 |
| XII. Platform Enablers | 7 |
| **TOTAL** | **118** |

---

*This is the canonical master plan. All development must comply.*
