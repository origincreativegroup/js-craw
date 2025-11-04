"""Task reminder service for sending notifications about due tasks"""
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.tasks.task_service import TaskService
from app.notifications.notifier import NotificationService

logger = logging.getLogger(__name__)


class TaskReminderService:
    """Service for checking and sending task reminders"""
    
    def __init__(self, notifier: NotificationService):
        self.notifier = notifier
    
    async def check_and_send_reminders(self, db: AsyncSession):
        """
        Check for due tasks and send reminder notifications.
        Should be called periodically by scheduler.
        """
        try:
            # Get tasks due within the next hour
            due_tasks = await TaskService.get_due_tasks(
                db, within_hours=1, include_snoozed=True
            )
            
            if not due_tasks:
                logger.debug("No tasks due in the next hour")
                return
            
            logger.info(f"Found {len(due_tasks)} tasks due in the next hour")
            
            sent_count = 0
            for task in due_tasks:
                try:
                    # Check if task is actually due (not snoozed)
                    if task.status == "snoozed":
                        if task.snooze_until and task.snooze_until > datetime.utcnow():
                            continue  # Still snoozed, skip
                        else:
                            # Snooze expired, update status back to pending
                            await TaskService.update_task(db, task.id, status="pending")
                    
                    # Send reminder
                    success = await self.notifier.send_task_reminder(task)
                    if success:
                        sent_count += 1
                        logger.debug(f"Sent reminder for task {task.id}: {task.title}")
                    else:
                        logger.warning(f"Failed to send reminder for task {task.id}")
                
                except Exception as e:
                    logger.error(f"Error sending reminder for task {task.id}: {e}", exc_info=True)
            
            logger.info(f"Sent {sent_count} task reminders")
            return sent_count
            
        except Exception as e:
            logger.error(f"Error checking task reminders: {e}", exc_info=True)
            return 0

