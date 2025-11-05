import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import SearchCriteria, Job, CrawlLog, User, Company
from app.crawler.greenhouse_crawler import GreenhouseCrawler
from app.crawler.lever_crawler import LeverCrawler
from app.crawler.generic_crawler import GenericCrawler
from app.crawler.indeed_crawler import IndeedCrawler
from app.crawler.linkedin_crawler import LinkedInCrawler
from app.crawler.fallback_manager import CrawlFallbackManager
from app.config import Settings, settings
from app.ai.analyzer import JobAnalyzer
from app.ai.job_filter import JobFilter
from app.notifications.notifier import NotificationService
from app.crawler.policies import PolicyRegistry
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class CrawlerOrchestrator:
    """Orchestrates crawling across company career pages"""
    
    def __init__(self, bot_agent=None):
        self.analyzer = JobAnalyzer()
        self.job_filter = JobFilter()  # AI-powered job filter
        self.notifier = NotificationService(bot_agent=bot_agent)
        # Initialize fallback manager with primary crawler method
        self.fallback_manager = CrawlFallbackManager(self._crawl_company_primary)
        # Ensure only one crawl runs at a time
        self._crawl_lock: asyncio.Lock = asyncio.Lock()
        # Cooperative cancellation flag checked between companies
        self._cancel_requested: bool = False
        # Progress tracking
        self._current_run_type: Optional[str] = None  # 'all_companies' or 'search'
        self._current_company_index: int = 0
        self._total_companies: int = 0
        self._current_company_name: Optional[str] = None
        self._start_time: Optional[datetime] = None
        self._crawl_durations: List[float] = []  # Track durations for ETA calculation
        # Per-domain rate limiting and circuit breaker
        self._policies = PolicyRegistry(
            rate_per_host=getattr(settings, 'HTTP_RATE_PER_HOST', 1.0),
            burst=getattr(settings, 'HTTP_BURST_PER_HOST', 2),
            failure_threshold=5,
            reset_timeout_seconds=300,
        )
    
    async def crawl_all_companies(self) -> List[Dict]:
        """
        Crawl ALL active companies and save jobs immediately.
        AI analysis is done in batch processing after jobs are saved for speed.

        Returns:
            List of newly discovered jobs
        """
        # Prevent overlapping runs
        if self._crawl_lock.locked():
            logger.warning("Crawl already in progress, skipping new crawl request")
            return []

        async with self._crawl_lock:
            all_results: List[Dict] = []
            all_new_job_ids: List[int] = []  # Collect IDs for batch AI processing
            self._cancel_requested = False
            self._start_time = datetime.utcnow()
            self._current_run_type = 'all_companies'
            self._current_company_index = 0
            self._current_company_name = None

            # Fetch companies list with a temporary session
            async with AsyncSessionLocal() as temp_db:
                result = await temp_db.execute(
                    select(Company).where(Company.is_active == True)
                )
                companies_orm = result.scalars().all()
                self._total_companies = len(companies_orm)
                # Expunge objects from session so they can be used after session closes
                for company in companies_orm:
                    temp_db.expunge(company)
                companies = companies_orm
            # Session closed - companies are now detached but still usable

            logger.info(
                f"Crawling all {len(companies)} active companies (parallel, each with own DB session)"
            )

            max_concurrent = getattr(settings, 'MAX_CONCURRENT_COMPANY_CRAWLS', 5)
            semaphore = asyncio.Semaphore(max_concurrent)

            async def crawl_single(index: int, company: Company):
                logger.info(f"crawl_single called for {company.name}")
                async with semaphore:
                    # Each task gets its own database session - fixes race condition
                    async with AsyncSessionLocal() as db:
                        self._current_company_index = index + 1
                        self._current_company_name = company.name
                        company_start = datetime.utcnow()
                        if self._cancel_requested:
                            logger.info("Crawl cancellation requested - skipping remaining companies")
                            return

                        log = CrawlLog(
                            search_criteria_id=None,
                            company_id=company.id,
                            platform=f"company_{company.id}",
                            started_at=datetime.utcnow(),
                            status='running'
                        )
                        db.add(log)
                        await db.commit()

                        try:
                            timeout_seconds = settings.CRAWL_TIMEOUT_SECONDS
                            try:
                                # Determine domain key for policy
                                domain_key = ''
                                if company.career_page_url:
                                    try:
                                        domain_key = urlparse(company.career_page_url).netloc.lower()
                                    except Exception:
                                        domain_key = ''
                                policy = self._policies.get_policy(domain_key or str(company.id))
                                async def _op():
                                    return await self.fallback_manager.crawl_with_fallback(company)
                                jobs, method_used = await asyncio.wait_for(
                                    policy.retry_policy.retry(_op),
                                    timeout=timeout_seconds
                                )
                                logger.info(f"Found {len(jobs)} jobs from {company.name} (method: {method_used})")
                            except asyncio.TimeoutError:
                                logger.error(f"Timeout crawling {company.name} after {timeout_seconds} seconds")
                                log.status = 'failed'
                                log.completed_at = datetime.utcnow()
                                log.error_message = f"Timeout after {timeout_seconds} seconds"
                                company.last_crawled_at = datetime.utcnow()
                                company.consecutive_empty_crawls += 1
                                await db.commit()
                                return

                            # Incremental filtering using last_seen_ids from crawler_config
                            cfg = company.crawler_config or {}
                            last_seen: List[str] = cfg.get('last_seen_ids', []) if isinstance(cfg, dict) else []
                            if last_seen:
                                jobs = [j for j in jobs if j.get('external_id') not in last_seen]

                            new_jobs = await self._process_company_jobs(
                                db,
                                search=None,
                                company=company,
                                jobs=jobs,
                                skip_ai_analysis=True
                            )

                            all_new_job_ids.extend(job.id for job in new_jobs)

                            log.completed_at = datetime.utcnow()
                            log.status = 'completed'
                            log.jobs_found = len(jobs)
                            log.new_jobs = len(new_jobs)

                            company.last_crawled_at = datetime.utcnow()
                            if len(new_jobs) > 0:
                                company.consecutive_empty_crawls = 0
                                company.last_successful_crawl = datetime.utcnow()
                                company.jobs_found_total += len(new_jobs)
                                # Update last_seen_ids (cap at 500)
                                try:
                                    cfg = company.crawler_config or {}
                                    if not isinstance(cfg, dict):
                                        cfg = {}
                                    new_ids = [j.external_id for j in new_jobs if getattr(j, 'external_id', None)]
                                    prev = cfg.get('last_seen_ids', [])
                                    merged = (new_ids + prev)[:500]
                                    cfg['last_seen_ids'] = merged
                                    company.crawler_config = cfg
                                except Exception:
                                    pass
                            else:
                                company.consecutive_empty_crawls += 1

                            if method_used != "career_page" and method_used != "no_results":
                                await self._record_fallback_success(db, company, method_used)

                            company_duration = (datetime.utcnow() - company_start).total_seconds()
                            self._crawl_durations.append(company_duration)
                            if len(self._crawl_durations) > 10:
                                self._crawl_durations = self._crawl_durations[-10:]

                            all_results.extend([
                                {
                                    'id': job.id,
                                    'title': job.title,
                                    'company': job.company,
                                    'url': job.url,
                                    'ai_match_score': None,
                                }
                                for job in new_jobs
                            ])

                            logger.info(
                                f"✓ {company.name}: Found {len(jobs)} jobs, saved {len(new_jobs)} new jobs (AI analysis pending)"
                            )
                        except Exception as e:
                            logger.error(f"Error crawling company {company.name}: {e}", exc_info=True)
                            log.status = 'failed'
                            log.completed_at = datetime.utcnow()
                            log.error_message = str(e)
                            company_duration = (datetime.utcnow() - company_start).total_seconds()
                            self._crawl_durations.append(company_duration)
                            if len(self._crawl_durations) > 10:
                                self._crawl_durations = self._crawl_durations[-10:]
                            company.last_crawled_at = datetime.utcnow()
                            company.consecutive_empty_crawls += 1
                        finally:
                            await db.commit()

            tasks = [crawl_single(idx, company) for idx, company in enumerate(companies)]
            await asyncio.gather(*tasks)

            if all_new_job_ids and not self._cancel_requested:
                logger.info(f"Starting batch AI analysis on {len(all_new_job_ids)} new jobs...")
                batch_size = getattr(settings, 'AI_BATCH_SIZE', 20)
                asyncio.create_task(self._batch_analyze_jobs(all_new_job_ids, batch_size=batch_size))

            # Reset progress tracking
            self._current_run_type = None
            self._current_company_index = 0
            self._total_companies = 0
            self._current_company_name = None
            self._start_time = None

            logger.info(f"Crawl complete: {len(all_results)} new jobs saved (AI analysis running in background)")

            return all_results


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
        """Run a single search across configured companies"""
        results = []

        # If no target_companies specified, use all active companies
        if not search.target_companies:
            logger.info(f"Search {search.id} has no target companies - using all active companies")
            # Get all active companies
            result = await db.execute(
                select(Company).where(Company.is_active == True)
            )
            all_companies = result.scalars().all()
            search.target_companies = [c.id for c in all_companies]
            logger.info(f"Using {len(search.target_companies)} active companies for search")

        # Run company-based search
        logger.info(f"Running company-based search for {len(search.target_companies)} companies")
        results = await self._run_company_search(db, search)

        return results

    def get_policy_metrics(self) -> Dict:
        return self._policies.metrics()

    async def _process_jobs(self, db: AsyncSession, search: SearchCriteria, jobs: List[Dict], skip_ai_analysis: bool = False) -> List[Job]:
        """
        Process and save jobs with AI analysis
        
        Args:
            db: Database session
            search: Search criteria
            jobs: List of job data dictionaries (may already contain AI analysis data)
            skip_ai_analysis: If True, skip AI analysis (AI data should already be in job_data)
        """
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
                
                # AI analysis - use existing data if available, otherwise run analysis
                if skip_ai_analysis and 'ai_match_score' in job_data:
                    # AI analysis already done during filtering
                    job.ai_summary = job_data.get('ai_summary')
                    job.ai_match_score = job_data.get('ai_match_score')
                    job.ai_pros = job_data.get('ai_pros')
                    job.ai_cons = job_data.get('ai_cons')
                    job.ai_keywords_matched = job_data.get('ai_keywords_matched')
                    job.ai_recommended = job_data.get('ai_recommended', False)
                else:
                    # Legacy: use analyzer for search-based crawls
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
        
        # Generate tasks for new jobs (if auto-generation is enabled)
        if new_jobs:
            try:
                from app.ai.task_generator import TaskGenerator
                from app.config import settings
                
                if settings.AUTO_GENERATE_TASKS:
                    for job in new_jobs:
                        try:
                            # Refresh job to ensure we have all fields
                            await db.refresh(job)
                            tasks = await TaskGenerator.generate_tasks_for_job(db, job)
                            if tasks:
                                logger.debug(f"Generated {len(tasks)} tasks for job {job.id}")
                        except Exception as e:
                            logger.error(f"Error generating tasks for job {job.id}: {e}")
            except Exception as e:
                logger.error(f"Error in task generation: {e}")
        
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
        
        # Track progress for search crawls
        self._current_run_type = 'search'
        self._current_company_index = 0
        self._total_companies = len(companies)
        self._start_time = datetime.utcnow()

        logger.info(f"Crawling {len(companies)} companies for search '{search.name}'")

        # Get user profile once for all filtering
        user_profile = await self.job_filter._get_user_profile_cached()

        for idx, company in enumerate(companies):
            self._current_company_index = idx + 1
            self._current_company_name = company.name
            company_start = datetime.utcnow()
            if self._cancel_requested:
                logger.info("Crawl cancellation requested - stopping search crawl")
                break
            log = CrawlLog(
                search_criteria_id=search.id,
                company_id=company.id,
                platform=f"company_{company.id}",
                started_at=datetime.utcnow(),
                status='running'
            )
            db.add(log)
            await db.commit()

            try:
                # Crawl company with fallback strategies and timeout
                timeout_seconds = settings.CRAWL_TIMEOUT_SECONDS
                try:
                    jobs, method_used = await asyncio.wait_for(
                        self.fallback_manager.crawl_with_fallback(company),
                        timeout=timeout_seconds
                    )
                    logger.info(f"Found {len(jobs)} jobs from {company.name} (method: {method_used})")
                except asyncio.TimeoutError:
                    logger.error(f"Timeout crawling {company.name} after {timeout_seconds} seconds")
                    log.status = 'failed'
                    log.completed_at = datetime.utcnow()
                    log.error_message = f"Timeout after {timeout_seconds} seconds"
                    # Update company stats for timeout
                    company.last_crawled_at = datetime.utcnow()
                    company.consecutive_empty_crawls += 1
                    await db.commit()
                    continue

                # Filter jobs by search criteria (basic keyword/location filtering)
                filtered_jobs = self._filter_jobs_by_criteria(jobs, search)
                logger.info(f"After search criteria filtering: {len(filtered_jobs)} jobs from {company.name}")
                
                # Apply AI filtering to all jobs
                if filtered_jobs:
                    logger.info(f"Applying AI filter to {len(filtered_jobs)} jobs from {company.name}")
                    ai_filtered_jobs = await self.job_filter.filter_jobs_batch(filtered_jobs, user_profile)
                else:
                    ai_filtered_jobs = []

                # Process and save jobs (AI analysis already included)
                new_jobs = await self._process_company_jobs(db, search, company, ai_filtered_jobs, skip_ai_analysis=True)

                log.completed_at = datetime.utcnow()
                log.status = 'completed'
                log.jobs_found = len(jobs)
                log.new_jobs = len(new_jobs)

                # Update company stats
                company.last_crawled_at = datetime.utcnow()
                if len(new_jobs) > 0:
                    # Successful crawl - reset consecutive empty crawls
                    company.consecutive_empty_crawls = 0
                    company.last_successful_crawl = datetime.utcnow()
                    company.jobs_found_total += len(new_jobs)
                else:
                    # Empty crawl - increment counter
                    company.consecutive_empty_crawls += 1
                
                # Track successful fallback method
                if method_used != "career_page" and method_used != "no_results":
                    await self._record_fallback_success(db, company, method_used)

                results.extend([{
                    'id': job.id,
                    'title': job.title,
                    'company': job.company,
                    'url': job.url,
                    'ai_match_score': job.ai_match_score
                } for job in new_jobs])

                logger.info(f"✓ {company.name}: Found {len(jobs)} jobs, {len(filtered_jobs)} passed search criteria, {len(ai_filtered_jobs)} passed AI filter, {len(new_jobs)} new")
                
                # Track duration for ETA calculation
                company_duration = (datetime.utcnow() - company_start).total_seconds()
                self._crawl_durations.append(company_duration)
                if len(self._crawl_durations) > 10:
                    self._crawl_durations = self._crawl_durations[-10:]

            except Exception as e:
                logger.error(f"Error crawling company {company.name}: {e}", exc_info=True)
                log.status = 'failed'
                log.error_message = str(e)
                # Track failed duration
                company_duration = (datetime.utcnow() - company_start).total_seconds()
                self._crawl_durations.append(company_duration)
                if len(self._crawl_durations) > 10:
                    self._crawl_durations = self._crawl_durations[-10:]

            await db.commit()

        # Reset progress tracking
        self._current_run_type = None
        self._current_company_index = 0
        self._total_companies = 0
        self._current_company_name = None
        self._start_time = None

        return results

    async def _crawl_company_primary(self, company: Company) -> List[Dict]:
        """Primary crawler method - crawls a specific company's career page"""
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

            elif crawler_type == 'indeed':
                query = config.get('query') or company.name
                if not query:
                    logger.warning(f"Indeed crawler for {company.name} missing query configuration")
                    return []

                crawler = IndeedCrawler(
                    query=query,
                    location=config.get('location'),
                    max_pages=config.get('max_pages', 2),
                    results_per_page=config.get('results_per_page', 20),
                    freshness_days=config.get('freshness_days'),
                    remote_only=config.get('remote_only', False),
                    company_name=company.name,
                )
                jobs = await crawler.fetch_jobs()
                crawler.close()
                return jobs

            elif crawler_type == 'linkedin':
                query = config.get('query') or company.name
                if not query:
                    logger.warning(f"LinkedIn crawler for {company.name} missing query configuration")
                    return []

                crawler = LinkedInCrawler(
                    query=query,
                    location=config.get('location'),
                    max_pages=config.get('max_pages', 2),
                    remote_only=config.get('remote_only', False),
                    filters=config.get('filters'),
                    company_name=company.name,
                )
                jobs = await crawler.fetch_jobs()
                crawler.close()
                return jobs

            elif crawler_type in {'generic', 'workday'}:
                if crawler_type == 'workday':
                    logger.info(
                        f"{company.name} uses a Workday-powered site – falling back to generic AI parsing"
                    )
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
    
    async def _crawl_company(self, company: Company) -> Tuple[List[Dict], str]:
        """Crawl company using fallback manager"""
        return await self.fallback_manager.crawl_with_fallback(company)
    
    async def _record_fallback_success(
        self,
        db: AsyncSession,
        company: Company,
        method_used: str
    ):
        """Record successful fallback method for future optimization"""
        from app.models import CrawlFallback
        
        try:
            # Check if fallback record exists for this company and method
            from sqlalchemy import select, and_
            result = await db.execute(
                select(CrawlFallback).where(
                    and_(
                        CrawlFallback.company_id == company.id,
                        CrawlFallback.method_used == method_used
                    )
                )
            )
            fallback_record = result.scalar_one_or_none()
            
            if fallback_record:
                # Update existing record
                fallback_record.success_count += 1
                fallback_record.last_success_at = datetime.utcnow()
                fallback_record.updated_at = datetime.utcnow()
            else:
                # Create new record
                fallback_record = CrawlFallback(
                    company_id=company.id,
                    method_used=method_used,
                    success_count=1,
                    last_success_at=datetime.utcnow()
                )
                db.add(fallback_record)
            
            await db.flush()
        except Exception as e:
            logger.error(f"Error recording fallback success: {e}", exc_info=True)
            # Don't fail the crawl if fallback tracking fails

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

    async def _process_company_jobs(self, db: AsyncSession, search: Optional[SearchCriteria],
                                    company: Company, jobs: List[Dict], skip_ai_analysis: bool = False) -> List[Job]:
        """
        Process and save jobs from company crawl
        
        Args:
            db: Database session
            search: Search criteria (optional - None for universal crawl)
            company: Company being crawled
            jobs: List of job data dictionaries (may already contain AI analysis data)
            skip_ai_analysis: If True, skip AI analysis (AI data should already be in job_data)
        """
        new_jobs = []

        for job_data in jobs:
            try:
                # Validate required fields
                if not job_data.get('external_id'):
                    logger.warning(f"Job missing external_id, skipping: {job_data.get('title', 'Unknown')}")
                    continue
                
                if not job_data.get('title'):
                    logger.warning(f"Job missing title, skipping: {job_data.get('external_id', 'Unknown')}")
                    continue
                
                # Check if job already exists (by external_id and company_id to handle duplicates across companies)
                result = await db.execute(
                    select(Job).where(
                        Job.external_id == job_data['external_id'],
                        Job.company_id == company.id
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    logger.debug(f"Job already exists: {job_data['external_id']} for {company.name}")
                    continue

                # Create new job
                job = Job(
                    search_criteria_id=search.id if search else None,  # Optional for universal crawl
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

                # AI analysis - use existing data if available, otherwise run analysis
                if skip_ai_analysis:
                    # Skip AI analysis - will be done in batch later
                    # Only use AI data if it's already in job_data (from previous filtering)
                    if 'ai_match_score' in job_data:
                        job.ai_summary = job_data.get('ai_summary')
                        job.ai_match_score = job_data.get('ai_match_score')
                        job.ai_pros = job_data.get('ai_pros')
                        job.ai_cons = job_data.get('ai_cons')
                        job.ai_keywords_matched = job_data.get('ai_keywords_matched')
                        job.ai_recommended = job_data.get('ai_recommended', False)
                    # Otherwise, leave AI fields as None - they'll be populated in batch processing
                elif search:
                    # Legacy: use analyzer for search-based crawls
                    try:
                        analysis = await self.analyzer.analyze_job(job_data, search)
                        job.ai_summary = analysis.get('summary')
                        job.ai_match_score = analysis.get('match_score')
                        job.ai_pros = analysis.get('pros')
                        job.ai_cons = analysis.get('cons')
                        job.ai_keywords_matched = analysis.get('keywords_matched')
                    except Exception as e:
                        logger.error(f"Error analyzing job: {e}")
                else:
                    # No search criteria - apply AI filtering
                    try:
                        filter_result = await self.job_filter.filter_job(job_data)
                        job.ai_summary = filter_result.get('summary')
                        job.ai_match_score = filter_result.get('match_score')
                        job.ai_pros = filter_result.get('pros')
                        job.ai_cons = filter_result.get('cons')
                        job.ai_keywords_matched = filter_result.get('keywords_matched')
                        job.ai_recommended = filter_result.get('recommended', False)
                    except Exception as e:
                        logger.error(f"Error applying AI filter to job: {e}")

                db.add(job)
                new_jobs.append(job)
                logger.debug(f"Added job to save queue: {job.title} (external_id: {job.external_id})")

            except Exception as e:
                logger.error(f"Error processing job {job_data.get('title', 'Unknown')} ({job_data.get('external_id', 'Unknown')}): {e}", exc_info=True)

        if new_jobs:
            await db.commit()
            logger.info(f"Saved {len(new_jobs)} new jobs from {company.name}")
        else:
            logger.info(f"No new jobs to save for {company.name} (all {len(jobs)} jobs already exist or invalid)")

        # Generate tasks for new jobs (if auto-generation is enabled)
        if new_jobs:
            try:
                from app.ai.task_generator import TaskGenerator
                from app.config import settings
                
                if settings.AUTO_GENERATE_TASKS:
                    for job in new_jobs:
                        try:
                            # Refresh job to ensure we have all fields
                            await db.refresh(job)
                            tasks = await TaskGenerator.generate_tasks_for_job(db, job)
                            if tasks:
                                logger.debug(f"Generated {len(tasks)} tasks for job {job.id}")
                        except Exception as e:
                            logger.error(f"Error generating tasks for job {job.id}: {e}")
            except Exception as e:
                logger.error(f"Error in task generation: {e}")

        # Send notifications (only if search criteria exists and notifications enabled)
        if new_jobs and search and search.notify_on_new:
            try:
                await self.notifier.send_job_alert(new_jobs)
            except Exception as e:
                logger.error(f"Error sending notifications: {e}")

        return new_jobs
    
    async def _batch_analyze_jobs(self, job_ids: List[int], batch_size: int = 10):
        """
        Batch analyze jobs with AI for speed.
        Processes jobs in batches to avoid overwhelming the AI service.
        
        Args:
            job_ids: List of job IDs to analyze
            batch_size: Number of jobs to process in parallel per batch
        """
        if not job_ids:
            return
        
        logger.info(f"Starting batch AI analysis: {len(job_ids)} jobs in batches of {batch_size}")
        
        async with AsyncSessionLocal() as db:
            # Get user profile once for all jobs
            user_profile = await self.job_filter._get_user_profile_cached()
            
            # Process jobs in batches
            for i in range(0, len(job_ids), batch_size):
                batch = job_ids[i:i + batch_size]
                
                try:
                    # Get jobs from database
                    result = await db.execute(
                        select(Job).where(Job.id.in_(batch))
                    )
                    jobs = result.scalars().all()
                    
                    # Convert to dict format for AI analysis
                    job_dicts = []
                    for job in jobs:
                        job_dict = {
                            'id': job.id,
                            'title': job.title,
                            'company': job.company,
                            'location': job.location,
                            'job_type': job.job_type,
                            'description': job.description or '',
                            'url': job.url
                        }
                        job_dicts.append(job_dict)
                    
                    # Process batch in parallel
                    tasks = []
                    for job_dict in job_dicts:
                        task = self._analyze_single_job(job_dict, user_profile, db)
                        tasks.append(task)
                    
                    # Wait for batch to complete
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Commit batch
                    await db.commit()
                    
                    logger.info(f"Batch AI analysis progress: {min(i + batch_size, len(job_ids))}/{len(job_ids)} jobs")
                    
                except Exception as e:
                    logger.error(f"Error in batch AI analysis: {e}", exc_info=True)
                    await db.rollback()
        
        logger.info(f"Batch AI analysis complete: {len(job_ids)} jobs analyzed")
    
    async def _analyze_single_job(self, job_dict: Dict, user_profile: Optional[Dict], db: AsyncSession):
        """Analyze a single job and update it in the database"""
        try:
            # Use job filter to analyze
            analysis_result = await self.job_filter.filter_job(job_dict)
            
            # Update job in database
            result = await db.execute(
                select(Job).where(Job.id == job_dict['id'])
            )
            job = result.scalar_one_or_none()
            
            if job:
                job.ai_match_score = analysis_result.get('match_score', 50)
                job.ai_recommended = analysis_result.get('recommended', False)
                job.ai_summary = analysis_result.get('summary', '')
                job.ai_pros = analysis_result.get('pros', [])
                job.ai_cons = analysis_result.get('cons', [])
                job.ai_keywords_matched = analysis_result.get('keywords_matched', [])
                
        except Exception as e:
            logger.error(f"Error analyzing job {job_dict.get('id')}: {e}", exc_info=True)
    
    def get_crawler_type_classification(self, crawler_type: str) -> str:
        """Classify crawler type as Selenium-based, API-based, or AI-assisted"""
        selenium_based = {'indeed', 'linkedin'}
        api_based = {'greenhouse', 'lever'}
        ai_assisted = {'generic', 'workday'}
        
        if crawler_type in selenium_based:
            return 'selenium'
        elif crawler_type in api_based:
            return 'api'
        elif crawler_type in ai_assisted:
            return 'ai'
        else:
            return 'unknown'
    
    def get_current_progress(self) -> Dict:
        """Get current crawl progress information"""
        if not self._current_run_type or self._total_companies == 0:
            return {
                'is_running': False,
                'queue_length': 0,
                'current_company': None,
                'progress': {'current': 0, 'total': 0},
                'eta_seconds': None
            }
        
        # Calculate ETA based on average duration
        avg_duration = sum(self._crawl_durations) / len(self._crawl_durations) if self._crawl_durations else 30
        remaining_companies = self._total_companies - self._current_company_index
        eta_seconds = int(avg_duration * remaining_companies)
        
        return {
            'is_running': True,
            'run_type': self._current_run_type,
            'queue_length': remaining_companies,
            'current_company': self._current_company_name,
            'progress': {
                'current': self._current_company_index,
                'total': self._total_companies
            },
            'eta_seconds': eta_seconds,
            'start_time': self._start_time.isoformat() if self._start_time else None
        }
    
    async def cleanup_stuck_logs(self) -> Dict:
        """
        Clean up crawl logs that have been stuck in 'running' status for too long.
        Marks them as 'failed' with a timeout error message.
        
        Returns:
            Dict with cleanup statistics
        """
        threshold_minutes = settings.STUCK_LOG_CLEANUP_THRESHOLD_MINUTES
        threshold = datetime.utcnow() - timedelta(minutes=threshold_minutes)
        
        async with AsyncSessionLocal() as db:
            # Find all logs that are still 'running' and started before the threshold
            result = await db.execute(
                select(CrawlLog).where(
                    CrawlLog.status == 'running',
                    CrawlLog.started_at < threshold
                )
            )
            stuck_logs = result.scalars().all()
            
            if not stuck_logs:
                return {
                    'cleaned': 0,
                    'threshold_minutes': threshold_minutes,
                    'message': 'No stuck logs found'
                }
            
            # Mark each stuck log as failed
            for log in stuck_logs:
                duration_minutes = (datetime.utcnow() - log.started_at).total_seconds() / 60
                log.status = 'failed'
                log.completed_at = datetime.utcnow()
                log.error_message = (
                    f"Automatically marked as failed - stuck in 'running' status for "
                    f"{duration_minutes:.1f} minutes (threshold: {threshold_minutes} minutes)"
                )
                logger.warning(
                    f"Cleaned up stuck log {log.id} for company {log.company_id} "
                    f"(stuck for {duration_minutes:.1f} minutes)"
                )
            
            await db.commit()
            
            return {
                'cleaned': len(stuck_logs),
                'threshold_minutes': threshold_minutes,
                'message': f"Cleaned up {len(stuck_logs)} stuck crawl log(s)"
            }
