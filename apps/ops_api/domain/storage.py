import uuid
import json
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)


def get_genesis_prev_hash() -> str:
    return "sha256:" + ("0" * 64)


def _parse_uuid(value: str) -> uuid.UUID:
    return uuid.UUID(value)


def _request_hash_payload(asset_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    return {"asset_id": asset_id, "event": event}


def read_idempotency(session: AsyncSession, entity_id: str, idempotency_key: str) -> Any:
    stmt = text(
        "SELECT request_hash, response_json FROM idempotency_keys WHERE entity_id = :entity_id AND idempotency_key = :idk"
    )
    return session.execute(stmt, {"entity_id": entity_id, "idk": idempotency_key})


def read_asset_tip(session: AsyncSession, asset_id: str, entity_id: str) -> Any:
    stmt = text(
        "SELECT aggregate_version, event_hash FROM event_store WHERE asset_id = :asset_id AND entity_id = :entity_id ORDER BY aggregate_version DESC LIMIT 1"
    )
    return session.execute(stmt, {"asset_id": _parse_uuid(asset_id), "entity_id": entity_id})


def insert_event_store(session: AsyncSession, row: Dict[str, Any]) -> Any:
    stmt = text(
        """
        INSERT INTO event_store (
          event_id, asset_id, entity_id,
          aggregate_version, event_type, emitter_class, emitter_id,
          ts_utc, evidence_policy, evidence_hash, waiver_reason,
          payload_json, prev_event_hash, event_hash, signature
        ) VALUES (
          :event_id, :asset_id, :entity_id,
          :aggregate_version, :event_type, :emitter_class, :emitter_id,
          :ts_utc, :evidence_policy, :evidence_hash, :waiver_reason,
          CAST(:payload_json AS jsonb), :prev_event_hash, :event_hash, :signature
        )
        """
    )
    cooked = dict(row)
    cooked["payload_json"] = json.dumps(cooked.get("payload_json"), separators=(",", ":"), ensure_ascii=False)
    return session.execute(stmt, cooked)


def insert_idempotency(session: AsyncSession, entity_id: str, idempotency_key: str, request_hash: str, response_json: Dict[str, Any]) -> Any:
    stmt = text(
        """
        INSERT INTO idempotency_keys (entity_id, idempotency_key, request_hash, response_json)
        VALUES (:entity_id, :idempotency_key, :request_hash, CAST(:response_json AS jsonb))
        """
    )
    return session.execute(
        stmt,
        {
            "entity_id": entity_id,
            "idempotency_key": idempotency_key,
            "request_hash": request_hash,
            "response_json": json.dumps(response_json, separators=(",", ":"), ensure_ascii=False),
        },
    )


def insert_outbox_webhook(session: AsyncSession, entity_id: str, topic: str, payload_json: Dict[str, Any]) -> Any:
    stmt = text(
        """
        INSERT INTO outbox_webhooks (outbox_id, entity_id, topic, payload_json)
        VALUES (:outbox_id, :entity_id, :topic, CAST(:payload_json AS jsonb))
        """
    )
    return session.execute(
        stmt,
        {
            "outbox_id": uuid.uuid4(),
            "entity_id": entity_id,
            "topic": topic,
            "payload_json": json.dumps(payload_json, separators=(",", ":"), ensure_ascii=False),
        },
    )
