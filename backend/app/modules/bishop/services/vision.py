"""BISHOP Vision Service - OpenAI Vision API for Shelf Scanning

Uses GPT-4 Vision to analyze shelf images and detect inventory items.
"""
import base64
import httpx
from typing import Any

from app.core.config import settings


class VisionService:
    """Service for AI-powered shelf image analysis using OpenAI Vision."""

    SYSTEM_PROMPT = """You are an inventory analysis system for restaurants and retail stores. 
Analyze the shelf image and identify all visible products/items.

For each item you can identify, provide:
- sku: A generated SKU code based on the product (format: VENDOR-###)
- name: Product name
- detected_quantity: How many units you can see
- confidence: Your confidence level (0.0-1.0)

Also assess:
- scan_quality: "good", "fair", or "poor" based on image clarity
- overall_confidence: Your overall confidence in the analysis (0.0-1.0)

Respond ONLY with valid JSON in this exact format:
{
  "items": [
    {"sku": "SYSCO-001", "name": "Tomato Sauce Case", "detected_quantity": 8, "confidence": 0.95},
    {"sku": "USF-102", "name": "Olive Oil 1gal", "detected_quantity": 3, "confidence": 0.88}
  ],
  "scan_quality": "good",
  "overall_confidence": 0.92
}

If you cannot identify any items or the image is not of a shelf/inventory, respond with:
{"items": [], "scan_quality": "poor", "overall_confidence": 0.0, "error": "reason"}
"""

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = "gpt-4o"  # GPT-4 with vision capabilities

    async def analyze_image_url(self, image_url: str) -> dict[str, Any]:
        """
        Analyze a shelf image from a URL using OpenAI Vision.
        
        Args:
            image_url: URL of the shelf image to analyze
            
        Returns:
            Dict containing detected items and analysis metadata
        """
        if not self.api_key:
            return self._mock_response()

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": self.SYSTEM_PROMPT,
                            },
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Analyze this shelf image and identify all inventory items:",
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": image_url},
                                    },
                                ],
                            },
                        ],
                        "max_tokens": 1000,
                        "response_format": {"type": "json_object"},
                    },
                )
                
                response.raise_for_status()
                data = response.json()
                
                content = data["choices"][0]["message"]["content"]
                import json
                return json.loads(content)
                
        except Exception as e:
            return {
                "items": [],
                "scan_quality": "poor",
                "overall_confidence": 0.0,
                "error": f"Vision API error: {str(e)}",
            }

    async def analyze_image_base64(self, image_data: bytes, mime_type: str = "image/jpeg") -> dict[str, Any]:
        """
        Analyze a shelf image from base64-encoded data.
        
        Args:
            image_data: Raw image bytes
            mime_type: MIME type of the image
            
        Returns:
            Dict containing detected items and analysis metadata
        """
        if not self.api_key:
            return self._mock_response()

        base64_image = base64.b64encode(image_data).decode("utf-8")
        data_url = f"data:{mime_type};base64,{base64_image}"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": self.SYSTEM_PROMPT,
                            },
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Analyze this shelf image and identify all inventory items:",
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": data_url},
                                    },
                                ],
                            },
                        ],
                        "max_tokens": 1000,
                        "response_format": {"type": "json_object"},
                    },
                )
                
                response.raise_for_status()
                data = response.json()
                
                content = data["choices"][0]["message"]["content"]
                import json
                return json.loads(content)
                
        except Exception as e:
            return {
                "items": [],
                "scan_quality": "poor",
                "overall_confidence": 0.0,
                "error": f"Vision API error: {str(e)}",
            }

    def _mock_response(self) -> dict[str, Any]:
        """Return mock response when API key is not configured."""
        return {
            "items": [
                {"sku": "SYSCO-001", "name": "Tomato Sauce Case (6x#10)", "detected_quantity": 8, "confidence": 0.95},
                {"sku": "SYSCO-002", "name": "Extra Virgin Olive Oil 1gal", "detected_quantity": 3, "confidence": 0.88},
                {"sku": "USF-101", "name": "All Purpose Flour 50lb Bag", "detected_quantity": 2, "confidence": 0.92},
                {"sku": "SYSCO-003", "name": "Canola Oil 35lb JIB", "detected_quantity": 4, "confidence": 0.85},
            ],
            "scan_quality": "good",
            "overall_confidence": 0.90,
            "_mock": True,
        }

    def compare_with_expected(
        self,
        detected: dict[str, Any],
        expected_inventory: dict[str, int] | None,
    ) -> list[dict[str, Any]]:
        """
        Compare detected items with expected inventory to find discrepancies.
        
        Args:
            detected: Result from analyze_image
            expected_inventory: Dict of SKU -> expected quantity
            
        Returns:
            List of discrepancy records
        """
        if not expected_inventory:
            return []

        discrepancies = []
        detected_by_sku = {
            item["sku"]: item for item in detected.get("items", [])
        }

        for sku, expected_qty in expected_inventory.items():
            detected_item = detected_by_sku.get(sku)
            detected_qty = detected_item["detected_quantity"] if detected_item else 0
            
            if detected_qty != expected_qty:
                discrepancies.append({
                    "sku": sku,
                    "name": detected_item["name"] if detected_item else "Unknown",
                    "expected": expected_qty,
                    "detected": detected_qty,
                    "difference": detected_qty - expected_qty,
                    "confidence": detected_item["confidence"] if detected_item else 0.0,
                })

        # Also flag items detected but not expected
        for sku, item in detected_by_sku.items():
            if sku not in expected_inventory:
                discrepancies.append({
                    "sku": sku,
                    "name": item["name"],
                    "expected": 0,
                    "detected": item["detected_quantity"],
                    "difference": item["detected_quantity"],
                    "confidence": item["confidence"],
                    "unexpected": True,
                })

        return discrepancies

    def calculate_risk_score(self, discrepancies: list[dict[str, Any]]) -> float:
        """
        Calculate a risk score (0-100) based on discrepancies.
        
        Higher score = higher risk of shrinkage/issues.
        """
        if not discrepancies:
            return 0.0

        # Weight factors
        missing_weight = 10.0  # Points per missing item
        excess_weight = 3.0   # Points per excess item (less concerning)
        unexpected_weight = 5.0  # Points per unexpected item

        total_score = 0.0
        for disc in discrepancies:
            difference = disc.get("difference", 0)
            
            if disc.get("unexpected"):
                total_score += unexpected_weight
            elif difference < 0:  # Missing items
                total_score += abs(difference) * missing_weight
            else:  # Excess items
                total_score += difference * excess_weight

        return min(total_score, 100.0)
