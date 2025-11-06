"""Chat context service for aggregating full dataset context"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload, joinedload

from app.models import (
    Job, Company, Application, Task, FollowUp, 
    GeneratedDocument, UserProfile, CrawlLog
)

logger = logging.getLogger(__name__)


class ChatContextService:
    """Service for aggregating full dataset context for chat"""
    
    @staticmethod
    async def get_full_context(
        db: AsyncSession,
        limit_per_type: int = 50,
        days_back: int = 30
    ) -> Dict:
        """
        Aggregate full dataset context for chat
        
        Args:
            db: Database session
            limit_per_type: Maximum records per entity type
            days_back: Number of days to look back
            
        Returns:
            Dictionary with aggregated context
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        context = {
            "summary": {},
            "companies": [],
            "jobs": [],
            "applications": [],
            "tasks": [],
            "follow_ups": [],
            "generated_documents": [],
            "crawl_history": [],
            "user_profile": None
        }
        
        try:
            # Get summary statistics
            context["summary"] = await ChatContextService._get_summary_stats(db, cutoff_date)
            
            # Get companies (with eager loading)
            companies_result = await db.execute(
                select(Company)
                .options(selectinload(Company.jobs))
                .where(Company.is_active == True)
                .order_by(Company.name)
                .limit(limit_per_type)
            )
            context["companies"] = [
                {
                    "id": c.id,
                    "name": c.name,
                    "career_page_url": c.career_page_url,
                    "crawler_type": c.crawler_type,
                    "jobs_count": len(c.jobs),
                    "last_crawled_at": c.last_crawled_at.isoformat() if c.last_crawled_at else None
                }
                for c in companies_result.scalars().all()
            ]
            
            # Get recent jobs (with relationships)
            jobs_result = await db.execute(
                select(Job)
                .options(
                    joinedload(Job.company_relation),
                    joinedload(Job.applications),
                    joinedload(Job.generated_documents)
                )
                .where(Job.discovered_at >= cutoff_date)
                .order_by(desc(Job.discovered_at))
                .limit(limit_per_type)
            )
            context["jobs"] = [
                {
                    "id": j.id,
                    "title": j.title,
                    "company": j.company,
                    "company_id": j.company_id,
                    "location": j.location,
                    "status": j.status,
                    "ai_match_score": j.ai_match_score,
                    "ai_recommended": j.ai_recommended,
                    "discovered_at": j.discovered_at.isoformat() if j.discovered_at else None,
                    "applications_count": len(j.applications),
                    "documents_count": len(j.generated_documents)
                }
                for j in jobs_result.scalars().all()
            ]
            
            # Get applications
            apps_result = await db.execute(
                select(Application)
                .options(joinedload(Application.job))
                .order_by(desc(Application.created_at))
                .limit(limit_per_type)
            )
            context["applications"] = [
                {
                    "id": a.id,
                    "job_id": a.job_id,
                    "job_title": a.job.title if a.job else None,
                    "status": a.status,
                    "application_date": a.application_date.isoformat() if a.application_date else None,
                    "created_at": a.created_at.isoformat() if a.created_at else None
                }
                for a in apps_result.scalars().all()
            ]
            
            # Get tasks
            tasks_result = await db.execute(
                select(Task)
                .options(joinedload(Task.job))
                .where(Task.status != "completed")
                .order_by(Task.due_date)
                .limit(limit_per_type)
            )
            context["tasks"] = [
                {
                    "id": t.id,
                    "job_id": t.job_id,
                    "job_title": t.job.title if t.job else None,
                    "task_type": t.task_type,
                    "title": t.title,
                    "status": t.status,
                    "priority": t.priority,
                    "due_date": t.due_date.isoformat() if t.due_date else None
                }
                for t in tasks_result.scalars().all()
            ]
            
            # Get follow-ups
            followups_result = await db.execute(
                select(FollowUp)
                .options(joinedload(FollowUp.job))
                .where(FollowUp.follow_up_date >= datetime.utcnow())
                .order_by(FollowUp.follow_up_date)
                .limit(limit_per_type)
            )
            context["follow_ups"] = [
                {
                    "id": f.id,
                    "job_id": f.job_id,
                    "job_title": f.job.title if f.job else None,
                    "follow_up_date": f.follow_up_date.isoformat() if f.follow_up_date else None,
                    "notes": f.notes
                }
                for f in followups_result.scalars().all()
            ]
            
            # Get generated documents
            docs_result = await db.execute(
                select(GeneratedDocument)
                .options(joinedload(GeneratedDocument.job))
                .order_by(desc(GeneratedDocument.generated_at))
                .limit(limit_per_type)
            )
            context["generated_documents"] = [
                {
                    "id": d.id,
                    "job_id": d.job_id,
                    "job_title": d.job.title if d.job else None,
                    "document_type": d.document_type,
                    "review_status": d.review_status,
                    "generated_at": d.generated_at.isoformat() if d.generated_at else None
                }
                for d in docs_result.scalars().all()
            ]
            
            # Get recent crawl history
            crawl_logs_result = await db.execute(
                select(CrawlLog)
                .order_by(desc(CrawlLog.started_at))
                .limit(limit_per_type)
            )
            context["crawl_history"] = [
                {
                    "id": c.id,
                    "search_criteria_id": c.search_criteria_id,
                    "company_name": c.company_name,
                    "status": c.status,
                    "jobs_found": c.jobs_found,
                    "started_at": c.started_at.isoformat() if c.started_at else None,
                    "completed_at": c.completed_at.isoformat() if c.completed_at else None
                }
                for c in crawl_logs_result.scalars().all()
            ]
            
            # Get user profile (first one)
            profile_result = await db.execute(
                select(UserProfile).limit(1)
            )
            profile = profile_result.scalar_one_or_none()
            if profile:
                context["user_profile"] = {
                    "id": profile.id,
                    "skills": profile.skills,
                    "preferences": profile.preferences
                }
            
            logger.info(f"Aggregated context: {len(context['jobs'])} jobs, {len(context['companies'])} companies, etc.")
            
        except Exception as e:
            logger.error(f"Error aggregating context: {e}", exc_info=True)
            raise
        
        return context
    
    @staticmethod
    async def _get_summary_stats(db: AsyncSession, cutoff_date: datetime) -> Dict:
        """Get summary statistics"""
        stats = {}
        
        try:
            # Job counts
            jobs_total = await db.execute(select(func.count(Job.id)))
            stats["total_jobs"] = jobs_total.scalar()
            
            jobs_recent = await db.execute(
                select(func.count(Job.id)).where(Job.discovered_at >= cutoff_date)
            )
            stats["recent_jobs"] = jobs_recent.scalar()
            
            jobs_recommended = await db.execute(
                select(func.count(Job.id)).where(Job.ai_recommended == True)
            )
            stats["recommended_jobs"] = jobs_recommended.scalar()
            
            # Application counts
            apps_total = await db.execute(select(func.count(Application.id)))
            stats["total_applications"] = apps_total.scalar()
            
            # Task counts
            tasks_pending = await db.execute(
                select(func.count(Task.id)).where(Task.status == "pending")
            )
            stats["pending_tasks"] = tasks_pending.scalar()
            
            # Company counts
            companies_active = await db.execute(
                select(func.count(Company.id)).where(Company.is_active == True)
            )
            stats["active_companies"] = companies_active.scalar()
            
        except Exception as e:
            logger.error(f"Error getting summary stats: {e}")
            stats = {}
        
        return stats

