from fastapi import APIRouter, Header, HTTPException, Depends
from apps.ops_api.domain.validators import (
    validate_event_type, validate_rbac, validate_evidence_policy,
    validate_if_match, enforce_idempotency
)
from apps.ops_api.domain.append import append_event

router = APIRouter()

@router.post("/assets/{asset_id}/events", status_code=202)
def post_event(
    asset_id: str,
    body: dict,
    if_match: str = Header(..., alias="If-Match"),
    idem_key: str = Header(..., alias="Idempotency-Key"),
    # user=Depends(auth_current_user)  # implement in auth/
):
    """
    ONLY mutation endpoint: append an event.
    Server enforces: scope, RBAC, evidence policy, optimistic concurrency, idempotency, crypto.
    """
    entity_id = "dev-entity"
    role = "ADMIN"

    forbidden = {
        "event_id",
        "asset_id",
        "aggregate_version",
        "emitter_class",
        "emitter_id",
        "timestamp",
        "prev_event_hash",
        "event_hash",
        "signature",
        "entity_id",
        "role",
    }
    injected = forbidden.intersection(body.keys())
    if injected:
        raise HTTPException(status_code=400, detail=f"Client must not supply server fields: {sorted(injected)}")

    validate_event_type(body)
    validate_rbac(role, body)
    validate_evidence_policy(body)
    validate_if_match(asset_id, if_match, entity_id)

    # Idempotency wrapper returns stored response if duplicate
    cached = enforce_idempotency(entity_id, idem_key, body)
    if cached is not None:
        return cached

    resp = append_event(asset_id=asset_id, entity_id=entity_id, role=role, event=body)
    return resp
