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
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

