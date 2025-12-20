"""
PROVENIQ Ops - Decision Executor

Executes decisions through the DAG with policy enforcement.
Ensures deterministic, traceable execution.
"""

from typing import Dict, Any, Callable, Awaitable, Optional
from datetime import datetime
from uuid import UUID
import logging

from .dag import DecisionDAG, DecisionNode, DecisionGate, NodeStatus
from .policies import PolicyEngine, PolicyResult
from .trace import DecisionTrace, TraceStore

logger = logging.getLogger(__name__)


# Type for execution functions
ExecuteFn = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


class DecisionExecutor:
    """
    Executes a Decision DAG with full policy enforcement and tracing.
    
    Guarantees:
    1. Nodes execute in dependency order
    2. All gates must pass before node execution
    3. Every decision is traced for audit
    4. Reproducible: same input → same output
    """
    
    def __init__(
        self,
        org_id: UUID,
        trace_store: Optional[TraceStore] = None,
    ):
        self.org_id = org_id
        self.policy_engine = PolicyEngine(org_id)
        self.trace_store = trace_store or TraceStore()
        
        # Registered execution functions
        self._executors: Dict[str, ExecuteFn] = {}
    
    def register_executor(self, name: str, fn: ExecuteFn) -> None:
        """Register an execution function by name"""
        self._executors[name] = fn
        logger.debug(f"Registered executor: {name}")
    
    async def execute(
        self,
        dag: DecisionDAG,
        context: Dict[str, Any],
    ) -> DecisionTrace:
        """
        Execute a Decision DAG.
        
        Args:
            dag: The DAG to execute
            context: Initial context data
        
        Returns:
            DecisionTrace with full execution history
        """
        # Create trace
        trace = DecisionTrace(
            trace_id=dag.trace_id,
            dag_id=dag.dag_id,
            dag_name=dag.name,
            org_id=self.org_id,
            initial_context=context.copy(),
        )
        
        dag.started_at = datetime.utcnow()
        dag.status = NodeStatus.IN_PROGRESS
        trace.start()
        
        logger.info(f"Starting DAG execution: {dag.name} (trace: {trace.trace_id})")
        
        # Execute nodes in order
        execution_order = dag.get_execution_order()
        
        for node_id in execution_order:
            node = dag.nodes[node_id]
            
            # Check if dependencies passed
            deps_passed = all(
                dag.nodes[dep_id].status == NodeStatus.PASSED
                for dep_id in node.depends_on
            )
            
            if not deps_passed:
                node.status = NodeStatus.BLOCKED
                trace.log_node_blocked(node_id, "Dependencies not met")
                continue
            
            # Execute node
            node_result = await self._execute_node(node, context, trace)
            
            if node_result["status"] == "passed":
                node.status = NodeStatus.PASSED
                node.result = node_result.get("result")
                # Merge result into context for downstream nodes
                context.update(node_result.get("result", {}))
            elif node_result["status"] == "blocked":
                node.status = NodeStatus.BLOCKED
                node.error = node_result.get("error")
                # Don't fail entire DAG, just this branch
            else:
                node.status = NodeStatus.FAILED
                node.error = node_result.get("error")
                dag.status = NodeStatus.FAILED
                break
            
            node.completed_at = datetime.utcnow()
        
        # Finalize
        dag.completed_at = datetime.utcnow()
        if dag.status != NodeStatus.FAILED:
            dag.status = NodeStatus.PASSED if dag.is_complete() else NodeStatus.BLOCKED
        
        trace.complete(
            status=dag.status.value,
            final_context=context,
        )
        
        # Persist trace
        await self.trace_store.save(trace)
        
        logger.info(f"DAG execution complete: {dag.name} -> {dag.status}")
        
        return trace
    
    async def _execute_node(
        self,
        node: DecisionNode,
        context: Dict[str, Any],
        trace: DecisionTrace,
    ) -> Dict[str, Any]:
        """Execute a single node with its gates"""
        node.started_at = datetime.utcnow()
        node.status = NodeStatus.IN_PROGRESS
        
        trace.log_node_start(node.node_id, node.name)
        
        # Check all gates
        for gate in node.gates:
            gate_result = await self.policy_engine.evaluate_gate(gate, context)
            
            gate.status = NodeStatus.PASSED if gate_result.passed else NodeStatus.FAILED
            gate.result = gate_result.details
            gate.checked_at = datetime.utcnow()
            
            trace.log_gate_result(node.node_id, gate.gate_id, gate_result)
            
            if not gate_result.passed and gate.required:
                trace.log_node_blocked(node.node_id, gate_result.message)
                return {
                    "status": "blocked",
                    "error": gate_result.message,
                    "gate_id": gate.gate_id,
                    "requires_action": gate_result.requires_action,
                    "action_type": gate_result.action_type,
                }
        
        # All gates passed, execute the node
        if node.execute_fn and node.execute_fn in self._executors:
            try:
                executor = self._executors[node.execute_fn]
                result = await executor(context)
                trace.log_node_complete(node.node_id, result)
                return {"status": "passed", "result": result}
            except Exception as e:
                logger.error(f"Node {node.node_id} execution failed: {e}")
                trace.log_node_error(node.node_id, str(e))
                return {"status": "failed", "error": str(e)}
        
        # No executor, just pass through
        trace.log_node_complete(node.node_id, {})
        return {"status": "passed", "result": {}}
    
    async def get_pending_approvals(self, dag: DecisionDAG) -> list:
        """Get list of nodes waiting for approval"""
        pending = []
        
        for node in dag.nodes.values():
            if node.status == NodeStatus.BLOCKED:
                for gate in node.gates:
                    if gate.status == NodeStatus.FAILED and gate.gate_type.value == "approval":
                        pending.append({
                            "node_id": node.node_id,
                            "node_name": node.name,
                            "gate_id": gate.gate_id,
                            "description": gate.description,
                        })
        
        return pending
    
    async def provide_approval(
        self,
        dag: DecisionDAG,
        node_id: str,
        approved_by: UUID,
        approval_token: str,
        context: Dict[str, Any],
    ) -> DecisionTrace:
        """
        Provide approval for a blocked node and resume execution.
        """
        # Add approval to context
        context["approval_token"] = approval_token
        context["approved_by"] = str(approved_by)
        
        # Reset the blocked node
        node = dag.nodes.get(node_id)
        if node:
            node.status = NodeStatus.PENDING
            for gate in node.gates:
                if gate.gate_type.value == "approval":
                    gate.status = NodeStatus.PENDING
        
        # Resume execution
        return await self.execute(dag, context)
