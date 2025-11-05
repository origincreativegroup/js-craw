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
    
    def __init__(self, keywords: str = "careers jobs", max_results: int = 100):
        self.keywords = keywords
        self.max_results = max_results
    
    async def fetch(self) -> List[CompanyRecord]:
        """Fetch companies from LinkedIn job postings"""
        companies: List[CompanyRecord] = []
        seen_companies: Set[str] = set()
        
        try:
            async with httpx.AsyncClient(timeout=30.0, headers=self._headers()) as client:
                max_pages = min(10, (self.max_results // 25) + 1)
                
                for page in range(max_pages):
                    start = page * 25
                    params = {
                        "keywords": self.keywords,
                        "start": str(start),
                    }
                    url = f"{self.BASE_URL}?{urlencode(params)}"
                    
                    try:
                        response = await client.get(url)
                        if response.status_code == 404:
                            logger.info(f"LinkedIn returned 404 for page {page + 1}")
                            break
                        response.raise_for_status()
                        
                        companies_found = self._extract_companies(response.text, seen_companies)
                        companies.extend(companies_found)
                        
                        if len(companies) >= self.max_results:
                            break
                            
                        await asyncio.sleep(1)  # Rate limiting
                    except Exception as e:
                        logger.warning(f"Error fetching LinkedIn page {page + 1}: {e}")
                        break
        except Exception as e:
            logger.error(f"Error in LinkedIn company discovery: {e}", exc_info=True)
        
        logger.info(f"LinkedIn discovery found {len(companies)} companies")
        return companies[:self.max_results]
    
    def _extract_companies(self, html: str, seen_companies: Set[str]) -> List[CompanyRecord]:
        """Extract company names and URLs from LinkedIn HTML"""
        companies = []
        soup = BeautifulSoup(html, "html.parser")
        
        # Find all job cards
        job_cards = soup.select("div.base-card, li.job-search-card")
        
        for card in job_cards:
            try:
                # Extract company name
                company_elem = card.select_one("h4.base-search-card__subtitle, a.job-search-card__subtitle-link")
                if not company_elem:
                    continue
                
                company_name = company_elem.get_text(strip=True)
                if not company_name or company_name.lower() in seen_companies:
                    continue
                
                seen_companies.add(company_name.lower())
                
                # Try to find career page URL
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
        """Try to find career page URL from LinkedIn card"""
        # Check for direct company link
        company_link = card.select_one("a.job-search-card__subtitle-link, a.base-card__full-link")
        if company_link:
            href = company_link.get("href", "")
            if href:
                # Convert LinkedIn company page to potential career page
                # e.g., linkedin.com/company/acme -> acme.com/careers
                if "linkedin.com/company/" in href:
                    company_slug = href.split("linkedin.com/company/")[-1].split("/")[0].split("?")[0]
                    # Try common career page patterns
                    domain = company_slug.replace("-", "").lower()
                    return f"https://www.{domain}.com/careers"
        
        # Try to construct from company name
        clean_name = re.sub(r'[^\w\s-]', '', company_name).lower().replace(' ', '')
        if clean_name:
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
    
    def __init__(self, keywords: str = "careers jobs", max_results: int = 100):
        self.keywords = keywords
        self.max_results = max_results
    
    async def fetch(self) -> List[CompanyRecord]:
        """Fetch companies from Indeed job postings"""
        companies: List[CompanyRecord] = []
        seen_companies: Set[str] = set()
        
        try:
            async with httpx.AsyncClient(timeout=30.0, headers=self._headers(), follow_redirects=True) as client:
                max_pages = min(10, (self.max_results // 20) + 1)
                
                for page in range(max_pages):
                    start = page * 20
                    params = {
                        "q": self.keywords,
                        "start": str(start),
                        "limit": "20"
                    }
                    url = f"{self.BASE_URL}?{urlencode(params)}"
                    
                    try:
                        response = await client.get(url)
                        response.raise_for_status()
                        
                        companies_found = self._extract_companies(response.text, seen_companies)
                        companies.extend(companies_found)
                        
                        if len(companies) >= self.max_results:
                            break
                            
                        await asyncio.sleep(1)  # Rate limiting
                    except Exception as e:
                        logger.warning(f"Error fetching Indeed page {page + 1}: {e}")
                        break
        except Exception as e:
            logger.error(f"Error in Indeed company discovery: {e}", exc_info=True)
        
        logger.info(f"Indeed discovery found {len(companies)} companies")
        return companies[:self.max_results]
    
    def _extract_companies(self, html: str, seen_companies: Set[str]) -> List[CompanyRecord]:
        """Extract company names and URLs from Indeed HTML"""
        companies = []
        soup = BeautifulSoup(html, "html.parser")
        
        # Find all job cards
        job_cards = soup.select("div.job_seen_beacon, div.cardOutline, td.resultContent")
        
        for card in job_cards:
            try:
                # Extract company name
                company_elem = card.select_one("span.companyName, a[data-testid='company-name']")
                if not company_elem:
                    continue
                
                company_name = company_elem.get_text(strip=True)
                if not company_name or company_name.lower() in seen_companies:
                    continue
                
                seen_companies.add(company_name.lower())
                
                # Try to find career page URL
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
        """Try to find career page URL from Indeed card"""
        # Check for company website link
        company_link = card.select_one("a[data-testid='company-name'], a.companyName")
        if company_link:
            href = company_link.get("href", "")
            if href and "http" in href:
                # Try to convert to career page
                parsed = urlparse(href)
                if parsed.netloc:
                    domain = parsed.netloc.replace("www.", "")
                    return f"https://www.{domain}/careers"
        
        # Try to construct from company name
        clean_name = re.sub(r'[^\w\s-]', '', company_name).lower().replace(' ', '')
        if clean_name:
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
        """Fetch companies using web search"""
        companies: List[CompanyRecord] = []
        seen_companies: Set[str] = set()
        
        try:
            async with httpx.AsyncClient(timeout=30.0, headers=self._headers(), follow_redirects=True) as client:
                # Search for companies with career pages
                search_queries = [
                    "companies with career pages",
                    "best companies to work for careers",
                    "fortune 500 companies careers",
                    "startup companies careers"
                ]
                
                for query in search_queries[:2]:  # Limit to avoid rate limiting
                    try:
                        params = {"q": query}
                        response = await client.post(
                            self.BASE_URL,
                            data=params,
                            headers=self._headers()
                        )
                        response.raise_for_status()
                        
                        companies_found = self._extract_companies(response.text, seen_companies)
                        companies.extend(companies_found)
                        
                        if len(companies) >= self.max_results:
                            break
                            
                        await asyncio.sleep(2)  # Rate limiting
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
        max_companies: int = 50,
        existing_company_names: Optional[Set[str]] = None
    ) -> List[Dict]:
        """
        Discover companies from all sources
        
        Args:
            keywords: Search keywords (optional, uses config defaults)
            max_companies: Maximum number of companies to discover
            existing_company_names: Set of existing company names to filter out
            
        Returns:
            List of company dictionaries
        """
        existing = existing_company_names or set()
        
        # Collect from all sources
        all_records: List[CompanyRecord] = []
        
        try:
            # Discover from LinkedIn
            linkedin_records = await self.linkedin_source.fetch()
            all_records.extend(linkedin_records)
            
            # Discover from Indeed
            indeed_records = await self.indeed_source.fetch()
            all_records.extend(indeed_records)
            
            # Discover from web search
            web_search_records = await self.web_search_source.fetch()
            all_records.extend(web_search_records)
        except Exception as e:
            logger.error(f"Error during company discovery: {e}", exc_info=True)
        
        # Deduplicate by company name
        unique_companies: Dict[str, CompanyRecord] = {}
        for record in all_records:
            name_lower = record.name.lower()
            if name_lower not in existing and name_lower not in unique_companies:
                unique_companies[name_lower] = record
        
        # Convert to dictionaries
        discovered = []
        for record in list(unique_companies.values())[:max_companies]:
            discovered.append({
                "name": record.name,
                "career_page_url": record.career_page_url,
                "source": record.source,
                "metadata": record.metadata,
                "priority": record.priority
            })
        
        logger.info(f"Company discovery completed: {len(discovered)} unique companies found")
        return discovered
