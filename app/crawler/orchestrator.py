import asyncio
import logging
from typing import List, Dict
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import SearchCriteria, Job, CrawlLog, User, Company
from app.crawler.linkedin_crawler import LinkedInCrawler
from app.crawler.indeed_crawler import IndeedCrawler
from app.crawler.greenhouse_crawler import GreenhouseCrawler
from app.crawler.lever_crawler import LeverCrawler
from app.crawler.generic_crawler import GenericCrawler
from app.config import Settings
from app.ai.analyzer import JobAnalyzer
from app.notifications.notifier import NotificationService
from app.utils.crypto import decrypt_password

logger = logging.getLogger(__name__)


class CrawlerOrchestrator:
    """Orchestrates crawling across multiple platforms"""
    
    def __init__(self):
        self.analyzer = JobAnalyzer()
        self.notifier = NotificationService()
    
    async def run_all_searches(self) -> List[Dict]:
        """Run all active searches"""
        all_results = []
        
        async with AsyncSessionLocal() as db:
            # Get all active search criteria
            result = await db.execute(
                select(SearchCriteria).where(SearchCriteria.is_active == True)
            )
            searches = result.scalars().all()
            
            logger.info(f"Found {len(searches)} active searches")
            
            for search in searches:
                try:
                    results = await self.run_search(db, search)
                    all_results.extend(results)
                except Exception as e:
                    logger.error(f"Error running search {search.id}: {e}", exc_info=True)
        
        return all_results
    
    async def run_search(self, db: AsyncSession, search: SearchCriteria) -> List[Dict]:
        """Run a single search across configured platforms or companies"""
        results = []

        # Check if this is a company-based search or platform-based search
        if search.target_companies:
            # New: Company-based crawling
            logger.info(f"Running company-based search for {len(search.target_companies)} companies")
            results = await self._run_company_search(db, search)
        else:
            # Legacy: Platform-based crawling (LinkedIn/Indeed)
            logger.info("Running legacy platform-based search")
            results = await self._run_platform_search(db, search)

        return results

    async def _run_platform_search(self, db: AsyncSession, search: SearchCriteria) -> List[Dict]:
        """Run legacy platform-based search (LinkedIn/Indeed)"""
        results = []

        # Get user credentials
        user_result = await db.execute(select(User).where(User.id == search.user_id))
        user_creds = {row.platform: row for row in user_result.scalars().all()}

        platforms = search.platforms or ['linkedin', 'indeed']

        for platform in platforms:
            log = CrawlLog(
                search_criteria_id=search.id,
                platform=platform,
                started_at=datetime.utcnow(),
                status='running'
            )
            db.add(log)
            await db.commit()
            
            try:
                jobs = await self._crawl_platform(platform, search, user_creds)
                
                # Process and save jobs
                new_jobs = await self._process_jobs(db, search, jobs)
                
                log.completed_at = datetime.utcnow()
                log.status = 'completed'
                log.jobs_found = len(jobs)
                log.new_jobs = len(new_jobs)
                
                results.extend(new_jobs)
                
            except Exception as e:
                logger.error(f"Error crawling {platform}: {e}", exc_info=True)
                log.status = 'failed'
                log.error_message = str(e)
            
            await db.commit()
        
        return results
    
    async def _crawl_platform(self, platform: str, search: SearchCriteria, user_creds: Dict) -> List[Dict]:
        """Crawl a specific platform"""
        criteria = {
            'keywords': search.keywords,
            'location': search.location,
            'remote_only': search.remote_only,
            'job_type': search.job_type,
            'experience_level': search.experience_level,
        }
        
        if platform == 'linkedin':
            cred = user_creds.get('linkedin')
            if not cred:
                logger.warning("No LinkedIn credentials found")
                return []
            
            crawler = LinkedInCrawler(
                email=cred.email,
                password=decrypt_password(cred.encrypted_password)
            )
            try:
                return await crawler.search_jobs(criteria)
            finally:
                crawler.close()
        
        elif platform == 'indeed':
            cred = user_creds.get('indeed')
            email = cred.email if cred else None
            password = decrypt_password(cred.encrypted_password) if cred else None
            
            crawler = IndeedCrawler(email=email, password=password)
            try:
                return await crawler.search_jobs(criteria)
            finally:
                crawler.close()
        
        else:
            logger.warning(f"Unknown platform: {platform}")
            return []
    
    async def _process_jobs(self, db: AsyncSession, search: SearchCriteria, jobs: List[Dict]) -> List[Job]:
        """Process and save jobs with AI analysis"""
        new_jobs = []
        
        for job_data in jobs:
            try:
                # Check if job already exists
                result = await db.execute(
                    select(Job).where(Job.external_id == job_data['external_id'])
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    logger.debug(f"Job already exists: {job_data['external_id']}")
                    continue
                
                # Create new job
                job = Job(
                    search_criteria_id=search.id,
                    platform=job_data['platform'],
                    external_id=job_data['external_id'],
                    title=job_data['title'],
                    company=job_data['company'],
                    location=job_data.get('location'),
                    url=job_data['url'],
                    description=job_data.get('description'),
                    posted_date=job_data.get('posted_date'),
                    is_new=True,
                    status='new'
                )
                
                # AI analysis
                try:
                    analysis = await self.analyzer.analyze_job(job_data, search)
                    job.ai_summary = analysis.get('summary')
                    job.ai_match_score = analysis.get('match_score')
                    job.ai_pros = analysis.get('pros')
                    job.ai_cons = analysis.get('cons')
                    job.ai_keywords_matched = analysis.get('keywords_matched')
                except Exception as e:
                    logger.error(f"Error analyzing job: {e}")
                
                db.add(job)
                new_jobs.append(job)
                
            except Exception as e:
                logger.error(f"Error processing job: {e}", exc_info=True)
        
        await db.commit()
        logger.info(f"Saved {len(new_jobs)} new jobs")
        
        # Send notifications if there are new jobs and search has notifications enabled
        if new_jobs and search.notify_on_new:
            try:
                await self.notifier.send_job_alert(new_jobs)
            except Exception as e:
                logger.error(f"Error sending notifications: {e}")

        return new_jobs

    async def _run_company_search(self, db: AsyncSession, search: SearchCriteria) -> List[Dict]:
        """Run search across specified companies"""
        results = []

        # Get companies to crawl
        company_ids = search.target_companies or []
        if not company_ids:
            logger.warning("No target companies specified")
            return results

        result = await db.execute(
            select(Company).where(Company.id.in_(company_ids), Company.is_active == True)
        )
        companies = result.scalars().all()

        logger.info(f"Crawling {len(companies)} companies")

        for company in companies:
            log = CrawlLog(
                search_criteria_id=search.id,
                platform=f"company_{company.id}",
                started_at=datetime.utcnow(),
                status='running'
            )
            db.add(log)
            await db.commit()

            try:
                # Crawl company career page
                jobs = await self._crawl_company(company)

                # Filter jobs by search criteria
                filtered_jobs = self._filter_jobs_by_criteria(jobs, search)

                # Process and save jobs
                new_jobs = await self._process_company_jobs(db, search, company, filtered_jobs)

                log.completed_at = datetime.utcnow()
                log.status = 'completed'
                log.jobs_found = len(jobs)
                log.new_jobs = len(new_jobs)

                # Update company stats
                company.last_crawled_at = datetime.utcnow()
                company.jobs_found_total += len(new_jobs)

                results.extend(new_jobs)

            except Exception as e:
                logger.error(f"Error crawling company {company.name}: {e}", exc_info=True)
                log.status = 'failed'
                log.error_message = str(e)

            await db.commit()

        return results

    async def _crawl_company(self, company: Company) -> List[Dict]:
        """Crawl a specific company's career page"""
        crawler_type = company.crawler_type
        config = company.crawler_config or {}

        try:
            if crawler_type == 'greenhouse':
                slug = config.get('slug', company.name.lower())
                crawler = GreenhouseCrawler(slug, company.name)
                jobs = await crawler.fetch_jobs()
                crawler.close()
                return jobs

            elif crawler_type == 'lever':
                slug = config.get('slug', company.name.lower())
                crawler = LeverCrawler(slug, company.name)
                jobs = await crawler.fetch_jobs()
                crawler.close()
                return jobs

            elif crawler_type == 'generic':
                settings = Settings()
                crawler = GenericCrawler(
                    company.name,
                    company.career_page_url,
                    ollama_host=settings.OLLAMA_HOST,
                    ollama_model=settings.OLLAMA_MODEL
                )
                jobs = await crawler.fetch_jobs()
                crawler.close()
                return jobs

            else:
                logger.warning(f"Unknown crawler type: {crawler_type}")
                return []

        except Exception as e:
            logger.error(f"Error in company crawler: {e}", exc_info=True)
            raise

    def _filter_jobs_by_criteria(self, jobs: List[Dict], search: SearchCriteria) -> List[Dict]:
        """Filter jobs based on search criteria"""
        filtered = []

        keywords = search.keywords.lower().split() if search.keywords else []

        for job in jobs:
            # Check keywords
            if keywords:
                title_lower = job.get('title', '').lower()
                description_lower = job.get('description', '').lower()
                combined = f"{title_lower} {description_lower}"

                if not any(keyword in combined for keyword in keywords):
                    continue

            # Check location (remote)
            if search.remote_only:
                location = job.get('location', '').lower()
                if not any(term in location for term in ['remote', 'anywhere', 'work from home']):
                    continue

            # Check job type
            if search.job_type:
                job_type = job.get('job_type', '').lower()
                if search.job_type.lower() not in job_type:
                    continue

            filtered.append(job)

        logger.info(f"Filtered {len(jobs)} jobs down to {len(filtered)} matches")
        return filtered

    async def _process_company_jobs(self, db: AsyncSession, search: SearchCriteria,
                                    company: Company, jobs: List[Dict]) -> List[Job]:
        """Process and save jobs from company crawl"""
        new_jobs = []

        for job_data in jobs:
            try:
                # Check if job already exists
                result = await db.execute(
                    select(Job).where(Job.external_id == job_data['external_id'])
                )
                existing = result.scalar_one_or_none()

                if existing:
                    logger.debug(f"Job already exists: {job_data['external_id']}")
                    continue

                # Create new job
                job = Job(
                    search_criteria_id=search.id,
                    company_id=company.id,
                    platform=job_data.get('platform'),
                    external_id=job_data['external_id'],
                    title=job_data['title'],
                    company=company.name,
                    location=job_data.get('location'),
                    url=job_data['url'],
                    source_url=job_data.get('source_url', job_data['url']),
                    description=job_data.get('description'),
                    posted_date=job_data.get('posted_date'),
                    job_type=job_data.get('job_type'),
                    is_new=True,
                    status='new'
                )

                # AI analysis
                try:
                    analysis = await self.analyzer.analyze_job(job_data, search)
                    job.ai_summary = analysis.get('summary')
                    job.ai_match_score = analysis.get('match_score')
                    job.ai_pros = analysis.get('pros')
                    job.ai_cons = analysis.get('cons')
                    job.ai_keywords_matched = analysis.get('keywords_matched')
                except Exception as e:
                    logger.error(f"Error analyzing job: {e}")

                db.add(job)
                new_jobs.append(job)

            except Exception as e:
                logger.error(f"Error processing job: {e}", exc_info=True)

        await db.commit()
        logger.info(f"Saved {len(new_jobs)} new jobs from {company.name}")

        # Send notifications
        if new_jobs and search.notify_on_new:
            try:
                await self.notifier.send_job_alert(new_jobs)
            except Exception as e:
                logger.error(f"Error sending notifications: {e}")

        return new_jobs
