"""LinkedIn job crawler"""
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


class LinkedInCrawler:
    """Crawler for LinkedIn job postings"""
    
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.driver = None
        self.base_url = "https://www.linkedin.com"
    
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
        """Search for jobs on LinkedIn"""
        driver = self._get_driver()
        jobs = []
        
        try:
            # Login
            await self._login(driver)
            
            # Navigate to jobs
            await self._navigate_to_jobs(driver)
            
            # Perform search
            await self._perform_search(driver, criteria)
            
            # Extract jobs
            jobs = await self._extract_jobs(driver, criteria)
            
        except Exception as e:
            logger.error(f"Error crawling LinkedIn: {e}", exc_info=True)
            raise
        
        return jobs
    
    async def _login(self, driver):
        """Login to LinkedIn"""
        logger.info("Logging into LinkedIn...")
        driver.get(f"{self.base_url}/login")
        
        await asyncio.sleep(2)
        
        # Enter email
        email_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        email_input.send_keys(self.email)
        
        # Enter password
        password_input = driver.find_element(By.ID, "password")
        password_input.send_keys(self.password)
        
        # Submit
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()
        
        # Wait for navigation
        await asyncio.sleep(5)
        
        # Check if login was successful
        if "feed" in driver.current_url or "linkedin.com/in" in driver.current_url:
            logger.info("LinkedIn login successful")
        else:
            raise Exception("LinkedIn login failed")
    
    async def _navigate_to_jobs(self, driver):
        """Navigate to jobs page"""
        logger.info("Navigating to jobs page...")
        driver.get(f"{self.base_url}/jobs")
        await asyncio.sleep(3)
    
    async def _perform_search(self, driver, criteria: Dict):
        """Perform job search"""
        logger.info(f"Searching for: {criteria.get('keywords')}")
        
        try:
            # Find search input
            search_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[aria-label*='Search']"))
            )
            search_input.clear()
            search_input.send_keys(criteria.get('keywords', ''))
            search_input.send_keys(Keys.RETURN)
            
            await asyncio.sleep(3)
            
            # Apply location filter if specified
            if criteria.get('location'):
                try:
                    location_input = driver.find_element(
                        By.CSS_SELECTOR, 
                        "input[aria-label*='Location']"
                    )
                    location_input.clear()
                    location_input.send_keys(criteria.get('location'))
                    location_input.send_keys(Keys.RETURN)
                    await asyncio.sleep(2)
                except NoSuchElementException:
                    logger.warning("Could not find location input")
            
            # Apply remote filter if specified
            if criteria.get('remote_only'):
                try:
                    remote_button = driver.find_element(
                        By.XPATH,
                        "//button[contains(text(), 'Remote')]"
                    )
                    remote_button.click()
                    await asyncio.sleep(2)
                except NoSuchElementException:
                    logger.warning("Could not find remote filter")
            
            await asyncio.sleep(3)
            
        except Exception as e:
            logger.error(f"Error performing search: {e}")
            raise
    
    async def _extract_jobs(self, driver, criteria: Dict) -> List[Dict]:
        """Extract job listings from current page"""
        jobs = []
        
        try:
            # Scroll to load more jobs
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            await asyncio.sleep(2)
            
            # Find job cards
            job_cards = driver.find_elements(
                By.CSS_SELECTOR,
                "div[data-entity-urn*='job']"
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
            # Click to get full details
            card.click()
            await asyncio.sleep(1)
            
            # Extract title
            title_element = driver.find_element(
                By.CSS_SELECTOR,
                "h2.job-details-jobs-unified-top-card__job-title"
            )
            title = title_element.text.strip()
            
            # Extract company
            try:
                company_element = driver.find_element(
                    By.CSS_SELECTOR,
                    "a.job-details-jobs-unified-top-card__company-name"
                )
                company = company_element.text.strip()
            except NoSuchElementException:
                company = "Unknown"
            
            # Extract location
            try:
                location_element = driver.find_element(
                    By.CSS_SELECTOR,
                    "span.job-details-jobs-unified-top-card__bullet"
                )
                location = location_element.text.strip()
            except NoSuchElementException:
                location = "Not specified"
            
            # Extract URL
            try:
                url_element = driver.find_element(
                    By.CSS_SELECTOR,
                    "a[data-tracking-control-name='job_details_top_card_inline_list']"
                )
                url = url_element.get_attribute('href')
            except NoSuchElementException:
                url = driver.current_url
            
            # Extract description
            try:
                description_element = driver.find_element(
                    By.CSS_SELECTOR,
                    "div.job-details-jobs-unified-top-card__job-description"
                )
                description = description_element.text.strip()
            except NoSuchElementException:
                description = ""
            
            # Generate external ID from URL
            external_id = url.split('/')[-1] if url else f"linkedin_{hash(title + company)}"
            
            return {
                'platform': 'linkedin',
                'external_id': external_id,
                'title': title,
                'company': company,
                'location': location,
                'url': url,
                'description': description,
                'posted_date': None,  # LinkedIn doesn't always show this
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

