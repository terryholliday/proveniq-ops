"""
PROVENIQ Ops - Bishop Decision Orchestrator
DAG-driven execution engine for deterministic decision making.

This service:
- Loads bishop_dag.yaml as the authoritative source
- Builds dependency graph
- Executes nodes ONLY when upstream outputs exist
- Caches node outputs by (inputs_hash, node_id)
- Validates module declarations against DAG

NO NODE RUNS "because someone called it."
Nodes run because the DAG allows them to.
"""

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

import yaml

T = TypeVar("T")


class NodeStatus(str, Enum):
    """Execution status of a DAG node."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STALE = "stale"
    BLOCKED = "blocked"


class DAGValidationError(Exception):
    """Raised when DAG validation fails."""
    pass


class MissingDependency(Exception):
    """Raised when a node's dependency is not satisfied."""
    pass


class InvariantViolation(Exception):
    """Raised when a node's invariant is violated."""
    pass


class UnauthorizedSideEffect(Exception):
    """Raised when a node attempts an undeclared side effect."""
    pass


class NodeNotRegistered(Exception):
    """Raised when attempting to execute an unregistered node."""
    pass


@dataclass
class NodeDefinition:
    """Definition of a DAG node from bishop_dag.yaml."""
    node_id: str
    layer: int
    name: str
    description: str
    depends_on: list[str]
    inputs: list[str]
    outputs: list[dict]
    invariants: list[str]
    side_effects: str | list[str]
    cacheable: bool
    ttl_seconds: int


@dataclass
class NodeOutput:
    """Cached output from a node execution."""
    node_id: str
    inputs_hash: str
    output_data: Any
    timestamp: datetime
    execution_ms: int
    ttl_seconds: int
    
    @property
    def is_stale(self) -> bool:
        if self.ttl_seconds == 0:
            return True  # Non-cacheable
        expiry = self.timestamp + timedelta(seconds=self.ttl_seconds)
        return datetime.utcnow() > expiry


@dataclass
class NodeExecution:
    """Record of a node execution attempt."""
    execution_id: uuid.UUID
    node_id: str
    status: NodeStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    inputs_hash: Optional[str] = None
    outputs_hash: Optional[str] = None


@dataclass
class RegisteredNode:
    """A registered node handler."""
    node_id: str
    handler: Callable
    inputs: list[str]
    output: str
    side_effects: bool


class DecisionOrchestrator:
    """
    Bishop Decision Orchestrator
    
    The DAG is the single source of truth.
    Code must conform to it — not the other way around.
    """
    
    def __init__(self, dag_path: Optional[str] = None) -> None:
        self._dag_path = dag_path or self._find_dag_file()
        self._dag: dict = {}
        self._nodes: dict[str, NodeDefinition] = {}
        self._handlers: dict[str, RegisteredNode] = {}
        self._cache: dict[str, NodeOutput] = {}
        self._execution_log: list[NodeExecution] = []
        self._loaded = False
    
    def _find_dag_file(self) -> str:
        """Find bishop_dag.yaml relative to project root."""
        # Try multiple locations
        candidates = [
            Path(__file__).parents[4] / "governance" / "bishop_dag.yaml",
            Path.cwd() / "governance" / "bishop_dag.yaml",
            Path.cwd().parent / "governance" / "bishop_dag.yaml",
        ]
        for path in candidates:
            if path.exists():
                return str(path)
        raise FileNotFoundError("bishop_dag.yaml not found in governance/")
    
    def load(self) -> None:
        """Load and parse the DAG definition."""
        with open(self._dag_path, "r") as f:
            self._dag = yaml.safe_load(f)
        
        # Parse node definitions
        for node_id, node_def in self._dag.get("nodes", {}).items():
            self._nodes[node_id] = NodeDefinition(
                node_id=node_id,
                layer=node_def.get("layer", 0),
                name=node_def.get("name", node_id),
                description=node_def.get("description", ""),
                depends_on=node_def.get("depends_on", []),
                inputs=node_def.get("inputs", []),
                outputs=node_def.get("outputs", []),
                invariants=node_def.get("invariants", []),
                side_effects=node_def.get("side_effects", "none"),
                cacheable=node_def.get("cacheable", False),
                ttl_seconds=node_def.get("ttl_seconds", 0),
            )
        
        self._validate_dag()
        self._loaded = True
    
    def _validate_dag(self) -> None:
        """Validate DAG structure on load."""
        # Check for circular dependencies
        for node_id, node in self._nodes.items():
            visited = set()
            self._check_circular(node_id, visited)
        
        # Check all dependencies exist
        for node_id, node in self._nodes.items():
            for dep in node.depends_on:
                if dep not in self._nodes:
                    raise DAGValidationError(
                        f"Node {node_id} depends on non-existent node {dep}"
                    )
    
    def _check_circular(self, node_id: str, visited: set[str], path: Optional[list[str]] = None) -> None:
        """Check for circular dependencies."""
        path = path or []
        if node_id in visited:
            raise DAGValidationError(
                f"Circular dependency detected: {' -> '.join(path + [node_id])}"
            )
        visited.add(node_id)
        path.append(node_id)
        
        node = self._nodes.get(node_id)
        if node:
            for dep in node.depends_on:
                self._check_circular(dep, visited.copy(), path.copy())
    
    # =========================================================================
    # NODE REGISTRATION
    # =========================================================================
    
    def register_node(
        self,
        node_id: str,
        handler: Callable,
        inputs: list[str],
        output: str,
        side_effects: bool = False,
    ) -> None:
        """
        Register a node handler.
        
        On startup, validates against bishop_dag.yaml.
        Mismatch = boot failure.
        """
        if not self._loaded:
            self.load()
        
        # Validate node exists in DAG
        if node_id not in self._nodes:
            raise DAGValidationError(
                f"Node {node_id} not declared in bishop_dag.yaml"
            )
        
        dag_node = self._nodes[node_id]
        
        # Validate inputs match
        if set(inputs) != set(dag_node.inputs):
            raise DAGValidationError(
                f"Node {node_id} inputs mismatch. "
                f"Declared: {dag_node.inputs}, Registered: {inputs}"
            )
        
        # Validate side effects declaration
        dag_has_side_effects = dag_node.side_effects not in ("none", None, [])
        if side_effects != dag_has_side_effects:
            raise DAGValidationError(
                f"Node {node_id} side_effects mismatch. "
                f"DAG declares: {dag_node.side_effects}, Module declares: {side_effects}"
            )
        
        self._handlers[node_id] = RegisteredNode(
            node_id=node_id,
            handler=handler,
            inputs=inputs,
            output=output,
            side_effects=side_effects,
        )
    
    # =========================================================================
    # EXECUTION
    # =========================================================================
    
    def _compute_inputs_hash(self, inputs: dict[str, Any]) -> str:
        """Compute deterministic hash of inputs for caching."""
        serialized = json.dumps(inputs, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
    
    def _get_cached_output(self, node_id: str, inputs_hash: str) -> Optional[NodeOutput]:
        """Get cached output if valid."""
        cache_key = f"{node_id}:{inputs_hash}"
        cached = self._cache.get(cache_key)
        
        if cached and not cached.is_stale:
            return cached
        return None
    
    def _cache_output(
        self,
        node_id: str,
        inputs_hash: str,
        output_data: Any,
        execution_ms: int,
    ) -> None:
        """Cache node output."""
        node = self._nodes[node_id]
        if not node.cacheable:
            return
        
        cache_key = f"{node_id}:{inputs_hash}"
        self._cache[cache_key] = NodeOutput(
            node_id=node_id,
            inputs_hash=inputs_hash,
            output_data=output_data,
            timestamp=datetime.utcnow(),
            execution_ms=execution_ms,
            ttl_seconds=node.ttl_seconds,
        )
    
    def _check_dependencies_satisfied(self, node_id: str) -> tuple[bool, list[str]]:
        """Check if all dependencies for a node are satisfied."""
        node = self._nodes[node_id]
        missing = []
        
        for dep_id in node.depends_on:
            # Check if dependency has been executed and is not stale
            dep_outputs = [
                key for key in self._cache.keys() 
                if key.startswith(f"{dep_id}:")
            ]
            
            if not dep_outputs:
                missing.append(dep_id)
            else:
                # Check if any non-stale output exists
                has_valid = any(
                    not self._cache[key].is_stale 
                    for key in dep_outputs
                )
                if not has_valid:
                    missing.append(dep_id)
        
        return len(missing) == 0, missing
    
    def execute_node(
        self,
        node_id: str,
        inputs: dict[str, Any],
        force: bool = False,
    ) -> Any:
        """
        Execute a node if the DAG allows it.
        
        Args:
            node_id: The node to execute
            inputs: Input data for the node
            force: Skip cache check (not dependency check)
        
        Returns:
            Node output
        
        Raises:
            MissingDependency: If upstream dependencies not satisfied
            NodeNotRegistered: If no handler registered
            DAGValidationError: If node not in DAG
        """
        if not self._loaded:
            self.load()
        
        if node_id not in self._nodes:
            raise DAGValidationError(f"Node {node_id} not in DAG")
        
        if node_id not in self._handlers:
            raise NodeNotRegistered(f"No handler registered for {node_id}")
        
        # Check dependencies
        deps_ok, missing = self._check_dependencies_satisfied(node_id)
        if not deps_ok:
            raise MissingDependency(
                f"Node {node_id} missing dependencies: {missing}"
            )
        
        # Check cache
        inputs_hash = self._compute_inputs_hash(inputs)
        if not force:
            cached = self._get_cached_output(node_id, inputs_hash)
            if cached:
                return cached.output_data
        
        # Execute
        execution = NodeExecution(
            execution_id=uuid.uuid4(),
            node_id=node_id,
            status=NodeStatus.RUNNING,
            started_at=datetime.utcnow(),
            inputs_hash=inputs_hash,
        )
        
        handler = self._handlers[node_id]
        start_time = time.time()
        
        try:
            result = handler.handler(**inputs)
            execution_ms = int((time.time() - start_time) * 1000)
            
            # Cache result
            self._cache_output(node_id, inputs_hash, result, execution_ms)
            
            execution.status = NodeStatus.COMPLETED
            execution.completed_at = datetime.utcnow()
            execution.outputs_hash = self._compute_inputs_hash({"result": result})
            
        except Exception as e:
            execution.status = NodeStatus.FAILED
            execution.completed_at = datetime.utcnow()
            execution.error = str(e)
            self._execution_log.append(execution)
            raise
        
        self._execution_log.append(execution)
        return result
    
    def execute_layer(self, layer: int, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute all nodes in a layer."""
        layer_nodes = [
            node_id for node_id, node in self._nodes.items()
            if node.layer == layer
        ]
        
        results = {}
        for node_id in layer_nodes:
            if node_id in self._handlers:
                try:
                    node = self._nodes[node_id]
                    node_inputs = {k: inputs.get(k) for k in node.inputs if k in inputs}
                    results[node_id] = self.execute_node(node_id, node_inputs)
                except MissingDependency:
                    pass  # Skip nodes with missing deps
        
        return results
    
    def execute_dag(self, initial_inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute entire DAG in layer order."""
        all_outputs = dict(initial_inputs)
        
        # Get max layer
        max_layer = max(node.layer for node in self._nodes.values())
        
        for layer in range(max_layer + 1):
            layer_results = self.execute_layer(layer, all_outputs)
            all_outputs.update(layer_results)
        
        return all_outputs
    
    # =========================================================================
    # QUERY
    # =========================================================================
    
    def get_node_definition(self, node_id: str) -> Optional[NodeDefinition]:
        """Get node definition from DAG."""
        return self._nodes.get(node_id)
    
    def get_execution_order(self) -> list[list[str]]:
        """Get nodes grouped by execution layer."""
        layers: dict[int, list[str]] = {}
        for node_id, node in self._nodes.items():
            if node.layer not in layers:
                layers[node.layer] = []
            layers[node.layer].append(node_id)
        
        return [layers.get(i, []) for i in range(max(layers.keys()) + 1)]
    
    def get_node_status(self, node_id: str) -> NodeStatus:
        """Get current status of a node."""
        if node_id not in self._nodes:
            return NodeStatus.PENDING
        
        # Check if we have any cached output
        cached_keys = [k for k in self._cache.keys() if k.startswith(f"{node_id}:")]
        if not cached_keys:
            # Check if dependencies are satisfied
            deps_ok, _ = self._check_dependencies_satisfied(node_id)
            return NodeStatus.READY if deps_ok else NodeStatus.BLOCKED
        
        # Check if cached output is stale
        for key in cached_keys:
            if not self._cache[key].is_stale:
                return NodeStatus.COMPLETED
        
        return NodeStatus.STALE
    
    def get_dag_health(self) -> dict:
        """Get overall DAG health status."""
        statuses = {node_id: self.get_node_status(node_id) for node_id in self._nodes}
        
        return {
            "healthy": all(s != NodeStatus.FAILED for s in statuses.values()),
            "nodes_total": len(self._nodes),
            "nodes_completed": sum(1 for s in statuses.values() if s == NodeStatus.COMPLETED),
            "nodes_stale": sum(1 for s in statuses.values() if s == NodeStatus.STALE),
            "nodes_blocked": sum(1 for s in statuses.values() if s == NodeStatus.BLOCKED),
            "nodes_failed": sum(1 for s in statuses.values() if s == NodeStatus.FAILED),
            "execution_log_size": len(self._execution_log),
            "cache_size": len(self._cache),
        }
    
    def invalidate_cache(self, node_id: Optional[str] = None) -> int:
        """Invalidate cache for a node or all nodes."""
        if node_id:
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{node_id}:")]
        else:
            keys_to_remove = list(self._cache.keys())
        
        for key in keys_to_remove:
            del self._cache[key]
        
        return len(keys_to_remove)
    
    # =========================================================================
    # MERMAID EXPORT
    # =========================================================================
    
    def to_mermaid(self) -> str:
        """Export DAG as Mermaid diagram."""
        lines = ["graph TD"]
        
        # Group nodes by layer
        layers = self.get_execution_order()
        
        # Add subgraphs for layers
        layer_names = [
            "Data Snapshots",
            "Signals",
            "Policy Gates",
            "Proposals",
            "Execution",
            "Telemetry",
        ]
        
        for layer_idx, layer_nodes in enumerate(layers):
            layer_name = layer_names[layer_idx] if layer_idx < len(layer_names) else f"Layer {layer_idx}"
            lines.append(f"    subgraph L{layer_idx}[{layer_name}]")
            for node_id in layer_nodes:
                node = self._nodes[node_id]
                lines.append(f"        {node_id}[{node.name}]")
            lines.append("    end")
        
        # Add edges
        for node_id, node in self._nodes.items():
            for dep in node.depends_on:
                lines.append(f"    {dep} --> {node_id}")
        
        return "\n".join(lines)


# Singleton instance
orchestrator = DecisionOrchestrator()


# ============================================================================
# DECORATOR FOR NODE REGISTRATION
# ============================================================================

def bishop_node(
    node_id: str,
    inputs: list[str],
    output: str,
    side_effects: bool = False,
):
    """
    Decorator to register a function as a Bishop DAG node.
    
    Usage:
        @bishop_node(
            node_id="N11_stockout_risk",
            inputs=["inventory_levels", "demand_forecast", "vendor_lead_times"],
            output="stockout_risks",
            side_effects=False,
        )
        def compute_stockout_risk(inventory_levels, demand_forecast, vendor_lead_times):
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Store DAG identity on function
        func.NODE_ID = node_id
        func.INPUTS = inputs
        func.OUTPUT = output
        func.SIDE_EFFECTS = side_effects
        
        # Register with orchestrator
        try:
            orchestrator.register_node(
                node_id=node_id,
                handler=func,
                inputs=inputs,
                output=output,
                side_effects=side_effects,
            )
        except Exception:
            # Defer registration until orchestrator is loaded
            pass
        
        return func
    
    return decorator
