"""
PROVENIQ Ops - Mock System API Routes
Endpoints for testing and configuring mock external systems
"""

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter

from app.models.schemas import LedgerCheckRequest, LedgerCheckResponse, RiskCheckRequest, RiskCheckResponse
from app.services.mocks import capital_mock_instance, claimsiq_mock_instance, ledger_mock_instance
from app.services.mocks.capital import FinancingRequest, FinancingResponse

router = APIRouter(prefix="/mocks", tags=["Mock Systems"])


# =============================================================================
# LEDGER MOCK
# =============================================================================

@router.get("/ledger/balance")
async def get_ledger_balance() -> dict:
    """Get current mock Ledger balance."""
    return {
        "available_balance": str(ledger_mock_instance.balance),
        "currency": "USD",
    }


@router.post("/ledger/balance")
async def set_ledger_balance(amount: Decimal) -> dict:
    """Set mock Ledger balance for testing scenarios."""
    ledger_mock_instance.set_balance(amount)
    return {
        "new_balance": str(ledger_mock_instance.balance),
        "currency": "USD",
    }


@router.post("/ledger/check", response_model=LedgerCheckResponse)
async def check_ledger_funds(request: LedgerCheckRequest) -> LedgerCheckResponse:
    """
    Direct Ledger funds check.
    
    Ledger Guardrail:
        IF wallet_balance < order_total
        → block execution
        → alert Bishop
    """
    return await ledger_mock_instance.check_funds(request)


@router.get("/ledger/log")
async def get_ledger_log() -> list[dict]:
    """Get Ledger check audit log."""
    return ledger_mock_instance.get_check_log()


@router.post("/ledger/reset")
async def reset_ledger(balance: Optional[Decimal] = None) -> dict:
    """Reset Ledger mock state."""
    ledger_mock_instance.reset(balance)
    return {"status": "reset", "balance": str(ledger_mock_instance.balance)}


# =============================================================================
# CLAIMSIQ MOCK
# =============================================================================

@router.post("/claimsiq/check", response_model=RiskCheckResponse)
async def check_claimsiq_risk(request: RiskCheckRequest) -> RiskCheckResponse:
    """
    Direct ClaimsIQ risk check.
    
    ClaimsIQ Risk Audit Rule:
        IF item_expiry < today
        → flag as liability
        → recommend disposal
    """
    return await claimsiq_mock_instance.check_risk(request)


@router.get("/claimsiq/log")
async def get_claimsiq_log() -> list[dict]:
    """Get ClaimsIQ risk check audit log."""
    return claimsiq_mock_instance.get_check_log()


@router.post("/claimsiq/reset")
async def reset_claimsiq() -> dict:
    """Reset ClaimsIQ mock state."""
    claimsiq_mock_instance.reset()
    return {"status": "reset"}


# =============================================================================
# CAPITAL MOCK (Future Hook)
# =============================================================================

@router.get("/capital/credit")
async def get_capital_credit() -> dict:
    """Get available Capital credit line."""
    return {
        "available_credit": str(capital_mock_instance.available_credit),
        "currency": "USD",
        "note": "Future hook - not integrated into Ops workflow",
    }


@router.post("/capital/financing", response_model=FinancingResponse)
async def request_capital_financing(request: FinancingRequest) -> FinancingResponse:
    """
    Request inventory financing (future hook).
    
    NOTE: Not currently wired into Ops workflow.
    """
    return await capital_mock_instance.request_financing(request)


@router.get("/capital/log")
async def get_capital_log() -> list[dict]:
    """Get Capital financing request log."""
    return capital_mock_instance.get_request_log()


@router.post("/capital/reset")
async def reset_capital() -> dict:
    """Reset Capital mock state."""
    capital_mock_instance.reset()
    return {"status": "reset"}
