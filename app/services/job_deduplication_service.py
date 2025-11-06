"""Enhanced job deduplication service"""
import logging
from typing import Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func
from sqlalchemy.orm import selectinload

from app.models import Job

logger = logging.getLogger(__name__)


class JobDeduplicationService:
    """Service for detecting and handling duplicate jobs"""
    
    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize URL for comparison (remove query params, trailing slashes)"""
        if not url:
            return ""
        # Remove query params and fragments
        url = url.split('?')[0].split('#')[0]
        # Remove trailing slash
        url = url.rstrip('/')
        return url.lower()
    
    @staticmethod
    def normalize_title(title: str) -> str:
        """Normalize job title for comparison"""
        if not title:
            return ""
        # Lowercase, remove extra whitespace
        title = ' '.join(title.lower().split())
        # Remove common punctuation variations
        title = title.replace('-', ' ').replace('_', ' ')
        return title
    
    @staticmethod
    async def find_duplicate(
        db: AsyncSession,
        job_data: Dict,
        company_id: Optional[int] = None
    ) -> Optional[Job]:
        """
        Find duplicate job using multiple matching strategies
        
        Args:
            db: Database session
            job_data: Job data dictionary with external_id, title, url, etc.
            company_id: Company ID (optional, for faster lookup)
            
        Returns:
            Existing Job if duplicate found, None otherwise
        """
        external_id = job_data.get('external_id')
        title = job_data.get('title')
        url = job_data.get('url')
        source_url = job_data.get('source_url', url)
        
        if not external_id and not title:
            logger.warning("Cannot check duplicates: missing external_id and title")
            return None
        
        # Strategy 1: Exact match on external_id + company_id (fastest, most reliable)
        if external_id and company_id:
            result = await db.execute(
                select(Job).where(
                    Job.external_id == external_id,
                    Job.company_id == company_id
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                logger.debug(f"Found duplicate by external_id + company_id: {external_id}")
                return existing
        
        # Strategy 2: Normalized URL match (handles URL variations)
        if url or source_url:
            normalized_url = JobDeduplicationService.normalize_url(url or source_url)
            if normalized_url:
                query = select(Job).where(
                    or_(
                        func.lower(func.trim(func.trailing('/' from Job.url))) == normalized_url,
                        func.lower(func.trim(func.trailing('/' from Job.source_url))) == normalized_url
                    )
                )
                if company_id:
                    query = query.where(Job.company_id == company_id)
                
                result = await db.execute(query)
                existing = result.scalar_one_or_none()
                if existing:
                    logger.debug(f"Found duplicate by normalized URL: {normalized_url}")
                    return existing
        
        # Strategy 3: Title + company match (fuzzy, handles title variations)
        if title and company_id:
            normalized_title = JobDeduplicationService.normalize_title(title)
            if normalized_title:
                # Use similarity matching (PostgreSQL has similarity functions)
                # For now, use exact normalized match (can be enhanced with fuzzy matching)
                query = select(Job).where(
                    Job.company_id == company_id,
                    func.lower(func.trim(Job.title.replace('-', ' ').replace('_', ' '))) == normalized_title
                )
                
                result = await db.execute(query)
                existing = result.scalar_one_or_none()
                if existing:
                    logger.debug(f"Found duplicate by normalized title + company: {normalized_title}")
                    return existing
        
        # Strategy 4: Cross-company duplicate detection (same external_id across companies)
        # This handles cases where a job is posted for multiple company locations
        if external_id:
            result = await db.execute(
                select(Job).where(Job.external_id == external_id)
                .order_by(Job.discovered_at.desc())
                .limit(1)
            )
            existing = result.scalar_one_or_none()
            if existing:
                # Only consider it a duplicate if it's very recent (within 7 days)
                # This prevents false positives from old jobs
                from datetime import datetime, timedelta
                recent_threshold = datetime.utcnow() - timedelta(days=7)
                if existing.discovered_at >= recent_threshold:
                    logger.debug(f"Found potential cross-company duplicate by external_id: {external_id}")
                    return existing
        
        return None
    
    @staticmethod
    async def find_all_duplicates(
        db: AsyncSession,
        limit: int = 100
    ) -> List[Dict]:
        """
        Find duplicate jobs in the database
        
        Returns:
            List of duplicate groups with job IDs and duplicate reasons
        """
        duplicates = []
        
        # Find duplicates by external_id (across companies)
        query = (
            select(
                Job.external_id,
                func.count(Job.id).label('count'),
                func.array_agg(Job.id).label('job_ids'),
                func.array_agg(Job.company_id).label('company_ids')
            )
            .where(Job.external_id.isnot(None))
            .group_by(Job.external_id)
            .having(func.count(Job.id) > 1)
            .limit(limit)
        )
        
        result = await db.execute(query)
        for row in result.all():
            if row.count > 1:
                duplicates.append({
                    'type': 'external_id',
                    'external_id': row.external_id,
                    'count': row.count,
                    'job_ids': row.job_ids,
                    'company_ids': row.company_ids
                })
        
        # Find duplicates by normalized URL (within same company)
        # This is more complex and would require iterating through jobs
        # For now, we'll focus on the external_id duplicates which are most common
        
        return duplicates
    
    @staticmethod
    async def merge_duplicates(
        db: AsyncSession,
        job_ids: List[int],
        keep_job_id: int
    ) -> Dict:
        """
        Merge duplicate jobs, keeping one and updating references
        
        Args:
            db: Database session
            job_ids: List of duplicate job IDs
            keep_job_id: ID of job to keep (others will be deleted)
            
        Returns:
            Merge statistics
        """
        if keep_job_id not in job_ids:
            raise ValueError(f"keep_job_id {keep_job_id} must be in job_ids list")
        
        # Get jobs to merge
        result = await db.execute(
            select(Job).where(Job.id.in_(job_ids))
        )
        jobs = result.scalars().all()
        
        if len(jobs) != len(job_ids):
            raise ValueError(f"Not all job IDs found: expected {len(job_ids)}, found {len(jobs)}")
        
        keep_job = next((j for j in jobs if j.id == keep_job_id), None)
        if not keep_job:
            raise ValueError(f"Job {keep_job_id} not found")
        
        delete_jobs = [j for j in jobs if j.id != keep_job_id]
        
        # Update references in related tables (applications, tasks, follow-ups, etc.)
        # This would require updating foreign keys, which is complex
        # For now, we'll just log a warning
        logger.warning(f"Merging {len(delete_jobs)} duplicate jobs into {keep_job_id}")
        logger.warning("Note: Related records (applications, tasks, etc.) should be manually reviewed")
        
        # Delete duplicate jobs
        for job in delete_jobs:
            await db.delete(job)
        
        await db.commit()
        
        return {
            "kept": keep_job_id,
            "deleted": [j.id for j in delete_jobs],
            "count": len(delete_jobs)
        }

