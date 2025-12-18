"""
PROVENIQ Ops - Peer Benchmark Engine API Routes
Bishop anonymous performance comparison endpoints

GUARDRAILS:
- No peer identities exposed
- Opt-in only
- All peer data is anonymized
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query

from app.models.benchmark import (
    BenchmarkConfig,
    BenchmarkMetric,
    BenchmarkReport,
    MetricBenchmark,
    OptInStatus,
    OrgCategory,
    OrgMetrics,
    OrgSize,
)
from app.services.bishop.benchmark_engine import benchmark_engine

router = APIRouter(prefix="/benchmark", tags=["Peer Benchmark"])


# =============================================================================
# OPT-IN MANAGEMENT
# =============================================================================

@router.post("/opt-in/{org_id}")
async def opt_in(
    org_id: uuid.UUID,
    shares_waste: bool = True,
    shares_accuracy: bool = True,
    shares_turnover: bool = True,
    shares_financials: bool = False,
) -> dict:
    """
    Opt into peer benchmarking.
    
    GUARDRAIL: Explicit consent required. Data is anonymized.
    """
    status = benchmark_engine.opt_in(
        org_id=org_id,
        shares_waste=shares_waste,
        shares_accuracy=shares_accuracy,
        shares_turnover=shares_turnover,
        shares_financials=shares_financials,
    )
    
    return {
        "status": "opted_in",
        "org_id": str(org_id),
        "consent_timestamp": status.consent_timestamp.isoformat() if status.consent_timestamp else None,
        "shares": {
            "waste": shares_waste,
            "accuracy": shares_accuracy,
            "turnover": shares_turnover,
            "financials": shares_financials,
        },
        "privacy_notice": "Your data will be anonymized and aggregated with peers. No identities are shared.",
    }


@router.post("/opt-out/{org_id}")
async def opt_out(org_id: uuid.UUID) -> dict:
    """Opt out of peer benchmarking."""
    status = benchmark_engine.opt_out(org_id)
    
    return {
        "status": "opted_out",
        "org_id": str(org_id),
        "data_removed": True,
    }


@router.get("/opt-in/{org_id}/status")
async def get_opt_in_status(org_id: uuid.UUID) -> dict:
    """Get opt-in status for an organization."""
    status = benchmark_engine.get_opt_in_status(org_id)
    return status.model_dump()


# =============================================================================
# METRICS SUBMISSION
# =============================================================================

@router.post("/metrics")
async def submit_metrics(
    org_id: uuid.UUID,
    category: OrgCategory,
    size: OrgSize,
    period_start: date,
    period_end: date,
    waste_pct: Optional[Decimal] = None,
    inventory_accuracy_pct: Optional[Decimal] = None,
    inventory_turnover: Optional[Decimal] = None,
    stockout_rate_pct: Optional[Decimal] = None,
    order_accuracy_pct: Optional[Decimal] = None,
    receiving_accuracy_pct: Optional[Decimal] = None,
    food_cost_pct: Optional[Decimal] = None,
    margin_pct: Optional[Decimal] = None,
    vendor_fill_rate_pct: Optional[Decimal] = None,
) -> dict:
    """
    Submit organization metrics for benchmarking.
    
    GUARDRAIL: Only stored if organization has opted in.
    """
    metrics = OrgMetrics(
        org_id=org_id,
        category=category,
        size=size,
        period_start=period_start,
        period_end=period_end,
        waste_pct=waste_pct,
        inventory_accuracy_pct=inventory_accuracy_pct,
        inventory_turnover=inventory_turnover,
        stockout_rate_pct=stockout_rate_pct,
        order_accuracy_pct=order_accuracy_pct,
        receiving_accuracy_pct=receiving_accuracy_pct,
        food_cost_pct=food_cost_pct,
        margin_pct=margin_pct,
        vendor_fill_rate_pct=vendor_fill_rate_pct,
    )
    
    success = benchmark_engine.submit_metrics(metrics)
    
    if not success:
        return {
            "status": "rejected",
            "reason": "Organization must opt-in before submitting metrics",
            "org_id": str(org_id),
        }
    
    return {
        "status": "submitted",
        "org_id": str(org_id),
        "category": category.value,
        "size": size.value,
        "period": f"{period_start} to {period_end}",
    }


# =============================================================================
# BENCHMARKING
# =============================================================================

@router.get("/metric/{org_id}/{metric}")
async def benchmark_single_metric(
    org_id: uuid.UUID,
    metric: BenchmarkMetric,
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020),
) -> dict:
    """
    Benchmark a single metric against peers.
    
    Returns:
    - metric: WASTE | ACCURACY | TURNOVER | etc.
    - your_percentile: 0-100
    
    GUARDRAIL: Only aggregated peer data returned.
    """
    result = benchmark_engine.benchmark_metric(org_id, metric, month, year)
    
    if not result:
        return {
            "error": "Benchmark not available",
            "reason": "Insufficient data or peer pool too small",
            "org_id": str(org_id),
            "metric": metric.value,
        }
    
    return {
        "metric": result.metric.value,
        "your_percentile": result.your_percentile,
        "your_value": str(result.your_value),
        "your_quartile": result.your_quartile.value,
        "peer_avg": str(result.peer_avg),
        "peer_median": str(result.peer_median),
        "peer_count": result.peer_count,
        "interpretation": result.interpretation,
        "privacy_notice": "Peer data is anonymized. No identities revealed.",
    }


@router.get("/report/{org_id}")
async def get_benchmark_report(
    org_id: uuid.UUID,
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020),
) -> dict:
    """
    Generate complete benchmark report.
    
    GUARDRAIL: Only aggregated peer data returned.
    """
    report = benchmark_engine.generate_report(org_id, month, year)
    
    if not report:
        return {
            "error": "Report not available",
            "reason": "No metrics submitted or peer pool too small",
            "org_id": str(org_id),
        }
    
    return report.model_dump()


@router.get("/peers/{category}/{size}")
async def get_peer_pool_stats(
    category: OrgCategory,
    size: OrgSize,
) -> dict:
    """
    Get anonymized peer pool statistics.
    
    GUARDRAIL: Only aggregated data, no individual values.
    """
    stats = benchmark_engine.get_peer_pool_stats(category, size)
    
    return {
        "category": category.value,
        "size": size.value,
        "metrics": stats,
        "privacy_notice": "All data is aggregated from 5+ peers. No identities revealed.",
    }


# =============================================================================
# CONFIGURATION
# =============================================================================

@router.get("/config", response_model=BenchmarkConfig)
async def get_config() -> BenchmarkConfig:
    """Get benchmark engine configuration."""
    return benchmark_engine.get_config()


@router.delete("/data/clear")
async def clear_data() -> dict:
    """Clear all data (for testing)."""
    benchmark_engine.clear_data()
    return {"status": "cleared"}


# =============================================================================
# DEMO
# =============================================================================

@router.post("/demo/setup")
async def setup_demo() -> dict:
    """
    Set up demo data for peer benchmarking.
    
    Creates sample organizations with varied performance.
    """
    benchmark_engine.clear_data()
    
    today = date.today()
    period_start = date(today.year, today.month, 1)
    period_end = today
    
    # Create 8 peer organizations (anonymized)
    peer_data = [
        # Fast casual, medium size peers
        {"waste": 3.5, "accuracy": 96.0, "turnover": 4.2, "stockout": 2.1},
        {"waste": 4.2, "accuracy": 94.5, "turnover": 3.8, "stockout": 3.5},
        {"waste": 2.8, "accuracy": 97.5, "turnover": 5.1, "stockout": 1.5},
        {"waste": 5.1, "accuracy": 92.0, "turnover": 3.2, "stockout": 4.8},
        {"waste": 3.2, "accuracy": 95.5, "turnover": 4.5, "stockout": 2.8},
        {"waste": 4.8, "accuracy": 93.0, "turnover": 3.5, "stockout": 4.2},
        {"waste": 2.5, "accuracy": 98.0, "turnover": 5.5, "stockout": 1.2},
        {"waste": 3.8, "accuracy": 95.0, "turnover": 4.0, "stockout": 3.0},
    ]
    
    peer_ids = []
    for i, data in enumerate(peer_data):
        peer_id = uuid.uuid4()
        peer_ids.append(peer_id)
        
        # Opt in
        benchmark_engine.opt_in(peer_id)
        
        # Submit metrics
        metrics = OrgMetrics(
            org_id=peer_id,
            category=OrgCategory.FAST_CASUAL,
            size=OrgSize.MEDIUM,
            period_start=period_start,
            period_end=period_end,
            waste_pct=Decimal(str(data["waste"])),
            inventory_accuracy_pct=Decimal(str(data["accuracy"])),
            inventory_turnover=Decimal(str(data["turnover"])),
            stockout_rate_pct=Decimal(str(data["stockout"])),
        )
        benchmark_engine.submit_metrics(metrics)
    
    # Create YOUR organization
    your_org_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    benchmark_engine.opt_in(your_org_id)
    
    your_metrics = OrgMetrics(
        org_id=your_org_id,
        category=OrgCategory.FAST_CASUAL,
        size=OrgSize.MEDIUM,
        period_start=period_start,
        period_end=period_end,
        waste_pct=Decimal("3.0"),  # Good - below average
        inventory_accuracy_pct=Decimal("94.0"),  # Below average
        inventory_turnover=Decimal("4.8"),  # Good - above average
        stockout_rate_pct=Decimal("3.8"),  # Average
    )
    benchmark_engine.submit_metrics(your_metrics)
    
    # Generate report for your org
    report = benchmark_engine.generate_report(your_org_id)
    
    benchmarks_summary = []
    if report:
        for b in report.benchmarks:
            benchmarks_summary.append({
                "metric": b.metric.value,
                "your_value": str(b.your_value),
                "your_percentile": b.your_percentile,
                "quartile": b.your_quartile.value,
                "peer_median": str(b.peer_median),
            })
    
    return {
        "status": "demo_data_created",
        "your_org_id": str(your_org_id),
        "peer_count": len(peer_ids),
        "category": "fast_casual",
        "size": "medium",
        "your_benchmarks": benchmarks_summary,
        "overall": {
            "percentile": report.overall_percentile if report else None,
            "quartile": report.overall_quartile.value if report and report.overall_quartile else None,
        },
        "strengths": report.strengths if report else [],
        "opportunities": report.improvement_opportunities if report else [],
        "guardrail_reminder": "All peer data is anonymized. No identities are revealed.",
        "test_endpoints": [
            f"GET /benchmark/metric/{your_org_id}/waste",
            f"GET /benchmark/report/{your_org_id}",
            "GET /benchmark/peers/fast_casual/medium",
        ],
    }
