import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_prefixed(data: bytes) -> str:
    return "sha256:" + sha256_hex(data)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def genesis_prev_hash() -> str:
    return "sha256:" + ("0" * 64)


def load_ed25519_private_key_from_b64(private_key_b64: str) -> Ed25519PrivateKey:
    raw = base64.b64decode(private_key_b64)
    if len(raw) != 32:
        raise ValueError("Invalid Ed25519 private key length")
    return Ed25519PrivateKey.from_private_bytes(raw)


def load_ed25519_public_key_from_b64(public_key_b64: str) -> Ed25519PublicKey:
    raw = base64.b64decode(public_key_b64)
    if len(raw) != 32:
        raise ValueError("Invalid Ed25519 public key length")
    return Ed25519PublicKey.from_public_bytes(raw)


def sign_ed25519_b64(private_key: Ed25519PrivateKey, message: bytes) -> str:
    sig = private_key.sign(message)
    return "ed25519:" + base64.b64encode(sig).decode("ascii")


def verify_ed25519_b64(public_key: Ed25519PublicKey, message: bytes, signature: str) -> bool:
    if not signature.startswith("ed25519:"):
        raise ValueError("Invalid signature prefix")
    raw_sig = base64.b64decode(signature.removeprefix("ed25519:"))
    public_key.verify(raw_sig, message)
    return True


def compute_event_hash(canonical_payload: Dict[str, Any], prev_hash: str, evidence_hash: str) -> str:
    payload_bytes = canonical_json_bytes(canonical_payload)
    combined = payload_bytes + prev_hash.encode("utf-8") + evidence_hash.encode("utf-8")
    return sha256_prefixed(combined)


def build_server_event_envelope(
    *,
    asset_id: str,
    event_type: str,
    evidence: Dict[str, Any],
    payload: Dict[str, Any],
    emitter_class: str,
    emitter_id: str,
    aggregate_version: int,
    prev_event_hash: str,
    signing_private_key_b64: str,
    event_id: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    if aggregate_version < 1:
        raise ValueError("aggregate_version")

    eid = event_id or str(uuid4())
    ts = timestamp or utc_now_iso()

    canonical_payload = {
        "event_id": eid,
        "event_type": event_type,
        "asset_id": asset_id,
        "aggregate_version": aggregate_version,
        "emitter_class": emitter_class,
        "emitter_id": emitter_id,
        "timestamp": ts,
        "evidence": evidence,
        "payload": payload,
    }

    evidence_hash = (evidence or {}).get("evidence_hash")
    if not isinstance(evidence_hash, str) or not evidence_hash:
        raise ValueError("evidence.evidence_hash")

    event_hash = compute_event_hash(canonical_payload, prev_event_hash, evidence_hash)

    private_key = load_ed25519_private_key_from_b64(signing_private_key_b64)
    signature = sign_ed25519_b64(private_key, event_hash.encode("utf-8"))

    envelope = dict(canonical_payload)
    envelope["prev_event_hash"] = prev_event_hash
    envelope["event_hash"] = event_hash
    envelope["signature"] = signature

    return envelope
