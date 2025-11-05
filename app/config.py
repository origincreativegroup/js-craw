"""Application configuration"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    SECRET_KEY: str = "change-me-in-production"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/job_crawler"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Ollama
    OLLAMA_HOST: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "llama2"
    
    # Selenium
    SELENIUM_HOST: str = "http://selenium-chrome:4444"
    SELENIUM_TIMEOUT: int = 30
    
    # Scheduling
    CRAWL_INTERVAL_MINUTES: int = 30
    DAILY_TOP_JOBS_COUNT: int = 5
    DAILY_GENERATION_TIME: str = "15:00"  # 3 PM in HH:MM format
    
    # Crawl timeout settings
    CRAWL_TIMEOUT_SECONDS: int = 300  # 5 minutes timeout per company crawl
    MAX_CONCURRENT_COMPANY_CRAWLS: int = 5  # Parallel company crawls
    AI_BATCH_SIZE: int = 20  # Jobs analyzed in parallel per batch
    STUCK_LOG_CLEANUP_THRESHOLD_MINUTES: int = 60  # Mark logs as failed if running longer than this
    STUCK_LOG_CLEANUP_INTERVAL_MINUTES: int = 15  # How often to check for stuck logs
    
    # Document Generation
    RESUME_STORAGE_PATH: str = "/app/data/resumes"
    COVER_LETTER_STORAGE_PATH: str = "/app/data/cover_letters"
    
    # Notifications
    NOTIFICATION_METHOD: str = "ntfy"  # ntfy, pushover, telegram
    
    # ntfy.sh settings
    NTFY_SERVER: str = "https://ntfy.sh"
    NTFY_TOPIC: Optional[str] = None
    
    # Pushover settings
    PUSHOVER_USER_KEY: Optional[str] = None
    PUSHOVER_APP_TOKEN: Optional[str] = None
    
    # Telegram settings
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    TELEGRAM_BOT_MODE: str = "polling"  # "polling" or "webhook"
    TELEGRAM_WEBHOOK_URL: Optional[str] = None  # Full URL for webhook mode
    
    # OpenWebUI settings (point to your existing OpenWebUI instance)
    OPENWEBUI_ENABLED: bool = True
    OPENWEBUI_URL: str = "http://localhost:3000"  # Update to match your OpenWebUI URL
    OPENWEBUI_API_KEY: Optional[str] = None  # API key for OpenWebUI API access
    OPENWEBUI_AUTH_TOKEN: Optional[str] = None  # Auth token for user session
    OPENWEBUI_USERNAME: Optional[str] = None  # Optional username for basic auth
    
    # Company lifecycle management settings
    COMPANY_TARGET_COUNT: int = 4000  # Target number of companies to maintain
    COMPANY_DISCOVERY_BATCH_SIZE: int = 50  # Number of companies to discover per batch
    CONSECUTIVE_EMPTY_THRESHOLD: int = 3  # Remove companies after N consecutive empty crawls
    VIABILITY_SCORE_THRESHOLD: float = 30.0  # Minimum viability score to keep company (0-100)
    COMPANY_REFRESH_SCHEDULE: str = "daily"  # How often to refresh company list
    WEB_SEARCH_ENABLED: bool = True  # Enable AI web search for company discovery
    
    # Company discovery settings
    COMPANY_DISCOVERY_ENABLED: bool = True  # Enable automated company discovery
    COMPANY_DISCOVERY_INTERVAL_HOURS: int = 6  # How often to run discovery (in hours)
    COMPANY_AUTO_APPROVE_THRESHOLD: float = 70.0  # Auto-approve companies with confidence >= this value
    LINKEDIN_SEARCH_KEYWORDS: str = "careers jobs"  # Keywords for LinkedIn discovery
    INDEED_SEARCH_KEYWORDS: str = "careers jobs"  # Keywords for Indeed discovery
    WEB_SEARCH_KEYWORDS: str = "companies careers"  # Keywords for web search discovery
    
    # Task workspace settings
    AUTO_GENERATE_TASKS: bool = True  # Enable/disable automatic task generation from AI insights
    TASK_MATCH_SCORE_THRESHOLD: float = 50.0  # Minimum match score for auto-generating tasks
    TASK_REMINDER_CHECK_INTERVAL_MINUTES: int = 60  # How often to check for due tasks (in minutes)
    
    # HTTP client settings
    HTTP_MAX_RETRIES: int = 3
    HTTP_INITIAL_BACKOFF_MS: int = 300
    HTTP_MAX_BACKOFF_MS: int = 5000
    HTTP_REQUEST_TIMEOUT_SECONDS: int = 20
    HTTP_USER_AGENTS: Optional[list[str]] = None
    HTTP_PROXIES: Optional[list[str]] = None
    ROBOTS_RESPECT: bool = True
    HTTP_RATE_PER_HOST: float = 1.0
    HTTP_BURST_PER_HOST: int = 2
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

