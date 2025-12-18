"""
PROVENIQ Ops - Bishop Smart Receiving Engine
Scan-to-PO reconciliation with instant verification

LOGIC:
1. Match scans to PO line items
2. Detect shorts, overages, substitutions, damage flags
3. Generate adjustment proposal

GUARDRAILS:
- Never close PO without explicit confirmation
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.models.receiving import (
    AcceptReceivingRequest,
    DiscrepancyType,
    DockScan,
    LineItemDiscrepancy,
    POLineItem,
    POStatus,
    PurchaseOrder,
    ReceivingAlertType,
    ReceivingReconciliation,
    ReceivingResponse,
    ReceivingSession,
    VendorSubstitutionRule,
)


@dataclass
class MatchResult:
    """Result of matching a scan to PO line items."""
    matched: bool
    line_id: Optional[uuid.UUID] = None
    match_type: str = "exact"  # exact, substitution, unknown
    substitution_rule: Optional[VendorSubstitutionRule] = None


class ReceivingEngine:
    """
    Bishop Smart Receiving Engine
    
    Transforms receiving into instant verification.
    Deterministic scan-to-PO reconciliation.
    """
    
    def __init__(self) -> None:
        self._purchase_orders: dict[uuid.UUID, PurchaseOrder] = {}
        self._sessions: dict[uuid.UUID, ReceivingSession] = {}
        self._substitution_rules: dict[tuple[uuid.UUID, uuid.UUID], VendorSubstitutionRule] = {}
        self._barcode_to_product: dict[str, uuid.UUID] = {}
        self._product_names: dict[uuid.UUID, str] = {}
    
    # =========================================================================
    # DATA REGISTRATION
    # =========================================================================
    
    def register_purchase_order(self, po: PurchaseOrder) -> None:
        """Register a purchase order for receiving."""
        self._purchase_orders[po.po_id] = po
        # Index product names
        for item in po.line_items:
            self._product_names[item.product_id] = item.product_name
    
    def register_substitution_rule(self, rule: VendorSubstitutionRule) -> None:
        """Register an allowed substitution rule."""
        key = (rule.vendor_id, rule.original_product_id)
        self._substitution_rules[key] = rule
    
    def register_barcode(self, barcode: str, product_id: uuid.UUID, name: str) -> None:
        """Register barcode to product mapping."""
        self._barcode_to_product[barcode] = product_id
        self._product_names[product_id] = name
    
    def get_purchase_order(self, po_id: uuid.UUID) -> Optional[PurchaseOrder]:
        """Get a registered purchase order."""
        return self._purchase_orders.get(po_id)
    
    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================
    
    def start_session(self, po_id: uuid.UUID) -> ReceivingSession:
        """Start a new receiving session for a PO."""
        if po_id not in self._purchase_orders:
            raise ValueError(f"PO {po_id} not found")
        
        session = ReceivingSession(po_id=po_id)
        self._sessions[session.session_id] = session
        return session
    
    def get_session(self, session_id: uuid.UUID) -> Optional[ReceivingSession]:
        """Get an active receiving session."""
        return self._sessions.get(session_id)
    
    def add_scan(self, session_id: uuid.UUID, scan: DockScan) -> DockScan:
        """Add a scan to an active session."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Resolve product from barcode if not set
        if not scan.product_id and scan.barcode:
            scan.product_id = self._barcode_to_product.get(scan.barcode)
            if scan.product_id:
                scan.product_name = self._product_names.get(scan.product_id)
        
        session.scans.append(scan)
        return scan
    
    # =========================================================================
    # MATCHING LOGIC
    # =========================================================================
    
    def _match_scan_to_line(
        self,
        scan: DockScan,
        po: PurchaseOrder,
    ) -> MatchResult:
        """Match a scan to a PO line item."""
        if not scan.product_id:
            return MatchResult(matched=False, match_type="unknown")
        
        # Try exact match first
        for item in po.line_items:
            if item.product_id == scan.product_id:
                return MatchResult(
                    matched=True,
                    line_id=item.line_id,
                    match_type="exact",
                )
        
        # Try substitution match
        for item in po.line_items:
            key = (po.vendor_id, item.product_id)
            rule = self._substitution_rules.get(key)
            if rule and rule.substitute_product_id == scan.product_id:
                # Check if substitution is still valid
                if rule.valid_until and rule.valid_until < datetime.utcnow():
                    continue
                return MatchResult(
                    matched=True,
                    line_id=item.line_id,
                    match_type="substitution",
                    substitution_rule=rule,
                )
        
        return MatchResult(matched=False, match_type="unknown")
    
    def _aggregate_scans_by_product(
        self,
        scans: list[DockScan],
    ) -> dict[uuid.UUID, dict]:
        """Aggregate scans by product, summing quantities."""
        aggregated: dict[uuid.UUID, dict] = {}
        
        for scan in scans:
            if not scan.product_id:
                continue
            
            if scan.product_id not in aggregated:
                aggregated[scan.product_id] = {
                    "quantity": 0,
                    "damaged": 0,
                    "scans": [],
                }
            
            if scan.condition == "damaged":
                aggregated[scan.product_id]["damaged"] += scan.quantity_scanned
            else:
                aggregated[scan.product_id]["quantity"] += scan.quantity_scanned
            
            aggregated[scan.product_id]["scans"].append(scan)
        
        return aggregated
    
    # =========================================================================
    # RECONCILIATION
    # =========================================================================
    
    def reconcile(self, session_id: uuid.UUID) -> ReceivingReconciliation:
        """
        Reconcile scans against PO.
        
        Detects:
            - Shorts (received < ordered)
            - Overages (received > ordered)
            - Substitutions (different product received)
            - Damaged items
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        po = self._purchase_orders.get(session.po_id)
        if not po:
            raise ValueError(f"PO {session.po_id} not found")
        
        # Aggregate scans by product
        scan_totals = self._aggregate_scans_by_product(session.scans)
        
        # Track matches and discrepancies
        discrepancies: list[LineItemDiscrepancy] = []
        lines_matched = 0
        short_items = 0
        overages = 0
        substitutions = 0
        damaged_items = 0
        
        total_expected = Decimal("0.00")
        total_received = Decimal("0.00")
        
        # Process each PO line item
        matched_products: set[uuid.UUID] = set()
        
        for item in po.line_items:
            total_expected += item.unit_price * item.quantity_ordered
            
            received_qty = 0
            is_substitution = False
            substitute_id = None
            substitute_name = None
            damaged_qty = 0
            
            # Check for exact match
            if item.product_id in scan_totals:
                data = scan_totals[item.product_id]
                received_qty = data["quantity"]
                damaged_qty = data["damaged"]
                matched_products.add(item.product_id)
            
            # Check for substitution
            else:
                for product_id, data in scan_totals.items():
                    if product_id in matched_products:
                        continue
                    
                    key = (po.vendor_id, item.product_id)
                    rule = self._substitution_rules.get(key)
                    
                    if rule and rule.substitute_product_id == product_id:
                        received_qty = data["quantity"]
                        damaged_qty = data["damaged"]
                        is_substitution = True
                        substitute_id = product_id
                        substitute_name = self._product_names.get(product_id)
                        matched_products.add(product_id)
                        substitutions += 1
                        break
            
            # Calculate variance
            variance = received_qty - item.quantity_ordered
            received_value = item.unit_price * received_qty
            total_received += received_value
            
            # Determine discrepancy type
            if damaged_qty > 0:
                damaged_items += 1
                discrepancies.append(LineItemDiscrepancy(
                    line_id=item.line_id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    discrepancy_type=DiscrepancyType.DAMAGED,
                    expected_qty=item.quantity_ordered,
                    received_qty=received_qty,
                    variance=variance,
                    damage_notes=f"{damaged_qty} units damaged",
                    cost_impact=item.unit_price * damaged_qty,
                ))
            
            if variance < 0:
                short_items += 1
                discrepancies.append(LineItemDiscrepancy(
                    line_id=item.line_id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    discrepancy_type=DiscrepancyType.SHORT,
                    expected_qty=item.quantity_ordered,
                    received_qty=received_qty,
                    variance=variance,
                    substitute_product_id=substitute_id,
                    substitute_name=substitute_name,
                    cost_impact=item.unit_price * abs(variance),
                ))
            elif variance > 0:
                overages += 1
                discrepancies.append(LineItemDiscrepancy(
                    line_id=item.line_id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    discrepancy_type=DiscrepancyType.OVERAGE,
                    expected_qty=item.quantity_ordered,
                    received_qty=received_qty,
                    variance=variance,
                    cost_impact=item.unit_price * variance,
                ))
            elif is_substitution:
                discrepancies.append(LineItemDiscrepancy(
                    line_id=item.line_id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    discrepancy_type=DiscrepancyType.SUBSTITUTION,
                    expected_qty=item.quantity_ordered,
                    received_qty=received_qty,
                    variance=0,
                    substitute_product_id=substitute_id,
                    substitute_name=substitute_name,
                    cost_impact=Decimal("0.00"),
                ))
            else:
                lines_matched += 1
        
        # Determine alert type and recommended action
        lines_with_discrepancy = len([d for d in discrepancies if d.discrepancy_type != DiscrepancyType.SUBSTITUTION or d.variance != 0])
        
        if lines_with_discrepancy == 0 and substitutions == 0:
            alert_type = ReceivingAlertType.RECEIVING_COMPLETE
            recommended_action = "Close PO. All items received as ordered."
        elif lines_with_discrepancy == 0 and substitutions > 0:
            alert_type = ReceivingAlertType.SUBSTITUTION_DETECTED
            recommended_action = f"Accept {substitutions} substitution(s) and close PO."
        elif short_items > 0:
            alert_type = ReceivingAlertType.RECEIVING_PARTIAL
            recommended_action = f"Accept partial. {short_items} item(s) short. Request backorder or credit."
        else:
            alert_type = ReceivingAlertType.RECEIVING_DISCREPANCY
            recommended_action = "Review discrepancies. Accept with adjustments or dispute."
        
        variance_value = total_received - total_expected
        
        return ReceivingReconciliation(
            alert_type=alert_type,
            po_id=po.po_id,
            po_number=po.po_number,
            vendor_name=po.vendor_name,
            total_lines=len(po.line_items),
            lines_matched=lines_matched,
            lines_with_discrepancy=lines_with_discrepancy,
            short_items=short_items,
            overages=overages,
            substitutions=substitutions,
            damaged_items=damaged_items,
            discrepancies=discrepancies,
            total_expected_value=total_expected,
            total_received_value=total_received,
            variance_value=variance_value,
            requires_confirmation=True,
            recommended_action=recommended_action,
        )
    
    # =========================================================================
    # ACCEPTANCE
    # =========================================================================
    
    def accept_receiving(self, request: AcceptReceivingRequest) -> ReceivingResponse:
        """
        Accept receiving with adjustments.
        
        GUARDRAIL: Never closes PO without explicit confirmation.
        """
        session = self._sessions.get(request.session_id)
        if not session:
            return ReceivingResponse(
                success=False,
                message=f"Session {request.session_id} not found",
            )
        
        po = self._purchase_orders.get(session.po_id)
        if not po:
            return ReceivingResponse(
                success=False,
                message=f"PO {session.po_id} not found",
            )
        
        # Get reconciliation
        reconciliation = self.reconcile(request.session_id)
        
        # Update PO status based on discrepancies
        if reconciliation.short_items > 0 and not request.accept_shorts:
            po.status = POStatus.PARTIALLY_RECEIVED
            message = f"PO partially received. {reconciliation.short_items} item(s) pending."
        elif request.dispute_items:
            po.status = POStatus.DISPUTED
            message = f"PO disputed. {len(request.dispute_items)} line(s) under review."
        else:
            po.status = POStatus.RECEIVED
            message = "PO received and closed."
        
        # Update received quantities on line items
        scan_totals = self._aggregate_scans_by_product(session.scans)
        for item in po.line_items:
            if item.product_id in scan_totals:
                item.quantity_received = scan_totals[item.product_id]["quantity"]
        
        # Close session
        session.status = "completed"
        
        return ReceivingResponse(
            success=True,
            message=message,
            po_id=po.po_id,
            po_status=po.status,
            reconciliation=reconciliation,
        )
    
    def clear_data(self) -> None:
        """Clear all data (for testing)."""
        self._purchase_orders.clear()
        self._sessions.clear()
        self._substitution_rules.clear()
        self._barcode_to_product.clear()
        self._product_names.clear()


# Singleton instance
receiving_engine = ReceivingEngine()
