"""
PROVENIQ Ops - Event Publisher
Central event bus publisher per INTER_APP_CONTRACT.md

Contract:
    - All apps communicate via a central event bus (Kafka/Pub-Sub)
    - Events are idempotent
    - Events follow canonical schema

Ops MUST Publish:
    - ops.scan.initiated
    - ops.item.detected
    - ops.inventory.updated
    - ops.shrinkage.detected
    - ops.order.queued
    - ops.excess.flagged
"""

import os
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field


class OpsEventType(str, Enum):
    """Ops event types per contract."""
    SCAN_INITIATED = "ops.scan.initiated"
    ITEM_DETECTED = "ops.item.detected"
    INVENTORY_UPDATED = "ops.inventory.updated"
    SHRINKAGE_DETECTED = "ops.shrinkage.detected"
    ORDER_QUEUED = "ops.order.queued"
    EXCESS_FLAGGED = "ops.excess.flagged"


class EventPayload(BaseModel):
    """Base event payload schema per contract."""
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    wallet_id: Optional[str] = None  # Pseudonymous identifier
    correlation_id: Optional[str] = None
    version: str = "1.0"
    payload: dict = Field(default_factory=dict)
    source_app: str = "OPS"


class ScanInitiatedPayload(BaseModel):
    """Payload for ops.scan.initiated event."""
    scan_id: uuid.UUID
    location_id: uuid.UUID
    business_id: uuid.UUID
    scan_type: str  # "FULL_SHELF", "SPOT_CHECK", "SINGLE_ITEM"
    initiated_by: Optional[str] = None


class ItemDetectedPayload(BaseModel):
    """Payload for ops.item.detected event."""
    scan_id: uuid.UUID
    item_id: uuid.UUID
    product_id: Optional[uuid.UUID] = None
    product_name: str
    quantity: int
    confidence: Decimal
    location_id: uuid.UUID


class InventoryUpdatedPayload(BaseModel):
    """Payload for ops.inventory.updated event."""
    item_id: uuid.UUID
    product_id: uuid.UUID
    location_id: uuid.UUID
    previous_qty: Decimal
    new_qty: Decimal
    delta: Decimal
    reason: str  # "scan", "order", "transfer", "adjustment", "waste"


class ShrinkageDetectedPayload(BaseModel):
    """Payload for ops.shrinkage.detected event."""
    shrinkage_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    location_id: uuid.UUID
    business_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    expected_qty: Decimal
    actual_qty: Decimal
    variance: Decimal
    variance_value_micros: int
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class OrderQueuedPayload(BaseModel):
    """Payload for ops.order.queued event."""
    order_id: uuid.UUID
    vendor: str
    business_id: uuid.UUID
    location_id: uuid.UUID
    total_amount_micros: int
    item_count: int
    delivery_date: Optional[datetime] = None
    liquidity_check_passed: bool = True


class ExcessFlaggedPayload(BaseModel):
    """Payload for ops.excess.flagged event."""
    excess_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    business_id: uuid.UUID
    location_id: uuid.UUID
    item_count: int
    total_value_micros: int
    reason: str  # "overstock", "menu_change", "seasonal", "near_expiry"
    urgency: str  # "low", "medium", "high", "critical"


class EventPublisher:
    """
    Central event publisher for Ops.
    
    In production, this would connect to:
    - Kafka
    - Google Pub/Sub
    - AWS SNS/SQS
    
    For now, it logs events for testing and debugging.
    Events are also forwarded to Ledger mock for storage.
    """
    
    def __init__(self) -> None:
        self._event_log: list[EventPayload] = []
        self._subscribers: dict[str, list[callable]] = {}
        self.claimsiq_url = os.getenv("CLAIMSIQ_API_URL")
        self.claimsiq_token = os.getenv("CLAIMSIQ_SERVICE_TOKEN")
    
    async def publish(
        self,
        event_type: OpsEventType,
        payload: dict,
        wallet_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> EventPayload:
        """
        Publish an event to the bus.
        
        Args:
            event_type: Type of event (from OpsEventType enum)
            payload: Event-specific payload
            wallet_id: Pseudonymous identifier (no PII)
            correlation_id: For tracing related events
        
        Returns:
            The published event
        """
        event = EventPayload(
            event_type=event_type.value,
            payload=payload,
            wallet_id=wallet_id,
            correlation_id=correlation_id or str(uuid.uuid4()),
        )
        
        # Log event
        self._event_log.append(event)
        
        # Notify subscribers
        await self._notify_subscribers(event)
        
        return event
    
    async def _notify_subscribers(self, event: EventPayload) -> None:
        """Notify all subscribers of an event."""
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            try:
                if callable(handler):
                    await handler(event)
            except Exception as e:
                # Log but don't fail on subscriber errors
                pass
    
    def subscribe(self, event_type: str, handler: callable) -> None:
        """Subscribe to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    def unsubscribe(self, event_type: str, handler: callable) -> None:
        """Unsubscribe from an event type."""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type] if h != handler
            ]
    
    # =========================================================================
    # CONVENIENCE METHODS FOR OPS EVENTS
    # =========================================================================
    
    async def publish_scan_initiated(
        self,
        scan_id: uuid.UUID,
        location_id: uuid.UUID,
        business_id: uuid.UUID,
        scan_type: str = "FULL_SHELF",
        initiated_by: Optional[str] = None,
    ) -> EventPayload:
        """Publish ops.scan.initiated event."""
        payload = ScanInitiatedPayload(
            scan_id=scan_id,
            location_id=location_id,
            business_id=business_id,
            scan_type=scan_type,
            initiated_by=initiated_by,
        )
        return await self.publish(
            OpsEventType.SCAN_INITIATED,
            payload.model_dump(mode="json"),
        )
    
    async def publish_item_detected(
        self,
        scan_id: uuid.UUID,
        item_id: uuid.UUID,
        product_name: str,
        quantity: int,
        confidence: Decimal,
        location_id: uuid.UUID,
        product_id: Optional[uuid.UUID] = None,
    ) -> EventPayload:
        """Publish ops.item.detected event."""
        payload = ItemDetectedPayload(
            scan_id=scan_id,
            item_id=item_id,
            product_id=product_id,
            product_name=product_name,
            quantity=quantity,
            confidence=confidence,
            location_id=location_id,
        )
        return await self.publish(
            OpsEventType.ITEM_DETECTED,
            payload.model_dump(mode="json"),
        )
    
    async def publish_inventory_updated(
        self,
        item_id: uuid.UUID,
        product_id: uuid.UUID,
        location_id: uuid.UUID,
        previous_qty: Decimal,
        new_qty: Decimal,
        reason: str = "adjustment",
    ) -> EventPayload:
        """Publish ops.inventory.updated event."""
        payload = InventoryUpdatedPayload(
            item_id=item_id,
            product_id=product_id,
            location_id=location_id,
            previous_qty=previous_qty,
            new_qty=new_qty,
            delta=new_qty - previous_qty,
            reason=reason,
        )
        return await self.publish(
            OpsEventType.INVENTORY_UPDATED,
            payload.model_dump(mode="json"),
        )
    
    async def publish_shrinkage_detected(
        self,
        location_id: uuid.UUID,
        business_id: uuid.UUID,
        product_id: uuid.UUID,
        product_name: str,
        expected_qty: Decimal,
        actual_qty: Decimal,
        unit_cost_micros: int,
    ) -> EventPayload:
        """Publish ops.shrinkage.detected event."""
        variance = expected_qty - actual_qty
        variance_value = int(float(variance) * unit_cost_micros)
        
        payload = ShrinkageDetectedPayload(
            location_id=location_id,
            business_id=business_id,
            product_id=product_id,
            product_name=product_name,
            expected_qty=expected_qty,
            actual_qty=actual_qty,
            variance=variance,
            variance_value_micros=variance_value,
        )
        event = await self.publish(
            OpsEventType.SHRINKAGE_DETECTED,
            payload.model_dump(mode="json"),
        )

        # Forward to ClaimsIQ ingestion endpoint (fire-and-forget)
        await self._forward_shrinkage_to_claimsiq(event)
        return event
    
    async def publish_order_queued(
        self,
        order_id: uuid.UUID,
        vendor: str,
        business_id: uuid.UUID,
        location_id: uuid.UUID,
        total_amount_micros: int,
        item_count: int,
        delivery_date: Optional[datetime] = None,
        liquidity_check_passed: bool = True,
    ) -> EventPayload:
        """Publish ops.order.queued event."""
        payload = OrderQueuedPayload(
            order_id=order_id,
            vendor=vendor,
            business_id=business_id,
            location_id=location_id,
            total_amount_micros=total_amount_micros,
            item_count=item_count,
            delivery_date=delivery_date,
            liquidity_check_passed=liquidity_check_passed,
        )
        return await self.publish(
            OpsEventType.ORDER_QUEUED,
            payload.model_dump(mode="json"),
        )
    
    async def publish_excess_flagged(
        self,
        business_id: uuid.UUID,
        location_id: uuid.UUID,
        item_count: int,
        total_value_micros: int,
        reason: str,
        urgency: str = "medium",
    ) -> EventPayload:
        """Publish ops.excess.flagged event."""
        payload = ExcessFlaggedPayload(
            business_id=business_id,
            location_id=location_id,
            item_count=item_count,
            total_value_micros=total_value_micros,
            reason=reason,
            urgency=urgency,
        )
        return await self.publish(
            OpsEventType.EXCESS_FLAGGED,
            payload.model_dump(mode="json"),
        )
    
    # =========================================================================
    # UTILITIES
    # =========================================================================
    
    def get_event_log(self) -> list[dict]:
        """Return event log for debugging."""
        return [e.model_dump(mode="json") for e in self._event_log]
    
    def get_events_by_type(self, event_type: str) -> list[dict]:
        """Get events filtered by type."""
        return [
            e.model_dump(mode="json") 
            for e in self._event_log 
            if e.event_type == event_type
        ]
    
    def clear_log(self) -> None:
        """Clear event log."""
        self._event_log.clear()

    # =========================================================================
    # FORWARDERS
    # =========================================================================

    async def _forward_shrinkage_to_claimsiq(self, event: EventPayload) -> None:
        """Forward shrinkage event to ClaimsIQ ingest endpoint if configured."""
        if not self.claimsiq_url:
            return
        try:
            url = self.claimsiq_url.rstrip("/") + "/v1/claimsiq/claims/shrinkage"
            headers = {
                "Content-Type": "application/json",
                "X-Service-Name": "proveniq-ops",
            }
            if self.claimsiq_token:
                headers["Authorization"] = f"Bearer {self.claimsiq_token}"
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(url, json=event.model_dump(mode="json"), headers=headers)
        except Exception:
            # swallow failures to avoid blocking
            pass


# Singleton instance
event_publisher = EventPublisher()
