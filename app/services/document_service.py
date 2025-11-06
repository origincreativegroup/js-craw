"""Unified document service for job-context aware document management"""
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, or_
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.models import (
    Job,
    GeneratedDocument,
    UserDocument,
    UserProfile,
)

logger = logging.getLogger(__name__)


class DocumentService:
    """Unified service for managing all documents (user-uploaded and AI-generated)"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_job_documents(self, job_id: int) -> Dict[str, Any]:
        """Get all documents related to a job"""
        # Get user documents (all user documents can be used for any job)
        user_docs_result = await self.db.execute(
            select(UserDocument)
            .order_by(desc(UserDocument.created_at))
        )
        user_documents = user_docs_result.scalars().all()
        
        # Get generated documents for this job
        generated_docs_result = await self.db.execute(
            select(GeneratedDocument)
            .where(GeneratedDocument.job_id == job_id)
            .where(GeneratedDocument.is_current == True)
            .order_by(desc(GeneratedDocument.generated_at))
        )
        generated_documents = generated_docs_result.scalars().all()
        
        # Get document versions
        all_versions_result = await self.db.execute(
            select(GeneratedDocument)
            .where(GeneratedDocument.job_id == job_id)
            .order_by(desc(GeneratedDocument.version), desc(GeneratedDocument.generated_at))
        )
        all_versions = all_versions_result.scalars().all()
        
        # Organize by type
        documents_by_type = {
            "resume": [d for d in generated_documents if d.document_type == "resume"],
            "cover_letter": [d for d in generated_documents if d.document_type == "cover_letter"],
            "analysis": [],  # Can add job analysis exports here
        }
        
        # Group versions by document type
        versions_by_type: Dict[str, List[GeneratedDocument]] = {}
        for doc in all_versions:
            if doc.document_type not in versions_by_type:
                versions_by_type[doc.document_type] = []
            versions_by_type[doc.document_type].append(doc)
        
        return {
            "user_documents": [self._serialize_user_document(d) for d in user_documents],
            "generated_documents": [self._serialize_generated_document(d) for d in generated_documents],
            "documents_by_type": {
                k: [self._serialize_generated_document(d) for d in v]
                for k, v in documents_by_type.items()
            },
            "versions": {
                k: [self._serialize_generated_document(d) for d in v]
                for k, v in versions_by_type.items()
            },
        }
    
    async def get_document_versions(
        self, 
        job_id: int, 
        document_type: str
    ) -> List[Dict[str, Any]]:
        """Get all versions of a document for a job"""
        result = await self.db.execute(
            select(GeneratedDocument)
            .where(
                and_(
                    GeneratedDocument.job_id == job_id,
                    GeneratedDocument.document_type == document_type
                )
            )
            .order_by(desc(GeneratedDocument.version), desc(GeneratedDocument.generated_at))
        )
        documents = result.scalars().all()
        return [self._serialize_generated_document(d) for d in documents]
    
    async def create_document_version(
        self,
        job_id: int,
        document_type: str,
        content: str,
        parent_version_id: Optional[int] = None
    ) -> GeneratedDocument:
        """Create a new version of a document"""
        # Get the latest version number
        if parent_version_id:
            parent_result = await self.db.execute(
                select(GeneratedDocument).where(GeneratedDocument.id == parent_version_id)
            )
            parent = parent_result.scalar_one_or_none()
            if parent:
                version = parent.version + 1
            else:
                version = 1
        else:
            # Get max version for this job and document type
            result = await self.db.execute(
                select(GeneratedDocument)
                .where(
                    and_(
                        GeneratedDocument.job_id == job_id,
                        GeneratedDocument.document_type == document_type
                    )
                )
                .order_by(desc(GeneratedDocument.version))
                .limit(1)
            )
            latest = result.scalar_one_or_none()
            version = (latest.version + 1) if latest else 1
        
        # Mark all previous versions as not current
        existing_result = await self.db.execute(
            select(GeneratedDocument)
            .where(
                and_(
                    GeneratedDocument.job_id == job_id,
                    GeneratedDocument.document_type == document_type
                )
            )
        )
        for doc in existing_result.scalars().all():
            doc.is_current = False
        
        # Create new version
        new_doc = GeneratedDocument(
            job_id=job_id,
            document_type=document_type,
            content=content,
            version=version,
            parent_version_id=parent_version_id,
            is_current=True,
            generated_at=datetime.utcnow()
        )
        self.db.add(new_doc)
        await self.db.commit()
        await self.db.refresh(new_doc)
        return new_doc
    
    async def restore_document_version(self, document_id: int) -> GeneratedDocument:
        """Restore a previous version as the current version"""
        result = await self.db.execute(
            select(GeneratedDocument).where(GeneratedDocument.id == document_id)
        )
        old_version = result.scalar_one_or_none()
        if not old_version:
            raise ValueError(f"Document {document_id} not found")
        
        # Create a new version based on the old one
        return await self.create_document_version(
            job_id=old_version.job_id,
            document_type=old_version.document_type,
            content=old_version.content,
            parent_version_id=old_version.id
        )
    
    def _serialize_user_document(self, doc: UserDocument) -> Dict[str, Any]:
        """Serialize user document for API response"""
        return {
            "id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "content": doc.content,
            "metadata": doc.metadata_json or {},
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        }
    
    def _serialize_generated_document(self, doc: GeneratedDocument) -> Dict[str, Any]:
        """Serialize generated document for API response"""
        return {
            "id": doc.id,
            "job_id": doc.job_id,
            "document_type": doc.document_type,
            "content": doc.content,
            "version": doc.version,
            "parent_version_id": doc.parent_version_id,
            "is_current": doc.is_current,
            "generated_at": doc.generated_at.isoformat() if doc.generated_at else None,
            "review_status": doc.review_status,
            "reviewed_at": doc.reviewed_at.isoformat() if doc.reviewed_at else None,
            "review_notes": doc.review_notes,
            "edited_content": doc.edited_content,
            "file_path": doc.file_path,
        }

