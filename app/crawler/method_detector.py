"""Method detector for auto-detecting optimal crawling method"""
import logging
import re
from typing import Dict, Optional, Tuple, List
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from app.services.http_client import HttpClient
from app.config import settings

logger = logging.getLogger(__name__)


class MethodDetector:
    """Auto-detect optimal crawling method for a company career page"""

    def __init__(self):
        self.http = HttpClient()

    async def detect_method(
        self,
        company_name: str,
        career_url: str,
        crawler_config: Optional[Dict] = None
    ) -> Tuple[str, Dict]:
        """
        Detect optimal crawling method for a company

        Args:
            company_name: Company name
            career_url: Career page URL
            crawler_config: Existing crawler configuration (may contain cached detection)

        Returns:
            Tuple of (method, config_dict)
            Methods: 'api', 'browser', 'html', 'generic'
        """
        # Check for cached detection result
        if crawler_config and isinstance(crawler_config, dict):
            cached_method = crawler_config.get('detected_method')
            if cached_method and crawler_config.get('method_detection_cache'):
                logger.debug(f"Using cached method '{cached_method}' for {company_name}")
                return cached_method, crawler_config

        try:
            # Strategy 1: Check for known API patterns (fastest)
            api_method, api_config = await self._detect_api_method(career_url)
            if api_method:
                result_config = {
                    'detected_method': api_method,
                    'method_config': api_config,
                    'method_detection_cache': True
                }
                logger.info(f"Detected API method '{api_method}' for {company_name}")
                return api_method, result_config

            # Strategy 2: Analyze HTML to determine if browser is needed
            html = await self._fetch_html(career_url)
            if html:
                # Check if JavaScript-heavy (SPA)
                needs_browser = self._needs_browser(html, career_url)

                if needs_browser:
                    browser_config = {
                        'detected_method': 'browser',
                        'method_config': self._detect_browser_config(html),
                        'method_detection_cache': True
                    }
                    logger.info(f"Detected browser method for {company_name} (JavaScript-heavy)")
                    return 'browser', browser_config

                # Check if static HTML parsing is sufficient
                if self._can_parse_html(html):
                    html_config = {
                        'detected_method': 'html',
                        'method_config': {},
                        'method_detection_cache': True
                    }
                    logger.info(f"Detected HTML method for {company_name} (static content)")
                    return 'html', html_config

            # Default to generic (AI-assisted)
            generic_config = {
                'detected_method': 'generic',
                'method_config': {},
                'method_detection_cache': True
            }
            logger.info(f"Defaulting to generic method for {company_name}")
            return 'generic', generic_config

        except Exception as e:
            logger.error(f"Error detecting method for {company_name}: {e}", exc_info=True)
            # Default to generic on error
            return 'generic', {'detected_method': 'generic', 'method_config': {}}

    async def _detect_api_method(self, career_url: str) -> Tuple[Optional[str], Dict]:
        """
        Detect if API method is available

        Returns:
            Tuple of (api_type, config) or (None, {})
        """
        parsed = urlparse(career_url)
        domain = parsed.netloc.lower()

        # Greenhouse detection
        if 'greenhouse.io' in domain:
            slug = self._extract_slug_from_path(parsed.path, ['jobs', 'careers'])
            if slug:
                return 'api', {'api_type': 'greenhouse', 'slug': slug}

        # Lever detection
        if 'lever.co' in domain:
            slug = self._extract_slug_from_path(parsed.path, ['jobs', 'careers'])
            if slug:
                return 'api', {'api_type': 'lever', 'slug': slug}

        # Try to detect from HTML
        try:
            html = await self._fetch_html(career_url)
            if html:
                # Check for Greenhouse API references
                if 'greenhouse.io' in html or 'boards-api.greenhouse.io' in html:
                    slug = self._extract_slug_from_html(html, 'greenhouse')
                    if slug:
                        return 'api', {'api_type': 'greenhouse', 'slug': slug}

                # Check for Lever API references
                if 'api.lever.co' in html:
                    slug = self._extract_slug_from_html(html, 'lever')
                    if slug:
                        return 'api', {'api_type': 'lever', 'slug': slug}

                # Check for JSON-LD
                if 'application/ld+json' in html:
                    soup = BeautifulSoup(html, 'html.parser')
                    scripts = soup.find_all('script', type='application/ld+json')
                    for script in scripts:
                        try:
                            import json
                            data = json.loads(script.string or '{}')
                            if self._has_jobposting(data):
                                return 'api', {'api_type': 'jsonld'}
                        except:
                            continue
        except Exception as e:
            logger.debug(f"API detection from HTML failed: {e}")

        return None, {}

    def _extract_slug_from_path(self, path: str, exclude: List[str]) -> Optional[str]:
        """Extract company slug from URL path"""
        match = re.search(r'/([^/]+)', path)
        if match:
            slug = match.group(1)
            if slug not in exclude:
                return slug
        return None

    def _extract_slug_from_html(self, html: str, api_type: str) -> Optional[str]:
        """Extract company slug from HTML"""
        if api_type == 'greenhouse':
            matches = re.findall(r'greenhouse\.io/([^/"\']+)', html)
            if matches:
                slug = matches[0]
                if slug not in ['jobs', 'careers', 'openings', 'boards-api']:
                    return slug
        elif api_type == 'lever':
            matches = re.findall(r'lever\.co/v0/postings/([^/"\']+)', html)
            if matches:
                return matches[0]
            matches = re.findall(r'jobs\.lever\.co/([^/"\']+)', html)
            if matches:
                return matches[0]
        return None

    def _has_jobposting(self, data) -> bool:
        """Check if JSON-LD contains JobPosting"""
        if isinstance(data, dict):
            if data.get('@type') == 'JobPosting':
                return True
            for value in data.values():
                if isinstance(value, (dict, list)) and self._has_jobposting(value):
                    return True
        elif isinstance(data, list):
            for item in data:
                if self._has_jobposting(item):
                    return True
        return False

    def _needs_browser(self, html: str, career_url: str) -> bool:
        """
        Determine if page needs browser automation (JavaScript-heavy)

        Returns:
            True if browser is needed, False otherwise
        """
        # Check for SPA frameworks
        spa_indicators = [
            r'<div[^>]*id=["\']root["\']',
            r'<div[^>]*id=["\']app["\']',
            r'<div[^>]*id=["\']__next["\']',
            r'react',
            r'vue',
            r'angular',
            r'__NEXT_DATA__',
            r'__REACT_QUERY_STATE__',
            r'window\.__INITIAL_STATE__',
            r'ng-app',
        ]

        html_lower = html.lower()
        for pattern in spa_indicators:
            if re.search(pattern, html_lower, re.IGNORECASE):
                logger.debug(f"SPA indicator found: {pattern}")
                return True

        # Check if page has minimal content (likely loaded via JS)
        soup = BeautifulSoup(html, 'html.parser')
        text_content = soup.get_text()
        # If page has very little text content, likely needs JS
        if len(text_content.strip()) < 500:
            # But check if it's just a redirect or error page
            if 'job' in text_content.lower() or 'career' in text_content.lower():
                return True

        # Check for heavy JavaScript usage
        scripts = soup.find_all('script')
        external_scripts = [s for s in scripts if s.get('src')]
        if len(external_scripts) > 5:  # Many external scripts suggest SPA
            return True

        return False

    def _can_parse_html(self, html: str) -> bool:
        """
        Check if HTML parsing is sufficient (static content)

        Returns:
            True if HTML parsing should work
        """
        soup = BeautifulSoup(html, 'html.parser')
        text_content = soup.get_text()

        # Check for job-related content
        job_indicators = ['job', 'position', 'career', 'opening', 'role']
        has_job_content = any(indicator in text_content.lower() for indicator in job_indicators)

        # Check for common job listing selectors
        job_selectors = [
            '[class*="job"]',
            '[id*="job"]',
            '[class*="position"]',
            '[class*="opening"]',
            'article',
            '.listing'
        ]

        has_job_elements = False
        for selector in job_selectors:
            try:
                elements = soup.select(selector)
                if elements and len(elements) > 0:
                    has_job_elements = True
                    break
            except:
                continue

        return has_job_content and has_job_elements

    def _detect_browser_config(self, html: str) -> Dict:
        """
        Detect browser-specific configuration from HTML

        Returns:
            Configuration dict for browser crawler
        """
        config = {}

        # Try to find wait selector
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for common job container selectors
        wait_selectors = [
            '[data-job-id]',
            '.job-listing',
            '.job-item',
            '.job-card',
            '[class*="job"]',
            '#jobs',
            '#positions'
        ]

        for selector in wait_selectors:
            try:
                elements = soup.select(selector)
                if elements and len(elements) > 0:
                    config['wait_for_selector'] = selector
                    break
            except:
                continue

        return config

    async def _fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML content"""
        try:
            response = await self.http.get(url)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            logger.debug(f"Error fetching HTML for method detection: {e}")
        return None

    async def close(self):
        """Cleanup"""
        try:
            await self.http.close()
        except:
            pass

