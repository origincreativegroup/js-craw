"""AI-driven task generation from job insights"""
import logging
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Job, Task
from app.tasks.task_service import TaskService
from app.tasks.due_date_calculator import DueDateCalculator
from app.config import settings

logger = logging.getLogger(__name__)


class TaskGenerator:
    """Generate tasks from AI job insights"""
    
    @staticmethod
    async def generate_tasks_for_job(
        db: AsyncSession,
        job: Job,
        force_regenerate: bool = False
    ) -> List[Task]:
        """
        Generate recommended tasks for a job based on AI insights.
        
        Args:
            db: Database session
            job: Job to generate tasks for
            force_regenerate: If True, regenerate even if tasks exist
            
        Returns:
            List of generated tasks
        """
        # Check if tasks already exist
        if not force_regenerate:
            existing_tasks = await TaskService.list_tasks(
                db, job_id=job.id, status="pending"
            )
            if existing_tasks:
                logger.info(f"Tasks already exist for job {job.id}, skipping generation")
                return existing_tasks
        
        # Check if job meets threshold for auto-generation
        if not settings.AUTO_GENERATE_TASKS:
            logger.debug("Auto-generation disabled, skipping task generation")
            return []
        
        match_score = job.ai_match_score or 0.0
        if match_score < settings.TASK_MATCH_SCORE_THRESHOLD:
            logger.debug(f"Job {job.id} match score {match_score} below threshold {settings.TASK_MATCH_SCORE_THRESHOLD}")
            return []
        
        tasks = []
        
        # Generate tasks based on match score and job status
        if job.status == "new":
            # High match (≥75): Immediate apply task
            if match_score >= 75:
                task = await TaskGenerator._create_apply_task(db, job, match_score)
                if task:
                    tasks.append(task)
            
            # Medium match (50-74): Research first, then apply
            elif match_score >= 50:
                # Research task
                research_task = await TaskGenerator._create_research_task(db, job, match_score)
                if research_task:
                    tasks.append(research_task)
                
                # Apply task (due later)
                apply_task = await TaskGenerator._create_apply_task(db, job, match_score)
                if apply_task:
                    tasks.append(apply_task)
            
            # Lower match but still above threshold: Research only
            else:
                research_task = await TaskGenerator._create_research_task(db, job, match_score)
                if research_task:
                    tasks.append(research_task)
        
        elif job.status == "applied":
            # Auto-create follow-up task for applied jobs
            followup_task = await TaskGenerator._create_followup_task(db, job)
            if followup_task:
                tasks.append(followup_task)
        
        logger.info(f"Generated {len(tasks)} tasks for job {job.id}")
        return tasks
    
    @staticmethod
    async def _create_apply_task(
        db: AsyncSession,
        job: Job,
        match_score: float
    ) -> Optional[Task]:
        """Create an apply task"""
        # Check if apply task already exists
        existing = await TaskService.list_tasks(
            db, job_id=job.id, task_type="apply", status="pending"
        )
        if existing:
            return None
        
        due_date = DueDateCalculator.calculate_due_date(
            task_type="apply",
            match_score=match_score,
            job_discovered_at=job.discovered_at,
            job_posted_date=job.posted_date
        )
        
        priority = DueDateCalculator.calculate_priority_from_match_score(match_score)
        
        title = f"Apply to {job.title} at {job.company}"
        
        ai_insights = {
            "match_score": match_score,
            "pros": job.ai_pros or [],
            "cons": job.ai_cons or [],
            "summary": job.ai_summary
        }
        
        return await TaskService.create_task(
            db=db,
            job_id=job.id,
            task_type="apply",
            title=title,
            due_date=due_date,
            priority=priority,
            recommended_by="AI",
            ai_insights=ai_insights
        )
    
    @staticmethod
    async def _create_research_task(
        db: AsyncSession,
        job: Job,
        match_score: float
    ) -> Optional[Task]:
        """Create a research task"""
        # Check if research task already exists
        existing = await TaskService.list_tasks(
            db, job_id=job.id, task_type="research", status="pending"
        )
        if existing:
            return None
        
        due_date = DueDateCalculator.calculate_due_date(
            task_type="research",
            match_score=match_score,
            job_discovered_at=job.discovered_at,
            job_posted_date=job.posted_date
        )
        
        priority = DueDateCalculator.calculate_priority_from_match_score(match_score)
        
        title = f"Research {job.company} for {job.title} position"
        
        ai_insights = {
            "match_score": match_score,
            "company_profile": getattr(job, 'ai_company_profile', None),
            "key_requirements": getattr(job, 'ai_key_requirements', None)
        }
        
        return await TaskService.create_task(
            db=db,
            job_id=job.id,
            task_type="research",
            title=title,
            due_date=due_date,
            priority=priority,
            recommended_by="AI",
            ai_insights=ai_insights
        )
    
    @staticmethod
    async def _create_followup_task(
        db: AsyncSession,
        job: Job
    ) -> Optional[Task]:
        """Create a follow-up task for applied jobs"""
        # Check if follow-up task already exists
        existing = await TaskService.list_tasks(
            db, job_id=job.id, task_type="follow_up", status="pending"
        )
        if existing:
            return None
        
        # Use job updated_at as application date (when status changed to applied)
        application_date = job.updated_at if job.status == "applied" else datetime.utcnow()
        
        due_date = DueDateCalculator.calculate_due_date(
            task_type="follow_up",
            application_date=application_date,
            job_discovered_at=job.discovered_at
        )
        
        title = f"Follow up on application to {job.title} at {job.company}"
        
        return await TaskService.create_task(
            db=db,
            job_id=job.id,
            task_type="follow_up",
            title=title,
            due_date=due_date,
            priority="high",
            recommended_by="system",
            notes="Automatically created after application"
        )
    
    @staticmethod
    async def generate_task_recommendations(
        db: AsyncSession,
        limit: int = 10
    ) -> List[Dict]:
        """
        Generate task recommendations from jobs.
        Returns list of recommended tasks that haven't been created yet.
        
        Args:
            db: Database session
            limit: Maximum number of recommendations to return
            
        Returns:
            List of task recommendation dictionaries
        """
        recommendations = []
        
        # Get high-match jobs without tasks
        query = select(Job).where(
            Job.ai_match_score >= settings.TASK_MATCH_SCORE_THRESHOLD,
            Job.status == "new"
        ).order_by(Job.ai_match_score.desc()).limit(limit * 2)  # Get more to filter
        
        result = await db.execute(query)
        jobs = result.scalars().all()
        
        for job in jobs:
            # Check if tasks already exist
            existing_tasks = await TaskService.list_tasks(db, job_id=job.id)
            if existing_tasks:
                continue
            
            match_score = job.ai_match_score or 0.0
            
            if match_score >= 75:
                recommendations.append({
                    "job_id": job.id,
                    "job_title": job.title,
                    "company": job.company,
                    "match_score": match_score,
                    "recommended_action": "apply",
                    "priority": "high",
                    "reason": "High match score - immediate action recommended"
                })
            elif match_score >= 50:
                recommendations.append({
                    "job_id": job.id,
                    "job_title": job.title,
                    "company": job.company,
                    "match_score": match_score,
                    "recommended_action": "research",
                    "priority": "medium",
                    "reason": "Medium match - research recommended before applying"
                })
            
            if len(recommendations) >= limit:
                break
        
        # Get applied jobs without follow-up tasks
        applied_query = select(Job).where(
            Job.status == "applied"
        ).order_by(Job.updated_at.desc()).limit(limit)
        
        applied_result = await db.execute(applied_query)
        applied_jobs = applied_result.scalars().all()
        
        for job in applied_jobs:
            existing_followups = await TaskService.list_tasks(
                db, job_id=job.id, task_type="follow_up"
            )
            if not existing_followups:
                recommendations.append({
                    "job_id": job.id,
                    "job_title": job.title,
                    "company": job.company,
                    "match_score": job.ai_match_score,
                    "recommended_action": "follow_up",
                    "priority": "high",
                    "reason": "Application submitted - follow-up recommended"
                })
        
        return recommendations[:limit]

