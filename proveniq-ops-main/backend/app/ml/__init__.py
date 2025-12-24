"""
PROVENIQ Ops - ML Module
========================

ML-ready seam for future model integration.
Currently uses deterministic fallbacks.

P0 Features (Implemented):
- Burn Rate Calculation
- Stockout Prediction

P1 Features (Pending):
- Vision (container fill estimation, item classification)

Training data is being collected via inventory snapshots.
"""

from app.ml.interfaces import (
    MLInterface,
    ml_interface,
    PredictionResult,
    AnomalyResult,
    ClassificationResult,
)
from app.ml.burn_rate import (
    BurnRateCalculator,
    BurnRateResult,
    get_burn_rate_calculator,
)
from app.ml.stockout import (
    StockoutPredictor,
    StockoutPrediction,
    StockoutAlert,
    get_stockout_predictor,
)

__all__ = [
    # Interfaces
    "MLInterface",
    "ml_interface",
    "PredictionResult",
    "AnomalyResult",
    "ClassificationResult",
    # Burn Rate
    "BurnRateCalculator",
    "BurnRateResult",
    "get_burn_rate_calculator",
    # Stockout Prediction
    "StockoutPredictor",
    "StockoutPrediction",
    "StockoutAlert",
    "get_stockout_predictor",
]
