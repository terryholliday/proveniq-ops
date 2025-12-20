"""
PROVENIQ Ops - Decision DAG Structure

Directed Acyclic Graph for decision execution order.
Ensures deterministic, reproducible decision flows.
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Callable, Awaitable
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class GateType(str, Enum):
    """Types of policy gates"""
    LIQUIDITY = "liquidity"        # Check available funds
    CRITICALITY = "criticality"    # Assess urgency/importance
    APPROVAL = "approval"          # Require human approval
    COVERAGE = "coverage"          # Check insurance coverage
    VENDOR = "vendor"              # Validate vendor availability
    THRESHOLD = "threshold"        # Check against configured thresholds


class NodeStatus(str, Enum):
    """Status of a decision node"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class DecisionGate(BaseModel):
    """A policy gate that must be passed before proceeding"""
    gate_id: str
    gate_type: GateType
    description: str
    required: bool = True
    config: Dict[str, Any] = {}
    
    # Runtime state
    status: NodeStatus = NodeStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    checked_at: Optional[datetime] = None
    error: Optional[str] = None


class DecisionNode(BaseModel):
    """A node in the decision DAG"""
    node_id: str
    name: str
    description: str
    
    # Dependencies (node IDs that must complete before this node)
    depends_on: List[str] = []
    
    # Gates that must pass before execution
    gates: List[DecisionGate] = []
    
    # Execution function (set at runtime)
    execute_fn: Optional[str] = None  # Function name for serialization
    
    # Runtime state
    status: NodeStatus = NodeStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class DecisionDAG(BaseModel):
    """
    Directed Acyclic Graph for decision execution.
    
    Enforces:
    1. Execution order (dependencies)
    2. Policy gates (must pass before proceeding)
    3. No cycles (validated on construction)
    4. Deterministic execution
    """
    dag_id: UUID = Field(default_factory=uuid4)
    name: str
    description: str
    
    nodes: Dict[str, DecisionNode] = {}
    
    # Trace ID for audit
    trace_id: UUID = Field(default_factory=uuid4)
    
    # Execution state
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: NodeStatus = NodeStatus.PENDING
    
    def add_node(self, node: DecisionNode) -> None:
        """Add a node to the DAG"""
        # Validate dependencies exist
        for dep_id in node.depends_on:
            if dep_id not in self.nodes:
                raise ValueError(f"Dependency {dep_id} not found in DAG")
        
        # Check for cycles
        if self._would_create_cycle(node):
            raise ValueError(f"Adding node {node.node_id} would create a cycle")
        
        self.nodes[node.node_id] = node
        logger.debug(f"Added node {node.node_id} to DAG {self.dag_id}")
    
    def _would_create_cycle(self, new_node: DecisionNode) -> bool:
        """Check if adding this node would create a cycle"""
        # Simple DFS cycle detection
        visited = set()
        rec_stack = set()
        
        def visit(node_id: str) -> bool:
            if node_id in rec_stack:
                return True  # Cycle found
            if node_id in visited:
                return False
            
            visited.add(node_id)
            rec_stack.add(node_id)
            
            node = self.nodes.get(node_id, new_node if node_id == new_node.node_id else None)
            if node:
                for dep_id in node.depends_on:
                    if visit(dep_id):
                        return True
            
            rec_stack.remove(node_id)
            return False
        
        return visit(new_node.node_id)
    
    def get_ready_nodes(self) -> List[DecisionNode]:
        """Get nodes that are ready to execute (all dependencies met)"""
        ready = []
        
        for node in self.nodes.values():
            if node.status != NodeStatus.PENDING:
                continue
            
            # Check if all dependencies are complete
            all_deps_complete = all(
                self.nodes.get(dep_id, DecisionNode(node_id="", name="", description="")).status == NodeStatus.PASSED
                for dep_id in node.depends_on
            )
            
            if all_deps_complete:
                ready.append(node)
        
        return ready
    
    def is_complete(self) -> bool:
        """Check if all nodes have been processed"""
        return all(
            node.status in [NodeStatus.PASSED, NodeStatus.FAILED, NodeStatus.BLOCKED, NodeStatus.SKIPPED]
            for node in self.nodes.values()
        )
    
    def get_execution_order(self) -> List[str]:
        """Get topologically sorted execution order"""
        # Kahn's algorithm
        in_degree = {node_id: len(node.depends_on) for node_id, node in self.nodes.items()}
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        order = []
        
        while queue:
            node_id = queue.pop(0)
            order.append(node_id)
            
            for other_id, other_node in self.nodes.items():
                if node_id in other_node.depends_on:
                    in_degree[other_id] -= 1
                    if in_degree[other_id] == 0:
                        queue.append(other_id)
        
        return order


# Pre-defined DAGs for common operations

def create_reorder_dag(
    product_id: UUID,
    quantity: int,
    vendor_id: str,
) -> DecisionDAG:
    """Create a DAG for reorder decisions"""
    dag = DecisionDAG(
        name="Reorder Decision",
        description=f"Reorder {quantity} units of product {product_id}",
    )
    
    # Node 1: Verify stock levels
    dag.add_node(DecisionNode(
        node_id="verify_stock",
        name="Verify Stock Levels",
        description="Confirm current inventory is below par",
        gates=[
            DecisionGate(
                gate_id="threshold_check",
                gate_type=GateType.THRESHOLD,
                description="Stock must be below par level",
            )
        ],
    ))
    
    # Node 2: Check vendor availability
    dag.add_node(DecisionNode(
        node_id="check_vendor",
        name="Check Vendor Availability",
        description="Verify vendor can fulfill order",
        depends_on=["verify_stock"],
        gates=[
            DecisionGate(
                gate_id="vendor_availability",
                gate_type=GateType.VENDOR,
                description="Vendor must have stock available",
            )
        ],
    ))
    
    # Node 3: Check liquidity
    dag.add_node(DecisionNode(
        node_id="check_liquidity",
        name="Check Liquidity",
        description="Verify sufficient funds available",
        depends_on=["check_vendor"],
        gates=[
            DecisionGate(
                gate_id="liquidity_check",
                gate_type=GateType.LIQUIDITY,
                description="Must have sufficient funds or credit",
            )
        ],
    ))
    
    # Node 4: Approval gate (for high-value orders)
    dag.add_node(DecisionNode(
        node_id="approval",
        name="Manager Approval",
        description="Get approval if order exceeds threshold",
        depends_on=["check_liquidity"],
        gates=[
            DecisionGate(
                gate_id="approval_gate",
                gate_type=GateType.APPROVAL,
                description="Manager approval required for orders > $500",
                required=False,  # Only required if threshold exceeded
            )
        ],
    ))
    
    # Node 5: Submit order
    dag.add_node(DecisionNode(
        node_id="submit_order",
        name="Submit Order",
        description="Submit order to vendor",
        depends_on=["approval"],
        execute_fn="submit_order_to_vendor",
    ))
    
    return dag


def create_disposal_dag(
    item_id: UUID,
    quantity: int,
    reason: str,
) -> DecisionDAG:
    """Create a DAG for disposal decisions"""
    dag = DecisionDAG(
        name="Disposal Decision",
        description=f"Dispose {quantity} units of item {item_id}: {reason}",
    )
    
    # Node 1: Check coverage
    dag.add_node(DecisionNode(
        node_id="check_coverage",
        name="Check Insurance Coverage",
        description="Verify if loss is covered by insurance",
        gates=[
            DecisionGate(
                gate_id="coverage_check",
                gate_type=GateType.COVERAGE,
                description="Check ClaimsIQ for coverage",
            )
        ],
    ))
    
    # Node 2: Capture evidence
    dag.add_node(DecisionNode(
        node_id="capture_evidence",
        name="Capture Evidence",
        description="Ensure required evidence is captured",
        depends_on=["check_coverage"],
    ))
    
    # Node 3: Approval
    dag.add_node(DecisionNode(
        node_id="approval",
        name="Disposal Approval",
        description="Manager must approve disposal",
        depends_on=["capture_evidence"],
        gates=[
            DecisionGate(
                gate_id="disposal_approval",
                gate_type=GateType.APPROVAL,
                description="Manager approval required for disposal",
            )
        ],
    ))
    
    # Node 4: Execute disposal
    dag.add_node(DecisionNode(
        node_id="execute_disposal",
        name="Execute Disposal",
        description="Record disposal and update inventory",
        depends_on=["approval"],
        execute_fn="execute_disposal",
    ))
    
    # Node 5: File claim (if covered)
    dag.add_node(DecisionNode(
        node_id="file_claim",
        name="File Claim",
        description="File insurance claim if covered",
        depends_on=["execute_disposal"],
        execute_fn="file_insurance_claim",
    ))
    
    return dag
