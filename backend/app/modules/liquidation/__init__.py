"""Liquidation Module - PROVENIQ Bids Integration

Enables commercial landlords to liquidate abandoned/seized tenant items
via PROVENIQ Bids auction platform.
"""

from app.modules.liquidation.router import router as liquidation_router

__all__ = ["liquidation_router"]
