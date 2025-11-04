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
    
    # Create orchestrator
    orchestrator = CrawlerOrchestrator()
    app.state.crawler = orchestrator
    app.state.scheduler = scheduler  # Expose scheduler to API endpoints
    logger.info("Crawler orchestrator initialized")
    
    # Start scheduler - Phase 2: Crawl all companies (simplified approach)
    scheduler.add_job(
        orchestrator.crawl_all_companies,
        trigger=IntervalTrigger(minutes=settings.CRAWL_INTERVAL_MINUTES),
        id="crawl_all_companies",
        name="Crawl all active companies",
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Scheduler started: crawling all companies every {settings.CRAWL_INTERVAL_MINUTES} minutes")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
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

