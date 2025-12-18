"""
PROVENIQ Ops - Bishop Bulk Normalization Engine
N5 - The foundational node for all inventory truth

PHILOSOPHY:
Other systems ask: "How many units do you have?"
Bishop asks: "What do you observe?"
And then quietly does the math better than any human ever could.

OUTPUTS:
- normalized_quantity
- confidence
- measurement_method

Every downstream node (stockout, waste, pricing) consumes this output — not raw user input.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from app.models.units import (
    BaseUnit,
    BulkItemConfig,
    ConfidenceDecayConfig,
    ContainerCountInput,
    DirectWeightInput,
    HandlingUnit,
    HandlingUnitType,
    MeasurementMethod,
    METHOD_CONFIDENCE_CEILING,
    NormalizedQuantity,
    PartialContainer,
    RecipeDepletionInput,
    UnitCategory,
    UNIT_METADATA,
    VerificationRequest,
    VerificationTrigger,
    VolumeEstimateInput,
)


class BulkNormalizationEngine:
    """
    Bishop Bulk Normalization Engine (N5)
    
    The foundational node that converts human observations
    into normalized inventory truth with confidence scores.
    
    THREE MEASUREMENT METHODS:
    1. Container Count × Standard Weight (fastest, default)
    2. Direct Weight (highest accuracy)
    3. Recipe Depletion (projection, not reality)
    """
    
    def __init__(self) -> None:
        self._decay_config = ConfidenceDecayConfig()
        
        # Item configurations
        self._item_configs: dict[uuid.UUID, BulkItemConfig] = {}
        
        # Current inventory state
        self._inventory: dict[uuid.UUID, NormalizedQuantity] = {}
        
        # Pending verifications
        self._verification_requests: list[VerificationRequest] = []
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure_decay(self, config: ConfidenceDecayConfig) -> None:
        """Configure confidence decay parameters."""
        self._decay_config = config
    
    def register_item_config(self, config: BulkItemConfig) -> None:
        """Register configuration for a bulk item."""
        self._item_configs[config.product_id] = config
    
    def get_item_config(self, product_id: uuid.UUID) -> Optional[BulkItemConfig]:
        """Get configuration for an item."""
        return self._item_configs.get(product_id)
    
    # =========================================================================
    # UNIT CONVERSION
    # =========================================================================
    
    def convert_units(
        self,
        quantity: Decimal,
        from_unit: BaseUnit,
        to_unit: BaseUnit,
    ) -> Decimal:
        """
        Convert between compatible base units.
        Uses grams as weight base, milliliters as volume base.
        """
        from_meta = UNIT_METADATA[from_unit]
        to_meta = UNIT_METADATA[to_unit]
        
        # Must be same category
        if from_meta["category"] != to_meta["category"]:
            raise ValueError(
                f"Cannot convert between {from_meta['category']} and {to_meta['category']}"
            )
        
        # Convert to base, then to target
        base_quantity = quantity * from_meta["to_base"]
        result = base_quantity / to_meta["to_base"]
        
        return result.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    
    # =========================================================================
    # METHOD 1: CONTAINER COUNT (fastest, default)
    # =========================================================================
    
    def normalize_container_count(
        self,
        product_id: uuid.UUID,
        input_data: ContainerCountInput,
        measured_by: Optional[str] = None,
    ) -> NormalizedQuantity:
        """
        Method 1: Container Count × Standard Weight
        
        User input: "3 unopened bags + 1 open bag (about half)"
        Bishop calculation:
            3 × 50 lb = 150 lb
            + (0.5 × 50 lb) = 25 lb
            Total = 175 lb
            Confidence = 0.92
        """
        config = self._item_configs.get(product_id)
        if not config:
            raise ValueError(f"No configuration for product {product_id}")
        
        handling = config.primary_handling_unit
        standard_qty = input_data.override_standard_weight or handling.standard_quantity
        
        # Calculate full containers
        full_qty = Decimal(input_data.full_containers) * standard_qty
        
        # Calculate partial containers
        partial_qty = Decimal("0")
        for partial in input_data.partial_containers:
            if partial.was_weighed and partial.actual_weight:
                # User weighed the partial - higher confidence for this portion
                partial_qty += partial.actual_weight
            else:
                # Estimated from slider
                partial_qty += (partial.fullness_pct / 100) * standard_qty
        
        total_qty = full_qty + partial_qty
        
        # Calculate confidence
        base_confidence = METHOD_CONFIDENCE_CEILING[MeasurementMethod.CONTAINER_COUNT]
        
        # Adjust for partials (estimated partials reduce confidence)
        estimated_partials = len([p for p in input_data.partial_containers if not p.was_weighed])
        if estimated_partials > 0:
            partial_penalty = Decimal("0.03") * estimated_partials
            base_confidence = max(Decimal("0.70"), base_confidence - partial_penalty)
        
        # Store original input for audit
        original = f"{input_data.full_containers} full + {len(input_data.partial_containers)} partial {handling.display_name}"
        
        result = NormalizedQuantity(
            quantity_base_units=total_qty,
            base_unit=config.base_unit,
            confidence=base_confidence,
            measurement_method=MeasurementMethod.CONTAINER_COUNT,
            original_input=original,
            measured_by=measured_by,
        )
        
        self._inventory[product_id] = result
        return result
    
    # =========================================================================
    # METHOD 2: DIRECT WEIGHT (highest accuracy)
    # =========================================================================
    
    def normalize_direct_weight(
        self,
        product_id: uuid.UUID,
        input_data: DirectWeightInput,
        measured_by: Optional[str] = None,
    ) -> NormalizedQuantity:
        """
        Method 2: Weigh What's There
        
        User input: "Weighed bin: 18.4 lb"
        Bishop calculation:
            18.4 − 2.1 (tare) = 16.3 lb net
            Confidence = 0.99
        
        Used for:
        - High-value items (meat, alcohol)
        - End-of-period reconciliation
        - Shrinkage investigations
        """
        config = self._item_configs.get(product_id)
        if not config:
            raise ValueError(f"No configuration for product {product_id}")
        
        gross = input_data.gross_weight
        
        # Convert to item's base unit if needed
        if input_data.weight_unit != config.base_unit:
            gross = self.convert_units(gross, input_data.weight_unit, config.base_unit)
        
        # Calculate tare weight
        tare = Decimal("0")
        if input_data.include_container_tare:
            if input_data.tare_weight_override:
                tare = input_data.tare_weight_override
            elif config.primary_handling_unit.container_tare_weight:
                tare = config.primary_handling_unit.container_tare_weight * input_data.container_count
                # Convert tare if needed
                if config.primary_handling_unit.container_tare_unit != config.base_unit:
                    tare = self.convert_units(
                        tare,
                        config.primary_handling_unit.container_tare_unit,
                        config.base_unit
                    )
        
        net_qty = gross - tare
        
        # Direct weight has highest confidence
        confidence = METHOD_CONFIDENCE_CEILING[MeasurementMethod.DIRECT_WEIGHT]
        
        # For regulated items with dual verification
        if config.requires_dual_verification:
            confidence = METHOD_CONFIDENCE_CEILING[MeasurementMethod.DUAL_VERIFICATION]
        
        original = f"Weighed: {input_data.gross_weight} {input_data.weight_unit.value} gross, {tare} tare"
        
        result = NormalizedQuantity(
            quantity_base_units=net_qty,
            base_unit=config.base_unit,
            confidence=confidence,
            measurement_method=MeasurementMethod.DIRECT_WEIGHT,
            original_input=original,
            measured_by=measured_by,
        )
        
        self._inventory[product_id] = result
        return result
    
    # =========================================================================
    # METHOD 3: RECIPE DEPLETION (projection, NOT reality)
    # =========================================================================
    
    def normalize_recipe_depletion(
        self,
        product_id: uuid.UUID,
        input_data: RecipeDepletionInput,
        measured_by: Optional[str] = None,
    ) -> NormalizedQuantity:
        """
        Method 3: Depletion by Usage (recipe-driven)
        
        KEY RULE: This is a PROJECTION, not reality.
        Bishop labels it clearly and will:
        - Downgrade confidence
        - Trigger verification sooner
        
        Calculation:
            Last known flour = 200 lb
            Usage since = 180 plates × 0.18 lb
            Usage = 32.4 lb
            Remaining = 167.6 lb
            Confidence = 0.74
        """
        config = self._item_configs.get(product_id)
        if not config:
            raise ValueError(f"No configuration for product {product_id}")
        
        # Convert last known to base unit
        last_qty = input_data.last_known_quantity
        if input_data.last_known_unit != config.base_unit:
            last_qty = self.convert_units(last_qty, input_data.last_known_unit, config.base_unit)
        
        # Calculate usage
        usage_per = input_data.usage_per_serving
        if input_data.usage_unit != config.base_unit:
            usage_per = self.convert_units(usage_per, input_data.usage_unit, config.base_unit)
        
        total_usage = usage_per * input_data.servings_since_last_count
        remaining = max(Decimal("0"), last_qty - total_usage)
        
        # Base confidence is capped for projections
        confidence = METHOD_CONFIDENCE_CEILING[MeasurementMethod.RECIPE_DEPLETION]
        
        # Further reduce confidence based on time since last count
        hours_since = (datetime.utcnow() - input_data.last_known_at).total_seconds() / 3600
        if hours_since > 24:
            days = hours_since / 24
            decay = Decimal(str(self._decay_config.daily_decay_rate)) ** int(days)
            confidence = confidence * decay
            confidence = max(self._decay_config.floor_confidence, confidence)
        
        # Further reduce based on usage volume (high usage = more uncertainty)
        if total_usage > last_qty * Decimal("0.5"):
            confidence = confidence * Decimal("0.9")
        
        original = f"Projected: {last_qty} - ({input_data.servings_since_last_count} × {input_data.usage_per_serving})"
        
        result = NormalizedQuantity(
            quantity_base_units=remaining.quantize(Decimal("0.01")),
            base_unit=config.base_unit,
            confidence=confidence.quantize(Decimal("0.01")),
            measurement_method=MeasurementMethod.RECIPE_DEPLETION,
            original_input=original,
            measured_by=measured_by,
        )
        
        self._inventory[product_id] = result
        
        # Check if verification needed
        if confidence < config.reweigh_trigger_confidence:
            self._create_verification_request(
                product_id,
                result,
                VerificationTrigger.LOW_CONFIDENCE,
                f"Projected quantity confidence ({confidence}) below threshold ({config.reweigh_trigger_confidence})"
            )
        
        return result
    
    # =========================================================================
    # VOLUME ESTIMATE (for liquids)
    # =========================================================================
    
    def normalize_volume_estimate(
        self,
        product_id: uuid.UUID,
        input_data: VolumeEstimateInput,
        measured_by: Optional[str] = None,
    ) -> NormalizedQuantity:
        """
        Volume estimation for liquids.
        Confidence capped unless weighed.
        """
        config = self._item_configs.get(product_id)
        if not config:
            raise ValueError(f"No configuration for product {product_id}")
        
        # Calculate volume
        volume_per = input_data.container_capacity * (input_data.fill_level_pct / 100)
        total_volume = volume_per * input_data.container_count
        
        # Convert if needed
        if input_data.container_unit != config.base_unit:
            total_volume = self.convert_units(total_volume, input_data.container_unit, config.base_unit)
        
        # Confidence capped for estimates
        confidence = METHOD_CONFIDENCE_CEILING[MeasurementMethod.VOLUME_ESTIMATE]
        
        # Reduce confidence for low fill levels (harder to estimate)
        if input_data.fill_level_pct < 25:
            confidence = confidence * Decimal("0.85")
        
        original = f"{input_data.container_count}x containers at {input_data.fill_level_pct}% fill"
        
        result = NormalizedQuantity(
            quantity_base_units=total_volume.quantize(Decimal("0.01")),
            base_unit=config.base_unit,
            confidence=confidence,
            measurement_method=MeasurementMethod.VOLUME_ESTIMATE,
            original_input=original,
            measured_by=measured_by,
        )
        
        self._inventory[product_id] = result
        return result
    
    # =========================================================================
    # CONFIDENCE DECAY
    # =========================================================================
    
    def apply_confidence_decay(self, product_id: uuid.UUID) -> Optional[NormalizedQuantity]:
        """
        Apply time-based confidence decay to stored quantity.
        Prevents stale data from being trusted.
        """
        current = self._inventory.get(product_id)
        if not current:
            return None
        
        config = self._item_configs.get(product_id)
        
        # Calculate time since measurement
        hours_since = (datetime.utcnow() - current.measured_at).total_seconds() / 3600
        days_since = hours_since / 24
        
        if days_since < 1:
            return current  # No decay within first day
        
        # Get decay rate
        decay_rate = self._decay_config.daily_decay_rate
        if config:
            if config.is_regulated:
                decay_rate = self._decay_config.regulated_decay_rate
            # Could add high-turnover detection here
        
        # Apply decay
        new_confidence = current.confidence * (decay_rate ** Decimal(str(int(days_since))))
        new_confidence = max(self._decay_config.floor_confidence, new_confidence)
        
        # Update stored
        current.confidence = new_confidence.quantize(Decimal("0.01"))
        
        # Check for verification trigger
        if config and new_confidence < config.reweigh_trigger_confidence:
            self._create_verification_request(
                product_id,
                current,
                VerificationTrigger.CONFIDENCE_DECAY,
                f"Confidence decayed to {new_confidence} after {int(days_since)} days"
            )
        
        # Check max days
        if days_since > self._decay_config.max_days_without_verification:
            self._create_verification_request(
                product_id,
                current,
                VerificationTrigger.SCHEDULED_AUDIT,
                f"No verification for {int(days_since)} days (max: {self._decay_config.max_days_without_verification})"
            )
        
        return current
    
    # =========================================================================
    # VERIFICATION REQUESTS
    # =========================================================================
    
    def _create_verification_request(
        self,
        product_id: uuid.UUID,
        current: NormalizedQuantity,
        trigger: VerificationTrigger,
        reason: str,
    ) -> VerificationRequest:
        """Create a verification request for an item."""
        config = self._item_configs.get(product_id)
        
        # Determine recommended method
        if config and config.force_weigh_method:
            recommended = MeasurementMethod.DIRECT_WEIGHT
        elif config and config.is_regulated:
            recommended = MeasurementMethod.DUAL_VERIFICATION
        else:
            recommended = MeasurementMethod.CONTAINER_COUNT
        
        # Determine priority
        priority = "normal"
        if trigger == VerificationTrigger.SHRINKAGE_SIGNAL:
            priority = "high"
        elif trigger == VerificationTrigger.REGULATED_ITEM:
            priority = "critical"
        elif current.confidence < Decimal("0.50"):
            priority = "high"
        
        request = VerificationRequest(
            product_id=product_id,
            product_name=config.product_name if config else "Unknown",
            current_quantity=current,
            trigger=trigger,
            trigger_reason=reason,
            recommended_method=recommended,
            priority=priority,
            due_by=datetime.utcnow() + timedelta(hours=24 if priority == "high" else 72),
        )
        
        # Avoid duplicates
        existing = [r for r in self._verification_requests if r.product_id == product_id]
        if not existing:
            self._verification_requests.append(request)
        
        return request
    
    def get_verification_requests(
        self,
        priority: Optional[str] = None,
    ) -> list[VerificationRequest]:
        """Get pending verification requests."""
        requests = self._verification_requests
        if priority:
            requests = [r for r in requests if r.priority == priority]
        return sorted(requests, key=lambda r: r.created_at)
    
    def complete_verification(self, request_id: uuid.UUID) -> bool:
        """Mark a verification request as complete."""
        self._verification_requests = [
            r for r in self._verification_requests if r.request_id != request_id
        ]
        return True
    
    # =========================================================================
    # QUERY
    # =========================================================================
    
    def get_inventory(self, product_id: uuid.UUID) -> Optional[NormalizedQuantity]:
        """Get current normalized inventory for a product."""
        return self._inventory.get(product_id)
    
    def get_all_inventory(self) -> dict[uuid.UUID, NormalizedQuantity]:
        """Get all normalized inventory."""
        return self._inventory.copy()
    
    def get_low_confidence_items(
        self,
        threshold: Decimal = Decimal("0.70"),
    ) -> list[tuple[uuid.UUID, NormalizedQuantity]]:
        """Get items with confidence below threshold."""
        return [
            (pid, qty) for pid, qty in self._inventory.items()
            if qty.confidence < threshold
        ]
    
    def clear_data(self) -> None:
        """Clear all data (for testing)."""
        self._item_configs.clear()
        self._inventory.clear()
        self._verification_requests.clear()


# Singleton instance
bulk_engine = BulkNormalizationEngine()
