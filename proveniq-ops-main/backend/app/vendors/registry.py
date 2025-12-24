"""
PROVENIQ Ops - Vendor Registry

Central registry for all vendor clients.
Handles vendor selection, routing, and failover.
"""

import logging
from typing import Optional, List, Dict
from uuid import UUID

from .base import VendorClient, VendorProduct, VendorOrder, VendorOrderItem
from .sysco import SyscoClient
from .usfoods import USFoodsClient

logger = logging.getLogger(__name__)


class VendorRegistry:
    """
    Central registry for vendor clients.
    
    Provides:
    - Vendor lookup by ID or name
    - Multi-vendor price comparison
    - Automatic vendor selection based on criteria
    - Order routing to appropriate vendor
    """
    
    def __init__(self):
        self._vendors: Dict[str, VendorClient] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize all vendor clients"""
        if self._initialized:
            return
        
        # Register SYSCO
        sysco = SyscoClient(
            api_key="SYSCO_API_KEY",  # From config/env
            customer_id="SYSCO_CUSTOMER_ID",
        )
        await sysco.authenticate()
        self._vendors["sysco"] = sysco
        
        # Register US Foods
        usfoods = USFoodsClient(
            api_key="USFOODS_API_KEY",
            account_number="USFOODS_ACCOUNT",
        )
        await usfoods.authenticate()
        self._vendors["usfoods"] = usfoods
        
        self._initialized = True
        logger.info(f"VendorRegistry initialized with {len(self._vendors)} vendors")
    
    def get_vendor(self, vendor_id: str) -> Optional[VendorClient]:
        """Get vendor client by ID"""
        return self._vendors.get(vendor_id.lower())
    
    def list_vendors(self) -> List[VendorClient]:
        """List all registered vendors"""
        return list(self._vendors.values())
    
    async def compare_prices(
        self,
        product_name: str,
        quantity: int = 1,
    ) -> List[dict]:
        """
        Compare prices across all vendors for a product.
        
        Returns list of vendor options sorted by price.
        """
        results = []
        
        for vendor in self._vendors.values():
            products = await vendor.search_products(product_name, limit=1)
            if products:
                product = products[0]
                price = await vendor.get_price(product.vendor_sku, quantity)
                available, avail_qty, lead_time = await vendor.check_availability(
                    product.vendor_sku, quantity
                )
                
                results.append({
                    "vendor_id": vendor.vendor_id,
                    "vendor_name": vendor.vendor_name,
                    "vendor_sku": product.vendor_sku,
                    "product_name": product.name,
                    "unit_price_cents": price,
                    "total_cents": price * quantity,
                    "in_stock": available,
                    "available_quantity": avail_qty,
                    "lead_time_hours": lead_time,
                })
        
        # Sort by price
        results.sort(key=lambda x: x["total_cents"])
        return results
    
    async def find_best_vendor(
        self,
        product_name: str,
        quantity: int,
        prefer_price: bool = True,
        max_lead_time_hours: Optional[int] = None,
    ) -> Optional[dict]:
        """
        Find the best vendor for a product based on criteria.
        
        Args:
            product_name: Product to search for
            quantity: Required quantity
            prefer_price: If True, prioritize lowest price. If False, prioritize fastest delivery.
            max_lead_time_hours: Maximum acceptable lead time
        
        Returns:
            Best vendor option or None if no suitable vendor found
        """
        options = await self.compare_prices(product_name, quantity)
        
        # Filter by availability
        options = [o for o in options if o["in_stock"] and o["available_quantity"] >= quantity]
        
        # Filter by lead time
        if max_lead_time_hours:
            options = [o for o in options if (o["lead_time_hours"] or 0) <= max_lead_time_hours]
        
        if not options:
            return None
        
        if prefer_price:
            # Already sorted by price
            return options[0]
        else:
            # Sort by lead time
            options.sort(key=lambda x: x["lead_time_hours"] or 999)
            return options[0]
    
    async def submit_order(
        self,
        vendor_id: str,
        internal_order_id: UUID,
        items: List[VendorOrderItem],
    ) -> VendorOrder:
        """
        Submit order to specified vendor.
        """
        vendor = self.get_vendor(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {vendor_id} not found")
        
        return await vendor.submit_order(internal_order_id, items)
    
    async def get_order_status(
        self,
        vendor_id: str,
        vendor_order_id: str,
    ) -> VendorOrder:
        """Get order status from vendor"""
        vendor = self.get_vendor(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {vendor_id} not found")
        
        return await vendor.get_order_status(vendor_order_id)


# Singleton instance
_registry_instance: Optional[VendorRegistry] = None


async def get_vendor_registry() -> VendorRegistry:
    """Get or create the vendor registry singleton"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = VendorRegistry()
        await _registry_instance.initialize()
    return _registry_instance
