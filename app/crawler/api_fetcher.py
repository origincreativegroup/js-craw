"""API-based job fetcher with auto-detection for structured data sources"""
import logging
import json
import re
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, urljoin
from datetime import datetime, timezone
import httpx
from bs4 import BeautifulSoup
from app.services.http_client import HttpClient
from app.crawler.greenhouse_crawler import GreenhouseCrawler
from app.crawler.lever_crawler import LeverCrawler

logger = logging.getLogger(__name__)


class ApiFetcher:
    """Auto-detecting API fetcher for structured job data"""

    def __init__(self, company_name: str, career_url: str):
        """
        Initialize API fetcher

        Args:
            company_name: Human-readable company name
            career_url: URL to company's career page
        """
        self.company_name = company_name
        self.career_url = career_url
        self.http = HttpClient()

    async def fetch_jobs(self) -> List[Dict]:
        """
        Fetch jobs by auto-detecting and using appropriate API

        Returns:
            List of normalized job dictionaries
        """
        try:
            # Try to detect API type
            api_type, api_config = await self._detect_api()

            if not api_type:
                logger.debug(f"No API detected for {self.company_name}")
                return []

            logger.info(f"Detected API type '{api_type}' for {self.company_name}")

            # Fetch jobs using detected API
            jobs = await self._fetch_from_api(api_type, api_config)
            return jobs

        except Exception as e:
            logger.error(f"Error in API fetcher for {self.company_name}: {e}", exc_info=True)
            return []

    async def _detect_api(self) -> Tuple[Optional[str], Dict]:
        """
        Auto-detect API type and configuration

        Returns:
            Tuple of (api_type, config_dict) or (None, {}) if not detected
        """
        try:
            # Strategy 1: Check for known ATS patterns in URL
            parsed = urlparse(self.career_url)
            domain = parsed.netloc.lower()

            # Greenhouse detection
            if 'greenhouse.io' in domain or 'boards.greenhouse.io' in domain:
                slug = self._extract_greenhouse_slug(parsed.path)
                if slug:
                    return 'greenhouse', {'slug': slug}

            # Lever detection
            if 'lever.co' in domain or 'jobs.lever.co' in domain:
                slug = self._extract_lever_slug(parsed.path)
                if slug:
                    return 'lever', {'slug': slug}

            # Strategy 2: Check HTML for API hints
            html = await self._fetch_html()
            if html:
                # Check for Greenhouse API references
                if 'greenhouse.io' in html or 'boards-api.greenhouse.io' in html:
                    slug = self._extract_greenhouse_slug_from_html(html)
                    if slug:
                        return 'greenhouse', {'slug': slug}

                # Check for Lever API references
                if 'api.lever.co' in html or 'lever.co/v0/postings' in html:
                    slug = self._extract_lever_slug_from_html(html)
                    if slug:
                        return 'lever', {'slug': slug}

                # Check for Workday
                if 'workday.com' in html or 'myworkdayjobs.com' in html:
                    return 'workday', {}

                # Check for JSON-LD structured data
                if 'application/ld+json' in html:
                    soup = BeautifulSoup(html, 'html.parser')
                    scripts = soup.find_all('script', type='application/ld+json')
                    for script in scripts:
                        try:
                            data = json.loads(script.string or '{}')
                            if self._has_jobposting(data):
                                return 'jsonld', {}
                        except:
                            continue

                # Check for custom JSON endpoints
                json_endpoints = self._find_json_endpoints(html)
                if json_endpoints:
                    return 'custom_json', {'endpoints': json_endpoints}

        except Exception as e:
            logger.debug(f"API detection error: {e}")

        return None, {}

    def _extract_greenhouse_slug(self, path: str) -> Optional[str]:
        """Extract Greenhouse company slug from URL path"""
        # Pattern: /company-slug or /company-slug/jobs
        match = re.search(r'/([^/]+)', path)
        if match:
            slug = match.group(1)
            # Filter out common non-slug paths
            if slug not in ['jobs', 'careers', 'openings']:
                return slug
        return None

    def _extract_lever_slug(self, path: str) -> Optional[str]:
        """Extract Lever company slug from URL path"""
        # Pattern: /company-slug or /company-slug/jobs
        match = re.search(r'/([^/]+)', path)
        if match:
            slug = match.group(1)
            if slug not in ['jobs', 'careers', 'openings']:
                return slug
        return None

    def _extract_greenhouse_slug_from_html(self, html: str) -> Optional[str]:
        """Extract Greenhouse slug from HTML content"""
        # Look for greenhouse.io URLs
        matches = re.findall(r'greenhouse\.io/([^/"\']+)', html)
        if matches:
            slug = matches[0]
            if slug not in ['jobs', 'careers', 'openings', 'boards-api']:
                return slug
        return None

    def _extract_lever_slug_from_html(self, html: str) -> Optional[str]:
        """Extract Lever slug from HTML content"""
        # Look for lever.co URLs
        matches = re.findall(r'lever\.co/v0/postings/([^/"\']+)', html)
        if matches:
            return matches[0]
        matches = re.findall(r'jobs\.lever\.co/([^/"\']+)', html)
        if matches:
            return matches[0]
        return None

    def _has_jobposting(self, data) -> bool:
        """Check if JSON-LD data contains JobPosting"""
        if isinstance(data, dict):
            if data.get('@type') == 'JobPosting':
                return True
            for value in data.values():
                if self._has_jobposting(value):
                    return True
        elif isinstance(data, list):
            for item in data:
                if self._has_jobposting(item):
                    return True
        return False

    def _find_json_endpoints(self, html: str) -> List[str]:
        """Find potential JSON API endpoints in HTML"""
        endpoints = []
        # Look for common API endpoint patterns
        patterns = [
            r'["\']([^"\']*api[^"\']*jobs[^"\']*\.json)["\']',
            r'["\']([^"\']*jobs[^"\']*api[^"\']*\.json)["\']',
            r'["\']([^"\']*api[^"\']*positions[^"\']*\.json)["\']',
            r'fetch\(["\']([^"\']*api[^"\']*jobs[^"\']*)["\']',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            endpoints.extend(matches)
        return list(set(endpoints))[:5]  # Limit to 5 unique endpoints

    async def _fetch_html(self) -> Optional[str]:
        """Fetch HTML content from career page"""
        try:
            response = await self.http.get(self.career_url)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            logger.debug(f"Error fetching HTML: {e}")
        return None

    async def _fetch_from_api(self, api_type: str, config: Dict) -> List[Dict]:
        """
        Fetch jobs from detected API

        Args:
            api_type: Type of API (greenhouse, lever, jsonld, custom_json)
            config: API configuration

        Returns:
            List of normalized job dictionaries
        """
        try:
            if api_type == 'greenhouse':
                slug = config.get('slug')
                if slug:
                    crawler = GreenhouseCrawler(slug, self.company_name)
                    jobs = await crawler.fetch_jobs()
                    crawler.close()
                    return jobs

            elif api_type == 'lever':
                slug = config.get('slug')
                if slug:
                    crawler = LeverCrawler(slug, self.company_name)
                    jobs = await crawler.fetch_jobs()
                    crawler.close()
                    return jobs

            elif api_type == 'jsonld':
                return await self._fetch_jsonld_jobs()

            elif api_type == 'custom_json':
                endpoints = config.get('endpoints', [])
                return await self._fetch_custom_json(endpoints)

        except Exception as e:
            logger.error(f"Error fetching from {api_type} API: {e}", exc_info=True)

        return []

    async def _fetch_jsonld_jobs(self) -> List[Dict]:
        """Fetch jobs from JSON-LD structured data"""
        jobs = []
        try:
            html = await self._fetch_html()
            if not html:
                return []

            soup = BeautifulSoup(html, 'html.parser')
            scripts = soup.find_all('script', type='application/ld+json')

            for script in scripts:
                try:
                    data = json.loads(script.string or '{}')
                    job_postings = self._extract_jsonld_jobpostings(data)
                    jobs.extend(job_postings)
                except:
                    continue

            # Normalize jobs
            normalized = []
            for job in jobs:
                normalized_job = self._normalize_jsonld_job(job)
                if normalized_job:
                    normalized.append(normalized_job)

            return normalized

        except Exception as e:
            logger.error(f"Error fetching JSON-LD jobs: {e}", exc_info=True)
            return []

    def _extract_jsonld_jobpostings(self, data) -> List[Dict]:
        """Recursively extract JobPosting objects from JSON-LD"""
        jobs = []
        if isinstance(data, dict):
            if data.get('@type') == 'JobPosting':
                jobs.append(data)
            for value in data.values():
                if isinstance(value, (dict, list)):
                    jobs.extend(self._extract_jsonld_jobpostings(value))
        elif isinstance(data, list):
            for item in data:
                jobs.extend(self._extract_jsonld_jobpostings(item))
        return jobs

    def _normalize_jsonld_job(self, job_data: Dict) -> Optional[Dict]:
        """Normalize JSON-LD JobPosting to standard format"""
        try:
            title = job_data.get('title')
            if not title:
                return None

            location = None
            job_location = job_data.get('jobLocation', {})
            if isinstance(job_location, dict):
                address = job_location.get('address', {})
                if isinstance(address, dict):
                    location = address.get('addressLocality')

            url = job_data.get('url') or job_data.get('hiringOrganization', {}).get('sameAs')

            # Generate external ID
            url_part = urlparse(url).path.replace("/", "_") if url else title.replace(" ", "_").lower()
            external_id = f"api_jsonld_{self.company_name.lower().replace(' ', '_')}_{url_part}"[:255]

            return {
                "external_id": external_id,
                "title": title.strip(),
                "company": self.company_name,
                "location": location,
                "url": url or self.career_url,
                "source_url": url or self.career_url,
                "description": job_data.get('description'),
                "job_type": job_data.get('employmentType'),
                "posted_date": self._parse_date(job_data.get('datePosted')),
                "platform": "api_jsonld",
            }

        except Exception as e:
            logger.error(f"Error normalizing JSON-LD job: {e}")
            return None

    async def _fetch_custom_json(self, endpoints: List[str]) -> List[Dict]:
        """Fetch jobs from custom JSON endpoints"""
        jobs = []
        for endpoint in endpoints:
            try:
                # Make endpoint absolute if relative
                if not endpoint.startswith('http'):
                    endpoint = urljoin(self.career_url, endpoint)

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(endpoint)
                    response.raise_for_status()

                    data = response.json()
                    # Try to extract jobs from various JSON structures
                    extracted = self._extract_jobs_from_json(data)
                    jobs.extend(extracted)

            except Exception as e:
                logger.debug(f"Error fetching from custom endpoint {endpoint}: {e}")
                continue

        # Normalize jobs
        normalized = []
        for job in jobs:
            normalized_job = self._normalize_custom_json_job(job)
            if normalized_job:
                normalized.append(normalized_job)

        return normalized

    def _extract_jobs_from_json(self, data) -> List[Dict]:
        """Extract jobs from various JSON structures"""
        jobs = []
        if isinstance(data, list):
            # Assume list of jobs
            jobs.extend(data)
        elif isinstance(data, dict):
            # Look for common keys
            for key in ['jobs', 'positions', 'openings', 'results', 'data']:
                if key in data and isinstance(data[key], list):
                    jobs.extend(data[key])
                    break
            # If no jobs found, assume the dict itself is a job
            if not jobs and data.get('title'):
                jobs.append(data)
        return jobs

    def _normalize_custom_json_job(self, job_data: Dict) -> Optional[Dict]:
        """Normalize custom JSON job to standard format"""
        try:
            title = job_data.get('title') or job_data.get('name') or job_data.get('position')
            if not title:
                return None

            url = job_data.get('url') or job_data.get('link') or job_data.get('href')
            if url and not url.startswith('http'):
                url = urljoin(self.career_url, url)

            # Generate external ID
            url_part = urlparse(url).path.replace("/", "_") if url else title.replace(" ", "_").lower()
            external_id = f"api_custom_{self.company_name.lower().replace(' ', '_')}_{url_part}"[:255]

            return {
                "external_id": external_id,
                "title": str(title).strip(),
                "company": self.company_name,
                "location": job_data.get('location') or job_data.get('city'),
                "url": url or self.career_url,
                "source_url": url or self.career_url,
                "description": job_data.get('description') or job_data.get('summary'),
                "job_type": job_data.get('job_type') or job_data.get('type') or job_data.get('employmentType'),
                "posted_date": self._parse_date(job_data.get('posted_date') or job_data.get('datePosted') or job_data.get('created_at')),
                "platform": "api_custom",
            }

        except Exception as e:
            logger.error(f"Error normalizing custom JSON job: {e}")
            return None

    def _parse_date(self, date_str) -> Optional[datetime]:
        """Parse date string to datetime"""
        if not date_str:
            return None
        try:
            # Try ISO format
            if isinstance(date_str, str):
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            # Try timestamp
            elif isinstance(date_str, (int, float)):
                return datetime.fromtimestamp(date_str)
        except:
            pass
        return None

    async def close(self):
        """Cleanup"""
        try:
            await self.http.close()
        except:
            pass

