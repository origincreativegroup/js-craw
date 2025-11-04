"""Indeed search crawler with HTML parsing.

This crawler intentionally avoids brittle browser automation by using the
public job search endpoints that power the normal Indeed UI. We mimic a
standard browser request, paginate through result pages, and normalize the
job cards into the shared format consumed by the orchestrator.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlencode, urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class IndeedCrawler:
    """Scrape job listings from Indeed's public search endpoints."""

    BASE_URL = "https://www.indeed.com/jobs"
    JOB_URL = "https://www.indeed.com/viewjob"

    def __init__(
        self,
        query: str,
        *,
        location: Optional[str] = None,
        max_pages: int = 2,
        results_per_page: int = 20,
        freshness_days: Optional[int] = None,
        remote_only: bool = False,
        company_name: str = "Indeed Search",
    ) -> None:
        """Configure the crawler.

        Args:
            query: Search keywords.
            location: Optional location filter (e.g. "Remote" or "New York, NY").
            max_pages: Maximum number of paginated result pages to inspect.
            results_per_page: Pagination size to request from Indeed.
            freshness_days: Restrict results to postings within the last N days.
            remote_only: If True, ask Indeed for "remote" results where supported.
            company_name: Human readable label stored on each normalized job.
        """

        self.query = query
        self.location = location
        self.max_pages = max(1, max_pages)
        self.results_per_page = max(10, min(results_per_page, 50))
        self.freshness_days = freshness_days
        self.remote_only = remote_only
        self.company_name = company_name or "Indeed Search"

    async def fetch_jobs(self) -> List[Dict]:
        """Fetch and normalize jobs from Indeed."""

        params = {
            "q": self.query,
            "limit": str(self.results_per_page),
        }

        if self.location:
            params["l"] = self.location

        if self.remote_only:
            params["sc"] = "0kf%3Aattr(DSQF7)%3B"  # Remote friendly filter

        if self.freshness_days:
            params["fromage"] = str(max(1, self.freshness_days))

        jobs: List[Dict] = []
        seen_ids: set[str] = set()

        async with httpx.AsyncClient(timeout=30.0, headers=self._headers(), follow_redirects=True) as client:
            for page in range(self.max_pages):
                start = page * self.results_per_page
                page_params = {**params, "start": str(start)}
                url = f"{self.BASE_URL}?{urlencode(page_params)}"
                logger.info("Fetching Indeed page %s: %s", page + 1, url)

                try:
                    response = await client.get(url)
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 404:
                        logger.warning("Indeed search returned 404 for %s", url)
                        break
                    raise

                page_jobs = self._parse_jobs(response.text)
                if not page_jobs:
                    logger.info("No jobs detected on Indeed page %s", page + 1)
                    break

                new_jobs = 0
                for job in page_jobs:
                    job_id = job.get("external_id")
                    if not job_id or job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)
                    jobs.append(job)
                    new_jobs += 1

                logger.info("Indeed page %s yielded %s new jobs", page + 1, new_jobs)

                # Polite pause between requests to reduce the likelihood of throttling.
                await asyncio.sleep(1)

        return jobs

    def _parse_jobs(self, html: str) -> List[Dict]:
        """Parse job cards from an Indeed HTML page."""

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("div.job_seen_beacon")

        jobs: List[Dict] = []
        for card in cards:
            job_key = card.get("data-jk") or card.get("data-mobtk")
            if not job_key:
                continue

            title_el = card.select_one("h2.jobTitle span")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title or title.lower() == "new":
                # Some cards include a "new" badge span before the actual title.
                title_el = card.select_one("h2.jobTitle a")
                title = title_el.get_text(strip=True) if title_el else title

            link_el = card.select_one("a.jcs-JobTitle")
            job_url = self._build_job_url(link_el.get("href") if link_el else None, job_key)

            company_el = card.select_one("span.companyName")
            company = company_el.get_text(strip=True) if company_el else self.company_name

            location_el = card.select_one("div.companyLocation")
            location = location_el.get_text(" ", strip=True) if location_el else None

            snippet_el = card.select_one("div.job-snippet")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else None

            date_el = card.select_one("span.date")
            posted_text = date_el.get_text(strip=True) if date_el else None
            posted_date = self._parse_posted_date(posted_text) if posted_text else None

            job_type = self._extract_job_type(card.select("div.metadata div"))

            job_record = {
                "external_id": f"indeed_{job_key}",
                "title": title,
                "company": company,
                "location": location,
                "url": job_url,
                "source_url": job_url,
                "description": snippet,
                "job_type": job_type,
                "posted_date": posted_date,
                "platform": "indeed",
            }

            jobs.append(job_record)

        return jobs

    def _build_job_url(self, href: Optional[str], job_key: str) -> str:
        if href and href.startswith("http"):
            return href
        if href:
            return urljoin(self.BASE_URL, href)
        return f"{self.JOB_URL}?jk={job_key}"

    def _parse_posted_date(self, text: str) -> Optional[datetime]:
        """Translate Indeed's relative date strings into datetimes."""

        text_lower = text.lower()
        now = datetime.utcnow()

        if "today" in text_lower or "just posted" in text_lower:
            return now

        if "30+" in text_lower:
            return now - timedelta(days=30)

        match = re.search(r"(\d+)+\s*(day|hour|minute)", text_lower)
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            if unit.startswith("day"):
                return now - timedelta(days=value)
            if unit.startswith("hour"):
                return now - timedelta(hours=value)
            if unit.startswith("minute"):
                return now - timedelta(minutes=value)

        return None

    def _extract_job_type(self, metadata: Iterable) -> Optional[str]:
        """Attempt to pull the employment type from metadata chips."""

        for item in metadata:
            text = item.get_text(strip=True)
            lowered = text.lower()
            if any(keyword in lowered for keyword in ["full-time", "part-time", "contract", "internship", "temporary"]):
                return text
        return None

    def _headers(self) -> Dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/119.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

    def close(self) -> None:
        """Compatibility shim for orchestrator cleanup."""

        # No persistent resources to release, but keep method for symmetry.
        return None

