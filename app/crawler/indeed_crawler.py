"""Indeed job crawler"""
import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from app.config import settings

logger = logging.getLogger(__name__)


class IndeedCrawler:
    """Crawler for Indeed job postings"""
    
    def __init__(self, email: Optional[str] = None, password: Optional[str] = None):
        self.email = email
        self.password = password
        self.driver = None
        self.base_url = "https://www.indeed.com"
    
    def _get_driver(self):
        """Get Selenium WebDriver"""
        if self.driver is None:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            self.driver = webdriver.Remote(
                command_executor=settings.SELENIUM_HOST,
                options=options
            )
        return self.driver
    
    async def search_jobs(self, criteria: Dict) -> List[Dict]:
        """Search for jobs on Indeed"""
        driver = self._get_driver()
        jobs = []
        
        try:
            # Navigate to Indeed
            driver.get(self.base_url)
            await asyncio.sleep(2)
            
            # Login if credentials provided
            if self.email and self.password:
                await self._login(driver)
            
            # Perform search
            await self._perform_search(driver, criteria)
            
            # Extract jobs
            jobs = await self._extract_jobs(driver)
            
        except Exception as e:
            logger.error(f"Error crawling Indeed: {e}", exc_info=True)
            raise
        
        return jobs
    
    async def _login(self, driver):
        """Login to Indeed (if needed)"""
        # Indeed doesn't require login for job searches
        # But we can implement it if needed for saved searches
        logger.info("Indeed doesn't require login for basic searches")
        pass
    
    async def _perform_search(self, driver, criteria: Dict):
        """Perform job search"""
        logger.info(f"Searching Indeed for: {criteria.get('keywords')}")
        
        try:
            # Find search input
            search_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "text-input-what"))
            )
            search_input.clear()
            search_input.send_keys(criteria.get('keywords', ''))
            
            # Find location input
            location_input = driver.find_element(By.ID, "text-input-where")
            location_input.clear()
            location_input.send_keys(criteria.get('location', ''))
            
            # Submit search
            search_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            search_button.click()
            
            await asyncio.sleep(3)
            
            # Apply remote filter if specified
            if criteria.get('remote_only'):
                try:
                    remote_link = driver.find_element(
                        By.XPATH,
                        "//a[contains(text(), 'Remote')]"
                    )
                    remote_link.click()
                    await asyncio.sleep(2)
                except NoSuchElementException:
                    logger.warning("Could not find remote filter")
            
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Error performing search: {e}")
            raise
    
    async def _extract_jobs(self, driver) -> List[Dict]:
        """Extract job listings from current page"""
        jobs = []
        
        try:
            # Scroll to load more
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            await asyncio.sleep(2)
            
            # Find job cards
            job_cards = driver.find_elements(
                By.CSS_SELECTOR,
                "div[data-jk]"
            )
            
            logger.info(f"Found {len(job_cards)} job cards")
            
            for card in job_cards[:25]:  # Limit to first 25 jobs
                try:
                    job_data = await self._extract_job_details(card, driver)
                    if job_data:
                        jobs.append(job_data)
                except Exception as e:
                    logger.warning(f"Error extracting job: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error extracting jobs: {e}")
        
        return jobs
    
    async def _extract_job_details(self, card, driver) -> Optional[Dict]:
        """Extract details from a job card"""
        try:
            # Get job ID
            job_id = card.get_attribute('data-jk')
            if not job_id:
                return None
            
            # Extract title
            try:
                title_element = card.find_element(By.CSS_SELECTOR, "h2.jobTitle a")
                title = title_element.text.strip()
                url = title_element.get_attribute('href')
            except NoSuchElementException:
                try:
                    title_element = card.find_element(By.CSS_SELECTOR, "h2.jobTitle")
                    title = title_element.text.strip()
                    url = f"{self.base_url}/viewjob?jk={job_id}"
                except NoSuchElementException:
                    return None
            
            # Extract company
            try:
                company_element = card.find_element(By.CSS_SELECTOR, "span.companyName")
                company = company_element.text.strip()
            except NoSuchElementException:
                company = "Unknown"
            
            # Extract location
            try:
                location_element = card.find_element(By.CSS_SELECTOR, "div.companyLocation")
                location = location_element.text.strip()
            except NoSuchElementException:
                location = "Not specified"
            
            # Extract description snippet
            try:
                description_element = card.find_element(By.CSS_SELECTOR, "div.job-snippet")
                description = description_element.text.strip()
            except NoSuchElementException:
                description = ""
            
            # Extract posted date
            posted_date = None
            try:
                date_element = card.find_element(By.CSS_SELECTOR, "span.date")
                date_text = date_element.text.strip()
                # Parse date (e.g., "Just posted", "2 days ago", etc.)
                # This is simplified - you might want more robust parsing
                posted_date = datetime.utcnow()  # Placeholder
            except NoSuchElementException:
                pass
            
            return {
                'platform': 'indeed',
                'external_id': job_id,
                'title': title,
                'company': company,
                'location': location,
                'url': url if url else f"{self.base_url}/viewjob?jk={job_id}",
                'description': description,
                'posted_date': posted_date,
            }
            
        except Exception as e:
            logger.warning(f"Error extracting job details: {e}")
            return None
    
    def close(self):
        """Close the browser"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Error closing driver: {e}")
            finally:
                self.driver = None

