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
                "/api/v1/config",
                "/api/v1/health",
                "/health",
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
                                    if "version" in config_data or "models" in config_data:
                                        capabilities.append("api")
                            except:
                                pass
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
            prompt = self._format_context_prompt(context)
            
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
                        # Create chat with initial message
                        chat_data = {
                            "name": context.get("job", {}).get("title", "Job Analysis")[:100],
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
    
    def _format_context_prompt(self, context: Dict[str, Any]) -> str:
        """Format job context as a prompt for OpenWebUI"""
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


# Singleton instance
_openwebui_service: Optional[OpenWebUIService] = None


def get_openwebui_service() -> OpenWebUIService:
    """Get singleton OpenWebUI service instance"""
    global _openwebui_service
    if _openwebui_service is None:
        _openwebui_service = OpenWebUIService()
    return _openwebui_service

