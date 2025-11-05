"""Company Discovery Service - Automatically discovers companies from multiple sources"""
import logging
import re
import asyncio
from typing import List, Dict, Set, Optional
from urllib.parse import urlencode, urlparse, quote
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.services.company_update_pipeline import CompanyRecord
from app.services.company_sources import CompanyDataSource
from app.config import settings

logger = logging.getLogger(__name__)


class LinkedInCompanySource(CompanyDataSource):
    """Discover companies from LinkedIn job postings"""
    
    BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    
    def __init__(self, keywords: str = "careers jobs", max_results: int = 200):
        self.keywords = keywords
        self.max_results = max_results
        # Multiple search query variations for better coverage
        self.search_variations = [
            keywords,
            "software engineer jobs",
            "remote jobs",
            "hiring now",
            "tech jobs",
            "developer jobs",
        ]
    
    async def fetch(self) -> List[CompanyRecord]:
        """Fetch companies from LinkedIn job postings with enhanced pagination"""
        companies: List[CompanyRecord] = []
        seen_companies: Set[str] = set()
        
        try:
            async with httpx.AsyncClient(timeout=60.0, headers=self._headers(), follow_redirects=True) as client:
                # Try multiple search variations
                companies_per_variation = self.max_results // len(self.search_variations)
                
                for search_query in self.search_variations:
                    if len(companies) >= self.max_results:
                        break
                    
                    max_pages = min(20, (companies_per_variation // 25) + 1)  # Increased from 10 to 20
                    consecutive_empty = 0
                    
                    for page in range(max_pages):
                        start = page * 25
                        params = {
                            "keywords": search_query,
                            "start": str(start),
                        }
                        url = f"{self.BASE_URL}?{urlencode(params)}"
                        
                        try:
                            response = await client.get(url)
                            if response.status_code == 404:
                                logger.debug(f"LinkedIn returned 404 for page {page + 1} (query: {search_query})")
                                break
                            if response.status_code in [429, 503]:
                                logger.warning(f"LinkedIn rate limited, waiting...")
                                await asyncio.sleep(5)
                                continue
                            response.raise_for_status()
                            
                            companies_found = self._extract_companies(response.text, seen_companies)
                            
                            if not companies_found:
                                consecutive_empty += 1
                                if consecutive_empty >= 2:  # Stop after 2 empty pages
                                    break
                            else:
                                consecutive_empty = 0
                            
                            companies.extend(companies_found)
                            
                            if len(companies) >= self.max_results:
                                break
                                
                            await asyncio.sleep(1.5)  # Slightly longer delay
                        except Exception as e:
                            logger.warning(f"Error fetching LinkedIn page {page + 1} (query: {search_query}): {e}")
                            break
                    
                    await asyncio.sleep(2)  # Delay between search variations
        except Exception as e:
            logger.error(f"Error in LinkedIn company discovery: {e}", exc_info=True)
        
        logger.info(f"LinkedIn discovery found {len(companies)} companies")
        return companies[:self.max_results]
    
    def _extract_companies(self, html: str, seen_companies: Set[str]) -> List[CompanyRecord]:
        """Extract company names and URLs from LinkedIn HTML with improved parsing"""
        companies = []
        soup = BeautifulSoup(html, "html.parser")
        
        # Find all job cards - try multiple selectors
        job_cards = soup.select("li.jobs-search-results__list-item, div.base-card, li.job-search-card, div.job-card-container")
        
        for card in job_cards:
            try:
                # Extract company name - try multiple selectors
                company_elem = (
                    card.select_one("h4.base-search-card__subtitle") or
                    card.select_one("a.job-search-card__subtitle-link") or
                    card.select_one("span.job-search-card__company-name") or
                    card.select_one("a[data-tracking-control-name='public_jobs_jserp-result_job-search-card-subtitle']")
                )
                
                if not company_elem:
                    continue
                
                company_name = company_elem.get_text(strip=True)
                # Clean company name
                company_name = re.sub(r'\s+', ' ', company_name).strip()
                
                if not company_name or len(company_name) < 2:
                    continue
                
                # Skip common non-company names
                skip_patterns = ['remote', 'view job', 'easy apply', 'apply now', 'save job']
                if any(pattern in company_name.lower() for pattern in skip_patterns):
                    continue
                
                if company_name.lower() in seen_companies:
                    continue
                
                seen_companies.add(company_name.lower())
                
                # Try to find career page URL with better extraction
                career_url = self._find_career_url(card, company_name)
                
                if career_url:
                    companies.append(CompanyRecord(
                        name=company_name,
                        career_page_url=career_url,
                        source="linkedin",
                        priority=50,
                        metadata={
                            "discovered_at": datetime.utcnow().isoformat(),
                            "source_page": "linkedin_jobs"
                        }
                    ))
            except Exception as e:
                logger.debug(f"Error extracting company from LinkedIn card: {e}")
                continue
        
        return companies
    
    def _find_career_url(self, card, company_name: str) -> Optional[str]:
        """Try to find career page URL from LinkedIn card with better heuristics"""
        # Check for direct company link
        company_link = (
            card.select_one("a.job-search-card__subtitle-link") or
            card.select_one("a.base-card__full-link") or
            card.select_one("a[data-tracking-control-name='public_jobs_jserp-result_job-search-card-subtitle']")
        )
        
        if company_link:
            href = company_link.get("href", "")
            if href:
                # Convert LinkedIn company page to potential career page
                if "linkedin.com/company/" in href:
                    company_slug = href.split("linkedin.com/company/")[-1].split("/")[0].split("?")[0]
                    # Try common career page patterns
                    domain = company_slug.replace("-", "").lower()
                    # Try multiple common patterns
                    patterns = [
                        f"https://www.{domain}.com/careers",
                        f"https://{domain}.com/careers",
                        f"https://www.{domain}.com/jobs",
                        f"https://{domain}.com/jobs",
                        f"https://careers.{domain}.com",
                    ]
                    # Return first pattern (will be verified later)
                    return patterns[0]
        
        # Try to construct from company name with better cleaning
        clean_name = re.sub(r'[^\w\s-]', '', company_name).lower()
        # Remove common suffixes
        clean_name = re.sub(r'\s+(inc|llc|ltd|corp|corporation|company|co)\s*$', '', clean_name)
        clean_name = clean_name.replace(' ', '').replace('-', '').replace('_', '')
        
        if clean_name and len(clean_name) > 2:
            # Try multiple domain patterns
            return f"https://www.{clean_name}.com/careers"
        
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


class IndeedCompanySource(CompanyDataSource):
    """Discover companies from Indeed job postings"""
    
    BASE_URL = "https://www.indeed.com/jobs"
    
    def __init__(self, keywords: str = "careers jobs", max_results: int = 200):
        self.keywords = keywords
        self.max_results = max_results
        # Multiple search query variations
        self.search_variations = [
            keywords,
            "software engineer",
            "remote developer",
            "tech jobs",
            "engineering jobs",
            "hiring now",
        ]
    
    async def fetch(self) -> List[CompanyRecord]:
        """Fetch companies from Indeed job postings with enhanced pagination"""
        companies: List[CompanyRecord] = []
        seen_companies: Set[str] = set()
        
        try:
            async with httpx.AsyncClient(timeout=60.0, headers=self._headers(), follow_redirects=True) as client:
                # Try multiple search variations
                companies_per_variation = self.max_results // len(self.search_variations)
                
                for search_query in self.search_variations:
                    if len(companies) >= self.max_results:
                        break
                    
                    max_pages = min(20, (companies_per_variation // 20) + 1)  # Increased from 10 to 20
                    consecutive_empty = 0
                    
                    for page in range(max_pages):
                        start = page * 20
                        params = {
                            "q": search_query,
                            "start": str(start),
                            "limit": "20"
                        }
                        url = f"{self.BASE_URL}?{urlencode(params)}"
                        
                        try:
                            response = await client.get(url)
                            if response.status_code in [429, 503]:
                                logger.warning(f"Indeed rate limited, waiting...")
                                await asyncio.sleep(5)
                                continue
                            response.raise_for_status()
                            
                            companies_found = self._extract_companies(response.text, seen_companies)
                            
                            if not companies_found:
                                consecutive_empty += 1
                                if consecutive_empty >= 2:  # Stop after 2 empty pages
                                    break
                            else:
                                consecutive_empty = 0
                            
                            companies.extend(companies_found)
                            
                            if len(companies) >= self.max_results:
                                break
                                
                            await asyncio.sleep(1.5)  # Slightly longer delay
                        except Exception as e:
                            logger.warning(f"Error fetching Indeed page {page + 1} (query: {search_query}): {e}")
                            break
                    
                    await asyncio.sleep(2)  # Delay between search variations
        except Exception as e:
            logger.error(f"Error in Indeed company discovery: {e}", exc_info=True)
        
        logger.info(f"Indeed discovery found {len(companies)} companies")
        return companies[:self.max_results]
    
    def _extract_companies(self, html: str, seen_companies: Set[str]) -> List[CompanyRecord]:
        """Extract company names and URLs from Indeed HTML with improved parsing"""
        companies = []
        soup = BeautifulSoup(html, "html.parser")
        
        # Find all job cards - try multiple selectors
        job_cards = soup.select("div.job_seen_beacon, div.cardOutline, td.resultContent, div[data-jk]")
        
        for card in job_cards:
            try:
                # Extract company name - try multiple selectors
                company_elem = (
                    card.select_one("span.companyName") or
                    card.select_one("a[data-testid='company-name']") or
                    card.select_one("a.companyOverviewLink") or
                    card.select_one("span[data-testid='company-name']")
                )
                
                if not company_elem:
                    continue
                
                company_name = company_elem.get_text(strip=True)
                # Clean company name
                company_name = re.sub(r'\s+', ' ', company_name).strip()
                
                if not company_name or len(company_name) < 2:
                    continue
                
                # Skip common non-company names
                skip_patterns = ['remote', 'view job', 'easy apply', 'apply now', 'urgent', 'hiring']
                if any(pattern in company_name.lower() for pattern in skip_patterns):
                    continue
                
                if company_name.lower() in seen_companies:
                    continue
                
                seen_companies.add(company_name.lower())
                
                # Try to find career page URL with better extraction
                career_url = self._find_career_url(card, company_name)
                
                if career_url:
                    companies.append(CompanyRecord(
                        name=company_name,
                        career_page_url=career_url,
                        source="indeed",
                        priority=50,
                        metadata={
                            "discovered_at": datetime.utcnow().isoformat(),
                            "source_page": "indeed_jobs"
                        }
                    ))
            except Exception as e:
                logger.debug(f"Error extracting company from Indeed card: {e}")
                continue
        
        return companies
    
    def _find_career_url(self, card, company_name: str) -> Optional[str]:
        """Try to find career page URL from Indeed card with better heuristics"""
        # Check for company website link - try multiple selectors
        company_link = (
            card.select_one("a[data-testid='company-name']") or
            card.select_one("a.companyName") or
            card.select_one("a.companyOverviewLink")
        )
        
        if company_link:
            href = company_link.get("href", "")
            if href and "http" in href:
                # Try to convert to career page
                try:
                    parsed = urlparse(href)
                    if parsed.netloc:
                        domain = parsed.netloc.replace("www.", "").split(":")[0]
                        # Try multiple common patterns
                        patterns = [
                            f"https://www.{domain}/careers",
                            f"https://{domain}/careers",
                            f"https://www.{domain}/jobs",
                            f"https://{domain}/jobs",
                            f"https://careers.{domain}",
                        ]
                        return patterns[0]
                except Exception:
                    pass
        
        # Try to construct from company name with better cleaning
        clean_name = re.sub(r'[^\w\s-]', '', company_name).lower()
        # Remove common suffixes
        clean_name = re.sub(r'\s+(inc|llc|ltd|corp|corporation|company|co)\s*$', '', clean_name)
        clean_name = clean_name.replace(' ', '').replace('-', '').replace('_', '')
        
        if clean_name and len(clean_name) > 2:
            return f"https://www.{clean_name}.com/careers"
        
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


class WebSearchCompanySource(CompanyDataSource):
    """Discover companies using web search"""
    
    # Using DuckDuckGo HTML search as it doesn't require API keys
    BASE_URL = "https://html.duckduckgo.com/html/"
    
    def __init__(self, keywords: str = "companies careers", max_results: int = 50):
        self.keywords = keywords
        self.max_results = max_results
    
    async def fetch(self) -> List[CompanyRecord]:
        """Fetch companies using web search with more query variations"""
        companies: List[CompanyRecord] = []
        seen_companies: Set[str] = set()
        
        try:
            async with httpx.AsyncClient(timeout=60.0, headers=self._headers(), follow_redirects=True) as client:
                # Expanded search queries for better coverage
                search_queries = [
                    "companies with career pages",
                    "best companies to work for careers",
                    "fortune 500 companies careers",
                    "startup companies careers",
                    "tech companies hiring",
                    "remote companies careers",
                    "software companies jobs",
                    "engineering companies careers",
                ]
                
                for query in search_queries:
                    if len(companies) >= self.max_results:
                        break
                    
                    try:
                        params = {"q": query}
                        response = await client.post(
                            self.BASE_URL,
                            data=params,
                            headers=self._headers()
                        )
                        if response.status_code in [429, 503]:
                            logger.warning(f"Web search rate limited, waiting...")
                            await asyncio.sleep(5)
                            continue
                        response.raise_for_status()
                        
                        companies_found = self._extract_companies(response.text, seen_companies)
                        companies.extend(companies_found)
                        
                        if len(companies) >= self.max_results:
                            break
                            
                        await asyncio.sleep(2.5)  # Rate limiting
                    except Exception as e:
                        logger.warning(f"Error in web search query '{query}': {e}")
                        continue
        except Exception as e:
            logger.error(f"Error in web search company discovery: {e}", exc_info=True)
        
        logger.info(f"Web search discovery found {len(companies)} companies")
        return companies[:self.max_results]
    
    def _extract_companies(self, html: str, seen_companies: Set[str]) -> List[CompanyRecord]:
        """Extract company names and URLs from search results"""
        companies = []
        soup = BeautifulSoup(html, "html.parser")
        
        # Find all search result links
        results = soup.select("div.result, a.result__a")
        
        for result in results[:20]:  # Limit per page
            try:
                # Extract link
                link_elem = result.select_one("a.result__a, a") if hasattr(result, 'select_one') else result
                if not link_elem:
                    continue
                
                href = link_elem.get("href", "")
                if not href or not href.startswith("http"):
                    continue
                
                # Extract title/snippet
                title_elem = result.select_one("a.result__a, h2, .result__title")
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                
                # Try to extract company name from title or URL
                company_name = self._extract_company_name(title, href)
                if not company_name or company_name.lower() in seen_companies:
                    continue
                
                seen_companies.add(company_name.lower())
                
                # Check if URL looks like a career page
                if any(path in href.lower() for path in ["/careers", "/jobs", "/job", "/work-with-us", "/career"]):
                    companies.append(CompanyRecord(
                        name=company_name,
                        career_page_url=href,
                        source="web_search",
                        priority=40,
                        metadata={
                            "discovered_at": datetime.utcnow().isoformat(),
                            "source_page": "web_search",
                            "search_query": self.keywords
                        }
                    ))
            except Exception as e:
                logger.debug(f"Error extracting company from search result: {e}")
                continue
        
        return companies
    
    def _extract_company_name(self, title: str, url: str) -> Optional[str]:
        """Extract company name from title or URL"""
        # Try to extract from URL domain
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            if domain:
                # Extract company name from domain (e.g., "acme.com" -> "Acme")
                domain_parts = domain.split(".")[0]
                # Convert to title case
                return domain_parts.replace("-", " ").replace("_", " ").title()
        except:
            pass
        
        # Try to extract from title
        if title:
            # Remove common suffixes
            title_clean = re.sub(r'\s+(Careers?|Jobs?|Hiring|Career Page).*$', '', title, flags=re.IGNORECASE)
            return title_clean.strip()[:100]  # Limit length
        
        return None
    
    def _headers(self) -> Dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/119.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
        }


class CompanyDiscoveryService:
    """Orchestrates company discovery from multiple sources"""
    
    def __init__(self):
        self.linkedin_source = LinkedInCompanySource(
            keywords=getattr(settings, "LINKEDIN_SEARCH_KEYWORDS", "careers jobs"),
            max_results=getattr(settings, "COMPANY_DISCOVERY_BATCH_SIZE", 50)
        )
        self.indeed_source = IndeedCompanySource(
            keywords=getattr(settings, "INDEED_SEARCH_KEYWORDS", "careers jobs"),
            max_results=getattr(settings, "COMPANY_DISCOVERY_BATCH_SIZE", 50)
        )
        self.web_search_source = WebSearchCompanySource(
            keywords=getattr(settings, "WEB_SEARCH_KEYWORDS", "companies careers"),
            max_results=getattr(settings, "COMPANY_DISCOVERY_BATCH_SIZE", 50) // 2
        )
    
    async def discover_companies(
        self,
        keywords: Optional[str] = None,
        max_companies: int = 100,
        existing_company_names: Optional[Set[str]] = None
    ) -> List[Dict]:
        """
        Discover companies from all sources with parallel execution
        
        Args:
            keywords: Search keywords (optional, uses config defaults)
            max_companies: Maximum number of companies to discover
            existing_company_names: Set of existing company names to filter out
            
        Returns:
            List of company dictionaries
        """
        existing = existing_company_names or set()
        
        # Collect from all sources in parallel for faster execution
        all_records: List[CompanyRecord] = []
        
        try:
            # Discover from all sources in parallel
            linkedin_task = self.linkedin_source.fetch()
            indeed_task = self.indeed_source.fetch()
            web_search_task = self.web_search_source.fetch()
            
            # Wait for all sources to complete
            results = await asyncio.gather(
                linkedin_task,
                indeed_task,
                web_search_task,
                return_exceptions=True
            )
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error in company discovery source: {result}", exc_info=True)
                elif isinstance(result, list):
                    all_records.extend(result)
        except Exception as e:
            logger.error(f"Error during company discovery: {e}", exc_info=True)
        
        # Deduplicate by company name with better matching
        unique_companies: Dict[str, CompanyRecord] = {}
        for record in all_records:
            name_lower = record.name.lower().strip()
            
            # Skip if already exists in database
            if name_lower in existing:
                continue
            
            # Skip very short or invalid names
            if len(name_lower) < 2:
                continue
            
            # Prefer higher priority records for duplicates
            if name_lower in unique_companies:
                existing_record = unique_companies[name_lower]
                if record.priority > existing_record.priority:
                    unique_companies[name_lower] = record
            else:
                unique_companies[name_lower] = record
        
        # Sort by priority (higher first) and source quality
        sorted_records = sorted(
            unique_companies.values(),
            key=lambda r: (r.priority, r.source == "linkedin", r.source == "indeed"),
            reverse=True
        )
        
        # Convert to dictionaries
        discovered = []
        for record in sorted_records[:max_companies]:
            discovered.append({
                "name": record.name,
                "career_page_url": record.career_page_url,
                "source": record.source,
                "discovery_metadata": record.metadata,
                "priority": record.priority
            })
        
        logger.info(f"Company discovery completed: {len(discovered)} unique companies found from {len(all_records)} total records")
        return discovered
