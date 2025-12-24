"""
PROVENIQ Ops - DAG Governance API Routes
Bishop DAG inspection and validation endpoints
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from app.services.bishop.orchestrator import (
    DAGValidationError,
    MissingDependency,
    NodeStatus,
    orchestrator,
)

router = APIRouter(prefix="/dag", tags=["DAG Governance"])


@router.get("/health")
async def get_dag_health() -> dict:
    """Get overall DAG health status."""
    try:
        if not orchestrator._loaded:
            orchestrator.load()
        return orchestrator.get_dag_health()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nodes")
async def list_nodes(layer: Optional[int] = None) -> dict:
    """List all DAG nodes, optionally filtered by layer."""
    try:
        if not orchestrator._loaded:
            orchestrator.load()
        
        nodes = []
        for node_id, node in orchestrator._nodes.items():
            if layer is not None and node.layer != layer:
                continue
            
            nodes.append({
                "node_id": node_id,
                "name": node.name,
                "layer": node.layer,
                "depends_on": node.depends_on,
                "inputs": node.inputs,
                "outputs": [o["name"] for o in node.outputs],
                "cacheable": node.cacheable,
                "side_effects": node.side_effects,
                "status": orchestrator.get_node_status(node_id).value,
            })
        
        return {
            "total": len(nodes),
            "nodes": sorted(nodes, key=lambda n: (n["layer"], n["node_id"])),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nodes/{node_id}")
async def get_node(node_id: str) -> dict:
    """Get detailed information about a specific node."""
    try:
        if not orchestrator._loaded:
            orchestrator.load()
        
        node = orchestrator.get_node_definition(node_id)
        if not node:
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
        
        return {
            "node_id": node.node_id,
            "name": node.name,
            "description": node.description,
            "layer": node.layer,
            "depends_on": node.depends_on,
            "inputs": node.inputs,
            "outputs": node.outputs,
            "invariants": node.invariants,
            "side_effects": node.side_effects,
            "cacheable": node.cacheable,
            "ttl_seconds": node.ttl_seconds,
            "status": orchestrator.get_node_status(node_id).value,
            "registered": node_id in orchestrator._handlers,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/execution-order")
async def get_execution_order() -> dict:
    """Get nodes in execution order by layer."""
    try:
        if not orchestrator._loaded:
            orchestrator.load()
        
        layers = orchestrator.get_execution_order()
        layer_names = [
            "Data Snapshots",
            "Signals",
            "Policy Gates",
            "Proposals",
            "Execution",
            "Telemetry",
        ]
        
        return {
            "layers": [
                {
                    "layer": i,
                    "name": layer_names[i] if i < len(layer_names) else f"Layer {i}",
                    "nodes": layer,
                }
                for i, layer in enumerate(layers)
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mermaid", response_class=PlainTextResponse)
async def get_mermaid_diagram() -> str:
    """Export DAG as Mermaid diagram for visualization."""
    try:
        if not orchestrator._loaded:
            orchestrator.load()
        return orchestrator.to_mermaid()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate")
async def validate_dag() -> dict:
    """Validate DAG structure and module registrations."""
    try:
        if not orchestrator._loaded:
            orchestrator.load()
        
        issues = []
        
        # Check for unregistered nodes
        for node_id in orchestrator._nodes:
            if node_id not in orchestrator._handlers:
                issues.append({
                    "type": "unregistered_node",
                    "node_id": node_id,
                    "message": f"Node {node_id} declared in DAG but no handler registered",
                })
        
        # Check for nodes with missing dependencies
        for node_id, node in orchestrator._nodes.items():
            for dep in node.depends_on:
                if dep not in orchestrator._nodes:
                    issues.append({
                        "type": "missing_dependency",
                        "node_id": node_id,
                        "dependency": dep,
                        "message": f"Node {node_id} depends on non-existent node {dep}",
                    })
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "nodes_declared": len(orchestrator._nodes),
            "nodes_registered": len(orchestrator._handlers),
        }
    except DAGValidationError as e:
        return {
            "valid": False,
            "issues": [{"type": "validation_error", "message": str(e)}],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/invalidate")
async def invalidate_cache(node_id: Optional[str] = None) -> dict:
    """Invalidate cache for a node or all nodes."""
    try:
        count = orchestrator.invalidate_cache(node_id)
        return {
            "invalidated": count,
            "node_id": node_id or "all",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/policies")
async def get_policies() -> dict:
    """Get DAG execution policies."""
    try:
        if not orchestrator._loaded:
            orchestrator.load()
        
        return orchestrator._dag.get("policies", {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
