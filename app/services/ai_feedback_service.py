"""AI feedback service for improving job matching quality"""
import logging
from typing import Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta

from app.models import JobFeedback, Job

logger = logging.getLogger(__name__)


class AIFeedbackService:
    """Service for collecting and using user feedback to improve AI matching"""
    
    @staticmethod
    async def submit_feedback(
        db: AsyncSession,
        job_id: int,
        feedback_type: str,
        feedback_value: str,
        feedback_text: Optional[str] = None,
        ai_match_score_actual: Optional[float] = None
    ) -> JobFeedback:
        """
        Submit feedback on a job recommendation
        
        Args:
            db: Database session
            job_id: Job ID
            feedback_type: Type of feedback (match_score, recommendation, quality)
            feedback_value: Feedback value (positive, negative, neutral, or numeric)
            feedback_text: Optional text feedback
            ai_match_score_actual: User's assessment of actual match score
            
        Returns:
            Created JobFeedback
        """
        feedback = JobFeedback(
            job_id=job_id,
            feedback_type=feedback_type,
            feedback_value=feedback_value,
            feedback_text=feedback_text,
            ai_match_score_actual=ai_match_score_actual
        )
        
        db.add(feedback)
        await db.commit()
        await db.refresh(feedback)
        
        logger.info(f"Feedback submitted for job {job_id}: {feedback_type}={feedback_value}")
        
        return feedback
    
    @staticmethod
    async def get_feedback_stats(
        db: AsyncSession,
        days: int = 30
    ) -> Dict:
        """
        Get feedback statistics for analysis
        
        Args:
            db: Database session
            days: Number of days to look back
            
        Returns:
            Statistics dictionary
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get feedback counts by type
        query = select(
            JobFeedback.feedback_type,
            JobFeedback.feedback_value,
            func.count(JobFeedback.id).label('count')
        ).where(
            JobFeedback.created_at >= cutoff_date
        ).group_by(
            JobFeedback.feedback_type,
            JobFeedback.feedback_value
        )
        
        result = await db.execute(query)
        stats = {}
        
        for row in result.all():
            feedback_type = row.feedback_type
            if feedback_type not in stats:
                stats[feedback_type] = {}
            stats[feedback_type][row.feedback_value] = row.count
        
        # Get average score discrepancy
        query = select(
            func.avg(Job.ai_match_score - JobFeedback.ai_match_score_actual).label('avg_discrepancy')
        ).join(
            JobFeedback, Job.id == JobFeedback.job_id
        ).where(
            and_(
                JobFeedback.created_at >= cutoff_date,
                JobFeedback.ai_match_score_actual.isnot(None),
                Job.ai_match_score.isnot(None)
            )
        )
        
        result = await db.execute(query)
        avg_discrepancy = result.scalar()
        
        stats['avg_score_discrepancy'] = float(avg_discrepancy) if avg_discrepancy else None
        
        return stats
    
    @staticmethod
    async def get_jobs_needing_review(
        db: AsyncSession,
        limit: int = 10
    ) -> List[Job]:
        """
        Get jobs with negative feedback that may need AI score adjustment
        
        Args:
            db: Database session
            limit: Maximum number of jobs to return
            
        Returns:
            List of jobs with negative feedback
        """
        query = (
            select(Job)
            .join(JobFeedback, Job.id == JobFeedback.job_id)
            .where(
                JobFeedback.feedback_value.in_(['negative', 'low'])
            )
            .order_by(JobFeedback.created_at.desc())
            .limit(limit)
        )
        
        result = await db.execute(query)
        return list(result.scalars().all())

