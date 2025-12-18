"""
PROVENIQ Ops - Bishop Chain of Custody Engine
Track movement of high-risk items without assigning blame.

GUARDRAILS:
- No disciplinary language
- This is TRACEABILITY, not surveillance
- Track movement without assigning blame

LOGIC:
1. Append custody hop on each state change
2. Maintain chronological chain
3. Surface gaps or breaks
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.models.custody import (
    ActorRole,
    ChainGap,
    ChainStatus,
    CustodyAction,
    CustodyChain,
    CustodyConfig,
    CustodyHop,
    CustodyQuery,
    CustodyReport,
    DisposalEvent,
    ItemRiskLevel,
    PrepEvent,
    ReceivingEvent,
    TransferEvent,
)


class ChainOfCustodyEngine:
    """
    Bishop Chain of Custody Engine
    
    Tracks movement of high-risk items for traceability.
    
    GUARDRAIL: This is traceability, NOT surveillance.
    No disciplinary language. No blame assignment.
    """
    
    def __init__(self) -> None:
        self._config = CustodyConfig()
        
        # Custody chains by item_id
        self._chains: dict[uuid.UUID, CustodyChain] = {}
        
        # Detected gaps
        self._gaps: list[ChainGap] = []
        
        # Indexes
        self._by_product: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        self._by_location: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        self._by_batch: dict[str, list[uuid.UUID]] = defaultdict(list)
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure(self, config: CustodyConfig) -> None:
        """Update custody configuration."""
        self._config = config
    
    def get_config(self) -> CustodyConfig:
        """Get current configuration."""
        return self._config
    
    # =========================================================================
    # CHAIN CREATION
    # =========================================================================
    
    def create_chain(
        self,
        item_id: uuid.UUID,
        product_id: Optional[uuid.UUID] = None,
        product_name: Optional[str] = None,
        batch_id: Optional[str] = None,
        lot_number: Optional[str] = None,
        risk_level: ItemRiskLevel = ItemRiskLevel.STANDARD,
    ) -> CustodyChain:
        """
        Create a new custody chain for an item.
        """
        chain = CustodyChain(
            item_id=item_id,
            product_id=product_id,
            product_name=product_name,
            batch_id=batch_id,
            lot_number=lot_number,
            risk_level=risk_level,
        )
        
        self._chains[item_id] = chain
        
        # Index
        if product_id:
            self._by_product[product_id].append(item_id)
        if batch_id:
            self._by_batch[batch_id].append(item_id)
        
        return chain
    
    def get_or_create_chain(
        self,
        item_id: uuid.UUID,
        **kwargs,
    ) -> CustodyChain:
        """Get existing chain or create new one."""
        if item_id in self._chains:
            return self._chains[item_id]
        return self.create_chain(item_id, **kwargs)
    
    # =========================================================================
    # HOP RECORDING (Step 1)
    # =========================================================================
    
    def append_hop(
        self,
        item_id: uuid.UUID,
        actor_role: ActorRole,
        action: CustodyAction,
        location_id: Optional[uuid.UUID] = None,
        location_name: Optional[str] = None,
        quantity: Optional[Decimal] = None,
        quantity_unit: Optional[str] = None,
        notes: Optional[str] = None,
        verified: bool = False,
        verification_method: Optional[str] = None,
        source_event_id: Optional[uuid.UUID] = None,
        source_event_type: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> CustodyHop:
        """
        Append a custody hop to the chain.
        
        Each hop represents a state change for the item.
        """
        chain = self._chains.get(item_id)
        if not chain:
            chain = self.create_chain(item_id)
        
        hop = CustodyHop(
            actor_role=actor_role,
            action=action,
            timestamp=timestamp or datetime.utcnow(),
            location_id=location_id,
            location_name=location_name,
            quantity=quantity,
            quantity_unit=quantity_unit,
            notes=notes,
            verified=verified,
            verification_method=verification_method,
            source_event_id=source_event_id,
            source_event_type=source_event_type,
        )
        
        # Check for gaps before appending
        if chain.custody_chain:
            self._check_for_gaps(chain, hop)
        
        # Append hop
        chain.custody_chain.append(hop)
        chain.last_hop_at = hop.timestamp
        chain.current_actor = actor_role
        
        if location_id:
            chain.current_location_id = location_id
            self._by_location[location_id].append(item_id)
        
        # Check if chain is closed
        if action in (CustodyAction.DISPOSED, CustodyAction.DONATED, CustodyAction.RETURNED_TO_VENDOR):
            chain.status = ChainStatus.DISPOSED
            chain.chain_closed = hop.timestamp
        
        return hop
    
    # =========================================================================
    # EVENT PROCESSING
    # =========================================================================
    
    def process_receiving(self, event: ReceivingEvent) -> CustodyHop:
        """Process a receiving event into custody hop."""
        chain = self.get_or_create_chain(
            item_id=event.item_id,
            product_id=event.product_id,
        )
        
        action = CustodyAction.ACCEPTED if event.inspection_passed else CustodyAction.REJECTED
        notes = None
        if not event.inspection_passed:
            issues = []
            if event.temperature_ok is False:
                issues.append("temperature issue")
            if event.packaging_ok is False:
                issues.append("packaging issue")
            notes = f"Inspection: {', '.join(issues)}" if issues else "Inspection failed"
        
        return self.append_hop(
            item_id=event.item_id,
            actor_role=ActorRole.RECEIVING_TEAM,
            action=action,
            location_id=event.location_id,
            location_name=event.location_name,
            quantity=event.quantity_received,
            quantity_unit=event.quantity_unit,
            notes=notes,
            verified=True,
            verification_method="receiving_scan",
            source_event_id=event.event_id,
            source_event_type="receiving",
            timestamp=event.received_at,
        )
    
    def process_prep(self, event: PrepEvent) -> CustodyHop:
        """Process a prep event into custody hop."""
        return self.append_hop(
            item_id=event.item_id,
            actor_role=ActorRole.PREP_TEAM,
            action=CustodyAction.PREPPED,
            location_id=event.location_id,
            location_name=event.location_name,
            quantity=event.output_quantity or event.input_quantity,
            quantity_unit=event.quantity_unit,
            notes=f"Prep type: {event.prep_type}",
            source_event_id=event.event_id,
            source_event_type="prep",
            timestamp=event.prepped_at,
        )
    
    def process_transfer(self, event: TransferEvent) -> tuple[CustodyHop, CustodyHop]:
        """
        Process a transfer event into two custody hops.
        
        Returns (outbound_hop, inbound_hop)
        """
        # Outbound hop
        out_hop = self.append_hop(
            item_id=event.item_id,
            actor_role=ActorRole.INVENTORY_TEAM,
            action=CustodyAction.TRANSFERRED_OUT,
            location_id=event.from_location_id,
            location_name=event.from_location_name,
            quantity=event.quantity_transferred,
            quantity_unit=event.quantity_unit,
            verified=event.sent_verified,
            verification_method="transfer_scan" if event.sent_verified else None,
            source_event_id=event.event_id,
            source_event_type="transfer_out",
            timestamp=event.transferred_at,
        )
        
        # Inbound hop (slightly later)
        in_hop = self.append_hop(
            item_id=event.item_id,
            actor_role=ActorRole.INVENTORY_TEAM,
            action=CustodyAction.TRANSFERRED_IN,
            location_id=event.to_location_id,
            location_name=event.to_location_name,
            quantity=event.quantity_transferred,
            quantity_unit=event.quantity_unit,
            verified=event.received_verified,
            verification_method="transfer_scan" if event.received_verified else None,
            source_event_id=event.event_id,
            source_event_type="transfer_in",
            timestamp=event.transferred_at + timedelta(minutes=1),
        )
        
        return out_hop, in_hop
    
    def process_disposal(self, event: DisposalEvent) -> CustodyHop:
        """Process a disposal event into custody hop."""
        # Map disposal type to action
        action_map = {
            "donated": CustodyAction.DONATED,
            "returned": CustodyAction.RETURNED_TO_VENDOR,
        }
        action = action_map.get(event.disposal_type, CustodyAction.DISPOSED)
        
        return self.append_hop(
            item_id=event.item_id,
            actor_role=event.verified_by_role or ActorRole.MANAGER,
            action=action,
            location_id=event.location_id,
            location_name=event.location_name,
            quantity=event.quantity_disposed,
            quantity_unit=event.quantity_unit,
            notes=f"{event.disposal_type}: {event.disposal_reason}",
            verified=event.verified_by_role is not None,
            source_event_id=event.event_id,
            source_event_type="disposal",
            timestamp=event.disposed_at,
        )
    
    # =========================================================================
    # GAP DETECTION (Step 3)
    # =========================================================================
    
    def _check_for_gaps(self, chain: CustodyChain, new_hop: CustodyHop) -> None:
        """
        Check for gaps before appending a new hop.
        
        GUARDRAIL: Gap detection is for traceability, not blame.
        """
        last_hop = chain.custody_chain[-1]
        
        # Time gap check
        time_diff = (new_hop.timestamp - last_hop.timestamp).total_seconds() / 3600
        if time_diff > self._config.max_hours_between_hops:
            gap = ChainGap(
                chain_id=chain.chain_id,
                item_id=chain.item_id,
                gap_type="time_gap",
                gap_description=f"Time gap of {time_diff:.1f} hours detected between hops",
                before_hop_id=last_hop.hop_id,
                after_hop_id=new_hop.hop_id,
                time_gap_hours=Decimal(str(time_diff)),
            )
            self._gaps.append(gap)
            chain.gaps_detected += 1
            chain.gap_details.append(f"Time gap: {time_diff:.1f}h")
            
            if chain.status == ChainStatus.ACTIVE:
                chain.status = ChainStatus.GAP_DETECTED
        
        # Location gap check (if both hops have location)
        if last_hop.location_id and new_hop.location_id:
            if last_hop.location_id != new_hop.location_id:
                # Check if there's a transfer action
                if new_hop.action not in (CustodyAction.TRANSFERRED_IN, CustodyAction.TRANSFERRED_OUT):
                    gap = ChainGap(
                        chain_id=chain.chain_id,
                        item_id=chain.item_id,
                        gap_type="location_gap",
                        gap_description=f"Location changed without transfer: {last_hop.location_name} → {new_hop.location_name}",
                        before_hop_id=last_hop.hop_id,
                        after_hop_id=new_hop.hop_id,
                    )
                    self._gaps.append(gap)
                    chain.gaps_detected += 1
                    chain.gap_details.append(f"Location gap: {last_hop.location_name} → {new_hop.location_name}")
        
        # Quantity discrepancy check
        if last_hop.quantity and new_hop.quantity:
            if last_hop.quantity_unit == new_hop.quantity_unit:
                diff = abs(last_hop.quantity - new_hop.quantity)
                if diff > last_hop.quantity * Decimal("0.05"):  # >5% discrepancy
                    gap = ChainGap(
                        chain_id=chain.chain_id,
                        item_id=chain.item_id,
                        gap_type="quantity_gap",
                        gap_description=f"Quantity changed: {last_hop.quantity} → {new_hop.quantity} {new_hop.quantity_unit}",
                        before_hop_id=last_hop.hop_id,
                        after_hop_id=new_hop.hop_id,
                        quantity_discrepancy=diff,
                    )
                    self._gaps.append(gap)
                    chain.gaps_detected += 1
                    chain.gap_details.append(f"Quantity gap: {diff} {new_hop.quantity_unit}")
    
    def get_gaps(
        self,
        item_id: Optional[uuid.UUID] = None,
        unresolved_only: bool = False,
    ) -> list[ChainGap]:
        """Get detected gaps."""
        gaps = self._gaps
        
        if item_id:
            gaps = [g for g in gaps if g.item_id == item_id]
        if unresolved_only:
            gaps = [g for g in gaps if not g.resolved]
        
        return gaps
    
    def resolve_gap(
        self,
        gap_id: uuid.UUID,
        resolution_notes: str,
    ) -> bool:
        """Mark a gap as resolved with notes."""
        for gap in self._gaps:
            if gap.gap_id == gap_id:
                gap.resolved = True
                gap.resolution_notes = resolution_notes
                return True
        return False
    
    # =========================================================================
    # QUERY
    # =========================================================================
    
    def get_chain(self, item_id: uuid.UUID) -> Optional[CustodyChain]:
        """Get custody chain for an item."""
        return self._chains.get(item_id)
    
    def query_chains(self, query: CustodyQuery) -> list[CustodyChain]:
        """Query custody chains with filters."""
        chains = list(self._chains.values())
        
        if query.item_id:
            chains = [c for c in chains if c.item_id == query.item_id]
        if query.product_id:
            item_ids = self._by_product.get(query.product_id, [])
            chains = [c for c in chains if c.item_id in item_ids]
        if query.batch_id:
            item_ids = self._by_batch.get(query.batch_id, [])
            chains = [c for c in chains if c.item_id in item_ids]
        if query.location_id:
            chains = [c for c in chains if c.current_location_id == query.location_id]
        if query.risk_level:
            chains = [c for c in chains if c.risk_level == query.risk_level]
        if query.status:
            chains = [c for c in chains if c.status == query.status]
        if query.has_gaps is not None:
            if query.has_gaps:
                chains = [c for c in chains if c.gaps_detected > 0]
            else:
                chains = [c for c in chains if c.gaps_detected == 0]
        if query.from_date:
            chains = [c for c in chains if c.chain_started >= query.from_date]
        if query.to_date:
            chains = [c for c in chains if c.chain_started <= query.to_date]
        
        return chains
    
    def get_report(self) -> CustodyReport:
        """Generate custody report."""
        chains = list(self._chains.values())
        
        total = len(chains)
        active = len([c for c in chains if c.status == ChainStatus.ACTIVE])
        complete = len([c for c in chains if c.status == ChainStatus.COMPLETE])
        with_gaps = len([c for c in chains if c.gaps_detected > 0])
        
        high_risk = len([c for c in chains if c.risk_level == ItemRiskLevel.HIGH])
        regulated = len([c for c in chains if c.risk_level == ItemRiskLevel.REGULATED])
        
        unresolved_gaps = len([g for g in self._gaps if not g.resolved])
        
        # Count unique items and locations
        items = set(c.item_id for c in chains)
        locations = set(c.current_location_id for c in chains if c.current_location_id)
        
        return CustodyReport(
            total_chains=total,
            active_chains=active,
            complete_chains=complete,
            chains_with_gaps=with_gaps,
            high_risk_chains=high_risk,
            regulated_chains=regulated,
            total_gaps_detected=len(self._gaps),
            unresolved_gaps=unresolved_gaps,
            items_tracked=len(items),
            locations_covered=len(locations),
        )
    
    def clear_data(self) -> None:
        """Clear all custody data (for testing)."""
        self._chains.clear()
        self._gaps.clear()
        self._by_product.clear()
        self._by_location.clear()
        self._by_batch.clear()


# Singleton instance
custody_engine = ChainOfCustodyEngine()
