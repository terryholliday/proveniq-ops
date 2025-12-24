"""
PROVENIQ Ops - Vendor Client Base Interface

Abstract base class that all vendor integrations must implement.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel


class VendorOrderStatus(str, Enum):
    """Order status in vendor system"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    FAILED = "failed"


class VendorProduct(BaseModel):
    """Product information from vendor"""
    vendor_sku: str
    name: str
    description: Optional[str] = None
    unit_price_cents: int
    unit_of_measure: str  # "case", "lb", "each"
    pack_size: Optional[str] = None  # "12/1lb", "6/10oz"
    in_stock: bool = True
    available_quantity: Optional[int] = None
    lead_time_hours: Optional[int] = None
    category: Optional[str] = None
    brand: Optional[str] = None


class VendorOrderItem(BaseModel):
    """Line item in a vendor order"""
    vendor_sku: str
    quantity: int
    unit_price_cents: int
    product_name: Optional[str] = None


class VendorOrder(BaseModel):
    """Order submitted to vendor"""
    vendor_order_id: str
    internal_order_id: UUID
    status: VendorOrderStatus
    items: List[VendorOrderItem]
    total_cents: int
    submitted_at: datetime
    estimated_delivery: Optional[datetime] = None
    tracking_url: Optional[str] = None
    confirmation_number: Optional[str] = None


class VendorClient(ABC):
    """
    Abstract base class for vendor API integrations.
    
    All vendor clients must implement these methods.
    """
    
    @property
    @abstractmethod
    def vendor_name(self) -> str:
        """Return the vendor name (e.g., 'SYSCO', 'US Foods')"""
        pass
    
    @property
    @abstractmethod
    def vendor_id(self) -> str:
        """Return the vendor ID used in our system"""
        pass
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Authenticate with the vendor API.
        Returns True if authentication successful.
        """
        pass
    
    @abstractmethod
    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[VendorProduct]:
        """
        Search for products in vendor catalog.
        """
        pass
    
    @abstractmethod
    async def get_product(self, vendor_sku: str) -> Optional[VendorProduct]:
        """
        Get a specific product by vendor SKU.
        """
        pass
    
    @abstractmethod
    async def check_availability(
        self,
        vendor_sku: str,
        quantity: int,
    ) -> tuple[bool, int, Optional[int]]:
        """
        Check if a product is available in requested quantity.
        
        Returns:
            - available: bool
            - available_quantity: int
            - lead_time_hours: Optional[int]
        """
        pass
    
    @abstractmethod
    async def get_price(self, vendor_sku: str, quantity: int = 1) -> int:
        """
        Get current price for a product in cents.
        May vary based on quantity (volume discounts).
        """
        pass
    
    @abstractmethod
    async def submit_order(
        self,
        internal_order_id: UUID,
        items: List[VendorOrderItem],
        delivery_date: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> VendorOrder:
        """
        Submit an order to the vendor.
        """
        pass
    
    @abstractmethod
    async def get_order_status(self, vendor_order_id: str) -> VendorOrder:
        """
        Get current status of an order.
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, vendor_order_id: str, reason: str) -> bool:
        """
        Cancel an order if possible.
        Returns True if cancellation successful.
        """
        pass
    
    @abstractmethod
    async def sync_catalog(
        self,
        categories: Optional[List[str]] = None,
    ) -> List[VendorProduct]:
        """
        Sync full catalog or specific categories.
        Used for initial import and periodic updates.
        """
        pass
