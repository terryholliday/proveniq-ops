"""
PROVENIQ Ops - Bishop Ghost Inventory Detector
Detect inventory items that exist in records but have not been scanned.

DAG Node: N12

LOGIC:
1. Identify items with no scan activity for X days
2. Calculate theoretical vs observed variance
3. Compute financial exposure

GUARDRAILS:
- Do not accuse users
- This is a loss-signal, not a disciplinary tool
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.core.types import Money
from app.models.ghost import (
    GhostAlertType,
    GhostDetectorConfig,
    GhostDetectorSummary,
    GhostInventoryAlert,
    GhostItem,
    InventoryRecord,
    ProductScanHistory,
    RecommendedAction,
    RiskLevel,
    ScanRecord,
)


class GhostInventoryEngine:
    """
    Bishop Ghost Inventory Detection Engine
    
    Detects inventory that exists in records but hasn't been verified
    through scanning within a configurable threshold window.
    
    Maps to DAG node: N12
    
    IMPORTANT: This is a LOSS SIGNAL, not a disciplinary tool.
    """
    
    def __init__(self) -> None:
        self._config = GhostDetectorConfig()
        
        # Data stores
        self._inventory: dict[tuple[uuid.UUID, uuid.UUID], InventoryRecord] = {}  # (product_id, location_id) -> record
        self._scan_history: dict[tuple[uuid.UUID, uuid.UUID], ProductScanHistory] = {}
        self._scans: list[ScanRecord] = []
        
        # Location names
        self._locations: dict[uuid.UUID, str] = {}
        
        # Generated alerts
        self._alerts: list[GhostInventoryAlert] = []
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure(self, config: GhostDetectorConfig) -> None:
        """Update detector configuration."""
        self._config = config
    
    def get_config(self) -> GhostDetectorConfig:
        """Get current configuration."""
        return self._config
    
    # =========================================================================
    # DATA REGISTRATION
    # =========================================================================
    
    def register_inventory(self, record: InventoryRecord) -> None:
        """Register an inventory record."""
        key = (record.product_id, record.location_id)
        self._inventory[key] = record
        self._locations[record.location_id] = record.location_name
    
    def register_scan(self, scan: ScanRecord) -> None:
        """Register a scan event and update history."""
        self._scans.append(scan)
        
        key = (scan.product_id, scan.location_id)
        history = self._scan_history.get(key)
        
        if not history:
            history = ProductScanHistory(
                product_id=scan.product_id,
                location_id=scan.location_id,
            )
            self._scan_history[key] = history
        
        # Update if this is a more recent scan
        if not history.last_scanned_at or scan.scanned_at > history.last_scanned_at:
            history.last_scanned_at = scan.scanned_at
            history.last_scanned_qty = scan.scanned_qty
        
        # Update scan count
        cutoff = datetime.utcnow() - timedelta(days=30)
        history.scan_count_30d = len([
            s for s in self._scans
            if s.product_id == scan.product_id 
            and s.location_id == scan.location_id
            and s.scanned_at >= cutoff
        ])
    
    def register_location(self, location_id: uuid.UUID, name: str) -> None:
        """Register a location."""
        self._locations[location_id] = name
    
    # =========================================================================
    # GHOST DETECTION (N12)
    # =========================================================================
    
    def _calculate_days_since_scan(
        self,
        product_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> tuple[int, Optional[datetime], Optional[int]]:
        """Calculate days since last scan for a product at location."""
        key = (product_id, location_id)
        history = self._scan_history.get(key)
        
        if not history or not history.last_scanned_at:
            return 9999, None, None  # Never scanned
        
        days = (datetime.utcnow() - history.last_scanned_at).days
        return days, history.last_scanned_at, history.last_scanned_qty
    
    def _calculate_variance(
        self,
        system_qty: int,
        scanned_qty: Optional[int],
    ) -> Optional[int]:
        """Calculate variance between system and scanned quantity."""
        if scanned_qty is None:
            return None
        return system_qty - scanned_qty  # Positive = system has more (potential loss)
    
    def _calculate_risk_level(
        self,
        days_unscanned: int,
        exposure_micros: int,
        variance_qty: Optional[int],
        is_high_value: bool,
        is_controlled: bool,
    ) -> tuple[RiskLevel, list[str]]:
        """
        Calculate risk level for a ghost item.
        
        NOT an accusation - just a prioritization signal.
        """
        risk_factors = []
        score = Decimal("0")
        
        # Days factor
        if days_unscanned >= 30:
            score += Decimal("0.4")
            risk_factors.append(f"unscanned_{days_unscanned}_days")
        elif days_unscanned >= 14:
            score += Decimal("0.2")
            risk_factors.append(f"unscanned_{days_unscanned}_days")
        
        # Value factor
        if exposure_micros >= self._config.critical_exposure_threshold_micros:
            score += Decimal("0.4")
            risk_factors.append("critical_value")
        elif exposure_micros >= self._config.high_value_threshold_micros:
            score += Decimal("0.2")
            risk_factors.append("high_value")
        
        # Variance factor
        if variance_qty is not None and variance_qty > 0:
            score += Decimal("0.3")
            risk_factors.append(f"variance_{variance_qty}_units")
        
        # Special items
        if is_controlled:
            score += Decimal("0.2")
            risk_factors.append("controlled_item")
        if is_high_value:
            score += Decimal("0.1")
            risk_factors.append("high_value_item")
        
        # Determine level
        if score >= Decimal("0.7"):
            return RiskLevel.CRITICAL, risk_factors
        elif score >= Decimal("0.5"):
            return RiskLevel.HIGH, risk_factors
        elif score >= Decimal("0.3"):
            return RiskLevel.MEDIUM, risk_factors
        else:
            return RiskLevel.LOW, risk_factors
    
    def _get_possible_causes(
        self,
        days_unscanned: int,
        variance_qty: Optional[int],
        category: str,
    ) -> list[str]:
        """
        Suggest possible causes for ghost inventory.
        
        IMPORTANT: These are SYSTEM causes, not accusations.
        """
        causes = []
        
        if days_unscanned > 30:
            causes.append("item_may_be_in_storage_overflow")
            causes.append("scan_process_may_have_skipped_location")
        
        if variance_qty and variance_qty > 0:
            causes.append("receiving_scan_may_not_have_occurred")
            causes.append("transfer_may_not_be_recorded")
            causes.append("system_adjustment_may_be_needed")
        
        if category in ("perishable", "food"):
            causes.append("item_may_have_expired_and_disposed")
        
        if not causes:
            causes.append("routine_verification_recommended")
        
        return causes
    
    def detect_ghost_inventory(
        self,
        location_id: Optional[uuid.UUID] = None,
        category: Optional[str] = None,
    ) -> GhostInventoryAlert:
        """
        Detect ghost inventory across specified scope.
        
        Args:
            location_id: Optional filter by location
            category: Optional filter by category
        
        Returns:
            GhostInventoryAlert with flagged items
        """
        now = datetime.utcnow()
        flagged_items: list[GhostItem] = []
        
        total_system_value = 0
        total_variance_value = 0
        total_exposure_value = 0
        
        locations_seen = set()
        products_seen = set()
        
        for key, record in self._inventory.items():
            product_id, loc_id = key
            
            # Apply filters
            if location_id and loc_id != location_id:
                continue
            if category and record.category != category:
                continue
            if record.system_qty < self._config.min_system_qty:
                continue
            if not self._config.include_controlled_items and record.is_controlled:
                continue
            
            locations_seen.add(loc_id)
            products_seen.add(product_id)
            
            # Get scan info
            days_since, last_scanned_at, last_qty = self._calculate_days_since_scan(
                product_id, loc_id
            )
            
            # Check threshold
            if days_since < self._config.unscanned_threshold_days:
                continue  # Recently scanned, skip
            
            # Calculate variance
            variance = self._calculate_variance(record.system_qty, last_qty)
            
            # Calculate exposure
            exposure = record.system_qty * record.unit_cost_micros
            variance_value = (variance * record.unit_cost_micros) if variance else 0
            
            total_system_value += exposure
            total_exposure_value += exposure
            if variance_value > 0:
                total_variance_value += variance_value
            
            # Calculate risk
            risk_level, risk_factors = self._calculate_risk_level(
                days_since,
                exposure,
                variance,
                record.is_high_value,
                record.is_controlled,
            )
            
            # Skip low value items if configured
            if not self._config.include_low_value_items:
                if exposure < self._config.high_value_threshold_micros:
                    continue
            
            # Get possible causes (NOT accusations)
            causes = self._get_possible_causes(days_since, variance, record.category)
            
            ghost_item = GhostItem(
                product_id=record.product_id,
                product_name=record.product_name,
                canonical_sku=record.canonical_sku,
                location_id=record.location_id,
                location_name=record.location_name,
                system_qty=record.system_qty,
                last_scanned_qty=last_qty,
                variance_qty=variance,
                last_scanned_at=last_scanned_at,
                days_since_scan=days_since,
                unit_cost_micros=record.unit_cost_micros,
                exposure_value_micros=exposure,
                variance_value_micros=variance_value if variance_value > 0 else None,
                risk_level=risk_level,
                risk_factors=risk_factors,
                possible_causes=causes,
            )
            
            flagged_items.append(ghost_item)
        
        # Sort by exposure (highest first)
        flagged_items.sort(key=lambda x: x.exposure_value_micros, reverse=True)
        
        # Count by risk level
        critical = len([i for i in flagged_items if i.risk_level == RiskLevel.CRITICAL])
        high = len([i for i in flagged_items if i.risk_level == RiskLevel.HIGH])
        medium = len([i for i in flagged_items if i.risk_level == RiskLevel.MEDIUM])
        low = len([i for i in flagged_items if i.risk_level == RiskLevel.LOW])
        
        # Determine recommended action
        if critical > 0 or total_variance_value > self._config.critical_exposure_threshold_micros:
            action = RecommendedAction.PHYSICAL_AUDIT
            confidence = Decimal("0.85")
        elif high > 0:
            action = RecommendedAction.CYCLE_COUNT
            confidence = Decimal("0.75")
        elif medium > 0:
            action = RecommendedAction.LOCATION_CHECK
            confidence = Decimal("0.65")
        elif low > 0:
            action = RecommendedAction.MONITOR
            confidence = Decimal("0.55")
        else:
            action = RecommendedAction.NO_ACTION
            confidence = Decimal("0.9")
        
        # Determine scope description
        if location_id and category:
            scope = f"location:{self._locations.get(location_id, 'unknown')},category:{category}"
        elif location_id:
            scope = f"location:{self._locations.get(location_id, 'unknown')}"
        elif category:
            scope = f"category:{category}"
        else:
            scope = "all"
        
        alert = GhostInventoryAlert(
            alert_type=GhostAlertType.GHOST_INVENTORY,
            items_flagged=len(flagged_items),
            days_unscanned_threshold=self._config.unscanned_threshold_days,
            total_system_value_micros=total_system_value,
            total_variance_value_micros=total_variance_value,
            total_exposure_value_micros=total_exposure_value,
            critical_items=critical,
            high_risk_items=high,
            medium_risk_items=medium,
            low_risk_items=low,
            flagged_items=flagged_items,
            recommended_action=action,
            confidence=confidence,
            analysis_scope=scope,
            locations_analyzed=len(locations_seen),
            products_analyzed=len(products_seen),
        )
        
        self._alerts.append(alert)
        return alert
    
    # =========================================================================
    # SUMMARY & QUERY
    # =========================================================================
    
    def get_summary(self) -> GhostDetectorSummary:
        """Get summary of all ghost detection analysis."""
        # Run detection if no alerts yet
        if not self._alerts:
            self.detect_ghost_inventory()
        
        # Get latest alert
        latest = self._alerts[-1] if self._alerts else None
        
        # Build category breakdown
        flagged_by_cat: dict[str, int] = defaultdict(int)
        exposure_by_cat: dict[str, int] = defaultdict(int)
        flagged_by_loc: dict[str, int] = defaultdict(int)
        
        if latest:
            for item in latest.flagged_items:
                # Get category from inventory
                key = (item.product_id, item.location_id)
                record = self._inventory.get(key)
                if record:
                    flagged_by_cat[record.category] += 1
                    exposure_by_cat[record.category] += item.exposure_value_micros
                
                flagged_by_loc[item.location_name] += 1
        
        # Common patterns
        patterns = []
        if latest and latest.items_flagged > 0:
            avg_days = sum(i.days_since_scan for i in latest.flagged_items) / len(latest.flagged_items)
            patterns.append(f"average_days_unscanned:{int(avg_days)}")
            
            if latest.critical_items > 0:
                patterns.append("critical_items_require_immediate_audit")
        
        return GhostDetectorSummary(
            config=self._config,
            locations_analyzed=latest.locations_analyzed if latest else 0,
            products_analyzed=latest.products_analyzed if latest else 0,
            total_flagged=latest.items_flagged if latest else 0,
            total_exposure_micros=latest.total_exposure_value_micros if latest else 0,
            total_variance_micros=latest.total_variance_value_micros if latest else 0,
            flagged_by_category=dict(flagged_by_cat),
            exposure_by_category=dict(exposure_by_cat),
            flagged_by_location=dict(flagged_by_loc),
            top_exposures=latest.flagged_items[:10] if latest else [],
            common_patterns=patterns,
        )
    
    def get_alerts(self, limit: int = 100) -> list[GhostInventoryAlert]:
        """Get generated alerts."""
        return self._alerts[-limit:]
    
    def get_item_status(
        self,
        product_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> Optional[dict]:
        """Get ghost status for a specific item."""
        key = (product_id, location_id)
        record = self._inventory.get(key)
        
        if not record:
            return None
        
        days_since, last_scanned_at, last_qty = self._calculate_days_since_scan(
            product_id, location_id
        )
        
        variance = self._calculate_variance(record.system_qty, last_qty)
        is_ghost = days_since >= self._config.unscanned_threshold_days
        
        return {
            "product_id": str(product_id),
            "location_id": str(location_id),
            "product_name": record.product_name,
            "system_qty": record.system_qty,
            "last_scanned_qty": last_qty,
            "variance": variance,
            "days_since_scan": days_since,
            "last_scanned_at": last_scanned_at.isoformat() if last_scanned_at else None,
            "is_ghost": is_ghost,
            "threshold_days": self._config.unscanned_threshold_days,
        }
    
    def clear_data(self) -> None:
        """Clear all data (for testing)."""
        self._inventory.clear()
        self._scan_history.clear()
        self._scans.clear()
        self._locations.clear()
        self._alerts.clear()


# Singleton instance
ghost_engine = GhostInventoryEngine()
