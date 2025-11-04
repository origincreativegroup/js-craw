"""Task service for managing job-related tasks"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from app.models import Task, Job
from app.tasks.due_date_calculator import DueDateCalculator

logger = logging.getLogger(__name__)


class TaskService:
    """Service for managing tasks"""
    
    VALID_STATUSES = ["pending", "in_progress", "completed", "snoozed", "cancelled"]
    VALID_TASK_TYPES = ["apply", "follow_up", "research", "network", "prepare_interview"]
    VALID_PRIORITIES = ["high", "medium", "low"]
    
    SNOOZE_OPTIONS = {
        "1h": timedelta(hours=1),
        "1d": timedelta(days=1),
        "3d": timedelta(days=3),
        "1w": timedelta(weeks=1),
    }
    
    @staticmethod
    def validate_status_transition(current_status: str, new_status: str) -> bool:
        """Validate if status transition is allowed"""
        valid_transitions = {
            "pending": ["in_progress", "completed", "snoozed", "cancelled"],
            "in_progress": ["completed", "snoozed", "cancelled"],
            "snoozed": ["pending", "in_progress", "cancelled"],
            "completed": [],  # Cannot transition from completed
            "cancelled": [],  # Cannot transition from cancelled
        }
        return new_status in valid_transitions.get(current_status, [])
    
    @staticmethod
    async def create_task(
        db: AsyncSession,
        job_id: int,
        task_type: str,
        title: str,
        due_date: Optional[datetime] = None,
        priority: Optional[str] = None,
        notes: Optional[str] = None,
        recommended_by: Optional[str] = None,
        ai_insights: Optional[Dict] = None
    ) -> Task:
        """Create a new task"""
        # Validate task type
        if task_type not in TaskService.VALID_TASK_TYPES:
            raise ValueError(f"Invalid task_type: {task_type}")
        
        # Validate priority
        if priority and priority not in TaskService.VALID_PRIORITIES:
            raise ValueError(f"Invalid priority: {priority}")
        
        # Verify job exists
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        # Calculate due date if not provided
        if due_date is None:
            due_date = DueDateCalculator.calculate_due_date(
                task_type=task_type,
                match_score=job.ai_match_score,
                job_discovered_at=job.discovered_at,
                job_posted_date=job.posted_date
            )
        
        # Determine priority from match score if not provided
        if priority is None:
            priority = DueDateCalculator.calculate_priority_from_match_score(job.ai_match_score)
        
        task = Task(
            job_id=job_id,
            task_type=task_type,
            title=title,
            due_date=due_date,
            priority=priority,
            status="pending",
            notes=notes,
            recommended_by=recommended_by or "user",
            ai_insights=ai_insights
        )
        
        db.add(task)
        await db.commit()
        await db.refresh(task)
        
        logger.info(f"Created task {task.id} for job {job_id}: {task_type}")
        return task
    
    @staticmethod
    async def get_task(db: AsyncSession, task_id: int) -> Optional[Task]:
        """Get a task by ID"""
        result = await db.execute(
            select(Task)
            .options(selectinload(Task.job))
            .where(Task.id == task_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def list_tasks(
        db: AsyncSession,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        task_type: Optional[str] = None,
        job_id: Optional[int] = None,
        due_before: Optional[datetime] = None,
        due_after: Optional[datetime] = None,
        include_snoozed: bool = True,
        limit: int = 100
    ) -> List[Task]:
        """List tasks with filters"""
        query = select(Task).options(selectinload(Task.job))
        
        conditions = []
        
        if status:
            if status not in TaskService.VALID_STATUSES:
                raise ValueError(f"Invalid status: {status}")
            conditions.append(Task.status == status)
        
        if priority:
            if priority not in TaskService.VALID_PRIORITIES:
                raise ValueError(f"Invalid priority: {priority}")
            conditions.append(Task.priority == priority)
        
        if task_type:
            if task_type not in TaskService.VALID_TASK_TYPES:
                raise ValueError(f"Invalid task_type: {task_type}")
            conditions.append(Task.task_type == task_type)
        
        if job_id:
            conditions.append(Task.job_id == job_id)
        
        if due_before:
            conditions.append(Task.due_date <= due_before)
        
        if due_after:
            conditions.append(Task.due_date >= due_after)
        
        # Handle snoozed tasks
        if not include_snoozed:
            conditions.append(
                or_(
                    Task.status != "snoozed",
                    and_(Task.status == "snoozed", Task.snooze_until <= datetime.utcnow())
                )
            )
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(Task.due_date).limit(limit)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def update_task(
        db: AsyncSession,
        task_id: int,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        due_date: Optional[datetime] = None,
        title: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[Task]:
        """Update a task"""
        task = await TaskService.get_task(db, task_id)
        if not task:
            return None
        
        # Validate status transition
        if status and status != task.status:
            if not TaskService.validate_status_transition(task.status, status):
                raise ValueError(f"Invalid status transition: {task.status} -> {status}")
            task.status = status
            
            # Set completed_at if marking as completed
            if status == "completed":
                task.completed_at = datetime.utcnow()
            elif status != "snoozed" and task.completed_at:
                # Clear completed_at if moving away from completed
                task.completed_at = None
        
        if priority:
            if priority not in TaskService.VALID_PRIORITIES:
                raise ValueError(f"Invalid priority: {priority}")
            task.priority = priority
        
        if due_date:
            task.due_date = due_date
        
        if title is not None:
            task.title = title
        
        if notes is not None:
            task.notes = notes
        
        await db.commit()
        await db.refresh(task)
        
        logger.info(f"Updated task {task_id}")
        return task
    
    @staticmethod
    async def snooze_task(
        db: AsyncSession,
        task_id: int,
        duration: str = "1d"
    ) -> Optional[Task]:
        """Snooze a task for a specified duration"""
        if duration not in TaskService.SNOOZE_OPTIONS:
            raise ValueError(f"Invalid snooze duration: {duration}. Options: {list(TaskService.SNOOZE_OPTIONS.keys())}")
        
        task = await TaskService.get_task(db, task_id)
        if not task:
            return None
        
        snooze_delta = TaskService.SNOOZE_OPTIONS[duration]
        task.snooze_until = datetime.utcnow() + snooze_delta
        task.snooze_count += 1
        
        # Update status to snoozed if not already
        if task.status != "snoozed":
            if TaskService.validate_status_transition(task.status, "snoozed"):
                task.status = "snoozed"
        
        await db.commit()
        await db.refresh(task)
        
        logger.info(f"Snoozed task {task_id} until {task.snooze_until}")
        return task
    
    @staticmethod
    async def complete_task(db: AsyncSession, task_id: int) -> Optional[Task]:
        """Mark a task as completed"""
        task = await TaskService.get_task(db, task_id)
        if not task:
            return None
        
        if task.status == "completed":
            return task  # Already completed
        
        if not TaskService.validate_status_transition(task.status, "completed"):
            raise ValueError(f"Cannot transition from {task.status} to completed")
        
        task.status = "completed"
        task.completed_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(task)
        
        logger.info(f"Completed task {task_id}")
        return task
    
    @staticmethod
    async def cancel_task(db: AsyncSession, task_id: int) -> Optional[Task]:
        """Cancel a task"""
        task = await TaskService.get_task(db, task_id)
        if not task:
            return None
        
        if task.status == "cancelled":
            return task  # Already cancelled
        
        if not TaskService.validate_status_transition(task.status, "cancelled"):
            raise ValueError(f"Cannot transition from {task.status} to cancelled")
        
        task.status = "cancelled"
        
        await db.commit()
        await db.refresh(task)
        
        logger.info(f"Cancelled task {task_id}")
        return task
    
    @staticmethod
    async def get_due_tasks(
        db: AsyncSession,
        within_hours: int = 1,
        include_snoozed: bool = False
    ) -> List[Task]:
        """Get tasks that are due within the specified hours"""
        now = datetime.utcnow()
        due_by = now + timedelta(hours=within_hours)
        
        query = select(Task).options(selectinload(Task.job)).where(
            Task.due_date <= due_by,
            Task.status.in_(["pending", "in_progress"])
        )
        
        if not include_snoozed:
            query = query.where(
                or_(
                    Task.status != "snoozed",
                    and_(
                        Task.status == "snoozed",
                        Task.snooze_until <= now
                    )
                )
            )
        else:
            # Include snoozed tasks that are past their snooze time
            query = query.where(
                or_(
                    Task.status != "snoozed",
                    and_(
                        Task.status == "snoozed",
                        Task.snooze_until <= now
                    )
                )
            )
        
        query = query.order_by(Task.due_date)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def bulk_action(
        db: AsyncSession,
        task_ids: List[int],
        action: str
    ) -> Dict[str, int]:
        """Perform bulk action on tasks"""
        if action not in ["complete", "cancel", "snooze"]:
            raise ValueError(f"Invalid bulk action: {action}")
        
        results = {"success": 0, "failed": 0}
        
        for task_id in task_ids:
            try:
                if action == "complete":
                    await TaskService.complete_task(db, task_id)
                elif action == "cancel":
                    await TaskService.cancel_task(db, task_id)
                elif action == "snooze":
                    await TaskService.snooze_task(db, task_id, "1d")
                results["success"] += 1
            except Exception as e:
                logger.error(f"Error performing {action} on task {task_id}: {e}")
                results["failed"] += 1
        
        return results

