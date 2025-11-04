import logging
import httpx
from typing import Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Send notifications to mobile devices"""
    
    def __init__(self, bot_agent=None):
        self.method = settings.NOTIFICATION_METHOD
        self._bot_agent = bot_agent  # Telegram bot agent for rich notifications
    
    async def send_notification(
        self,
        title: str,
        message: str,
        data: Optional[Dict] = None,
        priority: str = "default"
    ) -> bool:
        """Send notification via configured method"""
        
        if self.method == "ntfy":
            return await self._send_ntfy(title, message, data, priority)
        elif self.method == "pushover":
            return await self._send_pushover(title, message, priority)
        elif self.method == "telegram":
            return await self._send_telegram(title, message)
        else:
            logger.warning(f"Unknown notification method: {self.method}")
            return False
    
    async def _send_ntfy(
        self,
        title: str,
        message: str,
        data: Optional[Dict],
        priority: str
    ) -> bool:
        """Send notification via ntfy.sh"""
        if not settings.NTFY_TOPIC:
            logger.warning("NTFY_TOPIC not configured")
            return False
        
        try:
            url = f"{settings.NTFY_SERVER}/{settings.NTFY_TOPIC}"
            
            headers = {
                "Title": title,
                "Priority": priority,
                "Tags": "briefcase,mag"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    content=message,
                    headers=headers
                )
                
                if response.status_code == 200:
                    logger.info(f"Notification sent via ntfy: {title}")
                    return True
                else:
                    logger.error(f"ntfy error: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending ntfy notification: {e}")
            return False
    
    async def _send_pushover(self, title: str, message: str, priority: str) -> bool:
        """Send notification via Pushover"""
        if not settings.PUSHOVER_USER_KEY or not settings.PUSHOVER_APP_TOKEN:
            logger.warning("Pushover credentials not configured")
            return False
        
        try:
            priority_map = {"low": -1, "default": 0, "high": 1, "urgent": 2}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.pushover.net/1/messages.json",
                    data={
                        "token": settings.PUSHOVER_APP_TOKEN,
                        "user": settings.PUSHOVER_USER_KEY,
                        "title": title,
                        "message": message,
                        "priority": priority_map.get(priority, 0)
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"Notification sent via Pushover: {title}")
                    return True
                else:
                    logger.error(f"Pushover error: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending Pushover notification: {e}")
            return False
    
    async def _send_telegram(self, title: str, message: str) -> bool:
        """Send notification via Telegram"""
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
            logger.warning("Telegram credentials not configured")
            return False
        
        try:
            # Try to use bot agent if available (for rich notifications)
            if hasattr(self, '_bot_agent') and self._bot_agent:
                return await self._bot_agent.send_rich_notification(title, message)
            
            # Fallback to simple API call
            text = f"*{title}*\n\n{message}"
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": settings.TELEGRAM_CHAT_ID,
                        "text": text,
                        "parse_mode": "Markdown"
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"Notification sent via Telegram: {title}")
                    return True
                else:
                    logger.error(f"Telegram error: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
            return False
    
    async def send_job_alert(self, jobs: list) -> bool:
        """Send alert about new jobs"""
        if not jobs:
            return True
        
        job_count = len(jobs)
        
        # Create message with top jobs
        message_lines = [f"Found {job_count} new job(s):"]
        
        for job in jobs[:5]:  # Show top 5
            match_text = f" ({job.ai_match_score:.0f}% match)" if job.ai_match_score else ""
            message_lines.append(f"\n• {job.title} at {job.company}{match_text}")
        
        if job_count > 5:
            message_lines.append(f"\n...and {job_count - 5} more")
        
        message = "\n".join(message_lines)
        
        # Use rich notification if Telegram bot agent is available
        if self.method == "telegram" and hasattr(self, '_bot_agent') and self._bot_agent:
            return await self._bot_agent.send_rich_notification(
                title="🆕 New Jobs Found!",
                message=message,
                jobs=jobs[:3]  # Include top 3 jobs as buttons
            )
        
        return await self.send_notification(
            title="New Jobs Found!",
            message=message,
            priority="high"
        )
    
    async def send_task_reminder(self, task) -> bool:
        """Send reminder notification for a task"""
        if not task:
            return False
        
        # Build task reminder message
        job_title = task.job.title if hasattr(task, 'job') and task.job else "Unknown Job"
        company = task.job.company if hasattr(task, 'job') and task.job else "Unknown Company"
        
        # Format due date
        from datetime import datetime
        due_str = task.due_date.strftime("%Y-%m-%d %H:%M") if task.due_date else "Unknown"
        
        title = f"📋 Task Reminder: {task.title}"
        
        message_lines = [
            f"Task: {task.title}",
            f"Type: {task.task_type.replace('_', ' ').title()}",
            f"Priority: {task.priority.upper()}",
            f"Due: {due_str}",
            f"Job: {job_title} at {company}"
        ]
        
        if task.notes:
            message_lines.append(f"\nNotes: {task.notes}")
        
        # Add action buttons for Telegram if available
        if self.method == "telegram" and hasattr(self, '_bot_agent') and self._bot_agent:
            # Try to send with task action buttons
            try:
                # Check if bot agent supports task actions
                if hasattr(self._bot_agent, 'send_task_reminder'):
                    return await self._bot_agent.send_task_reminder(task)
            except Exception as e:
                logger.warning(f"Error sending rich task reminder: {e}")
        
        message = "\n".join(message_lines)
        
        # Map task priority to notification priority
        priority_map = {
            "high": "high",
            "medium": "default",
            "low": "low"
        }
        notification_priority = priority_map.get(task.priority, "default")
        
        return await self.send_notification(
            title=title,
            message=message,
            priority=notification_priority
        )