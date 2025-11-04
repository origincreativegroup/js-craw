"""Generic Career Page Crawler - AI-assisted parsing for custom career pages"""
import logging
import httpx
import json
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class GenericCrawler:
    """AI-assisted crawler for custom career pages"""

    def __init__(self, company_name: str, career_url: str, ollama_host: str = "http://192.168.50.248:11434", ollama_model: str = "llama3.1"):
        """
        Initialize generic crawler

        Args:
            company_name: Human-readable company name
            career_url: URL to company's career page
            ollama_host: Ollama API endpoint
            ollama_model: Model to use for parsing
        """
        self.company_name = company_name
        self.career_url = career_url
        self.ollama_host = ollama_host
        self.ollama_model = ollama_model

    async def fetch_jobs(self) -> List[Dict]:
        """
        Fetch jobs from career page using AI parsing

        Returns:
            List of job dictionaries with normalized fields
        """
        try:
            logger.info(f"Fetching career page for {self.company_name}: {self.career_url}")

            # Fetch HTML
            html = await self._fetch_html(self.career_url)

            if not html:
                logger.warning(f"No HTML content fetched for {self.company_name}")
                return []

            # Extract jobs using AI
            jobs = await self._extract_jobs_with_ai(html)

            logger.info(f"Found {len(jobs)} jobs for {self.company_name} via AI parsing")

            # Normalize jobs
            normalized_jobs = []
            for job in jobs:
                normalized = self._normalize_job(job)
                if normalized:
                    normalized_jobs.append(normalized)

            return normalized_jobs

        except Exception as e:
            logger.error(f"Error fetching jobs for {self.company_name}: {e}", exc_info=True)
            raise

    async def _fetch_html(self, url: str) -> str:
        """Fetch HTML content from URL"""
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.error(f"Error fetching HTML from {url}: {e}")
            raise

    async def _extract_jobs_with_ai(self, html: str) -> List[Dict]:
        """
        Use Ollama to extract job listings from HTML

        Args:
            html: Raw HTML content

        Returns:
            List of extracted job dictionaries
        """
        try:
            # Clean HTML - extract text content
            soup = BeautifulSoup(html, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()

            # Get text content (limit to first 10000 chars to fit in context)
            text_content = soup.get_text()
            text_content = ' '.join(text_content.split())  # Normalize whitespace
            text_content = text_content[:10000]

            # Prepare prompt for Ollama
            prompt = f"""You are analyzing a company career page. Extract job listings from the text below.

Company: {self.company_name}
Career Page: {self.career_url}

Text Content:
{text_content}

Extract job listings and return ONLY a valid JSON array (no markdown, no explanation) with this exact format:
[
  {{
    "title": "Software Engineer",
    "location": "Remote" or "San Francisco, CA" or null,
    "url": "https://company.com/jobs/123" or null,
    "job_type": "Full-time" or "Contract" or null,
    "description": "Brief description..." or null
  }}
]

Important:
- Return ONLY the JSON array
- If no jobs found, return []
- Include only real job postings
- Make URLs absolute if relative
"""

            # Call Ollama
            async with httpx.AsyncClient(timeout=60.0) as client:
                logger.info(f"Calling Ollama at {self.ollama_host} with model {self.ollama_model}")

                response = await client.post(
                    f"{self.ollama_host}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "temperature": 0.1,  # Low temperature for consistency
                    },
                    timeout=60.0
                )
                response.raise_for_status()

                result = response.json()
                ai_response = result.get("response", "")

                logger.debug(f"AI response: {ai_response[:500]}...")

                # Parse JSON from response
                jobs = self._parse_ai_response(ai_response)

                return jobs

        except Exception as e:
            logger.error(f"Error extracting jobs with AI: {e}", exc_info=True)
            return []

    def _parse_ai_response(self, response: str) -> List[Dict]:
        """
        Parse AI response to extract JSON

        Args:
            response: Raw AI response text

        Returns:
            List of job dictionaries
        """
        try:
            # Try to find JSON array in response
            # Sometimes AI wraps it in markdown code blocks
            response = response.strip()

            # Remove markdown code blocks if present
            if response.startswith("```"):
                lines = response.split('\n')
                response = '\n'.join(lines[1:-1])  # Remove first and last line
                response = response.strip()

            # Try to parse JSON
            jobs = json.loads(response)

            if not isinstance(jobs, list):
                logger.warning("AI response is not a list")
                return []

            return jobs

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Response was: {response[:500]}")
            return []
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return []

    def _normalize_job(self, job_data: Dict) -> Optional[Dict]:
        """
        Normalize AI-extracted job data

        Args:
            job_data: Raw job data from AI

        Returns:
            Normalized job dictionary
        """
        try:
            title = job_data.get("title", "").strip()
            if not title:
                return None

            # Build job URL - make absolute if relative
            job_url = job_data.get("url", "")
            if job_url and not job_url.startswith("http"):
                job_url = urljoin(self.career_url, job_url)

            # If no URL provided, use career page URL
            if not job_url:
                job_url = self.career_url

            # Generate external ID
            # Use URL if available, otherwise use title
            url_part = urlparse(job_url).path.replace("/", "_") or title.replace(" ", "_").lower()
            external_id = f"generic_{self.company_name.lower().replace(' ', '_')}_{url_part}"[:255]

            normalized = {
                "external_id": external_id,
                "title": title,
                "company": self.company_name,
                "location": job_data.get("location"),
                "url": job_url,
                "source_url": job_url,
                "description": job_data.get("description"),
                "job_type": job_data.get("job_type"),
                "posted_date": None,  # AI usually can't extract reliable dates
                "platform": "generic",
            }

            return normalized

        except Exception as e:
            logger.error(f"Error normalizing generic job: {e}", exc_info=True)
            return None

    def close(self):
        """Cleanup - no-op for HTTP-based crawler"""
        pass
