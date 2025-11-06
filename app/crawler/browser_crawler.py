"""Browser-based crawler using Playwright for JavaScript-heavy sites"""
import logging
import json
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
from datetime import datetime
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
from app.config import settings

logger = logging.getLogger(__name__)


class BrowserCrawler:
    """Playwright-based crawler for JavaScript-heavy career pages"""

    def __init__(
        self,
        company_name: str,
        career_url: str,
        timeout: int = None,
        headless: bool = True,
        wait_for_selector: Optional[str] = None,
        wait_timeout: int = 30000
    ):
        """
        Initialize browser crawler

        Args:
            company_name: Human-readable company name
            career_url: URL to company's career page
            timeout: Page load timeout in milliseconds
            headless: Run browser in headless mode
            wait_for_selector: CSS selector to wait for before extracting jobs
            wait_timeout: Maximum time to wait for selector in milliseconds
        """
        self.company_name = company_name
        self.career_url = career_url
        self.timeout = timeout or getattr(settings, 'PLAYWRIGHT_TIMEOUT', 30000)
        self.headless = headless
        self.wait_for_selector = wait_for_selector
        self.wait_timeout = wait_timeout
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def fetch_jobs(self) -> List[Dict]:
        """
        Fetch jobs from career page using browser automation

        Returns:
            List of job dictionaries with normalized fields
        """
        try:
            async with async_playwright() as p:
                # Launch browser
                self.browser = await p.chromium.launch(
                    headless=self.headless,
                    args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
                )

                # Create context with realistic viewport
                context = await self.browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )

                # Create page
                self.page = await context.new_page()

                logger.info(f"Loading career page for {self.company_name}: {self.career_url}")

                # Navigate to career page
                try:
                    await self.page.goto(
                        self.career_url,
                        wait_until='networkidle',
                        timeout=self.timeout
                    )
                except PlaywrightTimeoutError:
                    logger.warning(f"Page load timeout for {self.company_name}, continuing anyway")
                    # Page may have loaded partially, continue

                # Wait for specific selector if provided
                if self.wait_for_selector:
                    try:
                        await self.page.wait_for_selector(
                            self.wait_for_selector,
                            timeout=self.wait_timeout
                        )
                        logger.info(f"Found selector {self.wait_for_selector} for {self.company_name}")
                    except PlaywrightTimeoutError:
                        logger.warning(f"Selector {self.wait_for_selector} not found for {self.company_name}")

                # Wait a bit for JavaScript to render
                await self.page.wait_for_timeout(2000)

                # Extract jobs using multiple strategies
                jobs = await self._extract_jobs()

                # Normalize jobs
                normalized_jobs = []
                for job in jobs:
                    normalized = self._normalize_job(job)
                    if normalized:
                        normalized_jobs.append(normalized)

                return self._dedupe(normalized_jobs)

        except Exception as e:
            logger.error(f"Error fetching jobs with browser for {self.company_name}: {e}", exc_info=True)
            raise
        finally:
            await self.close()

    async def _extract_jobs(self) -> List[Dict]:
        """
        Extract jobs from page using multiple strategies

        Returns:
            List of raw job dictionaries
        """
        jobs: List[Dict] = []

        # Strategy 1: Try to extract from JSON-LD structured data
        try:
            json_ld_jobs = await self._extract_json_ld()
            if json_ld_jobs:
                jobs.extend(json_ld_jobs)
                logger.info(f"Found {len(json_ld_jobs)} jobs via JSON-LD for {self.company_name}")
        except Exception as e:
            logger.debug(f"JSON-LD extraction failed: {e}")

        # Strategy 2: Try to find job listings via common selectors
        if not jobs:
            try:
                selector_jobs = await self._extract_via_selectors()
                if selector_jobs:
                    jobs.extend(selector_jobs)
                    logger.info(f"Found {len(selector_jobs)} jobs via selectors for {self.company_name}")
            except Exception as e:
                logger.debug(f"Selector extraction failed: {e}")

        # Strategy 3: Execute JavaScript to extract jobs (for SPAs)
        if not jobs:
            try:
                js_jobs = await self._extract_via_javascript()
                if js_jobs:
                    jobs.extend(js_jobs)
                    logger.info(f"Found {len(js_jobs)} jobs via JavaScript for {self.company_name}")
            except Exception as e:
                logger.debug(f"JavaScript extraction failed: {e}")

        # Strategy 4: Extract from page content using AI-like pattern matching
        if not jobs:
            try:
                content_jobs = await self._extract_from_content()
                if content_jobs:
                    jobs.extend(content_jobs)
                    logger.info(f"Found {len(content_jobs)} jobs via content extraction for {self.company_name}")
            except Exception as e:
                logger.debug(f"Content extraction failed: {e}")

        return jobs

    async def _extract_json_ld(self) -> List[Dict]:
        """Extract jobs from JSON-LD structured data"""
        jobs = []
        try:
            # Find all script tags with JSON-LD
            scripts = await self.page.query_selector_all('script[type="application/ld+json"]')
            for script in scripts:
                content = await script.text_content()
                if content:
                    try:
                        data = json.loads(content)
                        jobs.extend(self._parse_json_ld_jobposting(data))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.debug(f"JSON-LD extraction error: {e}")
        return jobs

    def _parse_json_ld_jobposting(self, data) -> List[Dict]:
        """Recursively parse JSON-LD for JobPosting objects"""
        jobs = []
        if isinstance(data, dict):
            if data.get('@type') == 'JobPosting':
                jobs.append({
                    'title': data.get('title'),
                    'location': data.get('jobLocation', {}).get('address', {}).get('addressLocality') if isinstance(data.get('jobLocation'), dict) else None,
                    'url': data.get('url') or data.get('hiringOrganization', {}).get('sameAs'),
                    'job_type': data.get('employmentType'),
                    'description': data.get('description')
                })
            for value in data.values():
                if isinstance(value, (dict, list)):
                    jobs.extend(self._parse_json_ld_jobposting(value))
        elif isinstance(data, list):
            for item in data:
                jobs.extend(self._parse_json_ld_jobposting(item))
        return jobs

    async def _extract_via_selectors(self) -> List[Dict]:
        """Extract jobs using common CSS selectors"""
        jobs = []
        # Common selectors for job listings
        selectors = [
            '[data-job-id]',
            '.job-listing',
            '.job-item',
            '.job-card',
            '[class*="job"]',
            '[id*="job"]',
            'article[class*="job"]',
            'div[class*="position"]',
            'li[class*="job"]'
        ]

        for selector in selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                if elements:
                    logger.debug(f"Found {len(elements)} elements with selector {selector}")
                    for element in elements[:50]:  # Limit to first 50
                        try:
                            job = await self._extract_job_from_element(element)
                            if job:
                                jobs.append(job)
                        except Exception as e:
                            logger.debug(f"Error extracting job from element: {e}")
                            continue
                    if jobs:
                        break  # Found jobs, stop trying other selectors
            except Exception:
                continue

        return jobs

    async def _extract_job_from_element(self, element) -> Optional[Dict]:
        """Extract job data from a DOM element"""
        try:
            # Try to get title
            title_elem = await element.query_selector('h2, h3, .title, [class*="title"]')
            title = await title_elem.text_content() if title_elem else None

            # Try to get URL
            link_elem = await element.query_selector('a[href]')
            url = None
            if link_elem:
                href = await link_elem.get_attribute('href')
                if href:
                    url = urljoin(self.career_url, href)

            # Try to get location
            location_elem = await element.query_selector('[class*="location"], [class*="city"]')
            location = await location_elem.text_content() if location_elem else None

            if title:
                return {
                    'title': title.strip() if title else None,
                    'url': url,
                    'location': location.strip() if location else None
                }
        except Exception:
            pass
        return None

    async def _extract_via_javascript(self) -> List[Dict]:
        """Extract jobs by executing JavaScript on the page"""
        jobs = []
        try:
            # Try to find common job data structures in JavaScript
            js_code = """
            () => {
                const jobs = [];
                // Look for common job data patterns
                const scripts = Array.from(document.querySelectorAll('script'));
                for (const script of scripts) {
                    const text = script.textContent || script.innerHTML;
                    if (text && (text.includes('jobs') || text.includes('positions') || text.includes('openings'))) {
                        try {
                            // Try to extract JSON from script
                            const jsonMatch = text.match(/\\{[\\s\\S]*"jobs"[\\s\\S]*\\}/);
                            if (jsonMatch) {
                                const data = JSON.parse(jsonMatch[0]);
                                if (data.jobs && Array.isArray(data.jobs)) {
                                    return data.jobs;
                                }
                            }
                        } catch (e) {}
                    }
                }
                // Look for window/global job data
                if (window.jobs && Array.isArray(window.jobs)) {
                    return window.jobs;
                }
                if (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.jobs) {
                    return window.__INITIAL_STATE__.jobs;
                }
                return [];
            }
            """
            result = await self.page.evaluate(js_code)
            if result and isinstance(result, list):
                for item in result:
                    if isinstance(item, dict):
                        jobs.append(item)
        except Exception as e:
            logger.debug(f"JavaScript extraction error: {e}")
        return jobs

    async def _extract_from_content(self) -> List[Dict]:
        """Extract jobs from page content using pattern matching"""
        jobs = []
        try:
            # Get page content
            content = await self.page.content()
            # Look for job-like patterns in HTML
            # This is a fallback - would ideally use AI parsing
            # For now, return empty and let generic crawler handle it
            pass
        except Exception as e:
            logger.debug(f"Content extraction error: {e}")
        return jobs

    def _normalize_job(self, job_data: Dict) -> Optional[Dict]:
        """
        Normalize browser-extracted job data

        Args:
            job_data: Raw job data from browser

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
                job_url = urljoin(self.career_url, job_url)
            if not job_url:
                job_url = self.career_url

            # Extract location
            location = job_data.get("location") or job_data.get("city") or job_data.get("address")
            if isinstance(location, dict):
                location = location.get("name") or location.get("addressLocality") or str(location)

            # Generate external ID
            url_part = urlparse(job_url).path.replace("/", "_") or title.replace(" ", "_").lower()
            external_id = f"browser_{self.company_name.lower().replace(' ', '_')}_{url_part}"[:255]

            normalized = {
                "external_id": external_id,
                "title": title,
                "company": self.company_name,
                "location": location.strip() if location else None,
                "url": job_url,
                "source_url": job_url,
                "description": job_data.get("description") or job_data.get("summary"),
                "job_type": job_data.get("job_type") or job_data.get("employmentType") or job_data.get("type"),
                "posted_date": None,  # Browser extraction usually can't get reliable dates
                "platform": "browser",
            }

            return normalized

        except Exception as e:
            logger.error(f"Error normalizing browser job: {e}", exc_info=True)
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

    async def close(self):
        """Cleanup browser resources"""
        try:
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
        except Exception as e:
            logger.debug(f"Error closing browser: {e}")

