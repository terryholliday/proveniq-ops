"""
PROVENIQ Ops - ClaimsIQ Mock Interface
Insurance, spoilage, liability, and risk controls

This is a MOCK implementation.
In production, this would connect to the PROVENIQ ClaimsIQ system.

Contract:
    - Ops queries ClaimsIQ for risk assessment
    - Ops does NOT own risk rules
    - ClaimsIQ provides authoritative risk flags
"""

import uuid
from datetime import datetime, timedelta
from typing import Literal, Optional

from app.models.schemas import RiskCheckRequest, RiskCheckResponse


class ClaimsIQMock:
    """
    Mock ClaimsIQ Risk System Interface
    
    Simulates risk assessment and liability flagging.
    Configurable risk scenarios for testing.
    """
    
    # Default risk rules
    RISK_THRESHOLDS = {
        "expiry_critical_days": 0,    # Expired = critical
        "expiry_high_days": 3,        # Within 3 days = high
        "expiry_medium_days": 7,      # Within 7 days = medium
        "expiry_low_days": 14,        # Within 14 days = low
    }
    
    # Product categories with inherent risk levels
    CATEGORY_RISK_MODIFIERS = {
        "standard": 0,
        "perishable": 1,      # +1 risk level
        "hazardous": 2,       # +2 risk levels
        "controlled": 2,      # +2 risk levels
    }
    
    def __init__(self) -> None:
        self._flagged_products: set[uuid.UUID] = set()
        self._check_log: list[dict] = []
        self._product_categories: dict[uuid.UUID, str] = {}
        self._product_expiries: dict[uuid.UUID, datetime] = {}
    
    def set_product_category(self, product_id: uuid.UUID, category: str) -> None:
        """Set product risk category for testing."""
        self._product_categories[product_id] = category
    
    def set_product_expiry(self, product_id: uuid.UUID, expiry: datetime) -> None:
        """Set product expiry date for testing."""
        self._product_expiries[product_id] = expiry
    
    def flag_product(self, product_id: uuid.UUID) -> None:
        """Manually flag a product as high risk."""
        self._flagged_products.add(product_id)
    
    def unflag_product(self, product_id: uuid.UUID) -> None:
        """Remove manual flag from product."""
        self._flagged_products.discard(product_id)
    
    def _calculate_risk_level(
        self,
        product_id: uuid.UUID,
        expiry_date: Optional[datetime],
    ) -> tuple[Literal["none", "low", "medium", "high", "critical"], list[str]]:
        """
        Calculate risk level based on expiry and category.
        
        ClaimsIQ Risk Audit Rule:
            IF item_expiry < today
            → flag as liability
            → recommend disposal
        
        Returns:
            Tuple of (risk_level, liability_flags)
        """
        liability_flags: list[str] = []
        risk_level: Literal["none", "low", "medium", "high", "critical"] = "none"
        
        # Check manual flags
        if product_id in self._flagged_products:
            liability_flags.append("MANUAL_FLAG")
            risk_level = "high"
        
        # Check expiry
        if expiry_date:
            now = datetime.utcnow()
            days_until_expiry = (expiry_date - now).days
            
            if days_until_expiry < self.RISK_THRESHOLDS["expiry_critical_days"]:
                liability_flags.append("EXPIRED")
                risk_level = "critical"
            elif days_until_expiry <= self.RISK_THRESHOLDS["expiry_high_days"]:
                liability_flags.append("EXPIRING_SOON")
                risk_level = max(risk_level, "high", key=self._risk_order)
            elif days_until_expiry <= self.RISK_THRESHOLDS["expiry_medium_days"]:
                liability_flags.append("EXPIRY_WARNING")
                risk_level = max(risk_level, "medium", key=self._risk_order)
            elif days_until_expiry <= self.RISK_THRESHOLDS["expiry_low_days"]:
                liability_flags.append("EXPIRY_NOTICE")
                risk_level = max(risk_level, "low", key=self._risk_order)
        
        # Apply category modifier
        category = self._product_categories.get(product_id, "standard")
        modifier = self.CATEGORY_RISK_MODIFIERS.get(category, 0)
        
        if modifier > 0:
            liability_flags.append(f"CATEGORY_{category.upper()}")
            risk_level = self._elevate_risk(risk_level, modifier)
        
        return risk_level, liability_flags
    
    @staticmethod
    def _risk_order(level: str) -> int:
        """Ordering function for risk levels."""
        order = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        return order.get(level, 0)
    
    def _elevate_risk(
        self,
        current: Literal["none", "low", "medium", "high", "critical"],
        levels: int,
    ) -> Literal["none", "low", "medium", "high", "critical"]:
        """Elevate risk level by specified number of levels."""
        risk_ladder = ["none", "low", "medium", "high", "critical"]
        current_idx = risk_ladder.index(current)
        new_idx = min(current_idx + levels, len(risk_ladder) - 1)
        return risk_ladder[new_idx]  # type: ignore
    
    def _get_recommended_action(
        self,
        risk_level: Literal["none", "low", "medium", "high", "critical"],
        liability_flags: list[str],
    ) -> Optional[str]:
        """Generate recommended action based on risk assessment."""
        if "EXPIRED" in liability_flags:
            return "Dispose immediately. Log spoilage claim."
        if risk_level == "critical":
            return "Halt operation. Manual review required."
        if risk_level == "high":
            return "Expedite sale or transfer. Monitor closely."
        if "EXPIRING_SOON" in liability_flags:
            return "Prioritize in rotation. Consider discount."
        if risk_level == "medium":
            return "Standard monitoring. No immediate action."
        return None
    
    async def check_risk(self, request: RiskCheckRequest) -> RiskCheckResponse:
        """
        Perform risk assessment on a product.
        
        Args:
            request: RiskCheckRequest with product details
        
        Returns:
            RiskCheckResponse with risk evaluation
        """
        # Use stored expiry if available, otherwise use request
        expiry = self._product_expiries.get(request.product_id) or request.expiry_date
        
        risk_level, liability_flags = self._calculate_risk_level(
            request.product_id,
            expiry,
        )
        
        recommended_action = self._get_recommended_action(risk_level, liability_flags)
        
        response = RiskCheckResponse(
            is_flagged=len(liability_flags) > 0,
            risk_level=risk_level,
            liability_flags=liability_flags,
            recommended_action=recommended_action,
        )
        
        # Log the check
        self._check_log.append({
            "product_id": str(request.product_id),
            "risk_level": risk_level,
            "liability_flags": liability_flags,
            "checked_at": datetime.utcnow().isoformat(),
        })
        
        return response
    
    def get_check_log(self) -> list[dict]:
        """Return risk check audit log."""
        return self._check_log.copy()
    
    def reset(self) -> None:
        """Reset mock state."""
        self._flagged_products = set()
        self._check_log = []
        self._product_categories = {}
        self._product_expiries = {}


# Singleton instance for application-wide use
claimsiq_mock_instance = ClaimsIQMock()
