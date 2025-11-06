"""Python wrapper for Node.js Puppeteer service"""
import logging
import httpx
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
from app.config import settings

logger = logging.getLogger(__name__)


class PuppeteerService:
    """Python wrapper for Node.js Puppeteer service"""

    def __init__(self, service_url: str = None):
        """
        Initialize Puppeteer service wrapper

        Args:
            service_url: URL of the Puppeteer service (defaults to config)
        """
        self.service_url = service_url or getattr(settings, 'PUPPETEER_SERVICE_URL', 'http://puppeteer-service:3000')
        self.base_url = f"{self.service_url.rstrip('/')}"

    async def crawl(self, company_name: str, career_url: str, timeout: int = 30000,
                    wait_for_selector: Optional[str] = None, wait_timeout: int = 30000) -> List[Dict]:
        """
        Request job extraction from Puppeteer service

        Args:
            company_name: Human-readable company name
            career_url: URL to company's career page
            timeout: Page load timeout in milliseconds
            wait_for_selector: CSS selector to wait for before extracting
            wait_timeout: Maximum time to wait for selector in milliseconds

        Returns:
            List of normalized job dictionaries
        """
        try:
            url = f"{self.base_url}/crawl"
            payload = {
                "company_name": company_name,
                "career_url": career_url,
                "timeout": timeout,
            }
            if wait_for_selector:
                payload["wait_for_selector"] = wait_for_selector
                payload["wait_timeout"] = wait_timeout

            async with httpx.AsyncClient(timeout=timeout / 1000 + 10) as client:
                logger.info(f"Requesting Puppeteer crawl for {company_name}: {career_url}")
                response = await client.post(url, json=payload)
                response.raise_for_status()

                result = response.json()
                if not result.get("success"):
                    logger.error(f"Puppeteer service returned error: {result.get('error')}")
                    return []

                jobs = result.get("jobs", [])
                logger.info(f"Puppeteer found {len(jobs)} jobs for {company_name}")

                # Normalize jobs
                normalized_jobs = []
                for job in jobs:
                    normalized = self._normalize_job(job, company_name, career_url)
                    if normalized:
                        normalized_jobs.append(normalized)

                return self._dedupe(normalized_jobs)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from Puppeteer service: {e}")
            return []
        except httpx.TimeoutException:
            logger.error(f"Timeout waiting for Puppeteer service")
            return []
        except Exception as e:
            logger.error(f"Error calling Puppeteer service: {e}", exc_info=True)
            return []

    def _normalize_job(self, job_data: Dict, company_name: str, career_url: str) -> Optional[Dict]:
        """
        Normalize Puppeteer-extracted job data

        Args:
            job_data: Raw job data from Puppeteer service
            company_name: Company name
            career_url: Base career page URL

        Returns:
            Normalized job dictionary
        """
        try:
            title = job_data.get("title") or job_data.get("name") or job_data.get("position")
            if not title or not isinstance(title, str):
                return None
            title = title.strip()
            if not title:
                return None

            # Build job URL
            job_url = job_data.get("url") or job_data.get("href") or job_data.get("link")
            if job_url and not job_url.startswith("http"):
                job_url = urljoin(career_url, job_url)
            if not job_url:
                job_url = career_url

            # Extract location
            location = job_data.get("location") or job_data.get("city") or job_data.get("address")
            if isinstance(location, dict):
                location = location.get("name") or location.get("addressLocality") or str(location)

            # Generate external ID
            url_part = urlparse(job_url).path.replace("/", "_") or title.replace(" ", "_").lower()
            external_id = f"puppeteer_{company_name.lower().replace(' ', '_')}_{url_part}"[:255]

            normalized = {
                "external_id": external_id,
                "title": title,
                "company": company_name,
                "location": location.strip() if location else None,
                "url": job_url,
                "source_url": job_url,
                "description": job_data.get("description") or job_data.get("summary"),
                "job_type": job_data.get("job_type") or job_data.get("employmentType") or job_data.get("type"),
                "posted_date": None,  # Puppeteer extraction usually can't get reliable dates
                "platform": "puppeteer",
            }

            return normalized

        except Exception as e:
            logger.error(f"Error normalizing Puppeteer job: {e}", exc_info=True)
            return None

    def _dedupe(self, jobs: List[Dict]) -> List[Dict]:
        """Remove duplicate jobs"""
        seen = set()
        out: List[Dict] = []
        for j in jobs:
            key = (j.get('url') or '').lower().strip(), (j.get('title') or '').lower().strip()
            if key in seen or not key[0] or not key[1]:
                continue
            seen.add(key)
            out.append(j)
        return out

    async def health_check(self) -> bool:
        """
        Check if Puppeteer service is healthy

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            url = f"{self.base_url}/health"
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json().get("status") == "ok"
        except Exception as e:
            logger.debug(f"Puppeteer health check failed: {e}")
            return False

