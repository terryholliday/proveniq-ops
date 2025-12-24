"""
PROVENIQ Ops - Vendor Bridge (Aggregator Engine)
Multi-vendor orchestration with automatic failover and price arbitrage

Core Logic:
    - Connect to multiple vendors (API-driven)
    - Each vendor has priority ranking, catalog mapping, SKU translation
    - Auto-query secondary vendors when primary is out of stock
    - Compare pricing for equivalent SKUs
    - Never auto-switch without logging rationale
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.models.schemas import VendorQueryRequest, VendorQueryResponse


@dataclass
class VendorInfo:
    """Internal vendor representation."""
    id: uuid.UUID
    name: str
    priority_level: int
    api_endpoint: Optional[str]
    is_active: bool


@dataclass
class ProductAvailability:
    """Product availability across vendors."""
    product_id: uuid.UUID
    vendor_results: list[VendorQueryResponse]
    recommended_vendor_id: Optional[uuid.UUID]
    recommendation_rationale: str
    queried_at: datetime


@dataclass
class VendorSwitchLog:
    """Audit log for vendor switching decisions."""
    original_vendor_id: uuid.UUID
    selected_vendor_id: uuid.UUID
    product_id: uuid.UUID
    reason: str
    price_delta: Optional[Decimal]
    logged_at: datetime


class VendorBridge:
    """
    Vendor Bridge Aggregator Engine
    
    Responsibilities:
        - Query vendors by priority order
        - Handle primary vendor out-of-stock failover
        - Execute price arbitrage comparisons
        - Log all switching rationale
    """
    
    def __init__(self) -> None:
        self._vendors: dict[uuid.UUID, VendorInfo] = {}
        self._switch_log: list[VendorSwitchLog] = []
        self._sku_mappings: dict[tuple[uuid.UUID, uuid.UUID], str] = {}  # (vendor_id, product_id) -> vendor_sku
    
    def register_vendor(self, vendor: VendorInfo) -> None:
        """Register a vendor in the bridge."""
        self._vendors[vendor.id] = vendor
    
    def register_sku_mapping(
        self,
        vendor_id: uuid.UUID,
        product_id: uuid.UUID,
        vendor_sku: str,
    ) -> None:
        """Register SKU translation for vendor-product pair."""
        self._sku_mappings[(vendor_id, product_id)] = vendor_sku
    
    def get_vendors_by_priority(self, active_only: bool = True) -> list[VendorInfo]:
        """Get vendors sorted by priority level (1 = highest)."""
        vendors = list(self._vendors.values())
        if active_only:
            vendors = [v for v in vendors if v.is_active]
        return sorted(vendors, key=lambda v: v.priority_level)
    
    def get_sku_for_vendor(
        self,
        vendor_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> Optional[str]:
        """Get vendor-specific SKU for a product."""
        return self._sku_mappings.get((vendor_id, product_id))
    
    async def query_vendor_availability(
        self,
        vendor: VendorInfo,
        product_id: uuid.UUID,
        quantity_needed: int,
        mock_response: Optional[VendorQueryResponse] = None,
    ) -> VendorQueryResponse:
        """
        Query a single vendor for product availability.
        
        In production: Makes API call to vendor.api_endpoint
        In development: Uses mock_response or generates default mock
        
        Args:
            vendor: Vendor to query
            product_id: Product to check
            quantity_needed: Required quantity
            mock_response: Optional mock for testing
        
        Returns:
            VendorQueryResponse with availability details
        """
        if mock_response:
            return mock_response
        
        # Default mock response for development
        # In production, this would make an HTTP call to vendor.api_endpoint
        return VendorQueryResponse(
            vendor_id=vendor.id,
            vendor_name=vendor.name,
            in_stock=True,
            available_quantity=quantity_needed,
            unit_price=Decimal("10.00"),
            estimated_delivery_hours=4,
        )
    
    async def find_best_vendor(
        self,
        product_id: uuid.UUID,
        quantity_needed: int,
        prefer_price: bool = False,
        vendor_responses: Optional[list[VendorQueryResponse]] = None,
    ) -> ProductAvailability:
        """
        Find best vendor for a product with failover logic.
        
        Algorithm:
            1. Query vendors in priority order
            2. If primary has stock → use primary
            3. If primary out of stock → query secondary vendors
            4. If prefer_price → select cheapest with stock
            5. Otherwise → select highest priority with stock
        
        Args:
            product_id: Product to source
            quantity_needed: Required quantity
            prefer_price: If True, optimize for price over priority
            vendor_responses: Optional pre-fetched responses for testing
        
        Returns:
            ProductAvailability with recommendation
        """
        vendors = self.get_vendors_by_priority()
        results: list[VendorQueryResponse] = []
        
        if vendor_responses:
            # Use provided responses (testing/mocking)
            results = vendor_responses
        else:
            # Query each vendor
            for vendor in vendors:
                response = await self.query_vendor_availability(
                    vendor, product_id, quantity_needed
                )
                results.append(response)
        
        # Filter vendors with sufficient stock
        available_vendors = [
            r for r in results
            if r.in_stock and r.available_quantity >= quantity_needed
        ]
        
        if not available_vendors:
            return ProductAvailability(
                product_id=product_id,
                vendor_results=results,
                recommended_vendor_id=None,
                recommendation_rationale="No vendors have sufficient stock.",
                queried_at=datetime.utcnow(),
            )
        
        # Selection logic
        if prefer_price:
            # Select cheapest
            selected = min(available_vendors, key=lambda r: r.unit_price)
            rationale = f"Price optimization: {selected.vendor_name} at {selected.unit_price}/unit."
        else:
            # Select by priority (results are already priority-sorted)
            vendor_priority = {v.id: v.priority_level for v in vendors}
            selected = min(
                available_vendors,
                key=lambda r: vendor_priority.get(r.vendor_id, 999),
            )
            rationale = f"Priority selection: {selected.vendor_name} (priority {vendor_priority.get(selected.vendor_id, 'unknown')})."
        
        return ProductAvailability(
            product_id=product_id,
            vendor_results=results,
            recommended_vendor_id=selected.vendor_id,
            recommendation_rationale=rationale,
            queried_at=datetime.utcnow(),
        )
    
    async def execute_failover(
        self,
        product_id: uuid.UUID,
        quantity_needed: int,
        primary_vendor_id: uuid.UUID,
        vendor_responses: Optional[list[VendorQueryResponse]] = None,
    ) -> ProductAvailability:
        """
        Execute failover when primary vendor is out of stock.
        
        Failsafe Rule:
            IF primary_vendor.stock == 0
            → auto-query secondary vendors
            → recommend or draft alternative order
        
        Args:
            product_id: Product needing failover
            quantity_needed: Required quantity
            primary_vendor_id: Original preferred vendor
            vendor_responses: Optional pre-fetched responses
        
        Returns:
            ProductAvailability with alternative recommendation
        """
        availability = await self.find_best_vendor(
            product_id,
            quantity_needed,
            prefer_price=False,
            vendor_responses=vendor_responses,
        )
        
        # Log the failover if we switched vendors
        if (
            availability.recommended_vendor_id
            and availability.recommended_vendor_id != primary_vendor_id
        ):
            # Find price delta
            primary_result = next(
                (r for r in availability.vendor_results if r.vendor_id == primary_vendor_id),
                None,
            )
            selected_result = next(
                (r for r in availability.vendor_results if r.vendor_id == availability.recommended_vendor_id),
                None,
            )
            
            price_delta = None
            if primary_result and selected_result:
                price_delta = selected_result.unit_price - primary_result.unit_price
            
            log_entry = VendorSwitchLog(
                original_vendor_id=primary_vendor_id,
                selected_vendor_id=availability.recommended_vendor_id,
                product_id=product_id,
                reason=f"Primary vendor out of stock. {availability.recommendation_rationale}",
                price_delta=price_delta,
                logged_at=datetime.utcnow(),
            )
            self._switch_log.append(log_entry)
        
        return availability
    
    async def compare_prices(
        self,
        product_id: uuid.UUID,
        quantity_needed: int,
        vendor_responses: Optional[list[VendorQueryResponse]] = None,
    ) -> ProductAvailability:
        """
        Execute price arbitrage comparison across vendors.
        
        Returns cheapest compliant option with rationale.
        
        Args:
            product_id: Product to compare
            quantity_needed: Required quantity
            vendor_responses: Optional pre-fetched responses
        
        Returns:
            ProductAvailability optimized for price
        """
        return await self.find_best_vendor(
            product_id,
            quantity_needed,
            prefer_price=True,
            vendor_responses=vendor_responses,
        )
    
    def get_switch_log(self) -> list[VendorSwitchLog]:
        """Return vendor switch audit log."""
        return self._switch_log.copy()
    
    def clear_switch_log(self) -> None:
        """Clear switch log (for testing)."""
        self._switch_log = []


# Singleton instance for application-wide use
vendor_bridge_instance = VendorBridge()
