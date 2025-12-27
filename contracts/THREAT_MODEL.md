# Threat Model — PROVENIQ Ops (Gold Master)

## Assets
- event_store (truth)
- evidence_objects (pointers + hashes)
- projections (derived)
- telemetry (ephemeral)
- keys (ops signing, ledger verify)
- outbox_webhooks (delivery pipeline)

## Attacker Goals
- falsify operational truth
- backdate/erase events
- force unauthorized state changes
- spoof ledger outcomes
- cause denial-of-service to reconciliation

## Controls (must exist)
1. Append-only event store (app role cannot UPDATE/DELETE)
2. Hash chain + signatures (Ed25519)
3. RBAC at event layer (role->event_type)
4. Evidence policy enforcement
5. Idempotency keys (dedupe, prevent replay effects)
6. Ledger signature verification (never trust transport)
7. Corruption protocol (read-only on chain break)
8. Forensic recovery (new chain / new asset id)
9. Outbox pattern (atomic webhook enqueue)
10. Rate limiting + auth hardening

## If Ops is compromised
### API credential theft
- RBAC + evidence gates prevent many high-impact actions
- All actions logged as events, attributable

### DB write compromise
- hash chain breaks -> asset CORRUPTED -> read-only
- forensic recovery required; no silent repair

### Bishop compromise
- Bishop can only emit recommendations; requires acceptance event

### Ledger spoofing
- reject invalid signature; poll status endpoint; escalate on mismatch

## Correct failure mode
Read-only but truthful. No silent corruption. No financial leakage.
