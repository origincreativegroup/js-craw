"""Main application entry point"""
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db, close_db
from app.api import router
from app.crawler.orchestrator import CrawlerOrchestrator
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global scheduler
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Job Search Crawler...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Load companies from CSV as fallback if database is empty or has few companies
    try:
        from app.utils.company_loader import load_companies_from_csv
        result = await load_companies_from_csv(min_companies=10)
        if result.get("success") and result.get("added", 0) > 0:
            logger.info(f"Loaded {result['added']} companies from companies.csv (fallback)")
            if result.get("parsing_stats", {}).get("skipped_no_url", 0) > 0:
                logger.warning(f"  Note: {result['parsing_stats']['skipped_no_url']} companies skipped due to missing URLs")
        elif result.get("reason") == "sufficient_companies":
            logger.debug(f"Company database has sufficient companies ({result.get('current_count', 0)})")
        elif not result.get("success"):
            error_msg = result.get("error") or result.get("reason", "unknown error")
            logger.warning(f"Failed to load companies from CSV: {error_msg}")
            logger.warning("  Use POST /api/companies/load-from-csv?force=true to manually load companies")
    except Exception as e:
        logger.warning(f"Failed to load companies from CSV: {e}", exc_info=True)
        logger.warning("  Use POST /api/companies/load-from-csv?force=true to manually load companies")
    
    # Create orchestrator first (will be updated with bot agent)
    orchestrator = CrawlerOrchestrator(bot_agent=None)
    app.state.crawler = orchestrator
    app.state.scheduler = scheduler  # Expose scheduler to API endpoints
    logger.info("Crawler orchestrator initialized")
    
    # Initialize Telegram bot if configured
    telegram_bot = None
    if settings.TELEGRAM_BOT_TOKEN:
        try:
            from app.notifications.telegram_bot import TelegramBotAgent
            telegram_bot = TelegramBotAgent(orchestrator=orchestrator)
            app.state.telegram_bot = telegram_bot
            
            # Update orchestrator with bot agent for rich notifications
            orchestrator.notifier._bot_agent = telegram_bot
            
            # Start bot in polling mode if configured
            if settings.TELEGRAM_BOT_MODE == "polling":
                # Start polling in background
                asyncio.create_task(telegram_bot.start_polling())
                logger.info("Telegram bot started in polling mode")
            elif settings.TELEGRAM_BOT_MODE == "webhook" and settings.TELEGRAM_WEBHOOK_URL:
                # Set webhook (user needs to configure this)
                if telegram_bot.application:
                    await telegram_bot.application.bot.set_webhook(settings.TELEGRAM_WEBHOOK_URL)
                    logger.info(f"Telegram bot webhook set to: {settings.TELEGRAM_WEBHOOK_URL}")
        except Exception as e:
            logger.warning(f"Failed to initialize Telegram bot: {e}")
            telegram_bot = None
    
    # Start scheduler - Phase 2: Crawl all companies (simplified approach)
    scheduler.add_job(
        orchestrator.crawl_all_companies,
        trigger=IntervalTrigger(minutes=settings.CRAWL_INTERVAL_MINUTES),
        id="crawl_all_companies",
        name="Crawl all active companies",
        replace_existing=True
    )
    
    # Daily company refresh workflow
    async def refresh_company_list_daily():
        """Daily company refresh workflow"""
        try:
            from app.services.company_lifecycle import CompanyLifecycleManager
            lifecycle_manager = CompanyLifecycleManager()
            summary = await lifecycle_manager.refresh_company_list()
            logger.info(f"Daily company refresh completed: {summary}")
        except Exception as e:
            logger.error(f"Error in daily company refresh: {e}", exc_info=True)
    
    # Schedule company refresh daily at 2 AM
    scheduler.add_job(
        refresh_company_list_daily,
        trigger=CronTrigger(hour=2, minute=0),
        id="refresh_company_list",
        name="Daily company list refresh",
        replace_existing=True
    )
    
    # Company discovery scheduler
    async def run_company_discovery():
        """Automated company discovery task"""
        if not settings.COMPANY_DISCOVERY_ENABLED:
            logger.debug("Company discovery is disabled, skipping")
            return
        
        try:
            from app.crawler.company_discovery import CompanyDiscoveryService
            from app.services.company_discovery_service import process_and_insert_discovered_companies
            from app.database import AsyncSessionLocal
            from app.models import Company
            from app.utils.company_loader import count_companies
            from sqlalchemy import select
            
            async with AsyncSessionLocal() as db:
                # Check if we need more companies
                current_count = await count_companies(db, active_only=True)
                target_count = settings.COMPANY_TARGET_COUNT
                
                if current_count >= target_count:
                    logger.info(f"Company count ({current_count}) meets target ({target_count}), skipping discovery")
                    return
                
                # Get existing company names for deduplication
                result = await db.execute(select(Company.name))
                existing_names = {row[0].lower() for row in result.fetchall()}
                
                # Discover companies
                discovery_service = CompanyDiscoveryService()
                discovered = await discovery_service.discover_companies(
                    max_companies=settings.COMPANY_DISCOVERY_BATCH_SIZE,
                    existing_company_names=existing_names
                )
                
                if not discovered:
                    logger.info("No new companies discovered")
                    return
                
                # Process and insert discovered companies
                result = await process_and_insert_discovered_companies(discovered, db)
                
                logger.info(
                    f"Company discovery completed: {result.get('auto_approved', 0)} auto-approved, "
                    f"{result.get('pending_added', 0)} pending, {result.get('skipped_existing', 0)} skipped"
                )
        except Exception as e:
            logger.error(f"Error in automated company discovery: {e}", exc_info=True)
    
    # Schedule company discovery
    discovery_interval_hours = getattr(settings, "COMPANY_DISCOVERY_INTERVAL_HOURS", 6)
    scheduler.add_job(
        run_company_discovery,
        trigger=IntervalTrigger(hours=discovery_interval_hours),
        id="company_discovery",
        name="Automated company discovery",
        replace_existing=True
    )
    logger.info(f"Scheduled company discovery to run every {discovery_interval_hours} hours")
    
    # Task reminder scheduler
    async def check_task_reminders():
        """Check for due tasks and send reminders"""
        try:
            from app.database import AsyncSessionLocal
            from app.tasks.task_reminder_service import TaskReminderService
            
            async with AsyncSessionLocal() as db:
                reminder_service = TaskReminderService(orchestrator.notifier)
                await reminder_service.check_and_send_reminders(db)
        except Exception as e:
            logger.error(f"Error checking task reminders: {e}", exc_info=True)
    
    # Schedule task reminder checks
    scheduler.add_job(
        check_task_reminders,
        trigger=IntervalTrigger(minutes=settings.TASK_REMINDER_CHECK_INTERVAL_MINUTES),
        id="check_task_reminders",
        name="Check task reminders",
        replace_existing=True
    )
    
    # OpenWebUI health check
    async def check_openwebui_health():
        """Periodically check OpenWebUI health and cache status"""
        try:
            from app.services.openwebui_service import get_openwebui_service
            service = get_openwebui_service()
            if service.enabled:
                # Get auth tokens from settings if available
                api_key = getattr(settings, 'OPENWEBUI_API_KEY', None)
                auth_token = getattr(settings, 'OPENWEBUI_AUTH_TOKEN', None)
                health = await service.check_health(api_key, auth_token)
                logger.debug(f"OpenWebUI health check: {health.get('status')}")
        except Exception as e:
            logger.debug(f"OpenWebUI health check error: {e}")
    
    # Schedule OpenWebUI health check every 5 minutes
    scheduler.add_job(
        check_openwebui_health,
        trigger=IntervalTrigger(minutes=5),
        id="check_openwebui_health",
        name="Check OpenWebUI health",
        replace_existing=True
    )
    
    # Daily AI filtering and document generation
    async def daily_ai_selection_and_documents():
        """Select top jobs and generate documents daily."""
        try:
            from app.ai.job_filter import JobFilter
            from app.ai.document_generator import DocumentGenerator
            from app.database import AsyncSessionLocal
            
            job_filter = JobFilter()
            doc_gen = DocumentGenerator()
            
            # Rank jobs for the day and select top N
            await job_filter.filter_and_rank_jobs()
            top_jobs = await job_filter.select_top_jobs(count=settings.DAILY_TOP_JOBS_COUNT)
            
            if not top_jobs:
                logger.info("Daily AI selection: no top jobs found today")
                return
            
            # Generate documents for selected jobs
            async with AsyncSessionLocal() as db:
                results = []
                for j in top_jobs:
                    try:
                        gen = await doc_gen.generate_both(j, None, db)  # generator fetches profile internally when needed
                        results.append({
                            'job_id': j.id,
                            'resume': gen.get('resume') is not None,
                            'cover_letter': gen.get('cover_letter') is not None,
                        })
                    except Exception as e:
                        logger.error(f"Error generating documents for job {j.id}: {e}")
                logger.info(f"Daily documents generated for {len(results)} jobs")
        except Exception as e:
            logger.error(f"Error in daily AI selection/doc generation: {e}", exc_info=True)
    
    # Schedule daily AI selection and document generation at configured time
    try:
        hour, minute = map(int, settings.DAILY_GENERATION_TIME.split(":"))
        scheduler.add_job(
            daily_ai_selection_and_documents,
            trigger=CronTrigger(hour=hour, minute=minute),
            id="daily_ai_documents",
            name="Daily AI top jobs selection and document generation",
            replace_existing=True
        )
        logger.info(f"Scheduled daily AI selection/doc generation at {settings.DAILY_GENERATION_TIME}")
    except Exception as e:
        logger.warning(f"Could not schedule daily AI selection/doc generation: {e}")
    
    # Cleanup stuck crawl logs
    async def cleanup_stuck_logs_job():
        """Periodically clean up crawl logs stuck in 'running' status"""
        try:
            result = await orchestrator.cleanup_stuck_logs()
            if result.get('cleaned', 0) > 0:
                logger.info(f"Cleanup: {result['message']}")
        except Exception as e:
            logger.error(f"Error cleaning up stuck logs: {e}", exc_info=True)
    
    # Schedule stuck log cleanup
    scheduler.add_job(
        cleanup_stuck_logs_job,
        trigger=IntervalTrigger(minutes=settings.STUCK_LOG_CLEANUP_INTERVAL_MINUTES),
        id="cleanup_stuck_logs",
        name="Cleanup stuck crawl logs",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"Scheduler started:")
    logger.info(f"  - Crawling all companies every {settings.CRAWL_INTERVAL_MINUTES} minutes")
    logger.info(f"  - Refreshing company list daily at 2:00 AM")
    logger.info(f"  - Daily AI selection/doc generation at {getattr(settings, 'DAILY_GENERATION_TIME', '15:00')}")
    logger.info(f"  - Checking task reminders every {settings.TASK_REMINDER_CHECK_INTERVAL_MINUTES} minutes")
    logger.info(f"  - Checking OpenWebUI health every 5 minutes")
    logger.info(f"  - Cleaning up stuck logs every {settings.STUCK_LOG_CLEANUP_INTERVAL_MINUTES} minutes")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    
    # Stop Telegram bot if running
    if telegram_bot:
        try:
            await telegram_bot.stop_polling()
        except Exception as e:
            logger.warning(f"Error stopping Telegram bot: {e}")
    
    scheduler.shutdown()
    await close_db()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Job Search Crawler",
    description="Automated job search and tracking system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(router, prefix="/api")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Job Search Crawler API",
        "docs": "/docs",
        "dashboard": "/static/index.html"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


# SPA fallback: serve frontend for non-API routes
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    # Allow API and static to 404 normally
    if full_path.startswith("api") or full_path.startswith("static"):
        return {"detail": "Not Found"}
    # Serve built index.html for client-side routing
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )

