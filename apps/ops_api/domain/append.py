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
from typing import Dict

def append_event(asset_id: str, entity_id: str, role: str, event: Dict) -> Dict:
    # TODO: implement storage layer (SQLAlchemy) and crypto functions
    return {"status":"accepted", "asset_id":asset_id}
