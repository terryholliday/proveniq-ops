import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[3]
EVENT_REGISTRY = {e["event_type"]: e for e in json.loads((ROOT / "contracts" / "event_types.json").read_text())["events"]}
RBAC_RULES = {r["event_type"]: r["allowed_roles"] for r in yaml.safe_load((ROOT / "contracts" / "rbac.yaml").read_text())["rules"]}
