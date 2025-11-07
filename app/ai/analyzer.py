import logging
import json
from typing import Dict, List
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class JobAnalyzer:
    """Analyzes jobs using local Ollama LLM"""
    
    def __init__(self):
        self.ollama_url = f"{settings.OLLAMA_HOST}/api/generate"
        self.model = settings.OLLAMA_MODEL
    
    @staticmethod
    def _is_enabled() -> bool:
        return getattr(settings, "OLLAMA_ENABLED", True)
    
    def _analysis_disabled_response(self) -> Dict:
        logger.info("Ollama integration disabled; returning fallback job analysis")
        return {
            'summary': 'AI analysis disabled in settings.',
            'match_score': 50,
            'pros': [],
            'cons': [],
            'keywords_matched': [],
            'key_requirements': [],
            'overall_fit': 'AI analysis disabled'
        }
    
    async def analyze_job(self, job_data: Dict, search_criteria) -> Dict:
        """Analyze a job posting and match against criteria"""
        if not self._is_enabled():
            return self._analysis_disabled_response()
        
        # Build analysis prompt
        prompt = self._build_analysis_prompt(job_data, search_criteria)
        
        try:
            # Call Ollama API
            analysis_text = await self._call_ollama(prompt)
            
            # Parse response
            analysis = self._parse_analysis(analysis_text)
            
            # Calculate match score
            match_score = self._calculate_match_score(job_data, search_criteria, analysis)
            analysis['match_score'] = match_score
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in job analysis: {e}", exc_info=True)
            return self._analysis_disabled_response()
    
    def _build_analysis_prompt(self, job_data: Dict, criteria) -> str:
        """Build prompt for AI analysis"""
        description = job_data.get('description', 'No description available')
        
        prompt = f"""Analyze this job posting and provide insights:

Job Title: {job_data['title']}
Company: {job_data['company']}
Location: {job_data.get('location', 'Not specified')}
Description: {description[:1000]}  # Limit description length

Search Criteria:
- Keywords: {criteria.keywords}
- Location: {criteria.location or 'Any'}
- Remote: {criteria.remote_only}
- Job Type: {criteria.job_type or 'Any'}
- Experience Level: {criteria.experience_level or 'Any'}

Provide your analysis in the following JSON format:
{{
    "summary": "A 2-3 sentence summary of the role and company",
    "pros": ["List of 3-5 positive aspects about this job"],
    "cons": ["List of 2-4 potential concerns or drawbacks"],
    "keywords_matched": ["List of search keywords that appear in the job posting"],
    "key_requirements": ["List of main requirements mentioned"],
    "overall_fit": "Brief assessment of how well this matches the criteria"
}}

Be concise and focus on the most important information."""
        
        return prompt
    
    async def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API"""
        if not self._is_enabled():
            raise RuntimeError("Ollama integration disabled via settings")

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    self.ollama_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,  # Lower temperature for more consistent output
                            "num_predict": 500,  # Limit response length
                        }
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get('response', '')
                else:
                    logger.error(f"Ollama API error: {response.status_code}")
                    return ""
                    
            except Exception as e:
                logger.error(f"Error calling Ollama: {e}")
                return ""
    
    def _parse_analysis(self, analysis_text: str) -> Dict:
        """Parse AI response"""
        try:
            # Try to extract JSON from response
            # Sometimes LLMs add extra text around the JSON
            start = analysis_text.find('{')
            end = analysis_text.rfind('}') + 1
            
            if start >= 0 and end > start:
                json_str = analysis_text[start:end]
                parsed = json.loads(json_str)
                return parsed
            else:
                # Fallback: basic parsing
                return {
                    'summary': analysis_text[:200],
                    'pros': [],
                    'cons': [],
                    'keywords_matched': [],
                    'key_requirements': [],
                    'overall_fit': 'Unable to parse analysis'
                }
                
        except json.JSONDecodeError:
            logger.warning("Could not parse AI response as JSON")
            return {
                'summary': analysis_text[:200] if analysis_text else 'No analysis available',
                'pros': [],
                'cons': [],
                'keywords_matched': [],
                'key_requirements': [],
                'overall_fit': 'Unable to parse analysis'
            }
    
    def _calculate_match_score(self, job_data: Dict, criteria, analysis: Dict) -> float:
        """Calculate match score based on various factors"""
        score = 50.0  # Base score
        
        # Check keyword matches
        keywords = criteria.keywords.lower().split()
        title = job_data['title'].lower()
        description = (job_data.get('description') or '').lower()
        
        keyword_matches = sum(1 for kw in keywords if kw in title or kw in description)
        if keywords:
            score += (keyword_matches / len(keywords)) * 30
        
        # Location match
        if criteria.location and job_data.get('location'):
            if criteria.location.lower() in job_data['location'].lower():
                score += 10
        
        # Remote preference
        if criteria.remote_only:
            if 'remote' in title or 'remote' in description:
                score += 10
        
        # Cap at 100
        return min(score, 100.0)
    
    async def generate_report(self, jobs: List[Dict]) -> str:
        """Generate a summary report of found jobs"""
        if not self._is_enabled():
            logger.info("Ollama integration disabled; skipping AI-generated job summary")
            return f"Found {len(jobs)} jobs. Enable AI analysis in settings for detailed summaries."

        if not jobs:
            return "No new jobs found in this search."
        
        prompt = f"""Generate a brief summary report of these job search results:

Total jobs found: {len(jobs)}

Jobs:
{self._format_jobs_for_report(jobs[:10])}  # Limit to top 10

Provide a 3-4 sentence summary highlighting:
1. Total number of jobs
2. Most common job types or companies
3. Any standout opportunities
4. Overall quality of matches

Keep it concise and actionable."""
        
        report = await self._call_ollama(prompt)
        return report or f"Found {len(jobs)} jobs. Check the dashboard for details."
    
    def _format_jobs_for_report(self, jobs: List[Dict]) -> str:
        """Format jobs for report prompt"""
        lines = []
        for job in jobs:
            lines.append(f"- {job['title']} at {job['company']} ({job.get('location', 'Remote')})")
        return '\n'.join(lines)
    
    async def analyze_company_job_profile(self, job_data: Dict, company_name: str = None) -> Dict:
        """
        Enhanced analysis that builds a company profile and simplifies what they're looking for.
        This provides a clearer, more actionable summary of the job and company needs.
        """
        if not self._is_enabled():
            logger.info("Ollama integration disabled; returning fallback company profile analysis")
            return {
                'company_profile': f"Company profile for {job_data.get('company', 'Unknown Company')}",
                'company_culture': 'AI analysis disabled',
                'what_they_want': 'Enable AI analysis to generate this insight.',
                'simplified_requirements': [],
                'must_haves': [],
                'nice_to_haves': [],
                'role_summary': job_data.get('title', 'Job role'),
                'why_this_role': 'AI analysis disabled'
            }

        company = company_name or job_data.get('company', 'Unknown Company')
        description = job_data.get('description', 'No description available')
        
        prompt = f"""You are a career advisor analyzing a job posting. Your task is to:
1. Build a profile about the company based on the job posting
2. Simplify what the company is looking for into clear, actionable points
3. Extract the key requirements in plain language

Job Information:
- Title: {job_data['title']}
- Company: {company}
- Location: {job_data.get('location', 'Not specified')}
- Job Type: {job_data.get('job_type', 'Not specified')}

Job Description:
{description[:2000]}

Provide your analysis in the following JSON format:
{{
    "company_profile": "A brief 2-3 sentence profile of what this company does based on the job posting",
    "company_culture": "What the job posting reveals about the company culture and work environment",
    "what_they_want": "A simplified, plain-language summary of what the company is looking for (1-2 sentences)",
    "simplified_requirements": [
        "Core requirement 1 in simple terms",
        "Core requirement 2 in simple terms",
        "Core requirement 3 in simple terms"
    ],
    "must_haves": ["Essential requirements that are non-negotiable"],
    "nice_to_haves": ["Preferred qualifications that are flexible"],
    "role_summary": "A clear, concise summary of what this role entails in 2-3 sentences",
    "why_this_role": "Why someone might want this role (based on what the posting reveals)"
}}

Focus on:
- Making requirements easy to understand
- Highlighting what makes this company/role unique
- Being specific and actionable
- Avoiding jargon and corporate speak"""
        
        try:
            analysis_text = await self._call_ollama(prompt)
            analysis = self._parse_analysis(analysis_text)
            
            # Ensure all expected fields are present
            if 'company_profile' not in analysis:
                analysis['company_profile'] = f"Company profile for {company} based on job posting"
            if 'what_they_want' not in analysis:
                analysis['what_they_want'] = "Requirements extraction pending"
            if 'simplified_requirements' not in analysis:
                analysis['simplified_requirements'] = []
            if 'must_haves' not in analysis:
                analysis['must_haves'] = []
            if 'nice_to_haves' not in analysis:
                analysis['nice_to_haves'] = []
                
            return analysis
            
        except Exception as e:
            logger.error(f"Error in company job profile analysis: {e}", exc_info=True)
            return {
                'company_profile': f"Company profile for {company}",
                'company_culture': 'Information not available',
                'what_they_want': 'Unable to extract requirements',
                'simplified_requirements': [],
                'must_haves': [],
                'nice_to_haves': [],
                'role_summary': job_data.get('title', 'Job role'),
                'why_this_role': 'Analysis unavailable'
            }