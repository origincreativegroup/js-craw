"""Fallback manager for crawling companies with multiple strategies"""
import logging
from typing import List, Dict, Callable, Tuple, Optional
from app.models import Company
from app.crawler.api_fetcher import ApiFetcher
from app.crawler.browser_crawler import BrowserCrawler
from app.crawler.puppeteer_service import PuppeteerService
from app.config import settings

logger = logging.getLogger(__name__)


class CrawlFallbackManager:
    """Manages fallback crawling strategies when primary method fails"""
    
    def __init__(self, primary_crawler: Callable):
        """
        Initialize fallback manager with primary crawler method.
        
        Args:
            primary_crawler: Async function that takes a Company and returns List[Dict]
        """
        self.primary_crawler = primary_crawler
    
    async def crawl_with_fallback(
        self,
        company: Company
    ) -> Tuple[List[Dict], str]:
        """
        Try to crawl company using primary method, then fallback strategies.
        Fallback chain: primary → API → browser → no_results
        
        Args:
            company: Company to crawl
            
        Returns:
            Tuple of (jobs list, method_used string)
        """
        # Try primary method first
        try:
            jobs = await self.primary_crawler(company)
            if jobs and len(jobs) > 0:
                return jobs, "career_page"
            else:
                logger.debug(f"Primary crawler returned no results for {company.name}")
        except Exception as e:
            logger.warning(f"Primary crawler failed for {company.name}: {e}")
        
        # Fallback 1: Try API fetcher
        if settings.API_DETECTION_ENABLED:
            try:
                logger.info(f"Trying API fetcher fallback for {company.name}")
                fetcher = ApiFetcher(company.name, company.career_page_url)
                jobs = await fetcher.fetch_jobs()
                await fetcher.close()
                if jobs and len(jobs) > 0:
                    logger.info(f"API fetcher found {len(jobs)} jobs for {company.name}")
                    return jobs, "api_fallback"
                else:
                    logger.debug(f"API fetcher returned no results for {company.name}")
            except Exception as e:
                logger.warning(f"API fetcher fallback failed for {company.name}: {e}")
        
        # Fallback 2: Try browser automation
        if settings.BROWSER_ENABLED:
            try:
                logger.info(f"Trying browser fallback for {company.name}")
                # Try Puppeteer first (if available)
                try:
                    puppeteer = PuppeteerService()
                    if await puppeteer.health_check():
                        jobs = await puppeteer.crawl(
                            company.name,
                            company.career_page_url,
                            timeout=settings.PLAYWRIGHT_TIMEOUT
                        )
                        if jobs and len(jobs) > 0:
                            logger.info(f"Puppeteer found {len(jobs)} jobs for {company.name}")
                            return jobs, "puppeteer_fallback"
                        else:
                            logger.debug(f"Puppeteer returned no results for {company.name}")
                    else:
                        logger.debug(f"Puppeteer service not available, trying Playwright")
                except Exception as e:
                    logger.debug(f"Puppeteer fallback error: {e}, trying Playwright")
                
                # Fallback to Playwright
                crawler = BrowserCrawler(
                    company.name,
                    company.career_page_url,
                    timeout=settings.PLAYWRIGHT_TIMEOUT,
                    headless=settings.BROWSER_HEADLESS
                )
                jobs = await crawler.fetch_jobs()
                await crawler.close()
                if jobs and len(jobs) > 0:
                    logger.info(f"Browser crawler found {len(jobs)} jobs for {company.name}")
                    return jobs, "browser_fallback"
                else:
                    logger.debug(f"Browser crawler returned no results for {company.name}")
            except Exception as e:
                logger.warning(f"Browser fallback failed for {company.name}: {e}")
        
        # All methods failed
        logger.info(f"No jobs found for {company.name} using any method")
        return [], "no_results"

