"""Job archival service for managing old jobs"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from sqlalchemy.orm import selectinload

from app.models import Job

logger = logging.getLogger(__name__)


class JobArchivalService:
    """Service for archiving old jobs"""
    
    DEFAULT_ARCHIVAL_DAYS = 90
    
    @staticmethod
    async def archive_old_jobs(
        db: AsyncSession,
        days_old: int = DEFAULT_ARCHIVAL_DAYS,
        dry_run: bool = False
    ) -> dict:
        """
        Archive jobs older than specified days
        
        Args:
            db: Database session
            days_old: Number of days after which to archive (default: 90)
            dry_run: If True, only count jobs that would be archived without actually archiving
            
        Returns:
            dict with archival statistics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Find jobs that should be archived:
        # - Older than cutoff_date
        # - Not already archived
        # - Not in active application status (applied, interviewing, etc.)
        query = select(Job).where(
            and_(
                Job.discovered_at < cutoff_date,
                Job.archived_at.is_(None),
                ~Job.status.in_(["applied", "interviewing", "accepted"])  # Don't archive active applications
            )
        )
        
        result = await db.execute(query)
        jobs_to_archive = result.scalars().all()
        
        count = len(jobs_to_archive)
        
        if dry_run:
            logger.info(f"DRY RUN: Would archive {count} jobs older than {days_old} days")
            return {
                "dry_run": True,
                "count": count,
                "cutoff_date": cutoff_date.isoformat(),
                "archived": []
            }
        
        if count == 0:
            logger.info(f"No jobs to archive (older than {days_old} days)")
            return {
                "count": 0,
                "cutoff_date": cutoff_date.isoformat(),
                "archived": []
            }
        
        # Archive jobs
        now = datetime.utcnow()
        archived_job_ids = []
        
        for job in jobs_to_archive:
            job.archived_at = now
            job.status = "archived"
            archived_job_ids.append(job.id)
        
        await db.commit()
        
        logger.info(f"Archived {count} jobs older than {days_old} days")
        
        return {
            "count": count,
            "cutoff_date": cutoff_date.isoformat(),
            "archived": archived_job_ids,
            "archived_at": now.isoformat()
        }
    
    @staticmethod
    async def unarchive_job(
        db: AsyncSession,
        job_id: int
    ) -> Optional[Job]:
        """
        Unarchive a job
        
        Args:
            db: Database session
            job_id: ID of job to unarchive
            
        Returns:
            Unarchived Job or None if not found
        """
        query = select(Job).where(Job.id == job_id)
        result = await db.execute(query)
        job = result.scalar_one_or_none()
        
        if not job:
            return None
        
        if job.archived_at is None:
            logger.warning(f"Job {job_id} is not archived")
            return job
        
        job.archived_at = None
        if job.status == "archived":
            job.status = "new"  # Reset to new status
        
        await db.commit()
        logger.info(f"Unarchived job {job_id}")
        
        return job
    
    @staticmethod
    async def get_archived_jobs_count(
        db: AsyncSession
    ) -> int:
        """Get count of archived jobs"""
        query = select(Job).where(Job.archived_at.isnot(None))
        result = await db.execute(query)
        return len(result.scalars().all())

