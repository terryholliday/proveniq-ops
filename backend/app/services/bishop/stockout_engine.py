"""
PROVENIQ Ops - Bishop Predictive Stockout Engine
Foresight engine that predicts stockouts BEFORE they occur.

LOGIC:
1. Calculate real-time burn rate from scan velocity
2. Compare against historical averages to detect acceleration
3. Project stockout timestamp
4. If projected stockout < (lead_time + safety_buffer):
   - Generate STOCKOUT_RISK alert
   - Pre-build reorder recommendation

GUARDRAILS:
- Never reorder without explicit approval unless flagged as CRITICAL
- Never fabricate demand patterns
- If data confidence < 0.6, downgrade to WARNING only
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.models.stockout import (
    AlertSeverity,
    AlertType,
    HistoricalUsage,
    InventoryLevel,
    OpenPurchaseOrder,
    ReorderRecommendation,
    ScanEvent,
    StockoutAlert,
    StockoutPredictionResponse,
    VendorLeadTime,
)


@dataclass
class ProductAnalysis:
    """Internal analysis result for a single product."""
    product_id: uuid.UUID
    product_name: str
    current_qty: int
    safety_stock: int
    realtime_burn_rate: float  # units per hour
    historical_burn_rate: float  # units per hour (avg)
    burn_acceleration: float  # ratio of realtime/historical
    hours_to_stockout: float
    hours_to_safety_stock: float
    confidence: float
    incoming_qty: int  # from open POs
    best_vendor_id: Optional[uuid.UUID]
    best_vendor_name: Optional[str]
    best_lead_time: Optional[int]
    best_unit_price: Optional[Decimal]


class StockoutEngine:
    """
    Bishop Predictive Stockout Engine
    
    Deterministic foresight system - NOT a chatbot.
    Outputs alerts and decision objects only.
    """
    
    # Configuration thresholds
    CONFIDENCE_THRESHOLD_WARNING = 0.6
    CONFIDENCE_THRESHOLD_ALERT = 0.75
    ACCELERATION_ALERT_THRESHOLD = 1.3  # 30% faster than historical
    CRITICAL_HOURS_THRESHOLD = 12  # less than 12h = CRITICAL
    HIGH_HOURS_THRESHOLD = 48
    MEDIUM_HOURS_THRESHOLD = 96
    
    def __init__(self) -> None:
        self._inventory_levels: dict[uuid.UUID, InventoryLevel] = {}
        self._scan_events: dict[uuid.UUID, list[ScanEvent]] = {}
        self._historical_usage: dict[uuid.UUID, HistoricalUsage] = {}
        self._vendor_lead_times: dict[uuid.UUID, list[VendorLeadTime]] = {}
        self._open_pos: dict[uuid.UUID, list[OpenPurchaseOrder]] = {}
        self._product_names: dict[uuid.UUID, str] = {}
        self._vendor_prices: dict[tuple[uuid.UUID, uuid.UUID], Decimal] = {}
    
    # =========================================================================
    # DATA REGISTRATION (Mock data injection for development)
    # =========================================================================
    
    def register_inventory(self, level: InventoryLevel, product_name: str) -> None:
        """Register current inventory level for a product."""
        self._inventory_levels[level.product_id] = level
        self._product_names[level.product_id] = product_name
    
    def register_scan_event(self, event: ScanEvent) -> None:
        """Register a scan event for burn rate calculation."""
        if event.product_id not in self._scan_events:
            self._scan_events[event.product_id] = []
        self._scan_events[event.product_id].append(event)
        # Keep only last 7 days of events
        cutoff = datetime.utcnow() - timedelta(days=7)
        self._scan_events[event.product_id] = [
            e for e in self._scan_events[event.product_id]
            if e.timestamp > cutoff
        ]
    
    def register_historical_usage(self, usage: HistoricalUsage) -> None:
        """Register historical usage statistics."""
        self._historical_usage[usage.product_id] = usage
    
    def register_vendor_lead_time(self, lead_time: VendorLeadTime) -> None:
        """Register vendor lead time for a product."""
        if lead_time.product_id not in self._vendor_lead_times:
            self._vendor_lead_times[lead_time.product_id] = []
        # Update or add
        existing = next(
            (lt for lt in self._vendor_lead_times[lead_time.product_id]
             if lt.vendor_id == lead_time.vendor_id),
            None
        )
        if existing:
            self._vendor_lead_times[lead_time.product_id].remove(existing)
        self._vendor_lead_times[lead_time.product_id].append(lead_time)
    
    def register_open_po(self, po: OpenPurchaseOrder) -> None:
        """Register an open purchase order."""
        if po.product_id not in self._open_pos:
            self._open_pos[po.product_id] = []
        self._open_pos[po.product_id].append(po)
    
    def register_vendor_price(
        self, 
        product_id: uuid.UUID, 
        vendor_id: uuid.UUID, 
        price: Decimal
    ) -> None:
        """Register vendor price for a product."""
        self._vendor_prices[(product_id, vendor_id)] = price
    
    # =========================================================================
    # BURN RATE CALCULATIONS
    # =========================================================================
    
    def _calculate_realtime_burn_rate(
        self, 
        product_id: uuid.UUID,
        window_hours: int = 72
    ) -> tuple[float, float]:
        """
        Calculate real-time burn rate from recent scan events.
        
        Returns:
            Tuple of (burn_rate_per_hour, confidence)
        """
        events = self._scan_events.get(product_id, [])
        if not events:
            return 0.0, 0.0
        
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        recent_events = [e for e in events if e.timestamp > cutoff]
        
        if len(recent_events) < 2:
            return 0.0, 0.3  # Low confidence with minimal data
        
        # Sum consumption (negative qty_delta)
        total_consumed = sum(
            abs(e.qty_delta) for e in recent_events if e.qty_delta < 0
        )
        
        # Calculate time span
        timestamps = sorted(e.timestamp for e in recent_events)
        time_span_hours = (timestamps[-1] - timestamps[0]).total_seconds() / 3600
        
        if time_span_hours < 1:
            return 0.0, 0.2
        
        burn_rate = total_consumed / time_span_hours
        
        # Confidence based on data points and time coverage
        data_point_factor = min(len(recent_events) / 20, 1.0)
        time_coverage_factor = min(time_span_hours / window_hours, 1.0)
        confidence = (data_point_factor * 0.6) + (time_coverage_factor * 0.4)
        
        return burn_rate, confidence
    
    def _get_historical_burn_rate(self, product_id: uuid.UUID) -> float:
        """Get historical average burn rate (units per hour)."""
        usage = self._historical_usage.get(product_id)
        if not usage:
            return 0.0
        # Use 7-day average, converted to hourly
        return usage.avg_daily_burn_7d / 24
    
    def _calculate_burn_acceleration(
        self, 
        realtime_rate: float, 
        historical_rate: float
    ) -> float:
        """
        Calculate acceleration ratio.
        > 1.0 means burning faster than historical average.
        """
        if historical_rate <= 0:
            return 1.0 if realtime_rate <= 0 else 2.0
        return realtime_rate / historical_rate
    
    # =========================================================================
    # STOCKOUT PROJECTION
    # =========================================================================
    
    def _project_stockout(
        self,
        current_qty: int,
        safety_stock: int,
        burn_rate: float,
        incoming_qty: int = 0
    ) -> tuple[float, float]:
        """
        Project hours until stockout and hours until safety stock breach.
        
        Returns:
            Tuple of (hours_to_stockout, hours_to_safety_stock)
        """
        if burn_rate <= 0:
            return float('inf'), float('inf')
        
        effective_qty = current_qty + incoming_qty
        
        hours_to_stockout = effective_qty / burn_rate
        hours_to_safety = max(0, (effective_qty - safety_stock) / burn_rate)
        
        return hours_to_stockout, hours_to_safety
    
    def _get_incoming_qty(self, product_id: uuid.UUID) -> int:
        """Get total incoming quantity from open POs."""
        pos = self._open_pos.get(product_id, [])
        now = datetime.utcnow()
        # Only count POs expected within reasonable timeframe
        relevant_pos = [
            po for po in pos 
            if po.status in ("pending", "shipped")
            and po.expected_delivery > now
            and (po.expected_delivery - now).days <= 7
        ]
        return sum(po.qty_ordered for po in relevant_pos)
    
    def _get_best_vendor(
        self, 
        product_id: uuid.UUID
    ) -> tuple[Optional[uuid.UUID], Optional[str], Optional[int], Optional[Decimal]]:
        """
        Get best vendor for reorder based on lead time and reliability.
        
        Returns:
            Tuple of (vendor_id, vendor_name, lead_time_hours, unit_price)
        """
        lead_times = self._vendor_lead_times.get(product_id, [])
        if not lead_times:
            return None, None, None, None
        
        # Sort by lead time, weighted by reliability
        def score(lt: VendorLeadTime) -> float:
            return lt.avg_lead_time_hours / max(lt.reliability_score, 0.1)
        
        best = min(lead_times, key=score)
        price = self._vendor_prices.get((product_id, best.vendor_id))
        
        return best.vendor_id, best.vendor_name, best.avg_lead_time_hours, price
    
    # =========================================================================
    # ALERT GENERATION
    # =========================================================================
    
    def _determine_severity(
        self, 
        hours_to_stockout: float,
        confidence: float
    ) -> AlertSeverity:
        """Determine alert severity based on time and confidence."""
        if hours_to_stockout <= self.CRITICAL_HOURS_THRESHOLD:
            return AlertSeverity.CRITICAL
        elif hours_to_stockout <= self.HIGH_HOURS_THRESHOLD:
            return AlertSeverity.HIGH
        elif hours_to_stockout <= self.MEDIUM_HOURS_THRESHOLD:
            return AlertSeverity.MEDIUM
        return AlertSeverity.LOW
    
    def _determine_alert_type(self, confidence: float) -> AlertType:
        """Determine alert type based on confidence."""
        if confidence < self.CONFIDENCE_THRESHOLD_WARNING:
            return AlertType.WARNING
        return AlertType.PREDICTIVE_STOCKOUT
    
    def _build_reorder_recommendation(
        self,
        analysis: ProductAnalysis,
        safety_buffer_hours: int
    ) -> Optional[ReorderRecommendation]:
        """Build reorder recommendation if vendor data available."""
        if not analysis.best_vendor_id:
            return None
        
        # Calculate reorder quantity to cover lead time + buffer + safety stock
        coverage_hours = (analysis.best_lead_time or 48) + safety_buffer_hours
        burn_during_lead = analysis.realtime_burn_rate * coverage_hours
        
        # Reorder to bring back to safety stock + buffer
        reorder_qty = max(
            int(burn_during_lead + analysis.safety_stock - analysis.current_qty),
            1
        )
        
        # Calculate estimated cost
        unit_price = analysis.best_unit_price or Decimal("10.00")
        estimated_cost = unit_price * reorder_qty
        
        # Auto-approve only if CRITICAL and high confidence
        requires_approval = not (
            analysis.hours_to_stockout <= self.CRITICAL_HOURS_THRESHOLD
            and analysis.confidence >= 0.85
        )
        
        return ReorderRecommendation(
            vendor_id=analysis.best_vendor_id,
            vendor_name=analysis.best_vendor_name or "Unknown",
            reorder_qty=reorder_qty,
            estimated_cost=estimated_cost,
            lead_time_hours=analysis.best_lead_time or 48,
            requires_approval=requires_approval,
        )
    
    def _analyze_product(
        self, 
        product_id: uuid.UUID,
        safety_buffer_hours: int = 24
    ) -> Optional[ProductAnalysis]:
        """Perform full analysis on a single product."""
        level = self._inventory_levels.get(product_id)
        if not level:
            return None
        
        product_name = self._product_names.get(product_id, "Unknown")
        
        # Calculate burn rates
        realtime_rate, confidence = self._calculate_realtime_burn_rate(product_id)
        historical_rate = self._get_historical_burn_rate(product_id)
        
        # Use historical if realtime confidence is too low
        if confidence < 0.3 and historical_rate > 0:
            effective_rate = historical_rate
            confidence = 0.5  # Moderate confidence for historical-only
        else:
            # Blend realtime and historical based on confidence
            blend_factor = confidence
            effective_rate = (
                realtime_rate * blend_factor + 
                historical_rate * (1 - blend_factor)
            )
        
        acceleration = self._calculate_burn_acceleration(realtime_rate, historical_rate)
        incoming = self._get_incoming_qty(product_id)
        
        hours_to_stockout, hours_to_safety = self._project_stockout(
            level.on_hand_qty,
            level.safety_stock,
            effective_rate,
            incoming
        )
        
        vendor_id, vendor_name, lead_time, price = self._get_best_vendor(product_id)
        
        return ProductAnalysis(
            product_id=product_id,
            product_name=product_name,
            current_qty=level.on_hand_qty,
            safety_stock=level.safety_stock,
            realtime_burn_rate=realtime_rate,
            historical_burn_rate=historical_rate,
            burn_acceleration=acceleration,
            hours_to_stockout=hours_to_stockout,
            hours_to_safety_stock=hours_to_safety,
            confidence=confidence,
            incoming_qty=incoming,
            best_vendor_id=vendor_id,
            best_vendor_name=vendor_name,
            best_lead_time=lead_time,
            best_unit_price=price,
        )
    
    def _should_alert(
        self, 
        analysis: ProductAnalysis,
        safety_buffer_hours: int
    ) -> bool:
        """Determine if this product warrants an alert."""
        # Get minimum lead time (or default)
        lead_time = analysis.best_lead_time or 48
        threshold = lead_time + safety_buffer_hours
        
        # Alert if projected stockout is within threshold
        if analysis.hours_to_stockout <= threshold:
            return True
        
        # Alert if hitting safety stock within threshold
        if analysis.hours_to_safety_stock <= threshold:
            return True
        
        # Alert if burn rate is accelerating significantly
        if (analysis.burn_acceleration >= self.ACCELERATION_ALERT_THRESHOLD
            and analysis.hours_to_stockout <= threshold * 2):
            return True
        
        return False
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    def analyze(
        self,
        product_ids: Optional[list[uuid.UUID]] = None,
        safety_buffer_hours: int = 24,
        include_warnings: bool = True
    ) -> StockoutPredictionResponse:
        """
        Analyze stockout risk for specified products (or all).
        
        Args:
            product_ids: Products to analyze (None = all registered)
            safety_buffer_hours: Extra buffer beyond lead time
            include_warnings: Include low-confidence warnings
        
        Returns:
            StockoutPredictionResponse with all alerts
        """
        if product_ids is None:
            product_ids = list(self._inventory_levels.keys())
        
        alerts: list[StockoutAlert] = []
        
        for product_id in product_ids:
            analysis = self._analyze_product(product_id, safety_buffer_hours)
            if not analysis:
                continue
            
            if not self._should_alert(analysis, safety_buffer_hours):
                continue
            
            alert_type = self._determine_alert_type(analysis.confidence)
            
            # Skip warnings if not requested
            if alert_type == AlertType.WARNING and not include_warnings:
                continue
            
            severity = self._determine_severity(
                analysis.hours_to_stockout,
                analysis.confidence
            )
            
            recommendation = self._build_reorder_recommendation(
                analysis,
                safety_buffer_hours
            )
            
            alert = StockoutAlert(
                alert_type=alert_type,
                severity=severity,
                product_id=analysis.product_id,
                product_name=analysis.product_name,
                current_on_hand=analysis.current_qty,
                safety_stock=analysis.safety_stock,
                projected_hours_to_stockout=round(analysis.hours_to_stockout, 1),
                confidence=round(analysis.confidence, 2),
                recommended_action=recommendation,
            )
            alerts.append(alert)
        
        # Sort by severity (critical first) then by hours to stockout
        severity_order = {
            AlertSeverity.CRITICAL: 0,
            AlertSeverity.HIGH: 1,
            AlertSeverity.MEDIUM: 2,
            AlertSeverity.LOW: 3,
        }
        alerts.sort(key=lambda a: (severity_order[a.severity], a.projected_hours_to_stockout))
        
        return StockoutPredictionResponse(
            alerts=alerts,
            products_analyzed=len(product_ids),
            alerts_generated=len(alerts),
        )
    
    def get_critical_alerts(self) -> list[StockoutAlert]:
        """Get only CRITICAL severity alerts."""
        response = self.analyze(include_warnings=False)
        return [a for a in response.alerts if a.severity == AlertSeverity.CRITICAL]
    
    def clear_data(self) -> None:
        """Clear all registered data (for testing)."""
        self._inventory_levels.clear()
        self._scan_events.clear()
        self._historical_usage.clear()
        self._vendor_lead_times.clear()
        self._open_pos.clear()
        self._product_names.clear()
        self._vendor_prices.clear()


# Singleton instance
stockout_engine = StockoutEngine()
