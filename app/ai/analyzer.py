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
    
    async def analyze_job(self, job_data: Dict, search_criteria) -> Dict:
        """Analyze a job posting and match against criteria"""
        
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
            return {
                'summary': 'Analysis unavailable',
                'match_score': 50,
                'pros': [],
                'cons': [],
                'keywords_matched': []
            }
    
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
