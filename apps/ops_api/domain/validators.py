import json
import hashlib
from apps.ops_api.domain.registry import EVENT_REGISTRY, RBAC_RULES

def validate_event_type(event: dict) -> None:
    et = event.get("event_type")
    if et not in EVENT_REGISTRY:
        raise ValueError(f"Unknown event_type: {et}")

def validate_rbac(role: str, event: dict) -> None:
    et = event.get("event_type")
    allowed = RBAC_RULES.get(et, [])
    if role not in allowed:
        raise PermissionError(f"Role {role} cannot emit {et}")

def validate_evidence_policy(event: dict) -> None:
    et = event.get("event_type")
    policy_required = EVENT_REGISTRY[et]["evidence_policy"]
    evidence = event.get("evidence") or {}
    policy = evidence.get("policy")
    if policy_required == "REQUIRED" and policy != "REQUIRED":
        raise ValueError("Evidence REQUIRED for this event_type")
    if policy_required == "INHERIT_LAST" and policy not in ("INHERIT_LAST","REQUIRED"):
        raise ValueError("Evidence must INHERIT_LAST or REQUIRED")
    if policy_required == "OPTIONAL" and policy not in ("OPTIONAL","REQUIRED","INHERIT_LAST","WAIVER"):
        raise ValueError("Invalid evidence policy")
    if policy == "WAIVER" and not evidence.get("waiver_reason"):
        raise ValueError("WAIVER requires waiver_reason")

def validate_if_match(asset_id: str, if_match: str, entity_id: str) -> None:
    # Implement: load current aggregate_version for asset_id + entity_id, compare to If-Match
    return

def enforce_idempotency(entity_id: str, idem_key: str, body: dict):
    # Implement: read idempotency_keys; if exists and request_hash matches, return stored response_json
    # If exists and request_hash differs => 409
    return None
