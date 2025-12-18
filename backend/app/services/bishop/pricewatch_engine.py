"""
PROVENIQ Ops - Bishop Vendor Price Watch Engine
Continuously monitor vendor pricing and surface arbitrage opportunities.

LOGIC:
1. Normalize SKUs across vendors
2. Track rolling price deltas
3. Trigger alert when delta > threshold

GUARDRAILS:
- Never auto-switch without approval
- Respect locked contracts
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.core.types import Money
from app.models.pricewatch import (
    ActionPrompt,
    ActiveContract,
    CheaperAlternative,
    ContractStatus,
    HistoricalPrice,
    PriceAlertType,
    PriceWatchConfig,
    PriceWatchSummary,
    SKUMapping,
    VendorPriceAlert,
    VendorPriceFeed,
)
from app.services.audit import audit_service


class PriceWatchEngine:
    """
    Bishop Vendor Price Watch Engine
    
    Monitors vendor pricing and detects arbitrage opportunities.
    Maps to DAG nodes: N3, N14, N23, N34
    """
    
    def __init__(self) -> None:
        self._config = PriceWatchConfig()
        
        # Data stores
        self._price_feeds: dict[str, list[VendorPriceFeed]] = defaultdict(list)  # canonical_sku -> feeds
        self._contracts: dict[uuid.UUID, ActiveContract] = {}  # contract_id -> contract
        self._sku_mappings: dict[str, SKUMapping] = {}  # canonical_sku -> mapping
        self._price_history: dict[str, list[HistoricalPrice]] = defaultdict(list)
        
        # Current vendor assignments
        self._current_vendors: dict[str, uuid.UUID] = {}  # canonical_sku -> vendor_id
        
        # Generated alerts
        self._alerts: list[VendorPriceAlert] = []
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure(self, config: PriceWatchConfig) -> None:
        """Update engine configuration."""
        self._config = config
    
    def get_config(self) -> PriceWatchConfig:
        """Get current configuration."""
        return self._config
    
    # =========================================================================
    # DATA REGISTRATION
    # =========================================================================
    
    def register_sku_mapping(self, mapping: SKUMapping) -> None:
        """Register SKU normalization mapping."""
        self._sku_mappings[mapping.canonical_sku] = mapping
    
    def register_contract(self, contract: ActiveContract) -> None:
        """Register active vendor contract."""
        self._contracts[contract.contract_id] = contract
        # Set as current vendor for this SKU
        self._current_vendors[contract.canonical_sku] = contract.vendor_id
    
    def register_price_feed(self, feed: VendorPriceFeed) -> None:
        """Register a vendor price feed."""
        self._price_feeds[feed.canonical_sku].append(feed)
        
        # Also record to history
        self._price_history[feed.canonical_sku].append(HistoricalPrice(
            canonical_sku=feed.canonical_sku,
            vendor_id=feed.vendor_id,
            price_micros=feed.price_micros,
            recorded_at=feed.effective_date,
            source="feed",
        ))
    
    def set_current_vendor(self, canonical_sku: str, vendor_id: uuid.UUID) -> None:
        """Set the current vendor for a SKU."""
        self._current_vendors[canonical_sku] = vendor_id
    
    # =========================================================================
    # SKU NORMALIZATION (N3)
    # =========================================================================
    
    def normalize_sku(self, vendor_id: uuid.UUID, vendor_sku: str) -> Optional[str]:
        """
        Normalize vendor SKU to canonical SKU.
        
        Args:
            vendor_id: Vendor identifier
            vendor_sku: Vendor-specific SKU
        
        Returns:
            Canonical SKU or None if not mapped
        """
        for canonical_sku, mapping in self._sku_mappings.items():
            for vm in mapping.vendor_mappings:
                if vm.get("vendor_id") == vendor_id and vm.get("vendor_sku") == vendor_sku:
                    return canonical_sku
        return None
    
    def get_vendor_skus(self, canonical_sku: str) -> list[dict]:
        """Get all vendor SKU mappings for a canonical SKU."""
        mapping = self._sku_mappings.get(canonical_sku)
        if mapping:
            return mapping.vendor_mappings
        return []
    
    # =========================================================================
    # PRICE ANALYSIS (N14)
    # =========================================================================
    
    def _get_current_price(self, canonical_sku: str, vendor_id: uuid.UUID) -> Optional[int]:
        """Get current price for SKU from vendor."""
        feeds = self._price_feeds.get(canonical_sku, [])
        for feed in reversed(feeds):  # Most recent first
            if feed.vendor_id == vendor_id:
                # Check if not expired
                if feed.expires_at and feed.expires_at < datetime.utcnow():
                    continue
                return feed.price_micros
        return None
    
    def _get_all_current_prices(self, canonical_sku: str) -> list[VendorPriceFeed]:
        """Get current prices from all vendors for a SKU."""
        feeds = self._price_feeds.get(canonical_sku, [])
        now = datetime.utcnow()
        
        # Get most recent feed per vendor
        vendor_feeds: dict[uuid.UUID, VendorPriceFeed] = {}
        for feed in feeds:
            if feed.expires_at and feed.expires_at < now:
                continue
            existing = vendor_feeds.get(feed.vendor_id)
            if not existing or feed.effective_date > existing.effective_date:
                vendor_feeds[feed.vendor_id] = feed
        
        return list(vendor_feeds.values())
    
    def _calculate_rolling_average(
        self,
        canonical_sku: str,
        vendor_id: uuid.UUID,
        days: int = 30,
    ) -> Optional[int]:
        """Calculate rolling average price."""
        history = self._price_history.get(canonical_sku, [])
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        prices = [
            h.price_micros for h in history
            if h.vendor_id == vendor_id and h.recorded_at >= cutoff
        ]
        
        if not prices:
            return None
        
        return sum(prices) // len(prices)
    
    def _find_cheapest_alternative(
        self,
        canonical_sku: str,
        current_vendor_id: uuid.UUID,
        current_price_micros: int,
    ) -> Optional[CheaperAlternative]:
        """Find the cheapest alternative vendor."""
        feeds = self._get_all_current_prices(canonical_sku)
        
        cheapest = None
        cheapest_price = current_price_micros
        
        for feed in feeds:
            if feed.vendor_id == current_vendor_id:
                continue
            if feed.price_micros < cheapest_price:
                cheapest = feed
                cheapest_price = feed.price_micros
        
        if not cheapest:
            return None
        
        savings_micros = current_price_micros - cheapest.price_micros
        savings_percent = Decimal(savings_micros) / Decimal(current_price_micros) * 100
        
        return CheaperAlternative(
            vendor_id=cheapest.vendor_id,
            vendor_name=cheapest.vendor_name,
            vendor_sku=cheapest.vendor_sku,
            price_micros=cheapest.price_micros,
            savings_micros=savings_micros,
            savings_percent=savings_percent.quantize(Decimal("0.01")),
            lead_time_hours=cheapest.lead_time_hours,
            stock_available=cheapest.stock_available,
        )
    
    # =========================================================================
    # CONTRACT CHECKING (N23)
    # =========================================================================
    
    def _get_contract_for_sku(self, canonical_sku: str) -> Optional[ActiveContract]:
        """Get active contract for a SKU."""
        for contract in self._contracts.values():
            if contract.canonical_sku == canonical_sku:
                if contract.status == ContractStatus.ACTIVE:
                    if contract.end_date > datetime.utcnow():
                        return contract
        return None
    
    def _is_contract_locked(self, canonical_sku: str) -> tuple[bool, Optional[str]]:
        """Check if SKU is locked by contract."""
        contract = self._get_contract_for_sku(canonical_sku)
        if contract and contract.is_locked:
            return True, contract.lock_reason
        return False, None
    
    # =========================================================================
    # ALERT GENERATION (N14 -> N34)
    # =========================================================================
    
    def analyze_sku(self, canonical_sku: str) -> Optional[VendorPriceAlert]:
        """
        Analyze a single SKU for price variance.
        
        Returns alert if variance exceeds threshold.
        """
        # Get current vendor
        current_vendor_id = self._current_vendors.get(canonical_sku)
        if not current_vendor_id:
            return None
        
        # Get SKU info
        mapping = self._sku_mappings.get(canonical_sku)
        if not mapping:
            return None
        
        # Get current price
        current_price = self._get_current_price(canonical_sku, current_vendor_id)
        if not current_price:
            return None
        
        # Find cheapest alternative
        alternative = self._find_cheapest_alternative(
            canonical_sku,
            current_vendor_id,
            current_price,
        )
        
        if not alternative:
            return None
        
        # Check if variance exceeds threshold
        if alternative.savings_percent < self._config.alert_threshold_percent:
            return None
        
        # Check contract status
        contract = self._get_contract_for_sku(canonical_sku)
        is_locked, lock_reason = self._is_contract_locked(canonical_sku)
        
        # Determine action prompt
        if is_locked:
            action_prompt = ActionPrompt.MONITOR
            reason_codes = ["contract_locked", lock_reason or "vendor_agreement"]
        elif contract and contract.end_date > datetime.utcnow() + timedelta(days=90):
            action_prompt = ActionPrompt.RENEGOTIATE
            reason_codes = ["active_contract", "significant_savings"]
        else:
            action_prompt = ActionPrompt.SWITCH_VENDOR
            reason_codes = ["no_contract_restriction", "savings_available"]
        
        # Calculate confidence
        # Higher confidence with more price history and larger savings
        history_count = len(self._price_history.get(canonical_sku, []))
        history_factor = min(Decimal("0.3"), Decimal(history_count) / 100)
        savings_factor = min(Decimal("0.5"), alternative.savings_percent / 20)
        confidence = Decimal("0.2") + history_factor + savings_factor
        
        # Get vendor name
        current_vendor_name = "Unknown"
        for feed in self._price_feeds.get(canonical_sku, []):
            if feed.vendor_id == current_vendor_id:
                current_vendor_name = feed.vendor_name
                break
        
        # Calculate annual impact
        annual_volume = 100  # Placeholder - would come from demand forecast
        annual_savings = alternative.savings_micros * annual_volume
        
        alert = VendorPriceAlert(
            alert_type=PriceAlertType.VENDOR_PRICE_VARIANCE,
            canonical_sku=canonical_sku,
            product_id=mapping.product_id,
            product_name=mapping.product_name,
            current_vendor_id=current_vendor_id,
            current_vendor_name=current_vendor_name,
            current_price_micros=current_price,
            price_delta_micros=alternative.savings_micros,
            price_delta_percent=alternative.savings_percent,
            cheaper_alternative=alternative,
            contract_id=contract.contract_id if contract else None,
            contract_locked=is_locked,
            contract_end_date=contract.end_date if contract else None,
            action_prompt=action_prompt,
            confidence=confidence,
            reason_codes=reason_codes,
            annual_volume=annual_volume,
            annual_savings_micros=annual_savings,
        )
        
        self._alerts.append(alert)
        return alert
    
    def analyze_all(self) -> PriceWatchSummary:
        """
        Analyze all SKUs for price variance.
        
        Returns summary with all alerts.
        """
        self._alerts = []  # Reset alerts
        
        alerts_by_type: dict[str, int] = defaultdict(int)
        total_savings = 0
        switch_opportunities = 0
        locked_opportunities = 0
        
        for canonical_sku in self._sku_mappings:
            alert = self.analyze_sku(canonical_sku)
            if alert:
                alerts_by_type[alert.alert_type.value] += 1
                
                if alert.annual_savings_micros:
                    total_savings += alert.annual_savings_micros
                
                if alert.contract_locked:
                    locked_opportunities += 1
                elif alert.action_prompt == ActionPrompt.SWITCH_VENDOR:
                    switch_opportunities += 1
        
        # Sort alerts by savings
        top_alerts = sorted(
            self._alerts,
            key=lambda a: a.annual_savings_micros or 0,
            reverse=True,
        )[:10]
        
        return PriceWatchSummary(
            skus_analyzed=len(self._sku_mappings),
            vendors_compared=len(set(
                feed.vendor_id
                for feeds in self._price_feeds.values()
                for feed in feeds
            )),
            alerts_generated=len(self._alerts),
            total_savings_available_micros=total_savings,
            switch_opportunities=switch_opportunities,
            locked_opportunities=locked_opportunities,
            alerts_by_type=dict(alerts_by_type),
            top_savings=top_alerts,
        )
    
    # =========================================================================
    # PRICE SPIKE DETECTION
    # =========================================================================
    
    def detect_price_spike(
        self,
        canonical_sku: str,
        vendor_id: uuid.UUID,
    ) -> Optional[VendorPriceAlert]:
        """
        Detect sudden price spikes above historical average.
        """
        current_price = self._get_current_price(canonical_sku, vendor_id)
        if not current_price:
            return None
        
        avg_price = self._calculate_rolling_average(
            canonical_sku,
            vendor_id,
            self._config.rolling_window_days,
        )
        
        if not avg_price:
            return None
        
        if current_price <= avg_price:
            return None
        
        delta_percent = Decimal(current_price - avg_price) / Decimal(avg_price) * 100
        
        if delta_percent < self._config.spike_threshold_percent:
            return None
        
        mapping = self._sku_mappings.get(canonical_sku)
        if not mapping:
            return None
        
        # Get vendor name
        vendor_name = "Unknown"
        for feed in self._price_feeds.get(canonical_sku, []):
            if feed.vendor_id == vendor_id:
                vendor_name = feed.vendor_name
                break
        
        alert = VendorPriceAlert(
            alert_type=PriceAlertType.PRICE_SPIKE,
            canonical_sku=canonical_sku,
            product_id=mapping.product_id,
            product_name=mapping.product_name,
            current_vendor_id=vendor_id,
            current_vendor_name=vendor_name,
            current_price_micros=current_price,
            price_delta_micros=current_price - avg_price,
            price_delta_percent=delta_percent.quantize(Decimal("0.01")),
            action_prompt=ActionPrompt.RENEGOTIATE,
            confidence=Decimal("0.7"),
            reason_codes=["price_spike_detected", f"above_{self._config.rolling_window_days}d_avg"],
        )
        
        self._alerts.append(alert)
        return alert
    
    # =========================================================================
    # QUERY
    # =========================================================================
    
    def get_alerts(
        self,
        alert_type: Optional[PriceAlertType] = None,
        min_savings_percent: Optional[Decimal] = None,
    ) -> list[VendorPriceAlert]:
        """Get generated alerts with optional filters."""
        alerts = self._alerts
        
        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]
        
        if min_savings_percent:
            alerts = [a for a in alerts if a.price_delta_percent >= min_savings_percent]
        
        return alerts
    
    def get_sku_price_comparison(self, canonical_sku: str) -> dict:
        """Get price comparison for a SKU across all vendors."""
        feeds = self._get_all_current_prices(canonical_sku)
        mapping = self._sku_mappings.get(canonical_sku)
        current_vendor_id = self._current_vendors.get(canonical_sku)
        
        return {
            "canonical_sku": canonical_sku,
            "product_name": mapping.product_name if mapping else "Unknown",
            "current_vendor_id": str(current_vendor_id) if current_vendor_id else None,
            "prices": [
                {
                    "vendor_id": str(f.vendor_id),
                    "vendor_name": f.vendor_name,
                    "price_micros": f.price_micros,
                    "price_display": Money.to_dollars_str(f.price_micros),
                    "is_current": f.vendor_id == current_vendor_id,
                    "lead_time_hours": f.lead_time_hours,
                }
                for f in sorted(feeds, key=lambda x: x.price_micros)
            ],
        }
    
    def clear_data(self) -> None:
        """Clear all data (for testing)."""
        self._price_feeds.clear()
        self._contracts.clear()
        self._sku_mappings.clear()
        self._price_history.clear()
        self._current_vendors.clear()
        self._alerts.clear()


# Singleton instance
pricewatch_engine = PriceWatchEngine()
