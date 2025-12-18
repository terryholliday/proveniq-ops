"""
PROVENIQ Ops - Ledger Mock Interface
Real-time cash & liquidity verification

This is a MOCK implementation.
In production, this would connect to the PROVENIQ Ledger system.

Contract:
    - Ops queries Ledger for balance verification
    - Ops does NOT own financial truth
    - Ledger provides authoritative balance data
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.models.schemas import LedgerCheckRequest, LedgerCheckResponse


class LedgerMock:
    """
    Mock Ledger System Interface
    
    Simulates real-time cash and liquidity checks.
    Configurable balance for testing scenarios.
    """
    
    def __init__(self, initial_balance: Decimal = Decimal("10000.00")) -> None:
        self._balance: Decimal = initial_balance
        self._currency: str = "USD"
        self._check_log: list[dict] = []
    
    @property
    def balance(self) -> Decimal:
        """Current mock balance."""
        return self._balance
    
    def set_balance(self, amount: Decimal) -> None:
        """Set mock balance for testing scenarios."""
        self._balance = amount
    
    def adjust_balance(self, delta: Decimal) -> Decimal:
        """Adjust balance by delta amount. Returns new balance."""
        self._balance += delta
        return self._balance
    
    async def check_funds(self, request: LedgerCheckRequest) -> LedgerCheckResponse:
        """
        Verify if sufficient funds are available for an order.
        
        Ledger Guardrail:
            IF wallet_balance < order_total
            → block execution
            → alert Bishop
        
        Args:
            request: LedgerCheckRequest with order_total
        
        Returns:
            LedgerCheckResponse with fund availability status
        """
        sufficient = self._balance >= request.order_total
        
        # Log the check for audit
        self._check_log.append({
            "order_total": str(request.order_total),
            "available_balance": str(self._balance),
            "sufficient": sufficient,
            "checked_at": datetime.utcnow().isoformat(),
        })
        
        return LedgerCheckResponse(
            sufficient_funds=sufficient,
            available_balance=self._balance,
            currency=self._currency,
        )
    
    async def reserve_funds(self, amount: Decimal, order_id: str) -> bool:
        """
        Reserve funds for a pending order.
        
        Args:
            amount: Amount to reserve
            order_id: Order identifier for tracking
        
        Returns:
            True if reservation successful, False otherwise
        """
        if self._balance >= amount:
            self._balance -= amount
            self._check_log.append({
                "action": "reserve",
                "amount": str(amount),
                "order_id": order_id,
                "new_balance": str(self._balance),
                "timestamp": datetime.utcnow().isoformat(),
            })
            return True
        return False
    
    async def release_funds(self, amount: Decimal, order_id: str) -> None:
        """
        Release reserved funds (order cancelled/failed).
        
        Args:
            amount: Amount to release
            order_id: Order identifier
        """
        self._balance += amount
        self._check_log.append({
            "action": "release",
            "amount": str(amount),
            "order_id": order_id,
            "new_balance": str(self._balance),
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def get_check_log(self) -> list[dict]:
        """Return fund check audit log."""
        return self._check_log.copy()
    
    def reset(self, balance: Optional[Decimal] = None) -> None:
        """Reset mock state."""
        self._balance = balance or Decimal("10000.00")
        self._check_log = []


# Singleton instance for application-wide use
ledger_mock_instance = LedgerMock()
