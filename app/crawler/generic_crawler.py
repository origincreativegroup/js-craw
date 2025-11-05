"""Generic Career Page Crawler - AI-assisted parsing for custom career pages"""
import logging
import httpx
import json
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from app.services.http_client import HttpClient
from app.crawler.errors import ParseError

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
        self.http = HttpClient()

    async def fetch_jobs(self) -> List[Dict]:
        """
        Fetch jobs from career page using AI parsing

        Returns:
            List of job dictionaries with normalized fields
        """
        try:
            logger.info(f"Fetching career page for {self.company_name}: {self.career_url}")

            # 1) Try structured sources first (sitemap, RSS/Atom, JSON-LD)
            jobs: List[Dict] = []

            structured_jobs = await self._extract_from_structured_sources()
            if structured_jobs:
                jobs.extend(structured_jobs)
            else:
                # 2) Fallback to HTML + AI extraction
                html = await self._fetch_html(self.career_url)
                if not html:
                    logger.warning(f"No HTML content fetched for {self.company_name}")
                    return []
                jobs = await self._extract_jobs_with_ai(html)

            logger.info(f"Found {len(jobs)} jobs for {self.company_name} via AI parsing")

            # Normalize jobs
            normalized_jobs = []
            for job in jobs:
                normalized = self._normalize_job(job)
                if normalized:
                    normalized_jobs.append(normalized)

            return self._dedupe(normalized_jobs)

        except Exception as e:
            logger.error(f"Error fetching jobs for {self.company_name}: {e}", exc_info=True)
            raise

    async def _fetch_html(self, url: str) -> str:
        """Fetch HTML content from URL"""
        try:
            response = await self.http.get(url)
            if response.status_code in (200, 304):
                return response.text
            raise ParseError(f"Unexpected status: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching HTML from {url}: {e}")
            raise

    async def _extract_from_structured_sources(self) -> List[Dict]:
        jobs: List[Dict] = []
        try:
            # Attempt robots-linked sitemap
            parsed = urlparse(self.career_url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            sitemap_urls = [f"{base}/sitemap.xml", f"{base}/sitemap_index.xml"]
            for sm in sitemap_urls:
                try:
                    r = await self.http.get(sm)
                    if r.status_code == 200 and ("<urlset" in r.text or "<sitemapindex" in r.text):
                        jobs.extend(self._parse_sitemap(r.text))
                        if jobs:
                            break
                except Exception:
                    continue

            if jobs:
                return [j for j in (self._normalize_job(j) for j in jobs) if j]

            # Check career page for RSS/Atom links
            html = await self._fetch_html(self.career_url)
            soup = BeautifulSoup(html, 'html.parser')
            for link in soup.find_all('link', rel='alternate'):
                typ = (link.get('type') or '').lower()
                if 'rss' in typ or 'atom' in typ or 'xml' in typ:
                    href = link.get('href')
                    if href:
                        feed_url = urljoin(self.career_url, href)
                        try:
                            fr = await self.http.get(feed_url)
                            if fr.status_code == 200 and fr.text:
                                jobs.extend(self._parse_feed(fr.text))
                                if jobs:
                                    break
                        except Exception:
                            continue

            if jobs:
                return [j for j in (self._normalize_job(j) for j in jobs) if j]

            # JSON-LD JobPosting
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    data = json.loads(script.string or '{}')
                    postings = self._extract_jobposting_from_jsonld(data)
                    if postings:
                        jobs.extend(postings)
                except Exception:
                    continue

            if jobs:
                return [j for j in (self._normalize_job(j) for j in jobs) if j]
        except Exception as e:
            logger.debug(f"Structured source extraction failed or empty: {e}")
        return []

    def _parse_sitemap(self, xml_text: str) -> List[Dict]:
        items: List[Dict] = []
        try:
            # naive url extraction to avoid new dependency
            for url_tag in BeautifulSoup(xml_text, 'xml').find_all('url'):
                loc = url_tag.find('loc')
                if loc and loc.text:
                    items.append({"title": None, "url": loc.text})
        except Exception:
            pass
        return items

    def _parse_feed(self, xml_text: str) -> List[Dict]:
        jobs: List[Dict] = []
        soup = BeautifulSoup(xml_text, 'xml')
        for item in soup.find_all(['item', 'entry']):
            title = (item.find('title').text if item.find('title') else '').strip()
            link_tag = item.find('link')
            href = link_tag.get('href') if link_tag and link_tag.has_attr('href') else (link_tag.text if link_tag else '')
            jobs.append({"title": title, "url": href})
        return jobs

    def _extract_jobposting_from_jsonld(self, data) -> List[Dict]:
        jobs: List[Dict] = []
        def collect(obj):
            if isinstance(obj, dict):
                t = obj.get('@type')
                if t == 'JobPosting':
                    jobs.append({
                        "title": obj.get('title'),
                        "location": (obj.get('jobLocation', {}) or {}).get('address', {}).get('addressLocality'),
                        "url": obj.get('url') or obj.get('hiringOrganization', {}).get('sameAs'),
                        "job_type": obj.get('employmentType'),
                        "description": obj.get('description')
                    })
                for v in obj.values():
                    collect(v)
            elif isinstance(obj, list):
                for v in obj:
                    collect(v)
        collect(data)
        return jobs

    def _dedupe(self, jobs: List[Dict]) -> List[Dict]:
        seen = set()
        out: List[Dict] = []
        for j in jobs:
            key = (j.get('url') or '').lower().strip(), (j.get('title') or '').lower().strip()
            if key in seen:
                continue
            seen.add(key)
            out.append(j)
        return out

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
        try:
            # best-effort
            import asyncio
            asyncio.create_task(self.http.close())
        except Exception:
            pass
