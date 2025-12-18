"""
PROVENIQ Ops - Bishop Audit Readiness Engine
Continuously detect documentation or compliance gaps before audits.

LOGIC:
1. Validate completeness against audit schema
2. Flag missing or weak evidence
3. Recommend remediation steps
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.models.auditready import (
    ApprovalRecord,
    AuditCategory,
    AuditReadinessConfig,
    AuditReadinessResult,
    AuditRequirement,
    AuditSchema,
    CategoryScore,
    ComplianceGap,
    ComplianceStatus,
    EvidenceAsset,
    EvidenceType,
    GapSeverity,
    InventoryRecord,
    RemediationPriority,
    RemediationStep,
    WasteLogEntry,
)


# =============================================================================
# DEFAULT AUDIT SCHEMA
# =============================================================================

DEFAULT_REQUIREMENTS: list[dict] = [
    # Food Safety
    {
        "category": AuditCategory.FOOD_SAFETY,
        "code": "FS-001",
        "name": "Temperature Logs",
        "description": "Walk-in cooler temperature logged every 4 hours",
        "required_evidence": [EvidenceType.TEMPERATURE_LOG, EvidenceType.TIMESTAMP],
        "frequency": "every_4_hours",
        "weight": 15,
        "critical": True,
    },
    {
        "category": AuditCategory.FOOD_SAFETY,
        "code": "FS-002",
        "name": "Receiving Temperature Check",
        "description": "Temperature check on cold deliveries",
        "required_evidence": [EvidenceType.TEMPERATURE_LOG, EvidenceType.SIGNATURE],
        "frequency": "per_delivery",
        "weight": 10,
        "critical": True,
    },
    {
        "category": AuditCategory.FOOD_SAFETY,
        "code": "FS-003",
        "name": "Date Labels",
        "description": "All prep items properly date-labeled",
        "required_evidence": [EvidenceType.PHOTO],
        "frequency": "daily",
        "weight": 10,
    },
    
    # Inventory
    {
        "category": AuditCategory.INVENTORY,
        "code": "INV-001",
        "name": "Weekly Inventory Count",
        "description": "Full inventory count completed weekly",
        "required_evidence": [EvidenceType.SCAN_RECORD, EvidenceType.SIGNATURE],
        "frequency": "weekly",
        "weight": 15,
    },
    {
        "category": AuditCategory.INVENTORY,
        "code": "INV-002",
        "name": "High-Value Item Tracking",
        "description": "Daily count of high-value items",
        "required_evidence": [EvidenceType.SCAN_RECORD],
        "frequency": "daily",
        "weight": 10,
    },
    {
        "category": AuditCategory.INVENTORY,
        "code": "INV-003",
        "name": "Variance Documentation",
        "description": "All inventory variances >5% documented",
        "required_evidence": [EvidenceType.DOCUMENT, EvidenceType.SIGNATURE],
        "frequency": "per_occurrence",
        "weight": 10,
    },
    
    # Waste
    {
        "category": AuditCategory.WASTE,
        "code": "WST-001",
        "name": "Waste Log Entries",
        "description": "All waste logged with reason",
        "required_evidence": [EvidenceType.DOCUMENT],
        "frequency": "per_occurrence",
        "weight": 10,
    },
    {
        "category": AuditCategory.WASTE,
        "code": "WST-002",
        "name": "Waste Photo Documentation",
        "description": "Photo evidence for waste >$20",
        "required_evidence": [EvidenceType.PHOTO],
        "frequency": "per_occurrence",
        "weight": 5,
    },
    {
        "category": AuditCategory.WASTE,
        "code": "WST-003",
        "name": "Manager Waste Approval",
        "description": "Manager approval for waste >$50",
        "required_evidence": [EvidenceType.SIGNATURE],
        "frequency": "per_occurrence",
        "weight": 10,
    },
    
    # Receiving
    {
        "category": AuditCategory.RECEIVING,
        "code": "RCV-001",
        "name": "Delivery Verification",
        "description": "All deliveries verified against PO",
        "required_evidence": [EvidenceType.RECEIPT, EvidenceType.SIGNATURE],
        "frequency": "per_delivery",
        "weight": 10,
    },
    {
        "category": AuditCategory.RECEIVING,
        "code": "RCV-002",
        "name": "Inspection Documentation",
        "description": "Quality inspection documented",
        "required_evidence": [EvidenceType.DOCUMENT],
        "frequency": "per_delivery",
        "weight": 5,
    },
    
    # Vendor
    {
        "category": AuditCategory.VENDOR,
        "code": "VND-001",
        "name": "Vendor Certificates",
        "description": "Current food safety certificates on file",
        "required_evidence": [EvidenceType.CERTIFICATE],
        "frequency": "annual",
        "weight": 10,
        "retention_days": 365,
    },
]


class AuditReadinessEngine:
    """
    Bishop Audit Readiness Engine
    
    Continuously detects documentation or compliance gaps before audits.
    """
    
    def __init__(self) -> None:
        self._config = AuditReadinessConfig()
        self._schema = self._build_default_schema()
        
        # Evidence storage
        self._evidence: list[EvidenceAsset] = []
        self._inventory_records: list[InventoryRecord] = []
        self._waste_logs: list[WasteLogEntry] = []
        self._approvals: list[ApprovalRecord] = []
        
        # Gap tracking
        self._detected_gaps: list[ComplianceGap] = []
    
    def _build_default_schema(self) -> AuditSchema:
        """Build the default audit schema."""
        requirements = []
        total_points = 0
        
        for req_data in DEFAULT_REQUIREMENTS:
            req = AuditRequirement(
                category=req_data["category"],
                code=req_data["code"],
                name=req_data["name"],
                description=req_data["description"],
                required_evidence=req_data["required_evidence"],
                frequency=req_data.get("frequency", "daily"),
                weight=req_data.get("weight", 10),
                critical=req_data.get("critical", False),
                retention_days=req_data.get("retention_days", 365),
            )
            requirements.append(req)
            total_points += req.weight
        
        return AuditSchema(
            schema_name="Standard Food Service Audit",
            requirements=requirements,
            total_points=total_points,
        )
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure(self, config: AuditReadinessConfig) -> None:
        """Update configuration."""
        self._config = config
    
    def get_config(self) -> AuditReadinessConfig:
        """Get current configuration."""
        return self._config
    
    def get_schema(self) -> AuditSchema:
        """Get current audit schema."""
        return self._schema
    
    # =========================================================================
    # DATA REGISTRATION
    # =========================================================================
    
    def register_evidence(self, evidence: EvidenceAsset) -> None:
        """Register a piece of evidence."""
        self._evidence.append(evidence)
    
    def register_inventory_record(self, record: InventoryRecord) -> None:
        """Register an inventory record."""
        self._inventory_records.append(record)
    
    def register_waste_log(self, entry: WasteLogEntry) -> None:
        """Register a waste log entry."""
        self._waste_logs.append(entry)
    
    def register_approval(self, approval: ApprovalRecord) -> None:
        """Register an approval record."""
        self._approvals.append(approval)
    
    # =========================================================================
    # GAP DETECTION (Step 2)
    # =========================================================================
    
    def _detect_gaps(self, period_start: datetime, period_end: datetime) -> list[ComplianceGap]:
        """Detect all compliance gaps in the period."""
        gaps = []
        
        for req in self._schema.requirements:
            req_gaps = self._check_requirement(req, period_start, period_end)
            gaps.extend(req_gaps)
        
        self._detected_gaps = gaps
        return gaps
    
    def _check_requirement(
        self,
        req: AuditRequirement,
        period_start: datetime,
        period_end: datetime,
    ) -> list[ComplianceGap]:
        """Check a single requirement for gaps."""
        gaps = []
        
        # Get relevant evidence for this requirement
        relevant_evidence = [
            e for e in self._evidence
            if e.category == req.category
            and e.evidence_type in req.required_evidence
            and period_start <= e.captured_at <= period_end
        ]
        
        # Check based on frequency
        if req.frequency == "daily":
            gaps.extend(self._check_daily_requirement(req, relevant_evidence, period_start, period_end))
        elif req.frequency == "weekly":
            gaps.extend(self._check_weekly_requirement(req, relevant_evidence, period_start, period_end))
        elif req.frequency == "every_4_hours":
            gaps.extend(self._check_periodic_requirement(req, relevant_evidence, period_start, period_end, 4))
        elif req.frequency == "per_delivery":
            gaps.extend(self._check_delivery_requirement(req, relevant_evidence, period_start, period_end))
        elif req.frequency == "per_occurrence":
            gaps.extend(self._check_occurrence_requirement(req, period_start, period_end))
        
        return gaps
    
    def _check_daily_requirement(
        self,
        req: AuditRequirement,
        evidence: list[EvidenceAsset],
        period_start: datetime,
        period_end: datetime,
    ) -> list[ComplianceGap]:
        """Check daily requirements."""
        gaps = []
        current = period_start
        
        while current < period_end:
            day_start = current.replace(hour=0, minute=0, second=0)
            day_end = day_start + timedelta(days=1)
            
            day_evidence = [e for e in evidence if day_start <= e.captured_at < day_end]
            
            if len(day_evidence) < req.min_evidence_count:
                gap = ComplianceGap(
                    requirement_id=req.requirement_id,
                    requirement_code=req.code,
                    requirement_name=req.name,
                    category=req.category,
                    gap_type="missing_evidence",
                    gap_description=f"Missing {req.name} for {day_start.date()}",
                    severity=GapSeverity.CRITICAL if req.critical else GapSeverity.HIGH,
                    is_critical=req.critical,
                    points_at_risk=req.weight,
                    period_start=day_start,
                    period_end=day_end,
                )
                gaps.append(gap)
            
            current = day_end
        
        return gaps
    
    def _check_weekly_requirement(
        self,
        req: AuditRequirement,
        evidence: list[EvidenceAsset],
        period_start: datetime,
        period_end: datetime,
    ) -> list[ComplianceGap]:
        """Check weekly requirements."""
        gaps = []
        
        # Check each week in period
        current = period_start
        while current < period_end:
            week_end = current + timedelta(days=7)
            week_evidence = [e for e in evidence if current <= e.captured_at < week_end]
            
            if len(week_evidence) < req.min_evidence_count:
                gap = ComplianceGap(
                    requirement_id=req.requirement_id,
                    requirement_code=req.code,
                    requirement_name=req.name,
                    category=req.category,
                    gap_type="missing_evidence",
                    gap_description=f"Missing {req.name} for week of {current.date()}",
                    severity=GapSeverity.HIGH,
                    points_at_risk=req.weight,
                    period_start=current,
                    period_end=week_end,
                )
                gaps.append(gap)
            
            current = week_end
        
        return gaps
    
    def _check_periodic_requirement(
        self,
        req: AuditRequirement,
        evidence: list[EvidenceAsset],
        period_start: datetime,
        period_end: datetime,
        hours: int,
    ) -> list[ComplianceGap]:
        """Check periodic (every N hours) requirements."""
        gaps = []
        
        # Sort evidence by time
        sorted_evidence = sorted(evidence, key=lambda e: e.captured_at)
        
        if not sorted_evidence:
            # No evidence at all
            gap = ComplianceGap(
                requirement_id=req.requirement_id,
                requirement_code=req.code,
                requirement_name=req.name,
                category=req.category,
                gap_type="missing_evidence",
                gap_description=f"No {req.name} found in period",
                severity=GapSeverity.CRITICAL if req.critical else GapSeverity.HIGH,
                is_critical=req.critical,
                points_at_risk=req.weight,
                period_start=period_start,
                period_end=period_end,
            )
            gaps.append(gap)
            return gaps
        
        # Check for gaps between evidence
        max_gap_hours = hours + 1  # Allow 1 hour grace
        
        # Check gap from period start
        first_evidence = sorted_evidence[0]
        if (first_evidence.captured_at - period_start).total_seconds() / 3600 > max_gap_hours:
            gap = ComplianceGap(
                requirement_id=req.requirement_id,
                requirement_code=req.code,
                requirement_name=req.name,
                category=req.category,
                gap_type="late",
                gap_description=f"{req.name} not recorded at start of period",
                severity=GapSeverity.MEDIUM,
                points_at_risk=req.weight // 2,
                period_start=period_start,
                period_end=first_evidence.captured_at,
            )
            gaps.append(gap)
        
        # Check gaps between evidence
        for i in range(len(sorted_evidence) - 1):
            curr = sorted_evidence[i]
            next_ev = sorted_evidence[i + 1]
            gap_hours = (next_ev.captured_at - curr.captured_at).total_seconds() / 3600
            
            if gap_hours > max_gap_hours:
                gap = ComplianceGap(
                    requirement_id=req.requirement_id,
                    requirement_code=req.code,
                    requirement_name=req.name,
                    category=req.category,
                    gap_type="time_gap",
                    gap_description=f"{req.name} gap of {gap_hours:.1f}h (max: {hours}h)",
                    severity=GapSeverity.HIGH if req.critical else GapSeverity.MEDIUM,
                    points_at_risk=req.weight // 2,
                    period_start=curr.captured_at,
                    period_end=next_ev.captured_at,
                )
                gaps.append(gap)
        
        return gaps
    
    def _check_delivery_requirement(
        self,
        req: AuditRequirement,
        evidence: list[EvidenceAsset],
        period_start: datetime,
        period_end: datetime,
    ) -> list[ComplianceGap]:
        """Check per-delivery requirements."""
        gaps = []
        
        # Look at receiving-category evidence
        receiving_evidence = [
            e for e in self._evidence
            if e.category == AuditCategory.RECEIVING
            and period_start <= e.captured_at <= period_end
        ]
        
        # Check if required evidence types present
        for ev_type in req.required_evidence:
            type_evidence = [e for e in evidence if e.evidence_type == ev_type]
            
            if not type_evidence and receiving_evidence:
                gap = ComplianceGap(
                    requirement_id=req.requirement_id,
                    requirement_code=req.code,
                    requirement_name=req.name,
                    category=req.category,
                    gap_type="incomplete",
                    gap_description=f"Missing {ev_type.value} for {req.name}",
                    severity=GapSeverity.HIGH if req.critical else GapSeverity.MEDIUM,
                    is_critical=req.critical,
                    points_at_risk=req.weight,
                )
                gaps.append(gap)
        
        return gaps
    
    def _check_occurrence_requirement(
        self,
        req: AuditRequirement,
        period_start: datetime,
        period_end: datetime,
    ) -> list[ComplianceGap]:
        """Check per-occurrence requirements (waste, adjustments, etc.)."""
        gaps = []
        
        # Check waste logs
        if req.category == AuditCategory.WASTE:
            for waste in self._waste_logs:
                if period_start <= waste.wasted_at <= period_end:
                    # Check photo requirement
                    if EvidenceType.PHOTO in req.required_evidence and not waste.has_photo:
                        gap = ComplianceGap(
                            requirement_id=req.requirement_id,
                            requirement_code=req.code,
                            requirement_name=req.name,
                            category=req.category,
                            gap_type="missing_evidence",
                            gap_description=f"Missing photo for waste: {waste.product_name}",
                            severity=GapSeverity.MEDIUM,
                            points_at_risk=req.weight,
                        )
                        gaps.append(gap)
                    
                    # Check approval requirement
                    if EvidenceType.SIGNATURE in req.required_evidence and not waste.manager_approved:
                        gap = ComplianceGap(
                            requirement_id=req.requirement_id,
                            requirement_code=req.code,
                            requirement_name=req.name,
                            category=req.category,
                            gap_type="missing_evidence",
                            gap_description=f"Missing manager approval for waste: {waste.product_name}",
                            severity=GapSeverity.HIGH,
                            points_at_risk=req.weight,
                        )
                        gaps.append(gap)
        
        return gaps
    
    # =========================================================================
    # REMEDIATION (Step 3)
    # =========================================================================
    
    def _generate_remediation(self, gaps: list[ComplianceGap]) -> list[RemediationStep]:
        """Generate remediation steps for detected gaps."""
        steps = []
        
        for gap in gaps:
            priority = self._determine_priority(gap)
            action, description, minutes = self._get_remediation_action(gap)
            
            step = RemediationStep(
                gap_id=gap.gap_id,
                action=action,
                description=description,
                priority=priority,
                estimated_minutes=minutes,
                requires_approval=gap.is_critical,
            )
            steps.append(step)
        
        return steps
    
    def _determine_priority(self, gap: ComplianceGap) -> RemediationPriority:
        """Determine remediation priority based on gap severity."""
        if gap.is_critical:
            return RemediationPriority.IMMEDIATE
        
        priority_map = {
            GapSeverity.CRITICAL: RemediationPriority.IMMEDIATE,
            GapSeverity.HIGH: RemediationPriority.URGENT,
            GapSeverity.MEDIUM: RemediationPriority.HIGH,
            GapSeverity.LOW: RemediationPriority.NORMAL,
            GapSeverity.INFO: RemediationPriority.LOW,
        }
        return priority_map.get(gap.severity, RemediationPriority.NORMAL)
    
    def _get_remediation_action(self, gap: ComplianceGap) -> tuple[str, str, int]:
        """Get remediation action, description, and estimated minutes."""
        actions = {
            "missing_evidence": (
                "Collect missing evidence",
                f"Document {gap.requirement_name} with required evidence types",
                15,
            ),
            "time_gap": (
                "Establish regular logging",
                f"Set up reminders to log {gap.requirement_name} at required intervals",
                10,
            ),
            "late": (
                "Backfill documentation",
                f"Complete late {gap.requirement_name} documentation",
                20,
            ),
            "incomplete": (
                "Complete documentation",
                f"Add missing elements to {gap.requirement_name}",
                15,
            ),
            "expired": (
                "Renew certification",
                f"Obtain updated {gap.requirement_name}",
                60,
            ),
        }
        
        return actions.get(gap.gap_type, (
            "Review and correct",
            f"Review {gap.requirement_name} and correct issues",
            30,
        ))
    
    # =========================================================================
    # ASSESSMENT (Main Entry Point)
    # =========================================================================
    
    def assess_readiness(
        self,
        period_days: Optional[int] = None,
    ) -> AuditReadinessResult:
        """
        Run complete audit readiness assessment.
        
        Returns score, gaps, and remediation steps.
        """
        period_days = period_days or self._config.lookback_days
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=period_days)
        
        # Step 1 & 2: Detect gaps
        gaps = self._detect_gaps(period_start, period_end)
        
        # Step 3: Generate remediation
        remediation = self._generate_remediation(gaps)
        
        # Calculate scores
        category_scores = self._calculate_category_scores(gaps)
        
        total_max = self._schema.total_points
        total_lost = sum(g.points_at_risk for g in gaps)
        compliance_score = max(0, min(100, int(100 * (total_max - total_lost) / total_max)))
        risk_score = 100 - compliance_score
        
        # Count critical gaps
        critical_gaps = len([g for g in gaps if g.is_critical])
        
        # Would pass audit?
        would_pass = compliance_score >= self._config.passing_score and critical_gaps == 0
        
        # Build missing evidence list
        missing_evidence = list(set(g.gap_description for g in gaps if g.gap_type == "missing_evidence"))
        
        # Build recommended fixes
        recommended_fixes = [
            f"[{s.priority.value.upper()}] {s.action}: {s.description}"
            for s in sorted(remediation, key=lambda x: x.priority.value)[:10]
        ]
        
        # Estimate remediation time
        total_minutes = sum(s.estimated_minutes for s in remediation)
        estimated_hours = Decimal(str(total_minutes / 60)).quantize(Decimal("0.1"))
        
        # Summary
        if would_pass:
            summary = f"Audit ready. Compliance score: {compliance_score}%"
        elif critical_gaps > 0:
            summary = f"CRITICAL: {critical_gaps} critical gap(s) must be resolved. Score: {compliance_score}%"
        else:
            summary = f"Needs attention. {len(gaps)} gap(s) found. Score: {compliance_score}%"
        
        return AuditReadinessResult(
            audit_risk_score=risk_score,
            compliance_score=compliance_score,
            would_pass_audit=would_pass,
            passing_threshold=self._config.passing_score,
            missing_evidence=missing_evidence,
            recommended_fixes=recommended_fixes,
            category_scores=category_scores,
            total_gaps=len(gaps),
            critical_gaps=critical_gaps,
            gaps=gaps,
            remediation_steps=remediation,
            estimated_remediation_hours=estimated_hours,
            summary=summary,
        )
    
    def _calculate_category_scores(self, gaps: list[ComplianceGap]) -> list[CategoryScore]:
        """Calculate scores by category."""
        scores = []
        
        # Group requirements by category
        by_category: dict[AuditCategory, list[AuditRequirement]] = defaultdict(list)
        for req in self._schema.requirements:
            by_category[req.category].append(req)
        
        # Group gaps by category
        gaps_by_category: dict[AuditCategory, list[ComplianceGap]] = defaultdict(list)
        for gap in gaps:
            gaps_by_category[gap.category].append(gap)
        
        for category, reqs in by_category.items():
            max_points = sum(r.weight for r in reqs)
            cat_gaps = gaps_by_category.get(category, [])
            lost_points = sum(g.points_at_risk for g in cat_gaps)
            earned = max(0, max_points - lost_points)
            
            pct = Decimal(str(100 * earned / max_points)) if max_points > 0 else Decimal("100")
            
            if pct >= 90:
                status = ComplianceStatus.COMPLIANT
            elif pct >= 70:
                status = ComplianceStatus.PARTIAL
            else:
                status = ComplianceStatus.NON_COMPLIANT
            
            critical = len([g for g in cat_gaps if g.is_critical])
            
            scores.append(CategoryScore(
                category=category,
                max_points=max_points,
                earned_points=earned,
                score_pct=pct.quantize(Decimal("0.1")),
                status=status,
                gap_count=len(cat_gaps),
                critical_gaps=critical,
            ))
        
        return sorted(scores, key=lambda s: s.score_pct)
    
    def clear_data(self) -> None:
        """Clear all data (for testing)."""
        self._evidence.clear()
        self._inventory_records.clear()
        self._waste_logs.clear()
        self._approvals.clear()
        self._detected_gaps.clear()


# Singleton instance
auditready_engine = AuditReadinessEngine()
