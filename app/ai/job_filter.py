"""AI-powered job filtering and ranking agent using Ollama"""
import logging
import json
from typing import Dict, List, Optional
from datetime import datetime
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Job, UserProfile

logger = logging.getLogger(__name__)


class JobFilter:
    """AI-powered job filtering and ranking agent"""
    
    def __init__(self):
        self.ollama_url = f"{settings.OLLAMA_HOST}/api/generate"
        self.model = settings.OLLAMA_MODEL
        self._user_profile_cache = None
    
    async def filter_job(self, job_data: Dict, user_profile: Optional[Dict] = None) -> Dict:
        """
        Filter and analyze a single job posting in real-time.
        This is used during crawling to filter jobs before saving them.
        
        Args:
            job_data: Job dictionary with title, company, location, description, etc.
            user_profile: Optional user profile (will fetch if not provided)
            
        Returns:
            Dict with:
            - should_keep: bool - Whether to keep this job
            - match_score: float - AI match score (0-100)
            - recommended: bool - Whether job is recommended
            - summary: str - Brief summary
            - pros: List[str] - Positive aspects
            - cons: List[str] - Negative aspects
            - keywords_matched: List[str] - Matched keywords
        """
        try:
            # Get user profile if not provided
            if user_profile is None:
                user_profile = await self._get_user_profile_cached()
            
            # Use Ollama to analyze job match
            match_data = await self._analyze_job_match_dict(job_data, user_profile)
            
            if not match_data:
                # Default: keep job but with neutral score
                return {
                    'should_keep': True,
                    'match_score': 50.0,
                    'recommended': False,
                    'summary': '',
                    'pros': [],
                    'cons': [],
                    'keywords_matched': []
                }
            
            # Decide if job should be kept (keep all for now, but mark with score)
            # In future, could filter out low-scoring jobs: match_data.get('match_score', 50) >= 30
            should_keep = True
            
            return {
                'should_keep': should_keep,
                'match_score': match_data.get('match_score', 50.0),
                'recommended': match_data.get('recommended', False),
                'summary': match_data.get('summary', ''),
                'pros': match_data.get('pros', []),
                'cons': match_data.get('cons', []),
                'keywords_matched': match_data.get('keywords_matched', []),
                'reasoning': match_data.get('reasoning', '')
            }
            
        except Exception as e:
            logger.error(f"Error filtering job {job_data.get('title', 'unknown')}: {e}", exc_info=True)
            # On error, keep the job but with neutral score
            return {
                'should_keep': True,
                'match_score': 50.0,
                'recommended': False,
                'summary': '',
                'pros': [],
                'cons': [],
                'keywords_matched': []
            }
    
    async def filter_jobs_batch(self, jobs: List[Dict], user_profile: Optional[Dict] = None) -> List[Dict]:
        """
        Filter multiple jobs in batch (more efficient than one-by-one).
        Returns filtered list with only jobs that should be kept.
        
        Args:
            jobs: List of job dictionaries
            user_profile: Optional user profile (will fetch if not provided)
            
        Returns:
            List of jobs with AI analysis data added
        """
        if not jobs:
            return []
        
        # Get user profile if not provided
        if user_profile is None:
            user_profile = await self._get_user_profile_cached()
        
        filtered_results = []
        
        for job_data in jobs:
            try:
                filter_result = await self.filter_job(job_data, user_profile)
                
                # Add AI analysis to job data
                job_data['ai_match_score'] = filter_result['match_score']
                job_data['ai_recommended'] = filter_result['recommended']
                job_data['ai_summary'] = filter_result['summary']
                job_data['ai_pros'] = filter_result['pros']
                job_data['ai_cons'] = filter_result['cons']
                job_data['ai_keywords_matched'] = filter_result['keywords_matched']
                
                # Only keep jobs that pass filter
                if filter_result['should_keep']:
                    filtered_results.append(job_data)
                    
            except Exception as e:
                logger.error(f"Error filtering job in batch: {e}")
                # On error, keep job but with neutral score
                job_data['ai_match_score'] = 50.0
                job_data['ai_recommended'] = False
                filtered_results.append(job_data)
        
        logger.info(f"Filtered {len(jobs)} jobs down to {len(filtered_results)} matches")
        return filtered_results
    
    async def _get_user_profile(self, db: AsyncSession) -> Optional[Dict]:
        """Get user profile with preferences"""
        result = await db.execute(select(UserProfile).limit(1))
        profile = result.scalar_one_or_none()
        
        if not profile:
            # Return default preferences if no profile exists
            return {
                'preferences': {
                    'keywords': 'software engineer, developer, programmer',
                    'remote_preferred': True,
                    'skills': [],
                    'experience_level': None
                },
                'skills': [],
                'experience': []
            }
        
        return {
            'preferences': profile.preferences or {},
            'skills': profile.skills or [],
            'experience': profile.experience or [],
            'education': profile.education or []
        }
    
    async def _analyze_job_match(self, job: Job, user_profile: Dict) -> Optional[Dict]:
        """
        Use Ollama to intelligently analyze how well a job matches user preferences
        """
        preferences = user_profile.get('preferences', {})
        skills = user_profile.get('skills', [])
        
        # Build intelligent prompt
        prompt = self._build_match_prompt(job, preferences, skills)
        
        try:
            response_text = await self._call_ollama(prompt)
            match_data = self._parse_match_response(response_text)
            return match_data
        except Exception as e:
            logger.error(f"Error in AI job matching: {e}")
            return None
    
    async def _analyze_job_match_dict(self, job_data: Dict, user_profile: Dict) -> Optional[Dict]:
        """
        Use Ollama to intelligently analyze how well a job (from dict) matches user preferences
        """
        preferences = user_profile.get('preferences', {})
        skills = user_profile.get('skills', [])
        
        # Build intelligent prompt
        prompt = self._build_match_prompt_dict(job_data, preferences, skills)
        
        try:
            response_text = await self._call_ollama(prompt)
            match_data = self._parse_match_response(response_text)
            return match_data
        except Exception as e:
            logger.error(f"Error in AI job matching: {e}")
            return None
    
    def _build_match_prompt(self, job: Job, preferences: Dict, skills: List) -> str:
        """Build intelligent prompt for Ollama to analyze job match"""
        
        job_desc = (job.description or '')[:2000]  # Limit description length
        
        user_prefs = preferences.get('keywords', '')
        remote_pref = preferences.get('remote_preferred', True)
        exp_level = preferences.get('experience_level', '')
        
        prompt = f"""You are an intelligent job matching assistant. Analyze how well this job matches the user's preferences and provide a detailed assessment.

JOB POSTING:
Title: {job.title}
Company: {job.company}
Location: {job.location or 'Not specified'}
Job Type: {job.job_type or 'Not specified'}
Description: {job_desc}

USER PREFERENCES:
- Keywords/Interests: {user_prefs or 'Not specified'}
- Remote Preferred: {remote_pref}
- Experience Level: {exp_level or 'Any'}
- User Skills: {', '.join(skills[:10]) if skills else 'Not specified'}

Analyze this job and provide a JSON response with this exact format:
{{
    "match_score": 85,
    "recommended": true,
    "summary": "Brief 2-3 sentence summary of why this is a good match",
    "pros": ["Why this job fits well - 3-5 reasons"],
    "cons": ["Potential concerns - 2-3 reasons"],
    "keywords_matched": ["Specific keywords from preferences that match"],
    "reasoning": "Detailed explanation of the match score"
}}

Guidelines:
- Match score: 0-100 (100 = perfect match)
- Consider: job requirements, location (remote vs on-site), company, role level, skills needed
- Be honest about cons - don't oversell
- recommended: true if match_score >= 70

Return ONLY valid JSON, no markdown formatting."""
        
        return prompt
    
    def _build_match_prompt_dict(self, job_data: Dict, preferences: Dict, skills: List) -> str:
        """Build intelligent prompt for Ollama to analyze job match from dict"""
        
        job_desc = (job_data.get('description') or '')[:2000]  # Limit description length
        
        user_prefs = preferences.get('keywords', '')
        remote_pref = preferences.get('remote_preferred', True)
        exp_level = preferences.get('experience_level', '')
        
        prompt = f"""You are an intelligent job matching assistant. Analyze how well this job matches the user's preferences and provide a detailed assessment.

JOB POSTING:
Title: {job_data.get('title', 'Unknown')}
Company: {job_data.get('company', 'Unknown')}
Location: {job_data.get('location') or 'Not specified'}
Job Type: {job_data.get('job_type') or 'Not specified'}
Description: {job_desc}

USER PREFERENCES:
- Keywords/Interests: {user_prefs or 'Not specified'}
- Remote Preferred: {remote_pref}
- Experience Level: {exp_level or 'Any'}
- User Skills: {', '.join(skills[:10]) if skills else 'Not specified'}

Analyze this job and provide a JSON response with this exact format:
{{
    "match_score": 85,
    "recommended": true,
    "summary": "Brief 2-3 sentence summary of why this is a good match",
    "pros": ["Why this job fits well - 3-5 reasons"],
    "cons": ["Potential concerns - 2-3 reasons"],
    "keywords_matched": ["Specific keywords from preferences that match"],
    "reasoning": "Detailed explanation of the match score"
}}

Guidelines:
- Match score: 0-100 (100 = perfect match)
- Consider: job requirements, location (remote vs on-site), company, role level, skills needed
- Be honest about cons - don't oversell
- recommended: true if match_score >= 70

Return ONLY valid JSON, no markdown formatting."""
        
        return prompt
    
    async def _intelligent_selection(self, candidate_jobs: List[Job], count: int) -> List[Job]:
        """
        Use Ollama to intelligently select the best jobs from candidates.
        Considers diversity, quality, and fit.
        """
        if len(candidate_jobs) <= count:
            return candidate_jobs
        
        # Build prompt with all candidates
        jobs_summary = []
        for i, job in enumerate(candidate_jobs[:20], 1):  # Limit to 20 for prompt size
            jobs_summary.append(
                f"{i}. {job.title} at {job.company} "
                f"(Score: {job.ai_match_score}, Location: {job.location or 'Unknown'})"
            )
        
        prompt = f"""You are selecting the top {count} best job opportunities from these candidates:

{chr(10).join(jobs_summary)}

Select the {count} best jobs considering:
1. Match quality (high AI scores)
2. Diversity (different companies/roles)
3. Location preferences (remote vs on-site)
4. Overall fit

Return ONLY a JSON array of job numbers: [1, 3, 5, 7, 9]

Example: [2, 5, 8, 12, 15]"""
        
        try:
            response = await self._call_ollama(prompt)
            # Parse JSON array
            selected_indices = json.loads(response.strip())
            
            # Convert to 0-based indexing and get jobs
            top_jobs = []
            for idx in selected_indices[:count]:
                if 1 <= idx <= len(candidate_jobs):
                    top_jobs.append(candidate_jobs[idx - 1])
            
            # If parsing failed, fall back to highest scores
            if not top_jobs:
                return candidate_jobs[:count]
            
            return top_jobs
            
        except Exception as e:
            logger.error(f"Error in intelligent selection: {e}, using top scores instead")
            return candidate_jobs[:count]
    
    async def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API with optimized settings for analysis"""
        async with httpx.AsyncClient(timeout=90.0) as client:
            try:
                response = await client.post(
                    self.ollama_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.2,  # Lower for more consistent analysis
                            "num_predict": 800,  # Enough for detailed analysis
                            "top_p": 0.9,
                        }
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get('response', '').strip()
                else:
                    logger.error(f"Ollama API error: {response.status_code}")
                    return ""
                    
            except Exception as e:
                logger.error(f"Error calling Ollama: {e}")
                return ""
    
    def _parse_match_response(self, response_text: str) -> Dict:
        """Parse Ollama's JSON response"""
        try:
            # Try to extract JSON from response (might have markdown or extra text)
            text = response_text.strip()
            
            # Remove markdown code blocks if present
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()
            
            # Parse JSON
            data = json.loads(text)
            
            # Validate and normalize
            match_score = min(100, max(0, int(data.get('match_score', 50))))
            
            return {
                'match_score': match_score,
                'recommended': data.get('recommended', match_score >= 70),
                'summary': data.get('summary', ''),
                'pros': data.get('pros', []),
                'cons': data.get('cons', []),
                'keywords_matched': data.get('keywords_matched', []),
                'reasoning': data.get('reasoning', '')
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            # Return default safe values
            return {
                'match_score': 50,
                'recommended': False,
                'summary': '',
                'pros': [],
                'cons': [],
                'keywords_matched': []
            }
        except Exception as e:
            logger.error(f"Error parsing match response: {e}")
            return {
                'match_score': 50,
                'recommended': False,
                'summary': '',
                'pros': [],
                'cons': [],
                'keywords_matched': []
            }
    
    async def _get_user_profile_cached(self) -> Dict:
        """Get user profile with caching"""
        if self._user_profile_cache is None:
            async with AsyncSessionLocal() as db:
                self._user_profile_cache = await self._get_user_profile(db)
        return self._user_profile_cache
    
    def clear_profile_cache(self):
        """Clear the cached user profile (call when profile is updated)"""
        self._user_profile_cache = None
