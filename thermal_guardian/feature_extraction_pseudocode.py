# Feature Extraction Pseudocode (Python-style)
# Goal: produce stable, canonical feature vectors for Bishop decisions.

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import math
import hashlib
import json

@dataclass
class Baseline:
    tset_c_median: float
    recovery_slope_median: float
    recovery_time_median: float
    duty_cycle_median: Optional[float]
    cycles_per_hour_median: Optional[float]
    temp_stddev_24h_median: float

@dataclass
class RecoveryFeatures:
    slope_c_per_min: float
    time_to_recover_min: float
    slope_delta_pct: float
    time_to_recover_delta_pct: float

@dataclass
class CycleFeatures:
    duty_cycle: Optional[float]
    cycles_per_hour: Optional[float]
    duty_cycle_delta_pct: float
    cycles_per_hour_delta_sigma: float
    short_cycling_detected: bool

@dataclass
class VarianceFeatures:
    stddev_c: float
    stddev_delta_sigma: float
    excursions_count: int

def canonical_json(obj: dict) -> str:
    # Canonicalize for hashing: sorted keys, no whitespace, stable floats
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def compute_setpoint(temp_series: List[Tuple[datetime, float]]) -> float:
    # robust: median of temps in "stable" windows (low slope); MVP: global median
    vals = [t for _, t in temp_series]
    vals.sort()
    mid = len(vals)//2
    return vals[mid] if vals else float("nan")

def compute_recovery_features(
    t0: datetime,
    temp_window: List[Tuple[datetime, float]],
    baseline: Baseline,
    tset_c: float,
    tol_c: float = 0.5
) -> RecoveryFeatures:
    # slope: linear regression on (minutes since t0, temp)
    xs, ys = [], []
    for ts, temp_c in temp_window:
        dt_min = (ts - t0).total_seconds()/60.0
        xs.append(dt_min); ys.append(temp_c)
    n = len(xs)
    if n < 2:
        return RecoveryFeatures(0, 0, 0, 0)

    xbar = sum(xs)/n
    ybar = sum(ys)/n
    num = sum((xs[i]-xbar)*(ys[i]-ybar) for i in range(n))
    den = sum((xs[i]-xbar)**2 for i in range(n)) or 1e-9
    slope = num/den  # temp per minute (should be negative during recovery)

    # time-to-recover: first time temp <= (tset + tol) for freezers/coolers with downward recovery
    target = tset_c + tol_c
    ttr = None
    for ts, temp_c in temp_window:
        if temp_c <= target:
            ttr = (ts - t0).total_seconds()/60.0
            break
    if ttr is None:
        ttr = (temp_window[-1][0]-t0).total_seconds()/60.0

    slope_delta_pct = 0.0
    if abs(baseline.recovery_slope_median) > 1e-6:
        slope_delta_pct = (abs(slope) - abs(baseline.recovery_slope_median)) / abs(baseline.recovery_slope_median) * 100.0

    ttr_delta_pct = 0.0
    if baseline.recovery_time_median > 1e-6:
        ttr_delta_pct = (ttr - baseline.recovery_time_median) / baseline.recovery_time_median * 100.0

    return RecoveryFeatures(slope, ttr, slope_delta_pct, ttr_delta_pct)

def compute_cycle_features(
    compressor_series: Optional[List[Tuple[datetime, bool]]],
    power_series: Optional[List[Tuple[datetime, float]]],
    baseline: Baseline
) -> CycleFeatures:
    # Preferred: compressor_on boolean; fallback: infer on/off from power_w > threshold
    # MVP placeholder: implement state machine to compute duty cycle and cycles/hour
    duty = None
    cph = None
    short = False

    duty_delta_pct = 0.0
    if duty is not None and baseline.duty_cycle_median:
        duty_delta_pct = (duty - baseline.duty_cycle_median) / baseline.duty_cycle_median * 100.0

    cycles_delta_sigma = 0.0
    # if you store baseline sigma, compute real sigma deltas; MVP uses zscore against empirical sigma.

    return CycleFeatures(duty, cph, duty_delta_pct, cycles_delta_sigma, short)

def compute_variance_features(
    temp_series: List[Tuple[datetime, float]],
    baseline: Baseline,
    excursion_threshold_c: float
) -> VarianceFeatures:
    vals = [v for _, v in temp_series]
    if len(vals) < 2:
        return VarianceFeatures(0.0, 0.0, 0)
    mean = sum(vals)/len(vals)
    var = sum((v-mean)**2 for v in vals)/(len(vals)-1)
    std = math.sqrt(var)

    # sigma delta: requires baseline sigma; MVP uses baseline median stddev as reference
    std_sigma = 0.0
    if baseline.temp_stddev_24h_median > 1e-6:
        std_sigma = (std - baseline.temp_stddev_24h_median) / baseline.temp_stddev_24h_median  # proxy

    excursions = sum(1 for v in vals if v > excursion_threshold_c)
    return VarianceFeatures(std, std_sigma, excursions)

def build_features_digest(features: dict) -> str:
    return sha256_hex(canonical_json(features))

# Output: canonical feature vector + digest -> used in RECOMMENDATION_EMITTED payload.evidence_basis.derived_features_digest
