"""
PROVENIQ Ops - ML Interfaces
============================

Future ML integration points.
Currently returns deterministic fallbacks.

RULE: Calling code uses these interfaces.
      When ML is ready, swap implementations — no refactor needed.

Training data source: /api/v1/audit/*
"""

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# RESULT TYPES
# =============================================================================

class PredictionResult(BaseModel):
    """Result from a prediction model."""
    prediction_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    model_version: str = "deterministic_v0"
    
    # Prediction
    value: Any
    confidence: Decimal = Field(..., ge=0, le=1)
    
    # Metadata
    model_used: str = "fallback"
    features_used: list[str] = []
    prediction_time_ms: int = 0
    
    # Explainability
    explanation: Optional[str] = None
    feature_importance: dict[str, float] = Field(default_factory=dict)
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AnomalyResult(BaseModel):
    """Result from anomaly detection."""
    detection_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    model_version: str = "deterministic_v0"
    
    # Detection
    is_anomaly: bool
    anomaly_score: Decimal = Field(..., ge=0, le=1)  # 0 = normal, 1 = extreme anomaly
    anomaly_type: Optional[str] = None
    
    # Context
    baseline_value: Optional[Any] = None
    observed_value: Any
    deviation_factor: Optional[Decimal] = None
    
    # Metadata
    model_used: str = "fallback"
    detection_time_ms: int = 0
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ClassificationResult(BaseModel):
    """Result from a classification model."""
    classification_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    model_version: str = "deterministic_v0"
    
    # Classification
    predicted_class: str
    confidence: Decimal = Field(..., ge=0, le=1)
    
    # All class probabilities
    class_probabilities: dict[str, float] = Field(default_factory=dict)
    
    # Metadata
    model_used: str = "fallback"
    classification_time_ms: int = 0
    
    # For image classification
    image_hash: Optional[str] = None
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# ML INTERFACE (Abstract Base)
# =============================================================================

class MLInterfaceBase(ABC):
    """
    Abstract base for ML implementations.
    
    Implement this when ML models are ready.
    """
    
    @abstractmethod
    def predict_depletion(
        self,
        product_id: uuid.UUID,
        current_qty: int,
        historical_burn_rates: list[Decimal],
        open_pos: Optional[list[dict]] = None,
    ) -> PredictionResult:
        """
        Predict when inventory will deplete.
        
        Args:
            product_id: Product to predict
            current_qty: Current on-hand quantity
            historical_burn_rates: List of daily burn rates [7d, 30d, 90d]
            open_pos: Open purchase orders for this product
        
        Returns:
            PredictionResult with hours_to_depletion
        """
        pass
    
    @abstractmethod
    def detect_anomaly(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
        observed_value: Any,
        historical_values: list[Any],
        context: Optional[dict] = None,
    ) -> AnomalyResult:
        """
        Detect if an observation is anomalous.
        
        Args:
            entity_type: Type of entity (scan, order, price, etc.)
            entity_id: Entity identifier
            observed_value: Current observation
            historical_values: Historical baseline
            context: Additional context (time, location, etc.)
        
        Returns:
            AnomalyResult indicating if anomaly detected
        """
        pass
    
    @abstractmethod
    def classify_waste_image(
        self,
        image_data: bytes,
        product_id: Optional[uuid.UUID] = None,
    ) -> ClassificationResult:
        """
        Classify waste/spoilage from image.
        
        Args:
            image_data: Raw image bytes
            product_id: Optional product context
        
        Returns:
            ClassificationResult with waste type
        
        Classes:
            - spoilage: Natural decay
            - damage: Physical damage
            - contamination: Foreign matter
            - mislabel: Wrong product
            - acceptable: Not actually waste
        """
        pass
    
    @abstractmethod
    def predict_demand(
        self,
        product_id: uuid.UUID,
        horizon_days: int,
        historical_sales: list[dict],
        external_factors: Optional[dict] = None,
    ) -> PredictionResult:
        """
        Predict future demand.
        
        Args:
            product_id: Product to predict
            horizon_days: Days to forecast
            historical_sales: Past sales data
            external_factors: Weather, events, holidays, etc.
        
        Returns:
            PredictionResult with forecasted demand
        """
        pass
    
    @abstractmethod
    def score_vendor_reliability(
        self,
        vendor_id: uuid.UUID,
        historical_deliveries: list[dict],
    ) -> PredictionResult:
        """
        Score vendor reliability.
        
        Args:
            vendor_id: Vendor to score
            historical_deliveries: Past delivery performance
        
        Returns:
            PredictionResult with reliability score 0-1
        """
        pass
    
    @abstractmethod
    def recommend_reorder_quantity(
        self,
        product_id: uuid.UUID,
        current_qty: int,
        demand_forecast: dict,
        vendor_options: list[dict],
        budget_constraint: Optional[int] = None,
    ) -> PredictionResult:
        """
        Recommend optimal reorder quantity.
        
        Args:
            product_id: Product to reorder
            current_qty: Current inventory
            demand_forecast: Predicted demand
            vendor_options: Available vendors with prices
            budget_constraint: Max spend in micros
        
        Returns:
            PredictionResult with recommended quantity
        """
        pass


# =============================================================================
# DETERMINISTIC FALLBACK IMPLEMENTATION
# =============================================================================

class MLInterface(MLInterfaceBase):
    """
    Deterministic fallback implementation.
    
    Uses rule-based logic until ML models are trained.
    Returns consistent, explainable results.
    """
    
    def predict_depletion(
        self,
        product_id: uuid.UUID,
        current_qty: int,
        historical_burn_rates: list[Decimal],
        open_pos: Optional[list[dict]] = None,
    ) -> PredictionResult:
        """
        Predict depletion using weighted average burn rate.
        
        Fallback logic:
            - Weight recent data more heavily (7d > 30d > 90d)
            - Calculate hours to depletion
            - High confidence if variance is low
        """
        if not historical_burn_rates or current_qty <= 0:
            return PredictionResult(
                value=0,
                confidence=Decimal("0.5"),
                model_used="fallback_empty",
                explanation="No historical data or zero inventory",
            )
        
        # Weighted average: 50% 7d, 30% 30d, 20% 90d
        weights = [Decimal("0.5"), Decimal("0.3"), Decimal("0.2")]
        weighted_burn = sum(
            rate * weight 
            for rate, weight in zip(historical_burn_rates[:3], weights[:len(historical_burn_rates)])
        )
        
        if weighted_burn <= 0:
            hours_to_depletion = Decimal("9999")  # Essentially infinite
            confidence = Decimal("0.3")
        else:
            hours_to_depletion = (Decimal(current_qty) / weighted_burn) * 24
            
            # Confidence based on data consistency
            if len(historical_burn_rates) >= 3:
                variance = max(historical_burn_rates) - min(historical_burn_rates)
                avg = sum(historical_burn_rates) / len(historical_burn_rates)
                cv = variance / avg if avg > 0 else Decimal("1")
                confidence = max(Decimal("0.5"), Decimal("1") - cv)
            else:
                confidence = Decimal("0.6")
        
        return PredictionResult(
            value=float(hours_to_depletion),
            confidence=confidence,
            model_used="fallback_weighted_average",
            features_used=["current_qty", "burn_rate_7d", "burn_rate_30d", "burn_rate_90d"],
            explanation=f"Weighted burn rate: {weighted_burn:.2f}/day. {current_qty} units remaining.",
            feature_importance={
                "burn_rate_7d": 0.5,
                "burn_rate_30d": 0.3,
                "burn_rate_90d": 0.2,
            },
        )
    
    def detect_anomaly(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
        observed_value: Any,
        historical_values: list[Any],
        context: Optional[dict] = None,
    ) -> AnomalyResult:
        """
        Detect anomaly using simple statistical thresholds.
        
        Fallback logic:
            - Calculate mean and std of historical
            - Flag if observed > mean + 2*std
        """
        if not historical_values:
            return AnomalyResult(
                is_anomaly=False,
                anomaly_score=Decimal("0"),
                observed_value=observed_value,
                model_used="fallback_no_history",
            )
        
        try:
            numeric_history = [float(v) for v in historical_values]
            numeric_observed = float(observed_value)
            
            mean = sum(numeric_history) / len(numeric_history)
            variance = sum((x - mean) ** 2 for x in numeric_history) / len(numeric_history)
            std = variance ** 0.5 if variance > 0 else 1
            
            deviation = abs(numeric_observed - mean) / std if std > 0 else 0
            
            # Z-score based anomaly detection
            is_anomaly = deviation > 2.0
            anomaly_score = min(Decimal(str(deviation / 4)), Decimal("1"))
            
            anomaly_type = None
            if is_anomaly:
                if numeric_observed > mean:
                    anomaly_type = "high_outlier"
                else:
                    anomaly_type = "low_outlier"
            
            return AnomalyResult(
                is_anomaly=is_anomaly,
                anomaly_score=anomaly_score,
                anomaly_type=anomaly_type,
                baseline_value=mean,
                observed_value=observed_value,
                deviation_factor=Decimal(str(round(deviation, 2))),
                model_used="fallback_zscore",
            )
            
        except (ValueError, TypeError):
            return AnomalyResult(
                is_anomaly=False,
                anomaly_score=Decimal("0"),
                observed_value=observed_value,
                model_used="fallback_non_numeric",
            )
    
    def classify_waste_image(
        self,
        image_data: bytes,
        product_id: Optional[uuid.UUID] = None,
    ) -> ClassificationResult:
        """
        Classify waste image.
        
        Fallback: Returns "unknown" requiring human classification.
        Real implementation would use computer vision model.
        """
        import hashlib
        image_hash = hashlib.sha256(image_data).hexdigest()[:16]
        
        return ClassificationResult(
            predicted_class="requires_human_review",
            confidence=Decimal("0"),
            class_probabilities={
                "spoilage": 0.2,
                "damage": 0.2,
                "contamination": 0.2,
                "mislabel": 0.2,
                "acceptable": 0.2,
            },
            model_used="fallback_no_cv_model",
            image_hash=image_hash,
        )
    
    def predict_demand(
        self,
        product_id: uuid.UUID,
        horizon_days: int,
        historical_sales: list[dict],
        external_factors: Optional[dict] = None,
    ) -> PredictionResult:
        """
        Predict demand using simple moving average.
        
        Fallback: Average of historical sales.
        """
        if not historical_sales:
            return PredictionResult(
                value=0,
                confidence=Decimal("0.3"),
                model_used="fallback_no_history",
                explanation="No historical sales data",
            )
        
        # Simple average
        total_qty = sum(s.get("quantity", 0) for s in historical_sales)
        avg_daily = total_qty / len(historical_sales) if historical_sales else 0
        forecast = avg_daily * horizon_days
        
        return PredictionResult(
            value=round(forecast),
            confidence=Decimal("0.5"),
            model_used="fallback_moving_average",
            features_used=["historical_sales"],
            explanation=f"Average daily: {avg_daily:.1f}. Forecast for {horizon_days} days: {forecast:.0f}",
        )
    
    def score_vendor_reliability(
        self,
        vendor_id: uuid.UUID,
        historical_deliveries: list[dict],
    ) -> PredictionResult:
        """
        Score vendor based on delivery history.
        
        Fallback: On-time delivery percentage.
        """
        if not historical_deliveries:
            return PredictionResult(
                value=0.5,  # Neutral score for new vendors
                confidence=Decimal("0.3"),
                model_used="fallback_no_history",
                explanation="No delivery history",
            )
        
        on_time = sum(1 for d in historical_deliveries if d.get("on_time", False))
        total = len(historical_deliveries)
        score = on_time / total if total > 0 else 0.5
        
        # Confidence increases with more data
        confidence = min(Decimal("0.9"), Decimal(str(total / 100 + 0.3)))
        
        return PredictionResult(
            value=round(score, 2),
            confidence=confidence,
            model_used="fallback_on_time_rate",
            features_used=["delivery_history"],
            explanation=f"{on_time}/{total} deliveries on time ({score*100:.0f}%)",
        )
    
    def recommend_reorder_quantity(
        self,
        product_id: uuid.UUID,
        current_qty: int,
        demand_forecast: dict,
        vendor_options: list[dict],
        budget_constraint: Optional[int] = None,
    ) -> PredictionResult:
        """
        Recommend reorder quantity.
        
        Fallback: Cover forecasted demand + safety stock.
        """
        forecast_qty = demand_forecast.get("quantity", 0)
        forecast_days = demand_forecast.get("days", 7)
        
        # Target: forecast + 20% safety stock
        target_qty = int(forecast_qty * 1.2)
        reorder_qty = max(0, target_qty - current_qty)
        
        # Check budget if provided
        if budget_constraint and vendor_options:
            cheapest = min(vendor_options, key=lambda v: v.get("price_micros", float("inf")))
            price = cheapest.get("price_micros", 0)
            if price > 0:
                max_affordable = budget_constraint // price
                reorder_qty = min(reorder_qty, max_affordable)
        
        return PredictionResult(
            value=reorder_qty,
            confidence=Decimal("0.6"),
            model_used="fallback_forecast_plus_safety",
            features_used=["demand_forecast", "current_qty", "safety_factor"],
            explanation=f"Forecast: {forecast_qty} over {forecast_days}d. Safety: 20%. Recommend: {reorder_qty}",
            feature_importance={
                "demand_forecast": 0.6,
                "current_qty": 0.3,
                "safety_factor": 0.1,
            },
        )


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

ml_interface = MLInterface()
