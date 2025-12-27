# PROVENIQ Ops — Thermal Guardian (Walk-in/Freezer Protection) — Code-Grade Artifacts
Version: 1.0
Date: 2025-12-26
Scope: Temperature + Door + Power/Compressor telemetry -> Bishop features -> Recommendations -> Accepted Events

This pack includes:
1) Postgres telemetry schema additions (tables, indexes, retention notes)
2) Feature extraction pseudocode (Python-style, implementation-ready)
3) Detection thresholds config schema (JSON)
4) Event payload JSON Schema for `RECOMMENDATION_EMITTED` (compressor/thermal risk)
5) Mermaid diagrams:
   - Telemetry -> Features -> Bishop -> Recommendation -> Acceptance -> Event Store
   - Door-close recovery analysis pipeline

## Gold Master Compliance
- Telemetry is NON-authoritative; never reconstruct truth from telemetry.
- Bishop emits only RECOMMENDATION_EVENTS.
- Any material action requires `RECOMMENDATION_ACCEPTED` with REQUIRED evidence.
- Ops never performs money logic.
