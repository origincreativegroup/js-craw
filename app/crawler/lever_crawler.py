"""Lever ATS Crawler - For companies using Lever.co"""
import logging
import httpx
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class LeverCrawler:
    """Crawler for Lever job boards"""

    def __init__(self, company_slug: str, company_name: str = ""):
        """
        Initialize Lever crawler

        Args:
            company_slug: The company identifier in Lever URL (e.g., 'netflix', 'figma')
            company_name: Human-readable company name
        """
        self.company_slug = company_slug.lower()
        self.company_name = company_name or company_slug
        self.base_url = f"https://api.lever.co/v0/postings/{self.company_slug}"

    async def fetch_jobs(self) -> List[Dict]:
        """
        Fetch all jobs from Lever API

        Returns:
            List of job dictionaries with normalized fields
        """
        try:
            url = self.base_url
            params = {"mode": "json"}

            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Fetching jobs from Lever for {self.company_name}: {url}")
                response = await client.get(url, params=params)
                response.raise_for_status()

                jobs_data = response.json()

                if not isinstance(jobs_data, list):
                    logger.warning(f"Unexpected Lever response format for {self.company_name}")
                    return []

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
                logger.warning(f"Lever board not found for {self.company_slug}")
                return []
            logger.error(f"HTTP error fetching Lever jobs: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching Lever jobs for {self.company_name}: {e}", exc_info=True)
            raise

    def _normalize_job(self, job_data: Dict) -> Optional[Dict]:
        """
        Normalize Lever job data to standard format

        Args:
            job_data: Raw job data from Lever API

        Returns:
            Normalized job dictionary
        """
        try:
            job_id = job_data.get("id", "")
            if not job_id:
                logger.warning("Job missing ID, skipping")
                return None

            # Extract location
            location = job_data.get("categories", {}).get("location", "")

            # Extract job type/commitment
            commitment = job_data.get("categories", {}).get("commitment", "")

            # Extract team
            team = job_data.get("categories", {}).get("team", "")

            # Get job URL
            job_url = job_data.get("hostedUrl", "") or job_data.get("applyUrl", "")

            # Parse posted date
            posted_date = None
            created_at = job_data.get("createdAt")
            if created_at:
                try:
                    # Lever uses Unix timestamp in milliseconds
                    posted_date = datetime.fromtimestamp(created_at / 1000)
                except:
                    pass

            # Get description
            description = job_data.get("description", "") or job_data.get("descriptionPlain", "")

            normalized = {
                "external_id": f"lever_{self.company_slug}_{job_id}",
                "title": job_data.get("text", "").strip(),
                "company": self.company_name,
                "location": location,
                "url": job_url,
                "source_url": job_url,
                "description": description,
                "job_type": commitment,
                "posted_date": posted_date,
                "platform": "lever",
                "team": team,  # Extra field
            }

            return normalized

        except Exception as e:
            logger.error(f"Error normalizing Lever job: {e}", exc_info=True)
            return None

    def close(self):
        """Cleanup - no-op for API-based crawler"""
        pass
