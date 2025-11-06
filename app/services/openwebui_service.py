"""OpenWebUI integration service"""
import logging
import httpx
from typing import Dict, Optional, Any
from datetime import datetime
from app.config import settings
from app.utils.crypto import encrypt_password, decrypt_password

logger = logging.getLogger(__name__)


class OpenWebUIService:
    """Service for interacting with OpenWebUI API"""
    
    def __init__(self):
        self.base_url = settings.OPENWEBUI_URL.rstrip('/')
        self.enabled = settings.OPENWEBUI_ENABLED
        self._health_cache: Optional[Dict[str, Any]] = None
        self._health_cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minutes
    
    def _get_auth_headers(self, api_key: Optional[str] = None, auth_token: Optional[str] = None) -> Dict[str, str]:
        """Get authentication headers for OpenWebUI API"""
        headers = {"Content-Type": "application/json"}
        
        # Try API key first (if available)
        if api_key:
            # OpenWebUI typically uses Bearer token or X-API-Key header
            headers["Authorization"] = f"Bearer {api_key}"
            # Alternative: headers["X-API-Key"] = api_key
        
        # Fallback to auth token
        elif auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        
        return headers
    
    async def check_health(self, api_key: Optional[str] = None, auth_token: Optional[str] = None) -> Dict[str, Any]:
        """Check OpenWebUI health and connectivity"""
        if not self.enabled:
            return {
                "status": "disabled",
                "message": "OpenWebUI integration is disabled"
            }
        
        # Check cache first
        if self._health_cache and self._health_cache_time:
            age = (datetime.utcnow() - self._health_cache_time).total_seconds()
            if age < self._cache_ttl_seconds:
                return self._health_cache
        
        try:
            # Try common health/status endpoints
            health_endpoints = [
                "/api/v1/configs",
                "/api/v1/health",
                "/api/health",
                "/health",
                "/api/v1/models",
                "/api/config"
            ]
            
            status = "offline"
            message = "Unable to connect"
            capabilities = []
            
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                for endpoint in health_endpoints:
                    try:
                        response = await client.get(f"{self.base_url}{endpoint}")
                        if response.status_code == 200:
                            status = "online"
                            message = "OpenWebUI is accessible"
                            capabilities.append("http_access")
                            
                            # Try to parse config to get capabilities
                            try:
                                config_data = response.json()
                                if isinstance(config_data, dict):
                                    # Check for common OpenWebUI config keys
                                    if "version" in config_data or "models" in config_data or "data" in config_data:
                                        capabilities.append("api")
                            except:
                                # If we get 200 but not JSON, it's still accessible
                                pass
                            break
                        elif response.status_code == 401:
                            # Authentication required but service is online
                            status = "online_auth_required"
                            message = "OpenWebUI is accessible but requires authentication"
                            capabilities.append("http_access")
                            capabilities.append("auth_required")
                            break
                    except Exception as e:
                        logger.debug(f"Health check failed for {endpoint}: {e}")
                        continue
            
            # Test authentication if credentials provided
            auth_status = None
            if api_key or auth_token:
                auth_result = await self.verify_auth(api_key, auth_token)
                auth_status = auth_result.get("status")
                if auth_status == "authenticated":
                    capabilities.append("authenticated_api")
                    status = "online_authenticated"
            
            result = {
                "status": status,
                "message": message,
                "last_checked": datetime.utcnow().isoformat(),
                "capabilities": capabilities,
                "auth_status": auth_status
            }
            
            # Cache the result
            self._health_cache = result
            self._health_cache_time = datetime.utcnow()
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking OpenWebUI health: {e}", exc_info=True)
            result = {
                "status": "error",
                "message": f"Health check failed: {str(e)}",
                "last_checked": datetime.utcnow().isoformat(),
                "capabilities": [],
                "auth_status": None
            }
            return result
    
    async def verify_auth(self, api_key: Optional[str] = None, auth_token: Optional[str] = None) -> Dict[str, Any]:
        """Verify OpenWebUI authentication"""
        if not self.enabled:
            return {"status": "disabled", "message": "OpenWebUI integration is disabled"}
        
        try:
            headers = self._get_auth_headers(api_key, auth_token)
            
            # Try common auth verification endpoints
            auth_endpoints = [
                "/api/v1/user",
                "/api/v1/auths",
                "/api/user",
                "/api/auth/verify"
            ]
            
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                for endpoint in auth_endpoints:
                    try:
                        response = await client.get(
                            f"{self.base_url}{endpoint}",
                            headers=headers
                        )
                        
                        if response.status_code == 200:
                            user_data = response.json()
                            return {
                                "status": "authenticated",
                                "message": "Authentication successful",
                                "user": user_data if isinstance(user_data, dict) else None
                            }
                        elif response.status_code == 401:
                            return {
                                "status": "invalid_token",
                                "message": "Authentication failed - invalid token"
                            }
                    except Exception as e:
                        logger.debug(f"Auth verification failed for {endpoint}: {e}")
                        continue
            
            # If no auth endpoints worked, assume auth not required
            return {
                "status": "no_auth_required",
                "message": "OpenWebUI does not require authentication"
            }
            
        except Exception as e:
            logger.error(f"Error verifying OpenWebUI authentication: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Auth verification failed: {str(e)}"
            }
    
    async def send_context(self, context: Dict[str, Any], api_key: Optional[str] = None, auth_token: Optional[str] = None) -> Dict[str, Any]:
        """Send job context to OpenWebUI to create a new chat"""
        if not self.enabled:
            return {"success": False, "error": "OpenWebUI integration is disabled"}
        
        try:
            headers = self._get_auth_headers(api_key, auth_token)
            
            # Format the context as a prompt
            is_full_context = "summary" in context and "companies" in context
            prompt = self._format_context_prompt(context, is_full_context=is_full_context)
            
            # Try to create a new chat via OpenWebUI API
            # OpenWebUI API endpoint: POST /api/v1/chats
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                # First, try to create a chat
                chat_endpoints = [
                    "/api/v1/chats",
                    "/api/chats",
                    "/api/v1/chat"
                ]
                
                for endpoint in chat_endpoints:
                    try:
                        # Determine chat name based on context type
                        if is_full_context:
                            # Full dataset context - use summary or generic name
                            summary = context.get("summary", {})
                            if summary:
                                total_jobs = summary.get("total_jobs", 0)
                                chat_name = f"Job Search Analysis ({total_jobs} jobs)"
                            else:
                                chat_name = "Job Search Analysis"
                        else:
                            # Single job context - use job title
                            chat_name = context.get("job", {}).get("title", "Job Analysis")
                        
                        # Create chat with initial message
                        chat_data = {
                            "name": chat_name[:100],
                            "messages": [
                                {
                                    "role": "user",
                                    "content": prompt
                                }
                            ]
                        }
                        
                        response = await client.post(
                            f"{self.base_url}{endpoint}",
                            headers=headers,
                            json=chat_data
                        )
                        
                        if response.status_code in [200, 201]:
                            result = response.json()
                            return {
                                "success": True,
                                "chat_id": result.get("id") or result.get("chat_id"),
                                "message": "Context sent to OpenWebUI successfully"
                            }
                    except Exception as e:
                        logger.debug(f"Failed to create chat via {endpoint}: {e}")
                        continue
                
                # Fallback: Return URL with context as query parameter
                # This allows opening OpenWebUI with pre-filled context
                import urllib.parse
                context_param = urllib.parse.quote(prompt[:500])  # Limit length
                return {
                    "success": True,
                    "url": f"{self.base_url}/?context={context_param}",
                    "message": "Use this URL to open OpenWebUI with context",
                    "fallback": True
                }
                
        except Exception as e:
            logger.error(f"Error sending context to OpenWebUI: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to send context: {str(e)}"
            }
    
    def _format_context_prompt(self, context: Dict[str, Any], is_full_context: bool = False) -> str:
        """Format job context as a prompt for OpenWebUI"""
        if is_full_context and "summary" in context:
            # Full context mode - summarize all sections
            return self._format_full_context_prompt(context)
        
        # Single job context mode (backward compatible)
        job = context.get("job", {})
        prompt_type = context.get("prompt_type", "analyze")
        
        base_prompt = f"""Analyze this job opportunity for me:

Job Title: {job.get('title', 'N/A')}
Company: {job.get('company', 'N/A')}
Location: {job.get('location', 'N/A')}
Match Score: {job.get('ai_match_score', 'N/A')}%
"""
        
        if job.get('description'):
            base_prompt += f"\nJob Description:\n{job.get('description', '')[:2000]}\n"
        
        if job.get('ai_summary'):
            base_prompt += f"\nAI Analysis Summary:\n{job.get('ai_summary')}\n"
        
        if job.get('ai_pros'):
            pros = job.get('ai_pros', [])
            if isinstance(pros, list):
                base_prompt += f"\nPros:\n" + "\n".join(f"- {p}" for p in pros[:5]) + "\n"
        
        if job.get('ai_cons'):
            cons = job.get('ai_cons', [])
            if isinstance(cons, list):
                base_prompt += f"\nCons:\n" + "\n".join(f"- {c}" for c in cons[:5]) + "\n"
        
        # Add prompt-specific instructions
        if prompt_type == "follow_up":
            base_prompt += "\n\nHelp me write a professional follow-up email for this application. Include key talking points based on the job description."
        elif prompt_type == "interview_prep":
            base_prompt += "\n\nHelp me prepare for an interview for this role. Generate likely interview questions and suggest how to answer them based on the job requirements."
        elif prompt_type == "cover_letter":
            base_prompt += "\n\nHelp me write a compelling cover letter for this position. Tailor it to highlight how my experience matches the job requirements."
        else:
            base_prompt += "\n\nPlease analyze this opportunity and provide insights on:\n- How well this role matches my profile\n- Key skills and requirements\n- Potential red flags or concerns\n- Recommendations for next steps"
        
        return base_prompt
    
    def _format_full_context_prompt(self, context: Dict[str, Any]) -> str:
        """Format full dataset context as a comprehensive prompt"""
        summary = context.get("summary", {})
        companies = context.get("companies", [])
        jobs = context.get("jobs", [])
        applications = context.get("applications", [])
        tasks = context.get("tasks", [])
        follow_ups = context.get("follow_ups", [])
        documents = context.get("generated_documents", [])
        crawl_history = context.get("crawl_history", [])
        user_profile = context.get("user_profile", {})
        
        prompt = """# Complete Job Search Dataset Context

## Summary Statistics
"""
        if summary:
            prompt += f"- Total Jobs: {summary.get('total_jobs', 0)}\n"
            prompt += f"- Recent Jobs (30 days): {summary.get('recent_jobs', 0)}\n"
            prompt += f"- Recommended Jobs: {summary.get('recommended_jobs', 0)}\n"
            prompt += f"- Total Applications: {summary.get('total_applications', 0)}\n"
            prompt += f"- Pending Tasks: {summary.get('pending_tasks', 0)}\n"
            prompt += f"- Active Companies: {summary.get('active_companies', 0)}\n"
        
        if user_profile:
            prompt += "\n## User Profile\n"
            if user_profile.get("skills"):
                prompt += f"Skills: {', '.join(user_profile['skills'][:10])}\n"
            if user_profile.get("preferences"):
                prompt += f"Preferences: {user_profile['preferences']}\n"
        
        if companies:
            prompt += f"\n## Active Companies ({len(companies)} shown)\n"
            for c in companies[:10]:
                prompt += f"- {c['name']} ({c['crawler_type']}) - {c['jobs_count']} jobs\n"
        
        if jobs:
            prompt += f"\n## Recent Jobs ({len(jobs)} shown)\n"
            for j in jobs[:15]:
                prompt += f"- {j['title']} at {j['company']} (Score: {j.get('ai_match_score', 'N/A')}%, Status: {j['status']})\n"
        
        if applications:
            prompt += f"\n## Applications ({len(applications)} shown)\n"
            for a in applications[:10]:
                prompt += f"- {a.get('job_title', 'N/A')} - Status: {a['status']}\n"
        
        if tasks:
            prompt += f"\n## Pending Tasks ({len(tasks)} shown)\n"
            for t in tasks[:10]:
                prompt += f"- {t['title']} ({t['task_type']}) - Priority: {t['priority']}, Due: {t.get('due_date', 'N/A')}\n"
        
        if follow_ups:
            prompt += f"\n## Upcoming Follow-ups ({len(follow_ups)} shown)\n"
            for f in follow_ups[:10]:
                prompt += f"- {f.get('job_title', 'N/A')} - Date: {f.get('follow_up_date', 'N/A')}\n"
        
        if documents:
            prompt += f"\n## Generated Documents ({len(documents)} shown)\n"
            for d in documents[:10]:
                prompt += f"- {d['document_type']} for {d.get('job_title', 'N/A')} - Status: {d.get('review_status', 'pending')}\n"
        
        if crawl_history:
            prompt += f"\n## Recent Crawl History ({len(crawl_history)} shown)\n"
            for c in crawl_history[:10]:
                prompt += f"- {c.get('company_name', 'N/A')} - {c['jobs_found']} jobs found, Status: {c['status']}\n"
        
        prompt += "\n\nBased on this complete dataset, help me understand:\n"
        prompt += "- Overall job search progress and trends\n"
        prompt += "- Recommended next actions\n"
        prompt += "- Areas that need attention\n"
        prompt += "- Insights about my job search strategy"
        
        return prompt


# Singleton instance
_openwebui_service: Optional[OpenWebUIService] = None


def get_openwebui_service() -> OpenWebUIService:
    """Get singleton OpenWebUI service instance"""
    global _openwebui_service
    if _openwebui_service is None:
        _openwebui_service = OpenWebUIService()
    return _openwebui_service

