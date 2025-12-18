# PROVENIQ Ops - ML Seam Contract

**ML-ready infrastructure without ML.**

---

## The Pattern

```
Calling Code → ML Interface → [Deterministic Fallback | Future ML Model]
```

When ML is ready:
1. Train model on audit data (`/api/v1/audit/*`)
2. Implement `MLInterfaceBase`
3. Swap `ml_interface` singleton
4. **No refactoring of calling code**

## Directory Structure

```
backend/app/ml/
├── __init__.py       # Exports
├── interfaces.py     # Interface + fallback implementation
├── models/           # Future: trained models
├── training/         # Future: training pipelines
└── inference/        # Future: inference servers
```

## Interface Methods

| Method | Purpose | Fallback Logic |
|--------|---------|----------------|
| `predict_depletion()` | Hours to stockout | Weighted avg burn rate |
| `detect_anomaly()` | Flag unusual patterns | Z-score threshold |
| `classify_waste_image()` | Categorize waste photos | Returns "requires_human_review" |
| `predict_demand()` | Forecast future demand | Moving average |
| `score_vendor_reliability()` | Rate vendor performance | On-time delivery % |
| `recommend_reorder_quantity()` | Optimal order qty | Forecast + 20% safety |

## Usage

```python
from app.ml import ml_interface, PredictionResult

# Predict depletion
result: PredictionResult = ml_interface.predict_depletion(
    product_id=product.id,
    current_qty=42,
    historical_burn_rates=[Decimal("5.2"), Decimal("4.8"), Decimal("5.0")],
)

print(result.value)       # Hours to depletion
print(result.confidence)  # 0.0 - 1.0
print(result.model_used)  # "fallback_weighted_average"
```

## Result Types

### PredictionResult

```python
{
    "prediction_id": "uuid",
    "model_version": "deterministic_v0",
    "value": 36.5,               # The prediction
    "confidence": 0.78,          # How sure
    "model_used": "fallback_weighted_average",
    "features_used": ["burn_rate_7d", "burn_rate_30d"],
    "explanation": "Weighted burn rate: 5.0/day",
    "feature_importance": {"burn_rate_7d": 0.5, ...}
}
```

### AnomalyResult

```python
{
    "detection_id": "uuid",
    "is_anomaly": true,
    "anomaly_score": 0.85,       # 0 = normal, 1 = extreme
    "anomaly_type": "high_outlier",
    "baseline_value": 100,
    "observed_value": 250,
    "deviation_factor": 2.5
}
```

### ClassificationResult

```python
{
    "classification_id": "uuid",
    "predicted_class": "spoilage",
    "confidence": 0.92,
    "class_probabilities": {
        "spoilage": 0.92,
        "damage": 0.05,
        "contamination": 0.02,
        "acceptable": 0.01
    }
}
```

## Training Data Source

All training data comes from the audit service:

```
GET /api/v1/audit/overrides          # Human corrections to Bishop
GET /api/v1/audit/proposals/modified # Where Bishop needed adjustment
GET /api/v1/audit/blocks             # What got blocked and why
```

## Implementing Real ML

1. **Create model class:**

```python
# app/ml/models/depletion_model.py
from app.ml.interfaces import MLInterfaceBase, PredictionResult

class DepletionModel(MLInterfaceBase):
    def __init__(self, model_path: str):
        self.model = load_model(model_path)
    
    def predict_depletion(self, product_id, current_qty, ...):
        features = self._extract_features(...)
        prediction = self.model.predict(features)
        return PredictionResult(
            value=prediction,
            confidence=self._calculate_confidence(...),
            model_used="xgboost_v1",
            ...
        )
```

2. **Swap singleton:**

```python
# app/ml/__init__.py
from app.ml.models.depletion_model import DepletionModel

ml_interface = DepletionModel("/models/depletion_v1.pkl")
```

3. **No changes to calling code.**

## Confidence Thresholds

| Confidence | Action |
|------------|--------|
| < 0.5 | Log warning, use fallback |
| 0.5 - 0.7 | Use prediction, flag for review |
| 0.7 - 0.85 | Use prediction |
| > 0.85 | Use prediction, eligible for auto-execute |

## DAG Integration

ML interfaces map to DAG nodes:

| ML Method | DAG Node |
|-----------|----------|
| `predict_depletion` | N10, N11 |
| `detect_anomaly` | N12, N15 |
| `predict_demand` | N10 |
| `score_vendor_reliability` | N3, N23 |
| `recommend_reorder_quantity` | N30, N31 |

---

**Rule: All ML outputs include confidence scores and explanations.**
