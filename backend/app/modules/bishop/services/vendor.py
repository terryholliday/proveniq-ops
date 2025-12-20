"""BISHOP Vendor Service - Integration with Food Service Vendors (SYSCO, US Foods, etc.)"""
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.bishop.models import BishopLocation


class VendorClient:
    """Base class for vendor API clients."""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def sync_catalog(self) -> list[dict[str, Any]]:
        """Sync product catalog from vendor."""
        raise NotImplementedError

    def submit_order(self, order: dict[str, Any]) -> dict[str, Any]:
        """Submit an order to the vendor."""
        raise NotImplementedError

    def get_order_status(self, order_id: str) -> dict[str, Any]:
        """Get status of an existing order."""
        raise NotImplementedError


class SYSCOClient(VendorClient):
    """Mock SYSCO API client."""

    def sync_catalog(self) -> list[dict[str, Any]]:
        """Sync SYSCO product catalog."""
        # MOCK: Would call SYSCO API in production
        return [
            {
                "vendor_sku": "SYSCO-001",
                "name": "Tomato Sauce Case (6x#10)",
                "unit": "case",
                "unit_cost": 24.99,
                "category": "Canned Goods",
            },
            {
                "vendor_sku": "SYSCO-002",
                "name": "Extra Virgin Olive Oil 1gal",
                "unit": "each",
                "unit_cost": 32.50,
                "category": "Oils & Vinegars",
            },
            {
                "vendor_sku": "SYSCO-003",
                "name": "All Purpose Flour 50lb",
                "unit": "bag",
                "unit_cost": 18.75,
                "category": "Dry Goods",
            },
        ]

    def submit_order(self, order: dict[str, Any]) -> dict[str, Any]:
        """Submit order to SYSCO."""
        # MOCK: Would call SYSCO API in production
        return {
            "order_id": f"SYSCO-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "status": "submitted",
            "estimated_delivery": "2024-01-15",
            "total": order.get("total", 0),
            "items_count": len(order.get("items", [])),
        }

    def get_order_status(self, order_id: str) -> dict[str, Any]:
        """Get SYSCO order status."""
        # MOCK
        return {
            "order_id": order_id,
            "status": "in_transit",
            "tracking_number": "1Z999AA10123456784",
        }


class USFoodsClient(VendorClient):
    """Mock US Foods API client."""

    def sync_catalog(self) -> list[dict[str, Any]]:
        """Sync US Foods product catalog."""
        # MOCK
        return [
            {
                "vendor_sku": "USF-101",
                "name": "All Purpose Flour 50lb Bag",
                "unit": "bag",
                "unit_cost": 17.99,
                "category": "Dry Goods",
            },
            {
                "vendor_sku": "USF-102",
                "name": "Canola Oil 35lb JIB",
                "unit": "each",
                "unit_cost": 28.50,
                "category": "Oils",
            },
        ]

    def submit_order(self, order: dict[str, Any]) -> dict[str, Any]:
        """Submit order to US Foods."""
        # MOCK
        return {
            "order_id": f"USF-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "status": "received",
            "estimated_delivery": "2024-01-16",
            "total": order.get("total", 0),
        }

    def get_order_status(self, order_id: str) -> dict[str, Any]:
        """Get US Foods order status."""
        # MOCK
        return {
            "order_id": order_id,
            "status": "processing",
        }


class VendorService:
    """Service for managing vendor integrations."""

    VENDOR_CLIENTS = {
        "sysco": SYSCOClient,
        "usfoods": USFoodsClient,
    }

    def __init__(self, db: Session):
        self.db = db
        self._clients: dict[str, VendorClient] = {}

    def get_client(self, vendor_name: str, config: dict[str, Any]) -> VendorClient:
        """Get or create a vendor client."""
        vendor_key = vendor_name.lower().replace(" ", "")
        
        if vendor_key not in self._clients:
            client_class = self.VENDOR_CLIENTS.get(vendor_key)
            if not client_class:
                raise ValueError(f"Unknown vendor: {vendor_name}")
            self._clients[vendor_key] = client_class(config)
        
        return self._clients[vendor_key]

    def sync_location_catalog(self, location: BishopLocation) -> dict[str, list[dict[str, Any]]]:
        """Sync catalogs for all configured vendors at a location."""
        results = {}
        
        vendor_config = location.vendor_config or {}
        
        for vendor_name, config in vendor_config.items():
            try:
                client = self.get_client(vendor_name, config)
                results[vendor_name] = client.sync_catalog()
            except ValueError:
                results[vendor_name] = {"error": f"Unknown vendor: {vendor_name}"}
        
        return results

    def submit_order(
        self,
        location: BishopLocation,
        vendor_name: str,
        order: dict[str, Any],
    ) -> dict[str, Any]:
        """Submit an order to a vendor."""
        vendor_config = (location.vendor_config or {}).get(vendor_name, {})
        client = self.get_client(vendor_name, vendor_config)
        return client.submit_order(order)

    def check_budget(
        self,
        location: BishopLocation,
        order_total: float,
    ) -> dict[str, Any]:
        """
        Check if an order is within budget limits.
        
        Returns approval status and any warnings.
        """
        if not location.daily_order_limit:
            return {
                "approved": True,
                "reason": "No daily limit configured",
            }

        if order_total <= location.daily_order_limit:
            return {
                "approved": True,
                "remaining_budget": location.daily_order_limit - order_total,
            }
        else:
            return {
                "approved": False,
                "reason": "Order exceeds daily limit",
                "order_total": order_total,
                "daily_limit": location.daily_order_limit,
                "overage": order_total - location.daily_order_limit,
            }
