"""
PROVENIQ Ops - Core Mock Interface
Intelligence layer: Optical Genome, Provenance Scoring, Identity Verification

This is a MOCK implementation.
In production, this would connect to the PROVENIQ Core system.

Contract:
    - Ops queries Core for item identification
    - Core provides genome vectors and identity verification
    - Core publishes genome.generated and genome.verified events
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class GenomeVectorizeRequest(BaseModel):
    """Request to generate Optical Genome from photos."""
    photos: list[str]  # Base64 encoded images
    item_type: Optional[str] = None  # "inventory", "vehicle", "equipment"


class GenomeVectorizeResponse(BaseModel):
    """Response with genome vectors."""
    genome_id: uuid.UUID
    vectors: list[float]  # 512-dim vector
    confidence: Decimal
    match_threshold: Decimal = Decimal("0.85")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    model_version: str = "genome-v2.1"


class IdentityVerifyRequest(BaseModel):
    """Request to verify asset identifiers."""
    asset_class: str  # "VEHICLE", "EQUIPMENT", "INVENTORY"
    identifiers: dict  # {"vin": "...", "serial": "...", "upc": "..."}


class IdentityVerifyResponse(BaseModel):
    """Response with identity verification result."""
    verified: bool
    source: Optional[str] = None  # "NMVTIS", "UPC_DB", "SERIAL_REGISTRY"
    issues: list[str] = []
    verified_at: datetime = Field(default_factory=datetime.utcnow)


class InventoryIdentifyRequest(BaseModel):
    """Request to identify inventory items from photos."""
    location_id: uuid.UUID
    business_id: uuid.UUID
    scan_type: str = "FULL_SHELF"  # "FULL_SHELF", "SPOT_CHECK", "SINGLE_ITEM"
    photos: list[str]  # Base64 encoded images


class IdentifiedItem(BaseModel):
    """A single identified item from scan."""
    item_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    product_name: str
    product_id: Optional[uuid.UUID] = None
    upc: Optional[str] = None
    quantity: int = 1
    confidence: Decimal
    bounding_box: Optional[dict] = None  # {"x": 0, "y": 0, "w": 100, "h": 100}


class InventoryIdentifyResponse(BaseModel):
    """Response with identified inventory items."""
    scan_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    items_detected: int
    items: list[IdentifiedItem] = []
    status: str = "COMPLETE"
    scan_duration_ms: int = 0
    completed_at: datetime = Field(default_factory=datetime.utcnow)


class ProvenanceScoreRequest(BaseModel):
    """Request to calculate provenance score."""
    item_id: uuid.UUID
    photo_count: int = 0
    receipt_count: int = 0
    warranty_count: int = 0
    genome_verified: bool = False
    ownership_transfers: int = 0
    documented_value: Optional[Decimal] = None


class ProvenanceScoreResponse(BaseModel):
    """Response with provenance score."""
    item_id: uuid.UUID
    score: int  # 0-100
    rating: str  # "EXCELLENT", "GOOD", "FAIR", "POOR"
    claim_readiness: str  # "HIGH", "MEDIUM", "LOW"
    trust_badges: list[str] = []
    fraud_flags: list[str] = []
    calculated_at: datetime = Field(default_factory=datetime.utcnow)


class GenomeMatchRequest(BaseModel):
    """Request to match genome against stored genomes."""
    genome_id: uuid.UUID
    candidate_photos: list[str]


class GenomeMatchResponse(BaseModel):
    """Response with genome match result."""
    matched: bool
    similarity_score: Decimal
    threshold: Decimal = Decimal("0.85")
    matched_genome_id: Optional[uuid.UUID] = None
    verified_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# CORE MOCK IMPLEMENTATION
# =============================================================================

class CoreMock:
    """
    Mock Proveniq Core System Interface
    
    Simulates the intelligence layer:
    - Optical Genome generation and matching
    - Provenance score calculation
    - Identity verification
    - Inventory identification from photos
    """
    
    def __init__(self) -> None:
        self._genomes: dict[uuid.UUID, GenomeVectorizeResponse] = {}
        self._items: dict[uuid.UUID, IdentifiedItem] = {}
        self._scores: dict[uuid.UUID, ProvenanceScoreResponse] = {}
        self._event_log: list[dict] = []
    
    # =========================================================================
    # GENOME OPERATIONS
    # =========================================================================
    
    async def vectorize_genome(self, request: GenomeVectorizeRequest) -> GenomeVectorizeResponse:
        """
        Generate Optical Genome vectors from photos.
        
        In production, this uses computer vision to create
        a unique fingerprint for an item.
        """
        import random
        
        # Generate mock 512-dim vector
        vectors = [random.uniform(0, 1) for _ in range(512)]
        confidence = Decimal(str(random.uniform(0.85, 0.99))).quantize(Decimal("0.01"))
        
        response = GenomeVectorizeResponse(
            genome_id=uuid.uuid4(),
            vectors=vectors,
            confidence=confidence,
        )
        
        # Store genome
        self._genomes[response.genome_id] = response
        
        # Log event
        self._log_event("genome.generated", {
            "genome_id": str(response.genome_id),
            "confidence": str(response.confidence),
            "photo_count": len(request.photos),
        })
        
        return response
    
    async def match_genome(self, request: GenomeMatchRequest) -> GenomeMatchResponse:
        """
        Match candidate photos against stored genome.
        """
        import random
        
        stored = self._genomes.get(request.genome_id)
        if not stored:
            return GenomeMatchResponse(
                matched=False,
                similarity_score=Decimal("0"),
            )
        
        # Simulate matching
        similarity = Decimal(str(random.uniform(0.7, 0.99))).quantize(Decimal("0.01"))
        matched = similarity >= Decimal("0.85")
        
        response = GenomeMatchResponse(
            matched=matched,
            similarity_score=similarity,
            matched_genome_id=request.genome_id if matched else None,
        )
        
        # Log event
        self._log_event("genome.verified", {
            "genome_id": str(request.genome_id),
            "matched": matched,
            "similarity": str(similarity),
        })
        
        return response
    
    # =========================================================================
    # IDENTITY VERIFICATION
    # =========================================================================
    
    async def verify_identity(self, request: IdentityVerifyRequest) -> IdentityVerifyResponse:
        """
        Verify asset identifiers (VIN, serial, UPC).
        """
        issues = []
        source = None
        verified = True
        
        if request.asset_class == "VEHICLE":
            vin = request.identifiers.get("vin")
            if vin:
                source = "NMVTIS"
                # Mock validation
                if len(vin) != 17:
                    issues.append("Invalid VIN length")
                    verified = False
        elif request.asset_class == "INVENTORY":
            upc = request.identifiers.get("upc")
            if upc:
                source = "UPC_DB"
                if len(upc) not in (12, 13):
                    issues.append("Invalid UPC length")
                    verified = False
        elif request.asset_class == "EQUIPMENT":
            serial = request.identifiers.get("serial")
            if serial:
                source = "SERIAL_REGISTRY"
        
        return IdentityVerifyResponse(
            verified=verified,
            source=source,
            issues=issues,
        )
    
    # =========================================================================
    # INVENTORY IDENTIFICATION
    # =========================================================================
    
    async def identify_inventory(self, request: InventoryIdentifyRequest) -> InventoryIdentifyResponse:
        """
        Identify inventory items from shelf photos.
        
        This is the primary Ops integration point with Core.
        """
        import random
        
        # Simulate item detection
        items = []
        
        # Mock product database
        mock_products = [
            ("Chicken Breast", "0012345678901", Decimal("0.95")),
            ("Ground Beef", "0012345678902", Decimal("0.92")),
            ("Tomatoes", "0094012345678", Decimal("0.88")),
            ("Lettuce", "0094012345679", Decimal("0.91")),
            ("Olive Oil", "0012345678903", Decimal("0.97")),
            ("Salt", "0012345678904", Decimal("0.99")),
            ("Flour", "0012345678905", Decimal("0.94")),
            ("Sugar", "0012345678906", Decimal("0.96")),
        ]
        
        # Detect 5-15 items based on scan type
        num_items = random.randint(5, 15) if request.scan_type == "FULL_SHELF" else random.randint(1, 5)
        
        for i in range(min(num_items, len(mock_products))):
            name, upc, base_conf = mock_products[i]
            conf_variance = Decimal(str(random.uniform(-0.05, 0.05)))
            confidence = max(Decimal("0.70"), min(Decimal("0.99"), base_conf + conf_variance))
            
            item = IdentifiedItem(
                product_name=name,
                product_id=uuid.uuid4(),
                upc=upc,
                quantity=random.randint(1, 20),
                confidence=confidence.quantize(Decimal("0.01")),
                bounding_box={"x": i * 100, "y": 0, "w": 80, "h": 120},
            )
            items.append(item)
            self._items[item.item_id] = item
        
        response = InventoryIdentifyResponse(
            items_detected=len(items),
            items=items,
            scan_duration_ms=random.randint(500, 2000),
        )
        
        # Log events for each item
        for item in items:
            self._log_event("ops.item.detected", {
                "scan_id": str(response.scan_id),
                "item_id": str(item.item_id),
                "product_name": item.product_name,
                "confidence": str(item.confidence),
            })
        
        return response
    
    # =========================================================================
    # PROVENANCE SCORING
    # =========================================================================
    
    async def calculate_provenance_score(self, request: ProvenanceScoreRequest) -> ProvenanceScoreResponse:
        """
        Calculate provenance score from evidence.
        
        Formula:
        score = (genome_confidence × 0.4) + 
                (ownership_history × 0.2) + 
                (custody_chain × 0.2) + 
                (documentation × 0.2)
        """
        # Calculate score components
        genome_score = 40 if request.genome_verified else 0
        
        # Ownership history (max 20 points, -5 per transfer beyond 1)
        ownership_score = max(0, 20 - (request.ownership_transfers - 1) * 5) if request.ownership_transfers > 0 else 15
        
        # Documentation score (photos + receipts + warranties)
        doc_points = min(request.photo_count * 2, 10) + min(request.receipt_count * 5, 5) + min(request.warranty_count * 5, 5)
        doc_score = min(20, doc_points)
        
        # Custody chain (assume 20 for now - would come from Ledger)
        custody_score = 20
        
        total_score = genome_score + ownership_score + doc_score + custody_score
        
        # Determine rating
        if total_score >= 80:
            rating = "EXCELLENT"
            claim_readiness = "HIGH"
        elif total_score >= 60:
            rating = "GOOD"
            claim_readiness = "HIGH"
        elif total_score >= 40:
            rating = "FAIR"
            claim_readiness = "MEDIUM"
        else:
            rating = "POOR"
            claim_readiness = "LOW"
        
        # Trust badges
        trust_badges = []
        if request.genome_verified:
            trust_badges.append("GENOME_VERIFIED")
        if request.receipt_count > 0:
            trust_badges.append("ORIGINAL_RECEIPT")
        if request.warranty_count > 0:
            trust_badges.append("WARRANTY_ACTIVE")
        if request.photo_count >= 5:
            trust_badges.append("MULTI_DOCUMENTED")
        
        response = ProvenanceScoreResponse(
            item_id=request.item_id,
            score=total_score,
            rating=rating,
            claim_readiness=claim_readiness,
            trust_badges=trust_badges,
        )
        
        self._scores[request.item_id] = response
        
        # Log event
        self._log_event("score.updated", {
            "item_id": str(request.item_id),
            "score": total_score,
            "rating": rating,
        })
        
        return response
    
    # =========================================================================
    # UTILITIES
    # =========================================================================
    
    def _log_event(self, event_type: str, payload: dict) -> None:
        """Log an event for the event bus."""
        self._event_log.append({
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload,
        })
    
    def get_event_log(self) -> list[dict]:
        """Return event log."""
        return self._event_log.copy()
    
    def get_genome(self, genome_id: uuid.UUID) -> Optional[GenomeVectorizeResponse]:
        """Get stored genome."""
        return self._genomes.get(genome_id)
    
    def reset(self) -> None:
        """Reset mock state."""
        self._genomes.clear()
        self._items.clear()
        self._scores.clear()
        self._event_log.clear()


# Singleton instance
core_mock_instance = CoreMock()
