# PROVENIQ Ops - Governance

**Bishop Decision DAG — Single Source of Truth**

This directory contains the authoritative governance files for Bishop's decision engine.

## Files

| File | Purpose |
|------|---------|
| `bishop_dag.yaml` | **Authoritative DAG definition** — Code must conform to this |

## Rules

1. **Code conforms to DAG** — not the other way around
2. **If logic is not declared here → it's invalid code**
3. **No node runs "because someone called it"** — nodes run because the DAG allows them
4. **All side effects must be declared** — undeclared side effects = boot failure

## DAG Layers

| Layer | Nodes | Purpose |
|-------|-------|---------|
| 0 | N0-N4 | **Data Snapshots** — Raw inputs, no computation |
| 1 | N10-N18 | **Signals** — Derived metrics, pattern detection |
| 2 | N20-N25 | **Policy Gates** — Business rule validation |
| 3 | N30-N37 | **Proposals** — Actionable recommendations |
| 4 | N40-N46 | **Execution** — State changes (require approval) |
| 5 | N50-N52 | **Telemetry** — Audit and observability |

## Viewing the DAG

### Mermaid Diagram
```bash
curl http://localhost:8000/api/v1/dag/mermaid
```

### JSON Structure
```bash
curl http://localhost:8000/api/v1/dag/nodes
```

### Health Check
```bash
curl http://localhost:8000/api/v1/dag/health
```

## Adding a New Node

1. **Declare in `bishop_dag.yaml`** first
2. Create module with DAG identity:
   ```python
   NODE_ID = "N99_new_node"
   INPUTS = ["upstream_data"]
   OUTPUT = "new_output"
   SIDE_EFFECTS = False
   ```
3. Register with orchestrator:
   ```python
   @bishop_node(
       node_id="N99_new_node",
       inputs=["upstream_data"],
       output="new_output",
       side_effects=False,
   )
   def compute_new_node(upstream_data):
       ...
   ```
4. **Mismatch = boot failure**

## AI Leash

When prompting AI assistants:

> "You may ONLY generate code for node N32.
> Inputs, outputs, and invariants are defined in bishop_dag.yaml.
> Do not create new dependencies."

This prevents AI from:
- Skipping policy gates
- Writing undeclared side effects
- Collapsing layers
- Inventing logic not in the DAG

---

**This graph explains the PROVENIQ moat in 10 seconds:**

*"This is why Bishop doesn't hallucinate decisions."*
