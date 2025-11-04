"""Main application entry point"""
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

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
        elif result.get("reason") == "sufficient_companies":
            logger.debug(f"Company database has sufficient companies ({result.get('current_count', 0)})")
    except Exception as e:
        logger.warning(f"Failed to load companies from CSV: {e}", exc_info=True)
    
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
    
    scheduler.start()
    logger.info(f"Scheduler started:")
    logger.info(f"  - Crawling all companies every {settings.CRAWL_INTERVAL_MINUTES} minutes")
    logger.info(f"  - Refreshing company list daily at 2:00 AM")
    logger.info(f"  - Checking task reminders every {settings.TASK_REMINDER_CHECK_INTERVAL_MINUTES} minutes")
    
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )

