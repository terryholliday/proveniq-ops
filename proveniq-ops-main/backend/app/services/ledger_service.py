
import httpx
import json
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from app.core.config import settings

def canonicalize(data: Any) -> str:
    """Canonicalize JSON payload for hashing (Sort keys)."""
    return json.dumps(data, sort_keys=True, separators=(',', ':'))

def hash_payload(data: Any) -> str:
    """SHA-256 hash of canonical payload."""
    canonical = canonicalize(data)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

class LedgerService:
    def __init__(self):
        self.base_url = settings.LEDGER_API_URL.rstrip('/')
        
    async def append_event(
        self,
        event_type: str,
        asset_id: Optional[str] = None,
        anchor_id: Optional[str] = None,
        payload: Dict[str, Any] = {},
        correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Write a canonical event to the Ledger using REST API.
        """
        
        # 1. Prepare Payload & Hash
        canonical_hash = hash_payload(payload)
        final_payload = {**payload, "canonical_hash_hex": canonical_hash}
        
        # 2. Construct Envelope
        envelope = {
            "source": "ops",
            "event_type": event_type,
            "asset_id": asset_id,
            "anchor_id": anchor_id,
            "correlation_id": correlation_id or str(uuid.uuid4()),
            "idempotency_key": idempotency_key or str(uuid.uuid4()),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": "1.0.0",
            "payload": final_payload
        }
        
        # 3. Send
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/events",
                    json=envelope,
                    timeout=5.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                print(f"Ledger Write Failed: {str(e)}")
                # In robust system: queue for retry
                # For now: fail loud
                raise e

ledger_service = LedgerService()
