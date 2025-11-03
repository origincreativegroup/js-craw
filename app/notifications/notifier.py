import logging
import httpx
from typing import Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Send notifications to mobile devices"""
    
    def __init__(self):
        self.method = settings.NOTIFICATION_METHOD
    
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
            message_lines.append(f"\n• {job.title} at {job.company}")
            if job.ai_match_score:
                message_lines.append(f"  Match: {job.ai_match_score:.0f}%")
        
        if job_count > 5:
            message_lines.append(f"\n...and {job_count - 5} more")
        
        message = "\n".join(message_lines)
        
        return await self.send_notification(
            title="New Jobs Found!",
            message=message,
            priority="high"
        )
