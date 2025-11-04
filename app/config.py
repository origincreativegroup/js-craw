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
    
    # OpenWebUI settings (point to your existing OpenWebUI instance)
    OPENWEBUI_ENABLED: bool = True
    OPENWEBUI_URL: str = "http://localhost:3000"  # Update to match your OpenWebUI URL
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

