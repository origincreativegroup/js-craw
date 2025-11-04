"""Fallback manager for crawling companies with multiple strategies"""
import logging
from typing import List, Dict, Callable, Tuple, Optional
from app.models import Company

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
        
        # If primary method failed or returned no results, try fallback methods
        # For now, return empty results with method indicator
        # Future: Implement LinkedIn, Indeed, and AI web search fallbacks
        logger.info(f"No jobs found for {company.name} using primary method")
        return [], "no_results"

