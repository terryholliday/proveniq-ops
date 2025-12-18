"""
PROVENIQ Ops - ML Module
========================

ML-ready seam for future model integration.
Currently uses deterministic fallbacks.

When ML is ready:
1. Implement the interfaces in this module
2. Replace stub implementations
3. No refactoring of calling code required

Training data is being collected in: app/services/audit.py
"""

from app.ml.interfaces import (
    MLInterface,
    ml_interface,
    PredictionResult,
    AnomalyResult,
    ClassificationResult,
)

__all__ = [
    "MLInterface",
    "ml_interface",
    "PredictionResult",
    "AnomalyResult",
    "ClassificationResult",
]
