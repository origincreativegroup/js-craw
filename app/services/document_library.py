"""Services for ingesting and managing user-provided documents"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import UploadFile
from pdfminer.high_level import extract_text
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserDocument, UserProfile

logger = logging.getLogger(__name__)


class DocumentIngestionError(Exception):
    """Raised when a document cannot be ingested"""


class UserDocumentService:
    """Manage uploads and retrieval of user documents"""

    SUPPORTED_TYPES = {"text/plain", "text/markdown", "text/csv", "application/pdf"}

    def __init__(self, db: AsyncSession):
        self.db = db

    async def ensure_profile(self) -> UserProfile:
        """Return the default user profile or raise if not present"""

        result = await self.db.execute(select(UserProfile).where(UserProfile.user_id == 1))
        profile = result.scalar_one_or_none()
        if not profile:
            raise DocumentIngestionError("User profile not found. Please create a profile first.")
        return profile

    async def list_documents(self) -> List[UserDocument]:
        result = await self.db.execute(
            select(UserDocument).order_by(UserDocument.created_at.desc())
        )
        return result.scalars().all()

    async def get_document(self, document_id: int) -> Optional[UserDocument]:
        result = await self.db.execute(select(UserDocument).where(UserDocument.id == document_id))
        return result.scalar_one_or_none()

    async def delete_document(self, document_id: int) -> bool:
        doc = await self.get_document(document_id)
        if not doc:
            return False
        await self.db.delete(doc)
        await self.db.commit()
        return True

    async def update_document(self, document_id: int, content: str, metadata: Optional[Dict] = None) -> Optional[UserDocument]:
        doc = await self.get_document(document_id)
        if not doc:
            return None
        doc.content = content
        doc.metadata_json = metadata or doc.metadata_json
        doc.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def ingest_upload(self, file: UploadFile) -> UserDocument:
        """Ingest a single uploaded file"""

        profile = await self.ensure_profile()
        raw_bytes = await file.read()
        if not raw_bytes:
            raise DocumentIngestionError("Uploaded file is empty")

        content_type = file.content_type or self._guess_mimetype(file.filename)
        if content_type not in self.SUPPORTED_TYPES:
            raise DocumentIngestionError(f"Unsupported file type: {content_type}")

        extracted_text, metadata = self._extract_text(raw_bytes, content_type, file.filename)

        document = UserDocument(
            user_profile_id=profile.id if profile else None,
            filename=file.filename or "document",
            file_type=content_type,
            content=extracted_text,
            raw_file=raw_bytes,
            metadata_json=metadata,
        )

        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        return document

    def _guess_mimetype(self, filename: Optional[str]) -> str:
        if not filename:
            return "text/plain"
        if filename.lower().endswith(".md"):
            return "text/markdown"
        if filename.lower().endswith(".csv"):
            return "text/csv"
        if filename.lower().endswith(".pdf"):
            return "application/pdf"
        return "text/plain"

    def _extract_text(self, raw: bytes, content_type: str, filename: Optional[str]) -> (str, Dict):
        """Extract plain text and metadata from the raw file"""

        metadata: Dict[str, Optional[str]] = {
            "source_filename": filename,
            "content_type": content_type,
        }

        if content_type == "application/pdf":
            try:
                with io.BytesIO(raw) as buffer:
                    text = extract_text(buffer)
                metadata["extraction_method"] = "pdfminer"
            except Exception as exc:  # pragma: no cover - pdf parsing can vary
                logger.exception("Failed to read PDF %s", filename)
                raise DocumentIngestionError(f"Unable to extract text from PDF: {exc}")
        elif content_type == "text/csv":
            text = self._extract_csv(raw, metadata)
        else:
            text = raw.decode("utf-8", errors="replace")

        metadata["char_count"] = len(text)
        metadata["word_count"] = len(text.split()) if text else 0
        return text, metadata

    def _extract_csv(self, raw: bytes, metadata: Dict) -> str:
        decoded = raw.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(decoded))
        rows = list(reader)
        metadata["row_count"] = len(rows)
        metadata["column_count"] = len(rows[0]) if rows else 0
        return "\n".join(
            [", ".join(cell.strip() for cell in row if cell is not None) for row in rows]
        )


def summarize_documents(documents: List[UserDocument]) -> str:
    """Create a condensed summary block from multiple documents"""

    if not documents:
        return ""

    blocks = []
    for doc in documents:
        meta = doc.metadata_json or {}
        descriptor = meta.get("summary") or meta.get("title")
        heading = descriptor or doc.filename
        blocks.append(f"### {heading}\n{doc.content.strip()}\n")
    return "\n".join(blocks)
