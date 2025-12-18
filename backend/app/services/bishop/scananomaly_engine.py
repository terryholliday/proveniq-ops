"""
PROVENIQ Ops - Bishop Scan Anomaly Detector
Detect unusual scan behavior patterns for passive loss prevention.

DAG Node: N15

LOGIC:
1. Detect temporal, volume, and repetition anomalies
2. Score severity

GUARDRAILS:
- This is a SIGNAL, not an accusation
- Used for operational improvement, not discipline
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.models.scananomaly import (
    AnomalyReason,
    HistoricalNorm,
    ScanAnomalyAlert,
    ScanAnomalyAnalysis,
    ScanAnomalyConfig,
    ScanAnomalyType,
    ScanEvent,
    Severity,
    UserAnomalySummary,
    UserProfile,
)


class ScanAnomalyEngine:
    """
    Bishop Scan Anomaly Detector
    
    Detects unusual scan patterns for passive loss prevention.
    
    Maps to DAG node: N15
    
    IMPORTANT: This generates SIGNALS for operational review.
    It does NOT make accusations or determinations of wrongdoing.
    """
    
    def __init__(self) -> None:
        self._config = ScanAnomalyConfig()
        
        # Data stores
        self._scans: list[ScanEvent] = []
        self._users: dict[uuid.UUID, UserProfile] = {}
        self._norms: dict[uuid.UUID, HistoricalNorm] = {}  # location_id -> norm
        
        # Location names
        self._locations: dict[uuid.UUID, str] = {}
        
        # Generated alerts
        self._alerts: list[ScanAnomalyAlert] = []
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure(self, config: ScanAnomalyConfig) -> None:
        """Update detector configuration."""
        self._config = config
    
    def get_config(self) -> ScanAnomalyConfig:
        """Get current configuration."""
        return self._config
    
    # =========================================================================
    # DATA REGISTRATION
    # =========================================================================
    
    def register_user(self, profile: UserProfile) -> None:
        """Register a user profile."""
        self._users[profile.user_id] = profile
    
    def register_norm(self, norm: HistoricalNorm) -> None:
        """Register historical norms for a location."""
        self._norms[norm.location_id] = norm
    
    def register_location(self, location_id: uuid.UUID, name: str) -> None:
        """Register a location name."""
        self._locations[location_id] = name
    
    def record_scan(self, scan: ScanEvent) -> Optional[ScanAnomalyAlert]:
        """
        Record a scan event and check for anomalies.
        
        Returns alert if anomaly detected, None otherwise.
        """
        self._scans.append(scan)
        
        # Update user stats
        user = self._users.get(scan.user_id)
        if user:
            user.total_scans += 1
        
        # Check for immediate anomalies
        alerts = []
        
        # Temporal check
        temporal_alert = self._check_temporal_anomaly(scan)
        if temporal_alert:
            alerts.append(temporal_alert)
        
        # Repetition check
        repetition_alert = self._check_repetition_anomaly(scan)
        if repetition_alert:
            alerts.append(repetition_alert)
        
        # Return highest severity alert if any
        if alerts:
            alerts.sort(key=lambda a: a.anomaly_score, reverse=True)
            self._alerts.append(alerts[0])
            return alerts[0]
        
        return None
    
    # =========================================================================
    # TEMPORAL ANOMALY DETECTION
    # =========================================================================
    
    def _check_temporal_anomaly(self, scan: ScanEvent) -> Optional[ScanAnomalyAlert]:
        """Check for temporal anomalies (unusual hours, rapid succession)."""
        hour = scan.scanned_at.hour
        
        # Check unusual hour
        if (hour >= self._config.unusual_hour_start or 
            hour < self._config.unusual_hour_end):
            
            user = self._users.get(scan.user_id)
            username = user.username if user and not self._config.anonymize_usernames else None
            
            return ScanAnomalyAlert(
                alert_type=ScanAnomalyType.TEMPORAL_ANOMALY,
                user_id=scan.user_id,
                username=username,
                location_id=scan.location_id,
                location_name=self._locations.get(scan.location_id),
                severity=Severity.LOW,
                anomaly_score=Decimal("0.4"),
                reason=AnomalyReason.UNUSUAL_HOUR,
                reason_detail=f"Scan at {hour}:00 (outside normal hours {self._config.unusual_hour_end}:00-{self._config.unusual_hour_start}:00)",
                baseline_value=f"{self._config.unusual_hour_end}:00-{self._config.unusual_hour_start}:00",
                observed_value=f"{hour}:00",
                affected_scans=[scan.scan_id],
            )
        
        # Check rapid succession
        recent_scans = self._get_user_recent_scans(
            scan.user_id,
            scan.scanned_at,
            seconds=60
        )
        
        if len(recent_scans) >= 2:
            # Calculate intervals
            intervals = []
            for i in range(1, len(recent_scans)):
                delta = (recent_scans[i].scanned_at - recent_scans[i-1].scanned_at).total_seconds()
                intervals.append(delta)
            
            if intervals:
                min_interval = min(intervals)
                if min_interval < self._config.min_scan_interval_seconds:
                    severity, score = self._calculate_severity(
                        Decimal(str(self._config.min_scan_interval_seconds / max(min_interval, 0.1)))
                    )
                    
                    user = self._users.get(scan.user_id)
                    username = user.username if user and not self._config.anonymize_usernames else None
                    
                    return ScanAnomalyAlert(
                        alert_type=ScanAnomalyType.TEMPORAL_ANOMALY,
                        user_id=scan.user_id,
                        username=username,
                        location_id=scan.location_id,
                        location_name=self._locations.get(scan.location_id),
                        severity=severity,
                        anomaly_score=score,
                        reason=AnomalyReason.RAPID_SUCCESSION,
                        reason_detail=f"{len(recent_scans)} scans in 60s, min interval {min_interval:.1f}s (threshold: {self._config.min_scan_interval_seconds}s)",
                        scan_count=len(recent_scans),
                        time_window_minutes=1,
                        baseline_value=f">{self._config.min_scan_interval_seconds}s between scans",
                        observed_value=f"{min_interval:.1f}s",
                        deviation_factor=Decimal(str(round(self._config.min_scan_interval_seconds / max(min_interval, 0.1), 2))),
                        affected_scans=[s.scan_id for s in recent_scans],
                    )
        
        return None
    
    # =========================================================================
    # VOLUME ANOMALY DETECTION
    # =========================================================================
    
    def _check_volume_anomaly(
        self,
        user_id: uuid.UUID,
        window_hours: int = 1,
    ) -> Optional[ScanAnomalyAlert]:
        """Check for volume anomalies (too many or too few scans)."""
        user = self._users.get(user_id)
        if not user:
            return None
        
        norm = self._norms.get(user.location_id)
        if not norm:
            return None
        
        # Get scans in window
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=window_hours)
        user_scans = [
            s for s in self._scans
            if s.user_id == user_id and s.scanned_at >= cutoff
        ]
        
        scans_per_hour = len(user_scans) / window_hours if window_hours > 0 else 0
        
        # Check high volume
        high_threshold = float(norm.avg_scans_per_hour + norm.std_scans_per_hour * float(self._config.high_volume_stddev))
        if scans_per_hour > high_threshold:
            deviation = (scans_per_hour - float(norm.avg_scans_per_hour)) / float(norm.std_scans_per_hour)
            severity, score = self._calculate_severity(Decimal(str(deviation / 3)))
            
            username = user.username if not self._config.anonymize_usernames else None
            
            return ScanAnomalyAlert(
                alert_type=ScanAnomalyType.VOLUME_ANOMALY,
                user_id=user_id,
                username=username,
                location_id=user.location_id,
                location_name=self._locations.get(user.location_id),
                severity=severity,
                anomaly_score=score,
                reason=AnomalyReason.HIGH_VOLUME,
                reason_detail=f"{scans_per_hour:.1f} scans/hour (normal: {norm.avg_scans_per_hour:.1f} ± {norm.std_scans_per_hour:.1f})",
                scan_count=len(user_scans),
                time_window_minutes=window_hours * 60,
                baseline_value=f"{norm.avg_scans_per_hour:.1f} scans/hour",
                observed_value=f"{scans_per_hour:.1f} scans/hour",
                deviation_factor=Decimal(str(round(deviation, 2))),
                affected_scans=[s.scan_id for s in user_scans[-20:]],  # Last 20
            )
        
        return None
    
    # =========================================================================
    # REPETITION ANOMALY DETECTION
    # =========================================================================
    
    def _check_repetition_anomaly(self, scan: ScanEvent) -> Optional[ScanAnomalyAlert]:
        """Check for repetition anomalies (duplicates, same item loops)."""
        # Check for duplicate in window
        recent_scans = self._get_user_recent_scans(
            scan.user_id,
            scan.scanned_at,
            seconds=self._config.duplicate_window_seconds
        )
        
        # Count same product scans
        same_product = [
            s for s in recent_scans
            if s.product_id == scan.product_id and s.scan_id != scan.scan_id
        ]
        
        if len(same_product) >= self._config.max_same_item_scans:
            severity, score = self._calculate_severity(
                Decimal(str(len(same_product) / self._config.max_same_item_scans))
            )
            
            user = self._users.get(scan.user_id)
            username = user.username if user and not self._config.anonymize_usernames else None
            
            return ScanAnomalyAlert(
                alert_type=ScanAnomalyType.REPETITION_ANOMALY,
                user_id=scan.user_id,
                username=username,
                location_id=scan.location_id,
                location_name=self._locations.get(scan.location_id),
                severity=severity,
                anomaly_score=score,
                reason=AnomalyReason.SAME_ITEM_LOOP,
                reason_detail=f"Same item ({scan.product_name}) scanned {len(same_product) + 1}x in {self._config.duplicate_window_seconds}s",
                scan_count=len(same_product) + 1,
                time_window_minutes=self._config.duplicate_window_seconds // 60 or 1,
                baseline_value=f"<{self._config.max_same_item_scans} same-item scans",
                observed_value=f"{len(same_product) + 1} same-item scans",
                affected_scans=[s.scan_id for s in same_product] + [scan.scan_id],
            )
        
        # Check for exact duplicate (same product, same quantity, very close time)
        for s in same_product:
            delta = abs((scan.scanned_at - s.scanned_at).total_seconds())
            if delta < 5 and s.quantity == scan.quantity:
                user = self._users.get(scan.user_id)
                username = user.username if user and not self._config.anonymize_usernames else None
                
                return ScanAnomalyAlert(
                    alert_type=ScanAnomalyType.REPETITION_ANOMALY,
                    user_id=scan.user_id,
                    username=username,
                    location_id=scan.location_id,
                    location_name=self._locations.get(scan.location_id),
                    severity=Severity.MEDIUM,
                    anomaly_score=Decimal("0.6"),
                    reason=AnomalyReason.DUPLICATE_SCAN,
                    reason_detail=f"Duplicate scan detected: {scan.product_name} x{scan.quantity} within {delta:.1f}s",
                    affected_scans=[s.scan_id, scan.scan_id],
                )
        
        return None
    
    # =========================================================================
    # PATTERN ANOMALY DETECTION
    # =========================================================================
    
    def _check_pattern_anomaly(
        self,
        user_id: uuid.UUID,
        window_hours: int = 8,
    ) -> Optional[ScanAnomalyAlert]:
        """Check for pattern anomalies (selective scanning, category skips)."""
        user = self._users.get(user_id)
        if not user:
            return None
        
        # Get scans in window
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=window_hours)
        user_scans = [
            s for s in self._scans
            if s.user_id == user_id and s.scanned_at >= cutoff
        ]
        
        if len(user_scans) < 10:
            return None  # Not enough data
        
        # Check for high-value item avoidance
        norm = self._norms.get(user.location_id)
        if norm and norm.high_value_threshold_micros:
            high_value_scans = [
                s for s in user_scans
                if s.unit_value_micros and s.unit_value_micros >= norm.high_value_threshold_micros
            ]
            
            # If very few high-value items scanned relative to normal
            high_value_ratio = len(high_value_scans) / len(user_scans) if user_scans else 0
            
            # This would need baseline comparison - simplified for now
            if high_value_ratio < 0.05 and len(user_scans) > 50:
                username = user.username if not self._config.anonymize_usernames else None
                
                return ScanAnomalyAlert(
                    alert_type=ScanAnomalyType.PATTERN_ANOMALY,
                    user_id=user_id,
                    username=username,
                    location_id=user.location_id,
                    location_name=self._locations.get(user.location_id),
                    severity=Severity.LOW,
                    anomaly_score=Decimal("0.35"),
                    reason=AnomalyReason.SELECTIVE_SCANNING,
                    reason_detail=f"Low high-value item scan rate: {high_value_ratio*100:.1f}% of {len(user_scans)} scans",
                    scan_count=len(user_scans),
                    time_window_minutes=window_hours * 60,
                )
        
        return None
    
    # =========================================================================
    # FULL ANALYSIS
    # =========================================================================
    
    def analyze(
        self,
        window_hours: int = 24,
        location_id: Optional[uuid.UUID] = None,
    ) -> ScanAnomalyAnalysis:
        """
        Perform full anomaly analysis.
        
        Checks all anomaly types across users in window.
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=window_hours)
        
        # Filter scans
        scans = [s for s in self._scans if s.scanned_at >= cutoff]
        if location_id:
            scans = [s for s in scans if s.location_id == location_id]
        
        # Get unique users
        user_ids = set(s.user_id for s in scans)
        
        # Clear previous alerts for fresh analysis
        analysis_alerts: list[ScanAnomalyAlert] = []
        
        # Check each user
        for user_id in user_ids:
            # Volume check
            volume_alert = self._check_volume_anomaly(user_id, window_hours)
            if volume_alert:
                analysis_alerts.append(volume_alert)
            
            # Pattern check
            pattern_alert = self._check_pattern_anomaly(user_id, window_hours)
            if pattern_alert:
                analysis_alerts.append(pattern_alert)
        
        # Add existing real-time alerts from window
        existing = [
            a for a in self._alerts
            if a.detected_at >= cutoff
        ]
        analysis_alerts.extend(existing)
        
        # Deduplicate by user+reason
        seen = set()
        unique_alerts = []
        for alert in analysis_alerts:
            key = (alert.user_id, alert.reason)
            if key not in seen:
                seen.add(key)
                unique_alerts.append(alert)
        
        # Count by severity
        high = len([a for a in unique_alerts if a.severity == Severity.HIGH])
        medium = len([a for a in unique_alerts if a.severity == Severity.MEDIUM])
        low = len([a for a in unique_alerts if a.severity == Severity.LOW])
        
        # Count by type
        by_type: dict[str, int] = defaultdict(int)
        for alert in unique_alerts:
            by_type[alert.alert_type.value] += 1
        
        # Count by location
        by_location: dict[str, int] = defaultdict(int)
        for alert in unique_alerts:
            loc_name = alert.location_name or str(alert.location_id)
            by_location[loc_name] += 1
        
        return ScanAnomalyAnalysis(
            time_window_hours=window_hours,
            scans_analyzed=len(scans),
            users_analyzed=len(user_ids),
            anomalies_detected=len(unique_alerts),
            high_severity_count=high,
            medium_severity_count=medium,
            low_severity_count=low,
            by_type=dict(by_type),
            by_location=dict(by_location),
            alerts=sorted(unique_alerts, key=lambda a: a.anomaly_score, reverse=True),
        )
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _get_user_recent_scans(
        self,
        user_id: uuid.UUID,
        reference_time: datetime,
        seconds: int,
    ) -> list[ScanEvent]:
        """Get user's scans within seconds of reference time."""
        cutoff = reference_time - timedelta(seconds=seconds)
        return [
            s for s in self._scans
            if s.user_id == user_id and cutoff <= s.scanned_at <= reference_time
        ]
    
    def _calculate_severity(self, factor: Decimal) -> tuple[Severity, Decimal]:
        """Calculate severity and score from deviation factor."""
        # Normalize to 0-1 score
        score = min(Decimal("1"), max(Decimal("0"), factor / 3))
        
        if score >= self._config.high_threshold:
            return Severity.HIGH, score
        elif score >= self._config.medium_threshold:
            return Severity.MEDIUM, score
        else:
            return Severity.LOW, score
    
    # =========================================================================
    # QUERY
    # =========================================================================
    
    def get_alerts(
        self,
        limit: int = 100,
        severity: Optional[Severity] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> list[ScanAnomalyAlert]:
        """Get alerts with optional filters."""
        alerts = self._alerts
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if user_id:
            alerts = [a for a in alerts if a.user_id == user_id]
        
        return alerts[-limit:]
    
    def get_user_summary(self, user_id: uuid.UUID) -> Optional[UserAnomalySummary]:
        """Get anomaly summary for a user."""
        user = self._users.get(user_id)
        if not user:
            return None
        
        user_alerts = [a for a in self._alerts if a.user_id == user_id]
        
        now = datetime.utcnow()
        alerts_7d = len([a for a in user_alerts if a.detected_at >= now - timedelta(days=7)])
        alerts_30d = len([a for a in user_alerts if a.detected_at >= now - timedelta(days=30)])
        
        # Determine trend
        if alerts_7d > alerts_30d / 4:
            trend = "increasing"
        elif alerts_7d < alerts_30d / 8:
            trend = "decreasing"
        else:
            trend = "stable"
        
        # Possible causes (operational, not accusations)
        causes = []
        types = [a.reason.value for a in user_alerts[-10:]]
        if "rapid_succession" in types:
            causes.append("May indicate scanner equipment issues or training needs")
        if "unusual_hour" in types:
            causes.append("Schedule may not align with typical shift patterns")
        if "high_volume" in types:
            causes.append("May indicate process bottleneck or workload imbalance")
        
        by_type: dict[str, int] = defaultdict(int)
        for alert in user_alerts:
            by_type[alert.alert_type.value] += 1
        
        return UserAnomalySummary(
            user_id=user_id,
            username=user.username,
            total_alerts=len(user_alerts),
            low_severity=len([a for a in user_alerts if a.severity == Severity.LOW]),
            medium_severity=len([a for a in user_alerts if a.severity == Severity.MEDIUM]),
            high_severity=len([a for a in user_alerts if a.severity == Severity.HIGH]),
            alerts_by_type=dict(by_type),
            alerts_last_7d=alerts_7d,
            alerts_last_30d=alerts_30d,
            trend=trend,
            possible_causes=causes,
        )
    
    def clear_data(self) -> None:
        """Clear all data (for testing)."""
        self._scans.clear()
        self._users.clear()
        self._norms.clear()
        self._locations.clear()
        self._alerts.clear()


# Singleton instance
scananomaly_engine = ScanAnomalyEngine()
