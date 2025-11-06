"""Document review service for human review workflow"""
import logging
from typing import Optional, Dict
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import GeneratedDocument

logger = logging.getLogger(__name__)


class DocumentReviewService:
    """Service for managing document review workflow"""
    
    @staticmethod
    async def approve_document(
        db: AsyncSession,
        document_id: int,
        notes: Optional[str] = None
    ) -> GeneratedDocument:
        """Approve a generated document"""
        result = await db.execute(
            select(GeneratedDocument).where(GeneratedDocument.id == document_id)
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise ValueError(f"Document {document_id} not found")
        
        doc.review_status = "approved"
        doc.reviewed_at = datetime.utcnow()
        if notes:
            doc.review_notes = notes
        
        await db.commit()
        await db.refresh(doc)
        
        logger.info(f"Document {document_id} approved")
        return doc
    
    @staticmethod
    async def reject_document(
        db: AsyncSession,
        document_id: int,
        notes: Optional[str] = None
    ) -> GeneratedDocument:
        """Reject a generated document"""
        result = await db.execute(
            select(GeneratedDocument).where(GeneratedDocument.id == document_id)
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise ValueError(f"Document {document_id} not found")
        
        doc.review_status = "rejected"
        doc.reviewed_at = datetime.utcnow()
        if notes:
            doc.review_notes = notes
        
        await db.commit()
        await db.refresh(doc)
        
        logger.info(f"Document {document_id} rejected")
        return doc
    
    @staticmethod
    async def edit_document(
        db: AsyncSession,
        document_id: int,
        edited_content: str,
        notes: Optional[str] = None
    ) -> GeneratedDocument:
        """Edit and approve a generated document"""
        result = await db.execute(
            select(GeneratedDocument).where(GeneratedDocument.id == document_id)
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise ValueError(f"Document {document_id} not found")
        
        doc.review_status = "edited"
        doc.edited_content = edited_content
        doc.reviewed_at = datetime.utcnow()
        if notes:
            doc.review_notes = notes
        
        await db.commit()
        await db.refresh(doc)
        
        logger.info(f"Document {document_id} edited and approved")
        return doc
    
    @staticmethod
    async def get_pending_reviews(
        db: AsyncSession,
        limit: int = 10
    ) -> list:
        """Get documents pending review"""
        result = await db.execute(
            select(GeneratedDocument)
            .where(GeneratedDocument.review_status == "pending")
            .order_by(GeneratedDocument.generated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

