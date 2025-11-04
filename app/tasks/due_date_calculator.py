"""Smart due date calculation for tasks"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class DueDateCalculator:
    """Calculate smart due dates for tasks based on job context"""
    
    @staticmethod
    def calculate_due_date(
        task_type: str,
        match_score: Optional[float] = None,
        job_discovered_at: Optional[datetime] = None,
        job_posted_date: Optional[datetime] = None,
        application_date: Optional[datetime] = None
    ) -> datetime:
        """
        Calculate smart due date for a task based on context.
        
        Args:
            task_type: Type of task (apply, follow_up, research, network, prepare_interview)
            match_score: AI match score (0-100)
            job_discovered_at: When the job was discovered
            job_posted_date: When the job was posted (if available)
            application_date: When application was submitted (for follow-up tasks)
            
        Returns:
            Calculated due date
        """
        base_date = datetime.utcnow()
        
        # Use job discovery date if available, otherwise use now
        if job_discovered_at:
            base_date = job_discovered_at
        
        # Adjust for task type
        if task_type == "apply":
            return DueDateCalculator._calculate_apply_due_date(
                match_score, base_date, job_posted_date
            )
        elif task_type == "follow_up":
            return DueDateCalculator._calculate_followup_due_date(application_date, base_date)
        elif task_type == "research":
            return DueDateCalculator._calculate_research_due_date(match_score, base_date)
        elif task_type == "network":
            return DueDateCalculator._calculate_network_due_date(base_date)
        elif task_type == "prepare_interview":
            return DueDateCalculator._calculate_interview_prep_due_date(base_date)
        else:
            # Default: 3 days
            return base_date + timedelta(days=3)
    
    @staticmethod
    def _calculate_apply_due_date(
        match_score: Optional[float],
        base_date: datetime,
        job_posted_date: Optional[datetime]
    ) -> datetime:
        """Calculate due date for apply tasks"""
        # High match (≥75): +1 day
        # Medium match (50-74): +3 days
        # Low match (<50): +5 days
        
        if match_score is None:
            match_score = 50.0
        
        if match_score >= 75:
            days = 1
        elif match_score >= 50:
            days = 3
        else:
            days = 5
        
        # If job was recently posted (within 24 hours), prioritize (reduce by 1 day)
        if job_posted_date:
            age_hours = (base_date - job_posted_date).total_seconds() / 3600
            if age_hours < 24:
                days = max(1, days - 1)
        
        return base_date + timedelta(days=days)
    
    @staticmethod
    def _calculate_followup_due_date(
        application_date: Optional[datetime],
        base_date: datetime
    ) -> datetime:
        """Calculate due date for follow-up tasks"""
        # Standard follow-up is 7 days after application
        if application_date:
            return application_date + timedelta(days=7)
        else:
            # If no application date, use 7 days from base
            return base_date + timedelta(days=7)
    
    @staticmethod
    def _calculate_research_due_date(
        match_score: Optional[float],
        base_date: datetime
    ) -> datetime:
        """Calculate due date for research tasks"""
        # Research should be done before applying
        # High match: +1 day (quick research)
        # Medium/low: +2 days (more thorough)
        
        if match_score is None or match_score >= 75:
            days = 1
        else:
            days = 2
        
        return base_date + timedelta(days=days)
    
    @staticmethod
    def _calculate_network_due_date(base_date: datetime) -> datetime:
        """Calculate due date for network tasks"""
        # Network tasks allow time for application prep
        # Usually done after initial research
        return base_date + timedelta(days=5)
    
    @staticmethod
    def _calculate_interview_prep_due_date(base_date: datetime) -> datetime:
        """Calculate due date for interview prep tasks"""
        # Interview prep is typically urgent
        return base_date + timedelta(days=1)
    
    @staticmethod
    def calculate_priority_from_match_score(match_score: Optional[float]) -> str:
        """
        Calculate task priority from AI match score.
        
        Args:
            match_score: AI match score (0-100)
            
        Returns:
            Priority level: high, medium, or low
        """
        if match_score is None:
            return "medium"
        
        if match_score >= 75:
            return "high"
        elif match_score >= 50:
            return "medium"
        else:
            return "low"

