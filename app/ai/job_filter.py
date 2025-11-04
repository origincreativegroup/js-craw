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
    
    async def filter_and_rank_jobs(self, limit: Optional[int] = None) -> List[Job]:
        """
        Analyze all jobs in database and rank them based on user preferences.
        Uses Ollama to intelligently match jobs to user profile.
        
        Args:
            limit: Maximum number of jobs to return (default: all)
            
        Returns:
            List of jobs sorted by AI match score
        """
        async with AsyncSessionLocal() as db:
            # Get user profile/preferences
            user_profile = await self._get_user_profile(db)
            
            # Get all jobs that haven't been analyzed yet or need re-ranking
            # Focus on new jobs or jobs without ai_recommended flag
            result = await db.execute(
                select(Job)
                .where(Job.description.isnot(None))
                .order_by(Job.discovered_at.desc())
                .limit(limit or 1000)  # Limit for performance
            )
            jobs = result.scalars().all()
            
            logger.info(f"Analyzing {len(jobs)} jobs with AI...")
            
            ranked_jobs = []
            for job in jobs:
                try:
                    # Use Ollama to analyze job match
                    match_data = await self._analyze_job_match(job, user_profile)
                    
                    # Update job with AI analysis
                    if match_data:
                        job.ai_match_score = match_data.get('match_score', 50)
                        job.ai_recommended = match_data.get('recommended', False)
                        job.ai_summary = match_data.get('summary', job.ai_summary)
                        job.ai_pros = match_data.get('pros', job.ai_pros)
                        job.ai_cons = match_data.get('cons', job.ai_cons)
                        job.ai_keywords_matched = match_data.get('keywords_matched', job.ai_keywords_matched)
                    
                    ranked_jobs.append(job)
                    
                except Exception as e:
                    logger.error(f"Error analyzing job {job.id}: {e}", exc_info=True)
                    # Keep job with default score
                    ranked_jobs.append(job)
            
            await db.commit()
            
            # Sort by match score (highest first)
            ranked_jobs.sort(key=lambda j: j.ai_match_score or 0, reverse=True)
            
            logger.info(f"Ranked {len(ranked_jobs)} jobs. Top score: {ranked_jobs[0].ai_match_score if ranked_jobs else 'N/A'}")
            
            return ranked_jobs
    
    async def select_top_jobs(self, count: int = 5) -> List[Job]:
        """
        Select the top N jobs for the day based on AI ranking.
        Marks them with ai_rank and ai_selected_date.
        
        Args:
            count: Number of top jobs to select
            
        Returns:
            List of top ranked jobs
        """
        async with AsyncSessionLocal() as db:
            # Get jobs from today that are recommended or have high scores
            today = datetime.utcnow().date()
            result = await db.execute(
                select(Job)
                .where(
                    Job.discovered_at >= datetime.combine(today, datetime.min.time()),
                    Job.ai_match_score.isnot(None)
                )
                .order_by(Job.ai_match_score.desc(), Job.discovered_at.desc())
                .limit(count * 3)  # Get more candidates for final selection
            )
            candidate_jobs = result.scalars().all()
            
            if not candidate_jobs:
                logger.info("No jobs found for today to rank")
                return []
            
            # Use Ollama to make final intelligent selection from candidates
            top_jobs = await self._intelligent_selection(candidate_jobs[:count * 3], count)
            
            # Update rankings
            today_datetime = datetime.utcnow()
            for i, job in enumerate(top_jobs, 1):
                job.ai_rank = i
                job.ai_selected_date = today_datetime
                job.ai_recommended = True
            
            await db.commit()
            
            logger.info(f"Selected top {len(top_jobs)} jobs for today")
            return top_jobs
    
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

    async def filter_and_rank_jobs(self, limit: Optional[int] = None) -> List[Job]:
        """
        Analyze all jobs in database and rank them based on user preferences.
        Uses Ollama to intelligently match jobs to user profile.
        
        Args:
            limit: Maximum number of jobs to return (default: all)
            
        Returns:
            List of jobs sorted by AI match score
        """
        async with AsyncSessionLocal() as db:
            # Get user profile/preferences
            user_profile = await self._get_user_profile(db)
            
            # Get all jobs that haven't been analyzed yet or need re-ranking
            # Focus on new jobs or jobs without ai_recommended flag
            result = await db.execute(
                select(Job)
                .where(Job.description.isnot(None))
                .order_by(Job.discovered_at.desc())
                .limit(limit or 1000)  # Limit for performance
            )
            jobs = result.scalars().all()
            
            logger.info(f"Analyzing {len(jobs)} jobs with AI...")
            
            ranked_jobs = []
            for job in jobs:
                try:
                    # Use Ollama to analyze job match
                    match_data = await self._analyze_job_match(job, user_profile)
                    
                    # Update job with AI analysis
                    if match_data:
                        job.ai_match_score = match_data.get('match_score', 50)
                        job.ai_recommended = match_data.get('recommended', False)
                        job.ai_summary = match_data.get('summary', job.ai_summary)
                        job.ai_pros = match_data.get('pros', job.ai_pros)
                        job.ai_cons = match_data.get('cons', job.ai_cons)
                        job.ai_keywords_matched = match_data.get('keywords_matched', job.ai_keywords_matched)
                    
                    ranked_jobs.append(job)
                    
                except Exception as e:
                    logger.error(f"Error analyzing job {job.id}: {e}", exc_info=True)
                    # Keep job with default score
                    ranked_jobs.append(job)
            
            await db.commit()
            
            # Sort by match score (highest first)
            ranked_jobs.sort(key=lambda j: j.ai_match_score or 0, reverse=True)
            
            logger.info(f"Ranked {len(ranked_jobs)} jobs. Top score: {ranked_jobs[0].ai_match_score if ranked_jobs else 'N/A'}")
            
            return ranked_jobs
    
    async def select_top_jobs(self, count: int = 5) -> List[Job]:
        """
        Select the top N jobs for the day based on AI ranking.
        Marks them with ai_rank and ai_selected_date.
        
        Args:
            count: Number of top jobs to select
            
        Returns:
            List of top ranked jobs
        """
        async with AsyncSessionLocal() as db:
            # Get jobs from today that are recommended or have high scores
            today = datetime.utcnow().date()
            result = await db.execute(
                select(Job)
                .where(
                    Job.discovered_at >= datetime.combine(today, datetime.min.time()),
                    Job.ai_match_score.isnot(None)
                )
                .order_by(Job.ai_match_score.desc(), Job.discovered_at.desc())
                .limit(count * 3)  # Get more candidates for final selection
            )
            candidate_jobs = result.scalars().all()
            
            if not candidate_jobs:
                logger.info("No jobs found for today to rank")
                return []
            
            # Use Ollama to make final intelligent selection from candidates
            top_jobs = await self._intelligent_selection(candidate_jobs[:count * 3], count)
            
            # Update rankings
            today_datetime = datetime.utcnow()
            for i, job in enumerate(top_jobs, 1):
                job.ai_rank = i
                job.ai_selected_date = today_datetime
                job.ai_recommended = True
            
            await db.commit()
            
            logger.info(f"Selected top {len(top_jobs)} jobs for today")
            return top_jobs
