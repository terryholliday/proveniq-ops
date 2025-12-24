"""
PROVENIQ Ops - Capital Mock Interface
Inventory financing (future hook only)

This is a MOCK implementation.
In production, this would connect to the PROVENIQ Capital system.

Contract:
    - Future hook for inventory financing
    - Not currently integrated into Ops workflow
    - Interface defined for forward compatibility
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class FinancingRequest(BaseModel):
    """Request for inventory financing."""
    order_id: uuid.UUID
    amount_requested: Decimal = Field(..., gt=0)
    term_days: int = Field(30, ge=7, le=90)
    collateral_product_ids: list[uuid.UUID] = []


class FinancingResponse(BaseModel):
    """Response from financing request."""
    approved: bool
    financing_id: Optional[uuid.UUID] = None
    amount_approved: Optional[Decimal] = None
    interest_rate: Optional[Decimal] = None
    term_days: Optional[int] = None
    rejection_reason: Optional[str] = None
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


class CapitalMock:
    """
    Mock Capital System Interface
    
    Future hook for inventory financing integration.
    Currently stubbed for forward compatibility.
    """
    
    def __init__(self) -> None:
        self._credit_limit: Decimal = Decimal("50000.00")
        self._used_credit: Decimal = Decimal("0.00")
        self._base_rate: Decimal = Decimal("0.05")  # 5% base rate
        self._request_log: list[dict] = []
    
    @property
    def available_credit(self) -> Decimal:
        """Available credit line."""
        return self._credit_limit - self._used_credit
    
    def set_credit_limit(self, limit: Decimal) -> None:
        """Set credit limit for testing."""
        self._credit_limit = limit
    
    async def request_financing(self, request: FinancingRequest) -> FinancingResponse:
        """
        Request inventory financing.
        
        NOTE: This is a future hook. Not currently wired into Ops workflow.
        
        Args:
            request: FinancingRequest with order details
        
        Returns:
            FinancingResponse with approval status
        """
        # Check credit availability
        if request.amount_requested > self.available_credit:
            response = FinancingResponse(
                approved=False,
                rejection_reason=f"Insufficient credit. Available: {self.available_credit}. Requested: {request.amount_requested}.",
            )
        else:
            # Calculate rate based on term
            rate_modifier = Decimal("0.001") * request.term_days
            interest_rate = self._base_rate + rate_modifier
            
            financing_id = uuid.uuid4()
            self._used_credit += request.amount_requested
            
            response = FinancingResponse(
                approved=True,
                financing_id=financing_id,
                amount_approved=request.amount_requested,
                interest_rate=interest_rate,
                term_days=request.term_days,
            )
        
        # Log the request
        self._request_log.append({
            "order_id": str(request.order_id),
            "amount_requested": str(request.amount_requested),
            "approved": response.approved,
            "financing_id": str(response.financing_id) if response.financing_id else None,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        return response
    
    async def check_eligibility(self, amount: Decimal) -> bool:
        """
        Quick check if financing amount is eligible.
        
        Args:
            amount: Amount to check
        
        Returns:
            True if eligible, False otherwise
        """
        return amount <= self.available_credit
    
    def get_request_log(self) -> list[dict]:
        """Return financing request log."""
        return self._request_log.copy()
    
    def reset(self) -> None:
        """Reset mock state."""
        self._used_credit = Decimal("0.00")
        self._request_log = []


# Singleton instance for application-wide use
capital_mock_instance = CapitalMock()
