"""Greenhouse ATS Crawler - For companies using Greenhouse.io"""
import logging
import httpx
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class GreenhouseCrawler:
    """Crawler for Greenhouse job boards"""

    def __init__(self, company_slug: str, company_name: str = ""):
        """
        Initialize Greenhouse crawler

        Args:
            company_slug: The company identifier in Greenhouse URL (e.g., 'stripe', 'airbnb')
            company_name: Human-readable company name
        """
        self.company_slug = company_slug.lower()
        self.company_name = company_name or company_slug
        self.base_url = f"https://boards-api.greenhouse.io/v1/boards/{self.company_slug}"

    async def fetch_jobs(self) -> List[Dict]:
        """
        Fetch all jobs from Greenhouse API

        Returns:
            List of job dictionaries with normalized fields
        """
        try:
            url = f"{self.base_url}/jobs"

            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Fetching jobs from Greenhouse for {self.company_name}: {url}")
                response = await client.get(url)
                response.raise_for_status()

                data = response.json()
                jobs_data = data.get("jobs", [])

                logger.info(f"Found {len(jobs_data)} jobs for {self.company_name}")

                normalized_jobs = []
                for job in jobs_data:
                    try:
                        normalized = self._normalize_job(job)
                        if normalized:
                            normalized_jobs.append(normalized)
                    except Exception as e:
                        logger.error(f"Error normalizing job {job.get('id')}: {e}")
                        continue

                return normalized_jobs

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Greenhouse board not found for {self.company_slug}")
                return []
            logger.error(f"HTTP error fetching Greenhouse jobs: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching Greenhouse jobs for {self.company_name}: {e}", exc_info=True)
            raise

    def _normalize_job(self, job_data: Dict) -> Optional[Dict]:
        """
        Normalize Greenhouse job data to standard format

        Args:
            job_data: Raw job data from Greenhouse API

        Returns:
            Normalized job dictionary
        """
        try:
            job_id = str(job_data.get("id", ""))
            if not job_id:
                logger.warning("Job missing ID, skipping")
                return None

            # Extract location
            location = job_data.get("location", {})
            if isinstance(location, dict):
                location_str = location.get("name", "")
            else:
                location_str = str(location) if location else ""

            # Build job URL
            absolute_url = job_data.get("absolute_url", "")
            if not absolute_url:
                # Fallback: construct URL
                absolute_url = f"https://boards.greenhouse.io/{self.company_slug}/jobs/{job_id}"

            # Extract metadata
            metadata = job_data.get("metadata") or []
            job_type = None
            if metadata:
                for meta in metadata:
                    if meta.get("name") == "Employment Type":
                        job_type = meta.get("value")
                        break

            # Parse posted date
            posted_date = None
            updated_at = job_data.get("updated_at")
            if updated_at:
                try:
                    posted_date = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                except:
                    pass

            normalized = {
                "external_id": f"greenhouse_{self.company_slug}_{job_id}",
                "title": job_data.get("title", "").strip(),
                "company": self.company_name,
                "location": location_str,
                "url": absolute_url,
                "source_url": absolute_url,
                "description": job_data.get("content", ""),
                "job_type": job_type,
                "posted_date": posted_date,
                "platform": "greenhouse",
            }

            return normalized

        except Exception as e:
            logger.error(f"Error normalizing Greenhouse job: {e}", exc_info=True)
            return None

    def close(self):
        """Cleanup - no-op for API-based crawler"""
        pass
