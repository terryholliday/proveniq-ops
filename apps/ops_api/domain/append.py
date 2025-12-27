"""
Append path skeleton.
Must:
- canonicalize payload
- compute event_hash with prev_hash + evidence_hash
- sign event
- append to event_store
- update projections (sync or queue)
- write outbox records
"""
import os
from datetime import datetime
from typing import Dict, Tuple

from fastapi import HTTPException

from apps.ops_api.domain.event_crypto import build_server_event_envelope
from apps.ops_api.domain.event_crypto import canonical_json_bytes
from apps.ops_api.domain.event_crypto import genesis_prev_hash
from apps.ops_api.domain.event_crypto import sha256_hex
from apps.ops_api.domain.registry import EVENT_REGISTRY
from apps.ops_api.domain.db import async_session_maker
from apps.ops_api.domain import storage

def _role_to_emitter_class(role: str) -> str:
    if role in ("USER", "MANAGER", "ADMIN"):
        return "HUMAN"
    if role == "SYSTEM":
        return "SYSTEM"
    if role == "LEDGER_EXTERNAL":
        return "LEDGER_EXTERNAL"
    raise ValueError("role")


def _load_prev_hash_and_next_version(asset_id: str, entity_id: str) -> Tuple[str, int]:
    raise NotImplementedError("storage")


def _parse_if_match_version(if_match: str) -> int:
    v = if_match.strip()
    if v.startswith("W/"):
        v = v[2:].strip()
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        v = v[1:-1]
    if not v.isdigit():
        raise HTTPException(status_code=400, detail="If-Match")
    return int(v)


async def append_event(asset_id: str, entity_id: str, role: str, event: Dict, if_match: str, idempotency_key: str) -> Dict:
    signing_key_b64 = os.environ.get("OPS_ED25519_PRIVATE_KEY_B64")
    if not signing_key_b64:
        raise RuntimeError("OPS_ED25519_PRIVATE_KEY_B64")

    event_type = event.get("event_type")
    if not isinstance(event_type, str) or not event_type:
        raise ValueError("event_type")

    evidence = event.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError("evidence")

    payload = event.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("payload")

    emitter_class = _role_to_emitter_class(role)
    emitter_id = "dev-emitter"

    allowed_emitter_classes = EVENT_REGISTRY[event_type]["emitter_class"]
    if emitter_class not in allowed_emitter_classes:
        raise PermissionError("emitter_class")

    async with async_session_maker() as session:
        async with session.begin():
            request_hash = sha256_hex(canonical_json_bytes({"asset_id": asset_id, "event": event}))
            idem_res = await storage.read_idempotency(session, entity_id, idempotency_key)
            idem_row = idem_res.first()
            if idem_row is not None:
                existing_request_hash = idem_row[0]
                existing_response_json = idem_row[1]
                if existing_request_hash != request_hash:
                    raise HTTPException(status_code=409, detail="Idempotency-Key")
                return existing_response_json

            tip_res = await storage.read_asset_tip(session, asset_id, entity_id)
            tip_row = tip_res.first()
            if tip_row is None:
                current_version = 0
                prev_event_hash = genesis_prev_hash()
            else:
                current_version = int(tip_row[0])
                prev_event_hash = str(tip_row[1])

            if_match_version = _parse_if_match_version(if_match)
            if current_version != if_match_version:
                raise HTTPException(status_code=409, detail="If-Match")

            next_version = current_version + 1
            envelope = build_server_event_envelope(
                asset_id=asset_id,
                event_type=event_type,
                evidence=evidence,
                payload=payload,
                emitter_class=emitter_class,
                emitter_id=emitter_id,
                aggregate_version=next_version,
                prev_event_hash=prev_event_hash,
                signing_private_key_b64=signing_key_b64,
            )

            evidence_policy = EVENT_REGISTRY[event_type]["evidence_policy"]
            evidence_hash = evidence.get("evidence_hash")
            waiver_reason = evidence.get("waiver_reason")

            ts_utc = datetime.fromisoformat(str(envelope["timestamp"]).replace("Z", "+00:00"))

            await storage.insert_event_store(
                session,
                {
                    "event_id": storage._parse_uuid(envelope["event_id"]),
                    "asset_id": storage._parse_uuid(asset_id),
                    "entity_id": entity_id,
                    "aggregate_version": next_version,
                    "event_type": event_type,
                    "emitter_class": emitter_class,
                    "emitter_id": emitter_id,
                    "ts_utc": ts_utc,
                    "evidence_policy": evidence_policy,
                    "evidence_hash": evidence_hash,
                    "waiver_reason": waiver_reason,
                    "payload_json": payload,
                    "prev_event_hash": prev_event_hash,
                    "event_hash": envelope["event_hash"],
                    "signature": envelope["signature"],
                },
            )

            await storage.insert_idempotency(session, entity_id, idempotency_key, request_hash, envelope)
            await storage.insert_outbox_webhook(session, entity_id, event_type, envelope)

            return envelope
