"""
PROVENIQ Core API Client for Ops App

Provides:
- Equipment PAID registration
- Inventory batch valuation
- Shrinkage fraud detection
- Equipment depreciation tracking
"""

import os
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime

CORE_API_URL = os.getenv("CORE_API_URL", "http://localhost:8000")


class CoreClient:
    """Client for PROVENIQ Core API integration."""

    def __init__(self):
        self.base_url = CORE_API_URL
        self.source_app = "proveniq-ops"

    async def register_equipment(
        self,
        org_id: str,
        equipment_name: str,
        category: str,
        location_id: str,
        purchase_price: Optional[float] = None,
        purchase_date: Optional[str] = None,
        serial_number: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Register high-value equipment in Core and get PAID."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/registry",
                    json={
                        "ownerId": org_id,
                        "ownerType": "organization",
                        "name": equipment_name,
                        "category": category,
                        "sourceApp": "ops",
                        "externalId": f"{location_id}:{equipment_name}:{serial_number or 'no-serial'}",
                        "initialValue": purchase_price,
                        "condition": "good",
                    },
                    headers={"X-Source-App": self.source_app},
                    timeout=10.0,
                )

                if response.status_code == 201:
                    data = response.json()
                    return {
                        "paid": data.get("paid"),
                        "registered_at": data.get("registeredAt"),
                        "status": data.get("status"),
                    }

                print(f"[Core] Equipment registration failed: {response.status_code}")
                return None

        except Exception as e:
            print(f"[Core] Equipment registration error: {e}")
            return None

    async def batch_valuate_inventory(
        self,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Bulk valuation for inventory items."""
        results = []
        total_value = 0
        successful = 0

        for item in items:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/api/v1/valuations",
                        json={
                            "assetId": item.get("id", item.get("sku")),
                            "name": item.get("name"),
                            "category": item.get("category", "inventory"),
                            "condition": "good",
                            "purchasePrice": item.get("unit_cost"),
                        },
                        headers={"X-Source-App": self.source_app},
                        timeout=5.0,
                    )

                    if response.status_code == 200:
                        data = response.json()
                        value = data.get("estimatedValue", 0)
                        quantity = item.get("quantity", 1)
                        line_value = value * quantity

                        results.append({
                            "item_id": item.get("id"),
                            "name": item.get("name"),
                            "unit_value": value,
                            "quantity": quantity,
                            "line_value": line_value,
                        })
                        total_value += line_value
                        successful += 1
                    else:
                        results.append({
                            "item_id": item.get("id"),
                            "error": f"Valuation failed: {response.status_code}",
                        })

            except Exception as e:
                results.append({
                    "item_id": item.get("id"),
                    "error": str(e),
                })

        return {
            "items": results,
            "total_value": round(total_value, 2),
            "currency": "USD",
            "items_processed": len(items),
            "items_successful": successful,
            "valued_at": datetime.utcnow().isoformat(),
        }

    async def detect_shrinkage_fraud(
        self,
        location_id: str,
        user_id: str,
        shrinkage_value: float,
        shrinkage_events_30d: int,
        total_shrinkage_30d: float,
    ) -> Dict[str, Any]:
        """Detect potential fraud in shrinkage reports."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/fraud/score",
                    json={
                        "assetId": f"shrinkage-{location_id}",
                        "userId": user_id,
                        "claimType": "valuation",
                        "claimedValue": shrinkage_value,
                        "category": "shrinkage",
                        "hasReceipt": False,
                        "hasImages": False,
                        "imageCount": 0,
                        "previousClaims": shrinkage_events_30d,
                        "previousClaimsTotal": total_shrinkage_30d,
                    },
                    headers={"X-Source-App": self.source_app},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "location_id": location_id,
                        "user_id": user_id,
                        "fraud_score": data.get("score"),
                        "risk_level": data.get("riskLevel"),
                        "recommendation": data.get("recommendation"),
                        "signals": [s.get("description") for s in data.get("signals", [])],
                        "requires_investigation": data.get("score", 0) > 60,
                    }

        except Exception as e:
            print(f"[Core] Shrinkage fraud detection error: {e}")

        return {
            "location_id": location_id,
            "user_id": user_id,
            "fraud_score": 50,
            "risk_level": "MEDIUM",
            "recommendation": "MANUAL_REVIEW",
            "signals": ["Core unavailable"],
            "requires_investigation": True,
        }

    async def get_equipment_depreciation(
        self,
        paid: str,
        category: str,
        purchase_date: str,
        purchase_price: float,
    ) -> Dict[str, Any]:
        """Get depreciation schedule for equipment."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/valuations",
                    json={
                        "assetId": paid,
                        "name": "Equipment",
                        "category": category,
                        "condition": "good",
                        "purchasePrice": purchase_price,
                        "purchaseDate": purchase_date,
                    },
                    headers={"X-Source-App": self.source_app},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    breakdown = data.get("breakdown", {})
                    
                    return {
                        "paid": paid,
                        "original_value": purchase_price,
                        "current_value": data.get("estimatedValue"),
                        "depreciation_rate": breakdown.get("depreciationRate"),
                        "years_owned": breakdown.get("yearsOwned"),
                        "accumulated_depreciation": purchase_price - data.get("estimatedValue", purchase_price),
                        "book_value": data.get("estimatedValue"),
                        "currency": "USD",
                        "calculated_at": datetime.utcnow().isoformat(),
                    }

        except Exception as e:
            print(f"[Core] Depreciation error: {e}")

        # Fallback: 15% annual depreciation
        from datetime import datetime as dt
        purchase = dt.fromisoformat(purchase_date.replace("Z", "+00:00"))
        years = (dt.now(purchase.tzinfo) - purchase).days / 365.25
        current_value = purchase_price * (0.85 ** years)

        return {
            "paid": paid,
            "original_value": purchase_price,
            "current_value": round(current_value, 2),
            "depreciation_rate": 0.15,
            "years_owned": round(years, 2),
            "accumulated_depreciation": round(purchase_price - current_value, 2),
            "book_value": round(current_value, 2),
            "currency": "USD",
            "calculated_at": datetime.utcnow().isoformat(),
            "fallback": True,
        }


# Singleton instance
_core_client: Optional[CoreClient] = None


def get_core_client() -> CoreClient:
    """Get singleton Core client instance."""
    global _core_client
    if _core_client is None:
        _core_client = CoreClient()
    return _core_client
