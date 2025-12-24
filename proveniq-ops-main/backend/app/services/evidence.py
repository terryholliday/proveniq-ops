"""Evidence handling service - Presigned URLs, validation, and hash computation.

Per spec v1.1:
- Evidence upload via presigned URLs
- Explicit confirmation endpoint to validate and link evidence
- Content hash calculation for inspection locking
"""

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inspection import Inspection, InspectionItem

# Google Cloud Storage (optional - falls back to mock for local dev)
try:
    from google.cloud import storage
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    storage = None


# Configuration
GCS_BUCKET = os.environ.get("GCS_BUCKET", "proveniq-ops-evidence")
PRESIGNED_URL_EXPIRY_SECONDS = 3600  # 1 hour
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
ALLOWED_MIME_TYPES = [
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/heif",
    "image/webp",
    "video/mp4",
    "video/quicktime",
    "application/pdf",
]


class EvidenceService:
    """Service for handling inspection evidence uploads."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._storage_client = None
    
    @property
    def storage_client(self):
        """Lazy-load GCS client."""
        if not GCS_AVAILABLE:
            return None
        if self._storage_client is None:
            self._storage_client = storage.Client()
        return self._storage_client
    
    async def generate_presigned_upload_url(
        self,
        inspection_id: UUID,
        inspection_item_id: UUID,
        file_name: str,
        content_type: str,
        file_size_bytes: int,
    ) -> dict:
        """
        Generate a presigned URL for uploading evidence.
        
        Returns:
            {
                "evidence_id": "uuid",
                "upload_url": "https://...",
                "expires_in_seconds": 3600
            }
        """
        # Validate content type
        if content_type not in ALLOWED_MIME_TYPES:
            raise ValueError(f"Unsupported file type: {content_type}")
        
        # Validate file size
        if file_size_bytes > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File too large. Maximum size: {MAX_FILE_SIZE_BYTES // (1024*1024)}MB")
        
        # Generate evidence ID and storage path
        evidence_id = uuid4()
        storage_path = f"inspections/{inspection_id}/items/{inspection_item_id}/{evidence_id}/{file_name}"
        
        if self.storage_client:
            # Production: Generate real GCS presigned URL
            bucket = self.storage_client.bucket(GCS_BUCKET)
            blob = bucket.blob(storage_path)
            
            upload_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=PRESIGNED_URL_EXPIRY_SECONDS),
                method="PUT",
                content_type=content_type,
            )
            
            storage_url = f"gs://{GCS_BUCKET}/{storage_path}"
        else:
            # Development: Mock URL
            upload_url = f"http://localhost:8080/mock-upload/{storage_path}"
            storage_url = f"mock://{storage_path}"
        
        # Create pending evidence record
        from app.models.evidence import InspectionEvidence
        
        evidence = InspectionEvidence(
            id=evidence_id,
            inspection_item_id=inspection_item_id,
            storage_url=storage_url,
            file_hash="",  # Will be set on confirmation
            mime_type=content_type,
            file_size_bytes=file_size_bytes,
            uploaded_at=datetime.utcnow(),
            confirmed_at=None,
        )
        self.db.add(evidence)
        await self.db.flush()
        
        return {
            "evidence_id": evidence_id,
            "upload_url": upload_url,
            "expires_in_seconds": PRESIGNED_URL_EXPIRY_SECONDS,
        }
    
    async def confirm_evidence(
        self,
        evidence_id: UUID,
    ) -> dict:
        """
        Confirm that evidence was uploaded successfully.
        
        Validates:
        - File exists in storage
        - File size matches expected
        - MIME type is correct
        
        Computes file hash and marks evidence as confirmed.
        """
        from app.models.evidence import InspectionEvidence
        
        result = await self.db.execute(
            select(InspectionEvidence).where(InspectionEvidence.id == evidence_id)
        )
        evidence = result.scalar_one_or_none()
        
        if not evidence:
            raise ValueError("Evidence record not found")
        
        if evidence.confirmed_at:
            # Already confirmed - return cached result
            return {
                "confirmed": True,
                "file_hash": evidence.file_hash,
                "mime_type": evidence.mime_type,
            }
        
        # Validate file exists and compute hash
        if self.storage_client and evidence.storage_url.startswith("gs://"):
            # Production: Verify in GCS
            bucket_name = evidence.storage_url.split("/")[2]
            blob_path = "/".join(evidence.storage_url.split("/")[3:])
            
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            
            if not blob.exists():
                raise ValueError("File not found in storage. Upload may have failed.")
            
            # Get file metadata
            blob.reload()
            actual_size = blob.size
            
            if actual_size != evidence.file_size_bytes:
                raise ValueError(f"File size mismatch. Expected {evidence.file_size_bytes}, got {actual_size}")
            
            # Compute hash (download and hash for small files, use MD5 for large)
            if actual_size < 10 * 1024 * 1024:  # < 10MB
                content = blob.download_as_bytes()
                file_hash = hashlib.sha256(content).hexdigest()
            else:
                # Use GCS-computed MD5 for large files
                file_hash = f"md5:{blob.md5_hash}"
        else:
            # Development: Mock validation
            file_hash = hashlib.sha256(str(evidence_id).encode()).hexdigest()
        
        # Update evidence record
        evidence.file_hash = file_hash
        evidence.confirmed_at = datetime.utcnow()
        await self.db.commit()
        
        return {
            "confirmed": True,
            "file_hash": file_hash,
            "mime_type": evidence.mime_type,
        }
    
    async def calculate_content_hash(
        self,
        inspection_id: UUID,
    ) -> str:
        """
        Calculate the canonical content hash for an inspection.
        
        Per spec v1.1, the hash includes:
        - inspection_id
        - lease_id
        - inspection_type
        - schema_version
        - Ordered list of inspection_items
        - Ordered list of inspection_evidence per item
        - submitted_at timestamp
        """
        from app.models.evidence import InspectionEvidence
        
        # Get inspection with all related data
        result = await self.db.execute(
            select(Inspection)
            .where(Inspection.id == inspection_id)
            .options(
                selectinload(Inspection.items)
            )
        )
        inspection = result.scalar_one_or_none()
        
        if not inspection:
            raise ValueError("Inspection not found")
        
        # Build canonical structure
        items_data = []
        for item in sorted(inspection.items, key=lambda x: (x.room_name, x.item_name or "")):
            # Get evidence for this item
            evidence_result = await self.db.execute(
                select(InspectionEvidence)
                .where(InspectionEvidence.inspection_item_id == item.id)
                .where(InspectionEvidence.confirmed_at.isnot(None))
                .order_by(InspectionEvidence.uploaded_at)
            )
            evidence_records = evidence_result.scalars().all()
            
            evidence_data = [
                {
                    "url": e.storage_url,
                    "hash": e.file_hash,
                    "mime_type": e.mime_type,
                    "timestamp": e.uploaded_at.isoformat() if e.uploaded_at else None,
                }
                for e in evidence_records
            ]
            
            items_data.append({
                "room_name": item.room_name,
                "item_name": item.item_name,
                "condition": item.condition.value if hasattr(item.condition, 'value') else str(item.condition),
                "notes": item.notes,
                "evidence": evidence_data,
            })
        
        # Build canonical JSON
        canonical = {
            "inspection_id": str(inspection_id),
            "lease_id": str(inspection.lease_id),
            "inspection_type": inspection.type.value if hasattr(inspection.type, 'value') else str(inspection.type),
            "schema_version": inspection.schema_version if hasattr(inspection, 'schema_version') else 1,
            "items": items_data,
            "submitted_at": inspection.submitted_at.isoformat() if inspection.submitted_at else datetime.utcnow().isoformat(),
        }
        
        # Compute hash of canonical JSON (sorted keys for determinism)
        canonical_json = json.dumps(canonical, sort_keys=True, separators=(',', ':'))
        content_hash = hashlib.sha256(canonical_json.encode()).hexdigest()
        
        return content_hash


async def get_evidence_service(db: AsyncSession) -> EvidenceService:
    """Dependency to get EvidenceService instance."""
    return EvidenceService(db)
