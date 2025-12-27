"""
PROVENIQ Ops - POS Integration Layer

Phase 5: Toast and Square POS integrations for:
- Real-time sales data sync
- Inventory depletion tracking
- Menu item cost analysis
- Automatic reorder triggers

NOTE: Actual API integrations require partnership agreements.
This module provides the integration structure and mock implementations.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass


class POSProvider(str, Enum):
    TOAST = "toast"
    SQUARE = "square"
    CLOVER = "clover"
    LIGHTSPEED = "lightspeed"


@dataclass
class POSConfig:
    """POS integration configuration."""
    provider: POSProvider
    api_key: str
    location_id: str
    webhook_secret: Optional[str] = None
    sandbox_mode: bool = True


@dataclass
class SaleItem:
    """Item sold through POS."""
    item_id: str
    name: str
    quantity: float
    unit_price_cents: int
    total_cents: int
    category: str
    sold_at: str


@dataclass
class InventoryUpdate:
    """Inventory update from POS sales."""
    item_id: str
    quantity_sold: float
    new_quantity: float
    below_par: bool
    reorder_suggested: bool


class POSIntegrationService:
    """
    Unified POS integration service.
    
    Provides:
    - Sales data ingestion
    - Inventory sync
    - Cost analysis
    - Reorder automation
    """
    
    def __init__(self):
        self.configs: Dict[str, POSConfig] = {}
        self.sales_buffer: List[SaleItem] = []
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure(self, location_id: str, config: POSConfig) -> None:
        """Configure POS integration for a location."""
        self.configs[location_id] = config
        print(f"[POS] Configured {config.provider.value} for location {location_id}")
    
    def get_config(self, location_id: str) -> Optional[POSConfig]:
        """Get POS config for location."""
        return self.configs.get(location_id)
    
    # =========================================================================
    # TOAST INTEGRATION
    # =========================================================================
    
    async def sync_toast_sales(
        self,
        location_id: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """
        Sync sales data from Toast POS.
        
        In production: Use Toast API
        https://doc.toasttab.com/openapi/orders/operation/ordersBulkGet/
        """
        config = self.configs.get(location_id)
        if not config or config.provider != POSProvider.TOAST:
            return {"error": "Toast not configured for this location"}
        
        # Mock Toast API response
        mock_sales = [
            SaleItem(
                item_id=f"TOAST-{i}",
                name=f"Menu Item {i}",
                quantity=float(i + 1),
                unit_price_cents=1299,
                total_cents=1299 * (i + 1),
                category="food",
                sold_at=datetime.utcnow().isoformat(),
            )
            for i in range(5)
        ]
        
        self.sales_buffer.extend(mock_sales)
        
        return {
            "provider": "toast",
            "location_id": location_id,
            "sales_count": len(mock_sales),
            "total_revenue_cents": sum(s.total_cents for s in mock_sales),
            "sync_time": datetime.utcnow().isoformat(),
            "sandbox": config.sandbox_mode,
        }
    
    async def handle_toast_webhook(
        self,
        location_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle Toast webhook events.
        
        Event types:
        - orders.created
        - orders.paid
        - inventory.updated
        """
        print(f"[POS/Toast] Webhook: {event_type} for {location_id}")
        
        if event_type == "orders.paid":
            # Process completed order
            items = payload.get("items", [])
            for item in items:
                sale = SaleItem(
                    item_id=item.get("guid", ""),
                    name=item.get("name", ""),
                    quantity=item.get("quantity", 1),
                    unit_price_cents=int(item.get("price", 0) * 100),
                    total_cents=int(item.get("total", 0) * 100),
                    category=item.get("category", "unknown"),
                    sold_at=datetime.utcnow().isoformat(),
                )
                self.sales_buffer.append(sale)
            
            return {"processed": len(items), "status": "ok"}
        
        return {"status": "ignored", "event": event_type}
    
    # =========================================================================
    # SQUARE INTEGRATION
    # =========================================================================
    
    async def sync_square_sales(
        self,
        location_id: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """
        Sync sales data from Square POS.
        
        In production: Use Square Orders API
        https://developer.squareup.com/reference/square/orders-api
        """
        config = self.configs.get(location_id)
        if not config or config.provider != POSProvider.SQUARE:
            return {"error": "Square not configured for this location"}
        
        # Mock Square API response
        mock_sales = [
            SaleItem(
                item_id=f"SQ-{i}",
                name=f"Square Item {i}",
                quantity=float(i + 2),
                unit_price_cents=999,
                total_cents=999 * (i + 2),
                category="retail",
                sold_at=datetime.utcnow().isoformat(),
            )
            for i in range(4)
        ]
        
        self.sales_buffer.extend(mock_sales)
        
        return {
            "provider": "square",
            "location_id": location_id,
            "sales_count": len(mock_sales),
            "total_revenue_cents": sum(s.total_cents for s in mock_sales),
            "sync_time": datetime.utcnow().isoformat(),
            "sandbox": config.sandbox_mode,
        }
    
    async def handle_square_webhook(
        self,
        location_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle Square webhook events.
        
        Event types:
        - payment.completed
        - inventory.count.updated
        """
        print(f"[POS/Square] Webhook: {event_type} for {location_id}")
        
        if event_type == "payment.completed":
            order = payload.get("data", {}).get("object", {}).get("order", {})
            line_items = order.get("line_items", [])
            
            for item in line_items:
                sale = SaleItem(
                    item_id=item.get("catalog_object_id", ""),
                    name=item.get("name", ""),
                    quantity=float(item.get("quantity", "1")),
                    unit_price_cents=int(item.get("base_price_money", {}).get("amount", 0)),
                    total_cents=int(item.get("total_money", {}).get("amount", 0)),
                    category=item.get("item_type", "unknown"),
                    sold_at=datetime.utcnow().isoformat(),
                )
                self.sales_buffer.append(sale)
            
            return {"processed": len(line_items), "status": "ok"}
        
        return {"status": "ignored", "event": event_type}
    
    # =========================================================================
    # INVENTORY SYNC
    # =========================================================================
    
    async def calculate_inventory_impact(
        self,
        location_id: str,
        inventory: Dict[str, float],  # item_id -> current_quantity
        par_levels: Dict[str, float],  # item_id -> par_level
    ) -> List[InventoryUpdate]:
        """
        Calculate inventory impact from buffered sales.
        
        Returns list of inventory updates with reorder suggestions.
        """
        updates: List[InventoryUpdate] = []
        
        # Aggregate sales by item
        sales_by_item: Dict[str, float] = {}
        for sale in self.sales_buffer:
            sales_by_item[sale.item_id] = sales_by_item.get(sale.item_id, 0) + sale.quantity
        
        for item_id, quantity_sold in sales_by_item.items():
            current = inventory.get(item_id, 0)
            new_quantity = max(0, current - quantity_sold)
            par = par_levels.get(item_id, 0)
            below_par = new_quantity < par
            
            updates.append(InventoryUpdate(
                item_id=item_id,
                quantity_sold=quantity_sold,
                new_quantity=new_quantity,
                below_par=below_par,
                reorder_suggested=below_par and par > 0,
            ))
        
        # Clear buffer after processing
        self.sales_buffer = []
        
        return updates
    
    # =========================================================================
    # ANALYTICS
    # =========================================================================
    
    def get_sales_summary(
        self,
        location_id: str,
    ) -> Dict[str, Any]:
        """Get summary of buffered sales data."""
        location_sales = [s for s in self.sales_buffer]  # In production: filter by location
        
        if not location_sales:
            return {"total_items": 0, "total_revenue_cents": 0}
        
        by_category: Dict[str, int] = {}
        for sale in location_sales:
            by_category[sale.category] = by_category.get(sale.category, 0) + sale.total_cents
        
        return {
            "total_items": len(location_sales),
            "total_quantity": sum(s.quantity for s in location_sales),
            "total_revenue_cents": sum(s.total_cents for s in location_sales),
            "by_category": by_category,
            "avg_item_price_cents": sum(s.unit_price_cents for s in location_sales) // len(location_sales),
        }
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get status of all POS integrations."""
        return {
            "configured_locations": len(self.configs),
            "providers": {
                loc_id: config.provider.value
                for loc_id, config in self.configs.items()
            },
            "buffered_sales": len(self.sales_buffer),
            "supported_providers": [p.value for p in POSProvider],
        }


# Singleton
_pos_service: Optional[POSIntegrationService] = None


def get_pos_service() -> POSIntegrationService:
    """Get singleton POS integration service."""
    global _pos_service
    if _pos_service is None:
        _pos_service = POSIntegrationService()
    return _pos_service
