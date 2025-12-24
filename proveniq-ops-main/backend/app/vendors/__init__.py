"""
PROVENIQ Ops - Vendor Integrations

Real vendor API clients for:
- SYSCO
- US Foods
- Performance Food Group

Each vendor client implements the VendorClient interface.
"""

from .base import VendorClient, VendorProduct, VendorOrder, VendorOrderStatus
from .sysco import SyscoClient
from .usfoods import USFoodsClient
from .registry import VendorRegistry, get_vendor_registry

__all__ = [
    "VendorClient",
    "VendorProduct",
    "VendorOrder",
    "VendorOrderStatus",
    "SyscoClient",
    "USFoodsClient",
    "VendorRegistry",
    "get_vendor_registry",
]
