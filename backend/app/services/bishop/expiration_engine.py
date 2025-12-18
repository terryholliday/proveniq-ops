"""
PROVENIQ Ops - Bishop Expiration Cascade Planner
Surface upcoming expirations and convert waste into intentional decisions.

DAG Nodes: N13, N33

LOGIC:
1. Bucket items into 24h / 48h / 72h windows
2. Estimate loss value
3. Recommend disposition actions

GUARDRAILS:
- Donation suggestions must respect compliance rules
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.core.types import Money
from app.models.expiration import (
    DispositionAction,
    DispositionPlan,
    DonationEligibility,
    DonationRule,
    ExpirationActionPlan,
    ExpirationAlertType,
    ExpirationCascadeAlert,
    ExpirationConfig,
    ExpiringItem,
    ItemCategory,
    LotRecord,
    WindowSummary,
)


class ExpirationCascadeEngine:
    """
    Bishop Expiration Cascade Planner
    
    Converts waste into intentional decisions by surfacing
    upcoming expirations and recommending disposition actions.
    
    Maps to DAG nodes: N13 (detection), N33 (action plan)
    """
    
    def __init__(self) -> None:
        self._config = ExpirationConfig()
        
        # Data stores
        self._lots: dict[uuid.UUID, LotRecord] = {}
        self._donation_rules: dict[ItemCategory, DonationRule] = {}
        
        # Location names
        self._locations: dict[uuid.UUID, str] = {}
        
        # Generated alerts
        self._alerts: list[ExpirationCascadeAlert] = []
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure(self, config: ExpirationConfig) -> None:
        """Update planner configuration."""
        self._config = config
    
    def get_config(self) -> ExpirationConfig:
        """Get current configuration."""
        return self._config
    
    # =========================================================================
    # DATA REGISTRATION
    # =========================================================================
    
    def register_lot(self, lot: LotRecord) -> None:
        """Register a lot with expiration tracking."""
        self._lots[lot.lot_id] = lot
        self._locations[lot.location_id] = lot.location_name
    
    def register_donation_rule(self, rule: DonationRule) -> None:
        """Register a donation compliance rule."""
        self._donation_rules[rule.category] = rule
    
    def update_lot_quantity(self, lot_id: uuid.UUID, new_qty: int) -> bool:
        """Update lot quantity (after partial use/sale)."""
        if lot_id in self._lots:
            self._lots[lot_id].quantity = new_qty
            return True
        return False
    
    # =========================================================================
    # EXPIRATION DETECTION (N13)
    # =========================================================================
    
    def _calculate_hours_until_expiry(self, expiration_date: datetime) -> int:
        """Calculate hours until expiration."""
        delta = expiration_date - datetime.utcnow()
        return max(0, int(delta.total_seconds() / 3600))
    
    def _get_window_bucket(self, hours: int) -> int:
        """Determine which window bucket an item falls into."""
        for window in sorted(self._config.window_hours):
            if hours <= window:
                return window
        return self._config.window_hours[-1]  # Beyond largest window
    
    def _check_donation_eligibility(
        self,
        lot: LotRecord,
        hours_until_expiry: int,
    ) -> tuple[DonationEligibility, Optional[str]]:
        """
        Check if item is eligible for donation.
        
        GUARDRAIL: Must respect compliance rules.
        """
        # Check if lot itself is marked ineligible
        if not lot.donation_eligible:
            return DonationEligibility.NOT_ELIGIBLE, "Item marked not eligible for donation"
        
        # Check category rules
        rule = self._donation_rules.get(lot.category)
        if rule:
            # Check minimum days requirement
            min_hours = rule.min_days_before_expiry * 24
            if hours_until_expiry < min_hours:
                return (
                    DonationEligibility.COMPLIANCE_BLOCK,
                    f"Requires {rule.min_days_before_expiry} days before expiry, has {hours_until_expiry // 24} days"
                )
            
            # Check prohibited items
            if lot.canonical_sku in rule.prohibited_items:
                return DonationEligibility.COMPLIANCE_BLOCK, "Item in prohibited list"
        
        # Check lot-specific restrictions
        if lot.donation_restrictions:
            return (
                DonationEligibility.REQUIRES_REVIEW,
                f"Restrictions: {', '.join(lot.donation_restrictions)}"
            )
        
        return DonationEligibility.ELIGIBLE, None
    
    def _determine_action(
        self,
        lot: LotRecord,
        hours_until_expiry: int,
        donation_eligible: DonationEligibility,
    ) -> tuple[DispositionAction, str]:
        """
        Determine recommended disposition action.
        
        Priority:
        1. If very close to expiry → Dispose (safety)
        2. If donation eligible and within window → Donate (recovery)
        3. If within discount window → Discount (recovery)
        4. Otherwise → Use first (FIFO)
        """
        # Critical: must dispose
        if hours_until_expiry <= self._config.dispose_window_hours:
            if hours_until_expiry <= 0:
                return DispositionAction.DISPOSE, "Expired - must dispose"
            return DispositionAction.DISPOSE, f"Within {self._config.dispose_window_hours}h disposal window"
        
        # Can donate?
        if hours_until_expiry <= self._config.donate_window_hours:
            if donation_eligible == DonationEligibility.ELIGIBLE:
                return DispositionAction.DONATE, "Eligible for donation, within donation window"
            elif donation_eligible == DonationEligibility.REQUIRES_REVIEW:
                return DispositionAction.HOLD, "Donation requires compliance review"
            # Fall through to discount if not donation eligible
        
        # Discount window
        if hours_until_expiry <= self._config.discount_window_hours:
            return DispositionAction.DISCOUNT, f"Within {self._config.discount_window_hours}h - recommend discount"
        
        # Beyond all windows - just use first
        return DispositionAction.USE_FIRST, "FIFO priority - use before newer stock"
    
    def analyze_expirations(
        self,
        location_id: Optional[uuid.UUID] = None,
        category: Optional[ItemCategory] = None,
    ) -> ExpirationCascadeAlert:
        """
        Analyze all lots for upcoming expirations.
        
        Args:
            location_id: Optional filter by location
            category: Optional filter by category
        
        Returns:
            ExpirationCascadeAlert with all expiring items
        """
        now = datetime.utcnow()
        max_window = max(self._config.window_hours)
        cutoff = now + timedelta(hours=max_window)
        
        expiring_items: list[ExpiringItem] = []
        
        # Counters
        items_by_action: dict[str, int] = defaultdict(int)
        value_by_action: dict[str, int] = defaultdict(int)
        
        window_items: dict[int, list[ExpiringItem]] = {w: [] for w in self._config.window_hours}
        
        total_loss = 0
        recoverable = 0
        donation_eligible_count = 0
        compliance_blocked_count = 0
        
        for lot in self._lots.values():
            # Apply filters
            if location_id and lot.location_id != location_id:
                continue
            if category and lot.category != category:
                continue
            
            # Check if expiring within window
            if lot.expiration_date > cutoff:
                continue  # Not expiring soon
            
            if lot.quantity <= 0:
                continue  # No quantity
            
            hours = self._calculate_hours_until_expiry(lot.expiration_date)
            bucket = self._get_window_bucket(hours)
            
            # Check donation eligibility
            donation_status, donation_note = self._check_donation_eligibility(lot, hours)
            
            if donation_status == DonationEligibility.ELIGIBLE:
                donation_eligible_count += 1
            elif donation_status == DonationEligibility.COMPLIANCE_BLOCK:
                compliance_blocked_count += 1
            
            # Determine action
            action, reason = self._determine_action(lot, hours, donation_status)
            
            # Calculate value
            total_value = lot.quantity * lot.unit_cost_micros
            
            # Track loss/recovery
            if action == DispositionAction.DISPOSE:
                total_loss += total_value
            elif action == DispositionAction.DONATE:
                total_loss += total_value  # Tax benefit handled elsewhere
                recoverable += 0  # No direct recovery, but social value
            elif action == DispositionAction.DISCOUNT:
                discount = self._config.default_discount_percent / 100
                loss = int(total_value * float(discount))
                total_loss += loss
                recoverable += total_value - loss
            
            # Build compliance flags
            compliance_flags = []
            if lot.disposal_requirements:
                compliance_flags.extend(lot.disposal_requirements)
            if donation_status == DonationEligibility.COMPLIANCE_BLOCK:
                compliance_flags.append("donation_blocked")
            
            item = ExpiringItem(
                lot_id=lot.lot_id,
                product_id=lot.product_id,
                product_name=lot.product_name,
                canonical_sku=lot.canonical_sku,
                lot_number=lot.lot_number,
                quantity=lot.quantity,
                unit_cost_micros=lot.unit_cost_micros,
                total_value_micros=total_value,
                expiration_date=lot.expiration_date,
                hours_until_expiry=hours,
                window_bucket=bucket,
                location_id=lot.location_id,
                location_name=lot.location_name,
                category=lot.category,
                recommended_action=action,
                action_reason=reason,
                donation_eligibility=donation_status,
                donation_notes=donation_note,
                compliance_flags=compliance_flags,
            )
            
            expiring_items.append(item)
            items_by_action[action.value] += 1
            value_by_action[action.value] += total_value
            
            # Add to window bucket
            if bucket in window_items:
                window_items[bucket].append(item)
        
        # Sort by urgency (hours until expiry)
        expiring_items.sort(key=lambda x: x.hours_until_expiry)
        
        # Build window summaries
        def build_window_summary(window: int, items: list[ExpiringItem]) -> WindowSummary:
            discount_items = [i for i in items if i.recommended_action == DispositionAction.DISCOUNT]
            donate_items = [i for i in items if i.recommended_action == DispositionAction.DONATE]
            dispose_items = [i for i in items if i.recommended_action == DispositionAction.DISPOSE]
            transfer_items = [i for i in items if i.recommended_action == DispositionAction.TRANSFER]
            
            return WindowSummary(
                window_hours=window,
                item_count=len(items),
                total_quantity=sum(i.quantity for i in items),
                total_value_micros=sum(i.total_value_micros for i in items),
                discount_count=len(discount_items),
                donate_count=len(donate_items),
                dispose_count=len(dispose_items),
                transfer_count=len(transfer_items),
                discount_value_micros=sum(i.total_value_micros for i in discount_items),
                donate_value_micros=sum(i.total_value_micros for i in donate_items),
                dispose_value_micros=sum(i.total_value_micros for i in dispose_items),
            )
        
        # Urgent actions
        urgent = []
        dispose_count = items_by_action.get("dispose", 0)
        if dispose_count > 0:
            urgent.append(f"URGENT: {dispose_count} items require immediate disposal")
        
        donate_count = items_by_action.get("donate", 0)
        if donate_count > 0:
            urgent.append(f"ACTION: {donate_count} items eligible for donation - coordinate pickup")
        
        alert = ExpirationCascadeAlert(
            alert_type=ExpirationAlertType.EXPIRATION_CASCADE,
            window_hours=self._config.window_hours,
            items_by_action=dict(items_by_action),
            value_by_action=dict(value_by_action),
            total_items=len(expiring_items),
            total_quantity=sum(i.quantity for i in expiring_items),
            estimated_loss_micros=total_loss,
            recoverable_value_micros=recoverable,
            window_24h=build_window_summary(24, window_items.get(24, [])),
            window_48h=build_window_summary(48, window_items.get(48, [])),
            window_72h=build_window_summary(72, window_items.get(72, [])),
            expiring_items=expiring_items,
            donation_eligible_count=donation_eligible_count,
            compliance_blocked_count=compliance_blocked_count,
            urgent_actions=urgent,
        )
        
        self._alerts.append(alert)
        return alert
    
    # =========================================================================
    # ACTION PLAN GENERATION (N33)
    # =========================================================================
    
    def generate_action_plan(
        self,
        alert: Optional[ExpirationCascadeAlert] = None,
    ) -> ExpirationActionPlan:
        """
        Generate detailed action plan from expiration alert.
        
        Creates disposition plans for each action type.
        """
        if not alert:
            alert = self.analyze_expirations()
        
        discount_plans: list[DispositionPlan] = []
        donate_plans: list[DispositionPlan] = []
        dispose_plans: list[DispositionPlan] = []
        
        total_original = 0
        total_recovery = 0
        total_loss = 0
        
        approval_notes = []
        
        for item in alert.expiring_items:
            original_value = item.total_value_micros
            total_original += original_value
            
            if item.recommended_action == DispositionAction.DISCOUNT:
                discount_pct = self._config.default_discount_percent
                recovery = int(original_value * (1 - float(discount_pct) / 100))
                loss = original_value - recovery
                
                plan = DispositionPlan(
                    lot_id=item.lot_id,
                    product_name=item.product_name,
                    action=DispositionAction.DISCOUNT,
                    quantity=item.quantity,
                    original_value_micros=original_value,
                    recovery_value_micros=recovery,
                    loss_value_micros=loss,
                    discount_percent=discount_pct,
                    discount_price_micros=int(item.unit_cost_micros * (1 - float(discount_pct) / 100)),
                    action_deadline=item.expiration_date,
                    compliance_approved=True,
                )
                discount_plans.append(plan)
                total_recovery += recovery
                total_loss += loss
                
            elif item.recommended_action == DispositionAction.DONATE:
                plan = DispositionPlan(
                    lot_id=item.lot_id,
                    product_name=item.product_name,
                    action=DispositionAction.DONATE,
                    quantity=item.quantity,
                    original_value_micros=original_value,
                    recovery_value_micros=0,  # No direct recovery
                    loss_value_micros=original_value,
                    donation_partner="Local Food Bank",  # Would be configurable
                    donation_documentation=["Donation receipt", "Temperature log"],
                    action_deadline=item.expiration_date - timedelta(hours=self._config.donation_lead_time_hours),
                    compliance_approved=item.donation_eligibility == DonationEligibility.ELIGIBLE,
                    compliance_notes=item.donation_notes,
                )
                donate_plans.append(plan)
                total_loss += original_value
                
                if item.donation_eligibility != DonationEligibility.ELIGIBLE:
                    approval_notes.append(f"{item.product_name}: Donation requires review")
                
            elif item.recommended_action == DispositionAction.DISPOSE:
                plan = DispositionPlan(
                    lot_id=item.lot_id,
                    product_name=item.product_name,
                    action=DispositionAction.DISPOSE,
                    quantity=item.quantity,
                    original_value_micros=original_value,
                    recovery_value_micros=0,
                    loss_value_micros=original_value,
                    action_deadline=item.expiration_date,
                    compliance_approved=True,
                    compliance_notes="Disposal documentation required" if item.compliance_flags else None,
                )
                dispose_plans.append(plan)
                total_loss += original_value
        
        return ExpirationActionPlan(
            total_items=len(alert.expiring_items),
            total_original_value_micros=total_original,
            total_recovery_value_micros=total_recovery,
            total_loss_value_micros=total_loss,
            discount_plans=discount_plans,
            donate_plans=donate_plans,
            dispose_plans=dispose_plans,
            requires_approval=len(donate_plans) > 0 or len(dispose_plans) > 0,
            approval_notes=approval_notes,
        )
    
    # =========================================================================
    # QUERY
    # =========================================================================
    
    def get_alerts(self, limit: int = 100) -> list[ExpirationCascadeAlert]:
        """Get historical alerts."""
        return self._alerts[-limit:]
    
    def get_lot(self, lot_id: uuid.UUID) -> Optional[LotRecord]:
        """Get a specific lot record."""
        return self._lots.get(lot_id)
    
    def get_expiring_by_window(self, window_hours: int) -> list[ExpiringItem]:
        """Get items expiring within a specific window."""
        alert = self.analyze_expirations()
        return [i for i in alert.expiring_items if i.window_bucket <= window_hours]
    
    def clear_data(self) -> None:
        """Clear all data (for testing)."""
        self._lots.clear()
        self._donation_rules.clear()
        self._locations.clear()
        self._alerts.clear()


# Singleton instance
expiration_engine = ExpirationCascadeEngine()
