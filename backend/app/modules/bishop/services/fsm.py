"""BISHOP FSM - Finite State Machine for Scan Operations

State Flow:
IDLE -> SCANNING -> ANALYZING_RISK -> CHECKING_FUNDS -> ORDER_QUEUED -> COMPLETED
                                                      -> COMPLETED (if no order needed)
Any state can transition to FAILED on error.
"""
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.bishop.models import BishopScan, BishopScanStatus


class FSMTransitionError(Exception):
    """Invalid state transition."""
    pass


class BishopFSM:
    """Manages state transitions for BISHOP scan operations."""

    # Valid state transitions
    TRANSITIONS: dict[BishopScanStatus, list[BishopScanStatus]] = {
        BishopScanStatus.IDLE: [BishopScanStatus.SCANNING, BishopScanStatus.FAILED],
        BishopScanStatus.SCANNING: [BishopScanStatus.ANALYZING_RISK, BishopScanStatus.FAILED],
        BishopScanStatus.ANALYZING_RISK: [BishopScanStatus.CHECKING_FUNDS, BishopScanStatus.COMPLETED, BishopScanStatus.FAILED],
        BishopScanStatus.CHECKING_FUNDS: [BishopScanStatus.ORDER_QUEUED, BishopScanStatus.COMPLETED, BishopScanStatus.FAILED],
        BishopScanStatus.ORDER_QUEUED: [BishopScanStatus.COMPLETED, BishopScanStatus.FAILED],
        BishopScanStatus.COMPLETED: [],  # Terminal state
        BishopScanStatus.FAILED: [],  # Terminal state
    }

    def __init__(self, db: Session):
        self.db = db

    def can_transition(self, current: BishopScanStatus, target: BishopScanStatus) -> bool:
        """Check if a transition is valid."""
        return target in self.TRANSITIONS.get(current, [])

    def transition(self, scan: BishopScan, target: BishopScanStatus, **kwargs) -> BishopScan:
        """
        Transition a scan to a new state.
        
        Args:
            scan: The scan to transition
            target: The target state
            **kwargs: Additional fields to update on the scan
            
        Returns:
            Updated scan object
            
        Raises:
            FSMTransitionError: If the transition is invalid
        """
        if not self.can_transition(scan.status, target):
            raise FSMTransitionError(
                f"Invalid transition: {scan.status.value} -> {target.value}"
            )

        scan.status = target

        # Apply any additional updates
        for key, value in kwargs.items():
            if hasattr(scan, key):
                setattr(scan, key, value)

        # Mark completion time for terminal states
        if target in (BishopScanStatus.COMPLETED, BishopScanStatus.FAILED):
            scan.completed_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(scan)
        return scan

    def start_scan(self, scan: BishopScan) -> BishopScan:
        """Transition from IDLE to SCANNING."""
        return self.transition(scan, BishopScanStatus.SCANNING)

    def complete_scanning(self, scan: BishopScan, ai_results: dict[str, Any]) -> BishopScan:
        """Transition from SCANNING to ANALYZING_RISK with AI results."""
        return self.transition(
            scan,
            BishopScanStatus.ANALYZING_RISK,
            ai_detected_items=ai_results.get("detected_items"),
            discrepancies=ai_results.get("discrepancies"),
        )

    def complete_risk_analysis(
        self, 
        scan: BishopScan, 
        risk_score: float, 
        suggested_order: dict[str, Any] | None = None
    ) -> BishopScan:
        """
        Transition from ANALYZING_RISK.
        If suggested_order exists, go to CHECKING_FUNDS.
        Otherwise, go to COMPLETED.
        """
        if suggested_order:
            return self.transition(
                scan,
                BishopScanStatus.CHECKING_FUNDS,
                risk_score=risk_score,
                suggested_order=suggested_order,
                order_total=suggested_order.get("total", 0),
            )
        else:
            return self.transition(
                scan,
                BishopScanStatus.COMPLETED,
                risk_score=risk_score,
            )

    def queue_order(self, scan: BishopScan) -> BishopScan:
        """Transition from CHECKING_FUNDS to ORDER_QUEUED."""
        return self.transition(scan, BishopScanStatus.ORDER_QUEUED)

    def complete(self, scan: BishopScan, order_approved: bool = False, approved_by: UUID | None = None) -> BishopScan:
        """Transition to COMPLETED."""
        return self.transition(
            scan,
            BishopScanStatus.COMPLETED,
            order_approved=order_approved,
            order_approved_by_id=approved_by,
        )

    def fail(self, scan: BishopScan, error_details: dict[str, Any] | None = None) -> BishopScan:
        """Transition to FAILED."""
        return self.transition(
            scan,
            BishopScanStatus.FAILED,
            discrepancies={"error": error_details} if error_details else None,
        )
