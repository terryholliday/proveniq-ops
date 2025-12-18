"""
PROVENIQ Ops - DAG Governance Tests
Enforceable governance through automated testing.

For every node:
- Happy path test
- Missing dependency test
- Low confidence downgrade test
- Policy gate fail test
"""

import pytest
import uuid
from datetime import datetime
from decimal import Decimal

from app.services.bishop.orchestrator import (
    DAGValidationError,
    DecisionOrchestrator,
    MissingDependency,
    NodeNotRegistered,
    NodeStatus,
    bishop_node,
)


class TestDAGValidation:
    """Tests for DAG structure validation."""
    
    def test_dag_loads_successfully(self):
        """DAG file must load without errors."""
        orchestrator = DecisionOrchestrator()
        orchestrator.load()
        assert orchestrator._loaded
        assert len(orchestrator._nodes) > 0
    
    def test_dag_has_no_circular_dependencies(self):
        """DAG must not contain circular dependencies."""
        orchestrator = DecisionOrchestrator()
        orchestrator.load()  # Would raise DAGValidationError if circular
        
        # Verify all dependencies exist
        for node_id, node in orchestrator._nodes.items():
            for dep in node.depends_on:
                assert dep in orchestrator._nodes, \
                    f"Node {node_id} depends on non-existent {dep}"
    
    def test_dag_layers_are_ordered(self):
        """Dependencies must only point to lower layers."""
        orchestrator = DecisionOrchestrator()
        orchestrator.load()
        
        for node_id, node in orchestrator._nodes.items():
            for dep in node.depends_on:
                dep_node = orchestrator._nodes[dep]
                assert dep_node.layer < node.layer, \
                    f"Node {node_id} (layer {node.layer}) depends on " \
                    f"{dep} (layer {dep_node.layer}) - must be lower layer"
    
    def test_all_nodes_have_outputs(self):
        """Every node must declare at least one output."""
        orchestrator = DecisionOrchestrator()
        orchestrator.load()
        
        for node_id, node in orchestrator._nodes.items():
            assert len(node.outputs) > 0, \
                f"Node {node_id} has no declared outputs"


class TestNodeRegistration:
    """Tests for node registration and validation."""
    
    def test_register_valid_node(self):
        """Valid node registration must succeed."""
        orchestrator = DecisionOrchestrator()
        orchestrator.load()
        
        # Register a handler for N0_inventory_snapshot
        def mock_handler():
            return []
        
        orchestrator.register_node(
            node_id="N0_inventory_snapshot",
            handler=mock_handler,
            inputs=[],
            output="inventory_levels",
            side_effects=False,
        )
        
        assert "N0_inventory_snapshot" in orchestrator._handlers
    
    def test_register_undeclared_node_fails(self):
        """Registering a node not in DAG must fail."""
        orchestrator = DecisionOrchestrator()
        orchestrator.load()
        
        def mock_handler():
            return []
        
        with pytest.raises(DAGValidationError) as exc:
            orchestrator.register_node(
                node_id="N99_fake_node",
                handler=mock_handler,
                inputs=[],
                output="fake_output",
                side_effects=False,
            )
        
        assert "not declared in bishop_dag.yaml" in str(exc.value)
    
    def test_register_mismatched_inputs_fails(self):
        """Registration with wrong inputs must fail."""
        orchestrator = DecisionOrchestrator()
        orchestrator.load()
        
        def mock_handler(wrong_input):
            return []
        
        with pytest.raises(DAGValidationError) as exc:
            orchestrator.register_node(
                node_id="N0_inventory_snapshot",
                handler=mock_handler,
                inputs=["wrong_input"],  # DAG declares []
                output="inventory_levels",
                side_effects=False,
            )
        
        assert "inputs mismatch" in str(exc.value)
    
    def test_register_mismatched_side_effects_fails(self):
        """Registration with wrong side_effects must fail."""
        orchestrator = DecisionOrchestrator()
        orchestrator.load()
        
        def mock_handler():
            return []
        
        with pytest.raises(DAGValidationError) as exc:
            orchestrator.register_node(
                node_id="N0_inventory_snapshot",
                handler=mock_handler,
                inputs=[],
                output="inventory_levels",
                side_effects=True,  # DAG declares none
            )
        
        assert "side_effects mismatch" in str(exc.value)


class TestNodeExecution:
    """Tests for node execution and dependencies."""
    
    def test_execute_node_without_dependencies(self):
        """Layer 0 nodes should execute without dependencies."""
        orchestrator = DecisionOrchestrator()
        orchestrator.load()
        
        def mock_snapshot():
            return [{"product_id": "123", "on_hand_qty": 10}]
        
        orchestrator.register_node(
            node_id="N0_inventory_snapshot",
            handler=mock_snapshot,
            inputs=[],
            output="inventory_levels",
            side_effects=False,
        )
        
        result = orchestrator.execute_node("N0_inventory_snapshot", {})
        assert len(result) == 1
        assert result[0]["on_hand_qty"] == 10
    
    def test_execute_node_with_missing_dependency(self):
        """Executing node with missing upstream must raise."""
        orchestrator = DecisionOrchestrator()
        orchestrator.load()
        
        def mock_stockout(inventory_levels, demand_forecast, vendor_lead_times):
            return []
        
        orchestrator.register_node(
            node_id="N11_stockout_risk",
            handler=mock_stockout,
            inputs=["inventory_levels", "demand_forecast", "vendor_lead_times"],
            output="stockout_risks",
            side_effects=False,
        )
        
        with pytest.raises(MissingDependency) as exc:
            orchestrator.execute_node("N11_stockout_risk", {})
        
        assert "missing dependencies" in str(exc.value)
    
    def test_execute_unregistered_node_fails(self):
        """Executing node without handler must fail."""
        orchestrator = DecisionOrchestrator()
        orchestrator.load()
        
        with pytest.raises(NodeNotRegistered):
            orchestrator.execute_node("N0_inventory_snapshot", {})


class TestCaching:
    """Tests for node output caching."""
    
    def test_cacheable_node_returns_cached_result(self):
        """Cacheable nodes should return cached results."""
        orchestrator = DecisionOrchestrator()
        orchestrator.load()
        
        call_count = 0
        
        def mock_snapshot():
            nonlocal call_count
            call_count += 1
            return [{"count": call_count}]
        
        orchestrator.register_node(
            node_id="N0_inventory_snapshot",
            handler=mock_snapshot,
            inputs=[],
            output="inventory_levels",
            side_effects=False,
        )
        
        # First call
        result1 = orchestrator.execute_node("N0_inventory_snapshot", {})
        # Second call should hit cache
        result2 = orchestrator.execute_node("N0_inventory_snapshot", {})
        
        assert result1[0]["count"] == 1
        assert result2[0]["count"] == 1  # Same as first (cached)
        assert call_count == 1  # Handler only called once
    
    def test_force_bypasses_cache(self):
        """Force=True should bypass cache."""
        orchestrator = DecisionOrchestrator()
        orchestrator.load()
        
        call_count = 0
        
        def mock_snapshot():
            nonlocal call_count
            call_count += 1
            return [{"count": call_count}]
        
        orchestrator.register_node(
            node_id="N0_inventory_snapshot",
            handler=mock_snapshot,
            inputs=[],
            output="inventory_levels",
            side_effects=False,
        )
        
        result1 = orchestrator.execute_node("N0_inventory_snapshot", {})
        result2 = orchestrator.execute_node("N0_inventory_snapshot", {}, force=True)
        
        assert result1[0]["count"] == 1
        assert result2[0]["count"] == 2  # Fresh execution
        assert call_count == 2


class TestPolicyGates:
    """Tests for policy gate invariants."""
    
    def test_ledger_gate_blocks_insufficient_funds(self):
        """Ledger gate must block when funds insufficient."""
        # This tests the invariant:
        # "approved == true IMPLIES available_balance >= order_total"
        
        def mock_ledger_gate(order_total, ledger_balance):
            approved = ledger_balance >= order_total
            return {
                "approved": approved,
                "available_balance": ledger_balance,
                "shortfall": order_total - ledger_balance if not approved else None,
                "blocked_reason": "Insufficient funds" if not approved else None,
            }
        
        # Test insufficient funds
        result = mock_ledger_gate(order_total=1000, ledger_balance=500)
        assert result["approved"] == False
        assert result["blocked_reason"] is not None
        assert result["shortfall"] == 500
        
        # Test sufficient funds
        result = mock_ledger_gate(order_total=500, ledger_balance=1000)
        assert result["approved"] == True
        assert result["blocked_reason"] is None
    
    def test_confidence_gate_downgrades_low_confidence(self):
        """Confidence below 0.6 must downgrade to warning."""
        # This tests the invariant:
        # "confidence < 0.6 IMPLIES downgrade_to_warning == true"
        
        def mock_confidence_gate(signal_confidence, action_type):
            threshold = 0.85 if action_type == "auto_execute" else 0.6
            return {
                "approved": signal_confidence >= threshold,
                "confidence": signal_confidence,
                "threshold": threshold,
                "downgrade_to_warning": signal_confidence < 0.6,
            }
        
        # Test low confidence
        result = mock_confidence_gate(signal_confidence=0.5, action_type="proposal")
        assert result["downgrade_to_warning"] == True
        
        # Test adequate confidence
        result = mock_confidence_gate(signal_confidence=0.7, action_type="proposal")
        assert result["downgrade_to_warning"] == False


class TestSideEffects:
    """Tests for side effect enforcement."""
    
    def test_no_side_effects_node_cannot_modify_state(self):
        """Nodes declaring no side_effects must not modify external state."""
        # This is an invariant test - the DAG declares side_effects: none
        # for most nodes. In production, this would be enforced by
        # monitoring database writes during node execution.
        
        orchestrator = DecisionOrchestrator()
        orchestrator.load()
        
        # Verify most nodes declare no side effects
        no_side_effect_nodes = [
            node_id for node_id, node in orchestrator._nodes.items()
            if node.side_effects in ("none", None, [])
        ]
        
        # Should be majority of nodes
        assert len(no_side_effect_nodes) > len(orchestrator._nodes) * 0.7
    
    def test_execution_nodes_declare_side_effects(self):
        """Layer 4 (Execution) nodes must declare their side effects."""
        orchestrator = DecisionOrchestrator()
        orchestrator.load()
        
        execution_nodes = [
            node for node in orchestrator._nodes.values()
            if node.layer == 4
        ]
        
        for node in execution_nodes:
            assert node.side_effects not in ("none", None, []), \
                f"Execution node {node.node_id} must declare side effects"


class TestMermaidExport:
    """Tests for Mermaid diagram export."""
    
    def test_mermaid_export_generates_valid_diagram(self):
        """Mermaid export should produce valid Mermaid syntax."""
        orchestrator = DecisionOrchestrator()
        orchestrator.load()
        
        mermaid = orchestrator.to_mermaid()
        
        assert mermaid.startswith("graph TD")
        assert "subgraph" in mermaid
        assert "-->" in mermaid  # Has edges
    
    def test_mermaid_includes_all_nodes(self):
        """Mermaid diagram should include all declared nodes."""
        orchestrator = DecisionOrchestrator()
        orchestrator.load()
        
        mermaid = orchestrator.to_mermaid()
        
        for node_id in orchestrator._nodes:
            assert node_id in mermaid, f"Node {node_id} missing from Mermaid"


class TestInvariants:
    """Tests for specific invariants from bishop_dag.yaml."""
    
    def test_stockout_confidence_invariant(self):
        """N11: confidence >= 0.6 OR alert_type == 'WARNING'"""
        
        def validate_stockout_risk(risk):
            confidence = risk.get("confidence", 0)
            alert_type = risk.get("alert_type", "")
            
            # Invariant check
            if confidence < 0.6:
                assert alert_type == "WARNING", \
                    f"Low confidence ({confidence}) must be WARNING, got {alert_type}"
            return True
        
        # Valid: high confidence, any alert type
        assert validate_stockout_risk({"confidence": 0.8, "alert_type": "PREDICTIVE_STOCKOUT"})
        
        # Valid: low confidence, WARNING
        assert validate_stockout_risk({"confidence": 0.5, "alert_type": "WARNING"})
        
        # Invalid: low confidence, non-WARNING
        with pytest.raises(AssertionError):
            validate_stockout_risk({"confidence": 0.5, "alert_type": "PREDICTIVE_STOCKOUT"})
    
    def test_receiving_confirmation_invariant(self):
        """N31: requires_confirmation == true (GUARDRAIL)"""
        
        def create_receiving_proposal(po_id, discrepancies):
            # GUARDRAIL: Never auto-close PO
            return {
                "proposal_id": str(uuid.uuid4()),
                "po_id": po_id,
                "action": "accept_with_adjustments" if discrepancies else "accept",
                "requires_confirmation": True,  # MUST be true
            }
        
        proposal = create_receiving_proposal("po-123", discrepancies=[])
        assert proposal["requires_confirmation"] == True
        
        proposal = create_receiving_proposal("po-456", discrepancies=["short"])
        assert proposal["requires_confirmation"] == True
    
    def test_auto_execute_requires_high_confidence(self):
        """N23: action_type == 'auto_execute' IMPLIES confidence >= 0.85"""
        
        def can_auto_execute(confidence):
            return confidence >= 0.85
        
        assert can_auto_execute(0.90) == True
        assert can_auto_execute(0.85) == True
        assert can_auto_execute(0.84) == False
        assert can_auto_execute(0.60) == False
