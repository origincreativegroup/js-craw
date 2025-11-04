"""Crawler for LinkedIn's public guest job search endpoint."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlencode, urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class LinkedInCrawler:
    """Fetch job listings using LinkedIn's unauthenticated guest endpoints."""

    BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def __init__(
        self,
        query: str,
        *,
        location: Optional[str] = None,
        max_pages: int = 2,
        remote_only: bool = False,
        filters: Optional[Dict[str, str]] = None,
        company_name: str = "LinkedIn Search",
    ) -> None:
        self.query = query
        self.location = location
        self.max_pages = max(1, max_pages)
        self.remote_only = remote_only
        self.filters = filters or {}
        self.company_name = company_name or "LinkedIn Search"

    async def fetch_jobs(self) -> List[Dict]:
        """Fetch and normalize jobs from LinkedIn search."""

        jobs: List[Dict] = []
        seen_ids: set[str] = set()

        async with httpx.AsyncClient(timeout=30.0, headers=self._headers()) as client:
            for page in range(self.max_pages):
                start = page * 25
                params = self._build_params(start=start)
                url = f"{self.BASE_URL}?{urlencode(params)}"

                logger.info("Fetching LinkedIn page %s: %s", page + 1, url)

                try:
                    response = await client.get(url)
                    if response.status_code == 404:
                        logger.info("LinkedIn returned 404 for page %s", page + 1)
                        break
                    response.raise_for_status()
                except httpx.HTTPStatusError:
                    logger.exception("Failed to fetch LinkedIn jobs")
                    raise

                page_jobs = self._parse_jobs(response.text)
                if not page_jobs:
                    logger.info("No LinkedIn jobs found on page %s", page + 1)
                    break

                new_jobs = 0
                for job in page_jobs:
                    job_id = job.get("external_id")
                    if not job_id or job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)
                    jobs.append(job)
                    new_jobs += 1

                logger.info("LinkedIn page %s yielded %s new jobs", page + 1, new_jobs)
                await asyncio.sleep(1)

        return jobs

    def _parse_jobs(self, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("li.jobs-search-results__list-item")
        jobs: List[Dict] = []

        for card in cards:
            urn = card.get("data-entity-urn") or ""
            job_id = urn.split(":")[-1] if urn else card.get("data-id")
            if not job_id:
                continue

            title_el = card.select_one("h3.base-search-card__title")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            link_el = card.select_one("a.base-card__full-link")
            job_url = urljoin("https://www.linkedin.com", link_el.get("href")) if link_el else None
            if not job_url:
                job_url = f"https://www.linkedin.com/jobs/view/{job_id}"

            company_el = card.select_one("h4.base-search-card__subtitle")
            company = company_el.get_text(strip=True) if company_el else self.company_name

            location_el = card.select_one("span.job-search-card__location")
            location = location_el.get_text(strip=True) if location_el else None

            snippet_el = card.select_one("div.job-search-card__snippet")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else None

            job_type = self._extract_job_type(card)
            posted_date = self._parse_posted_date(card.select_one("time"))

            job = {
                "external_id": f"linkedin_{job_id}",
                "title": title,
                "company": company,
                "location": location,
                "url": job_url,
                "source_url": job_url,
                "description": snippet,
                "job_type": job_type,
                "posted_date": posted_date,
                "platform": "linkedin",
            }

            jobs.append(job)

        return jobs

    def _extract_job_type(self, card) -> Optional[str]:
        for insight in card.select("li.job-search-card__insight"):
            text = insight.get_text(strip=True)
            lowered = text.lower()
            if any(keyword in lowered for keyword in ["full-time", "part-time", "contract", "intern", "temporary"]):
                return text
        return None

    def _parse_posted_date(self, time_element) -> Optional[datetime]:
        if not time_element:
            return None

        datetime_attr = time_element.get("datetime")
        if datetime_attr:
            try:
                # LinkedIn emits ISO-8601 date strings.
                return datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
            except ValueError:
                pass

        return None

    def _build_params(self, *, start: int) -> Dict[str, str]:
        params = {
            "keywords": self.query,
            "start": str(start),
        }

        if self.location:
            params["location"] = self.location

        if self.remote_only:
            params["f_WT"] = "2"  # LinkedIn's remote work filter

        params.update(self.filters)

        return params

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
        return None

