"""Seed settings from config to database"""
import asyncio
import sys
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import engine
from app.config import settings
from sqlalchemy import text


async def seed_settings():
    """Seed settings from current config to database"""
    print("🔄 Seeding settings to database...")
    
    async with engine.begin() as conn:
        # Check if app_settings table exists
        result = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'app_settings'
                )
            """)
        )
        table_exists = result.scalar()
        
        if not table_exists:
            print("  ❌ app_settings table does not exist. Run migration first.")
            return
        
        # Settings to seed (all current settings from config)
        settings_to_seed = {
            # OpenWebUI
            'openwebui_enabled': settings.OPENWEBUI_ENABLED,
            'openwebui_url': settings.OPENWEBUI_URL,
            'openwebui_api_key': getattr(settings, 'OPENWEBUI_API_KEY', None),
            'openwebui_auth_token': getattr(settings, 'OPENWEBUI_AUTH_TOKEN', None),
            'openwebui_username': getattr(settings, 'OPENWEBUI_USERNAME', None),
            
            # Notifications
            'notification_method': settings.NOTIFICATION_METHOD,
            'ntfy_server': settings.NTFY_SERVER,
            'ntfy_topic': settings.NTFY_TOPIC,
            'pushover_user_key': settings.PUSHOVER_USER_KEY,
            'pushover_app_token': settings.PUSHOVER_APP_TOKEN,
            'telegram_bot_token': settings.TELEGRAM_BOT_TOKEN,
            'telegram_chat_id': settings.TELEGRAM_CHAT_ID,
            'telegram_bot_mode': settings.TELEGRAM_BOT_MODE,
            'telegram_webhook_url': settings.TELEGRAM_WEBHOOK_URL,
            
            # Company lifecycle
            'company_target_count': settings.COMPANY_TARGET_COUNT,
            'company_discovery_batch_size': settings.COMPANY_DISCOVERY_BATCH_SIZE,
            'consecutive_empty_threshold': settings.CONSECUTIVE_EMPTY_THRESHOLD,
            'viability_score_threshold': settings.VIABILITY_SCORE_THRESHOLD,
            'company_refresh_schedule': settings.COMPANY_REFRESH_SCHEDULE,
            'web_search_enabled': settings.WEB_SEARCH_ENABLED,
            
            # Task workspace
            'auto_generate_tasks': settings.AUTO_GENERATE_TASKS,
            'task_match_score_threshold': settings.TASK_MATCH_SCORE_THRESHOLD,
            'task_reminder_check_interval_minutes': settings.TASK_REMINDER_CHECK_INTERVAL_MINUTES,
            
            # Crawl scheduling
            'crawl_interval_minutes': settings.CRAWL_INTERVAL_MINUTES,
            'daily_top_jobs_count': settings.DAILY_TOP_JOBS_COUNT,
            'daily_generation_time': settings.DAILY_GENERATION_TIME,
            
            # AI/Ollama
            'ollama_host': settings.OLLAMA_HOST,
            'ollama_model': settings.OLLAMA_MODEL,
        }
        
        # Seed each setting
        seeded_count = 0
        updated_count = 0
        
        for key, value in settings_to_seed.items():
            if value is None:
                continue  # Skip None values
            
            # Check if setting exists
            result = await conn.execute(
                text("SELECT EXISTS(SELECT 1 FROM app_settings WHERE key = :key)"),
                {"key": key}
            )
            exists = result.scalar()
            
            if exists:
                # Update existing
                await conn.execute(
                    text("""
                        UPDATE app_settings 
                        SET value = :value, updated_at = NOW()
                        WHERE key = :key
                    """),
                    {"key": key, "value": json.dumps(value)}
                )
                updated_count += 1
            else:
                # Insert new
                await conn.execute(
                    text("""
                        INSERT INTO app_settings (key, value, updated_at)
                        VALUES (:key, :value, NOW())
                    """),
                    {"key": key, "value": json.dumps(value)}
                )
                seeded_count += 1
        
        print(f"  ✓ Seeded {seeded_count} new settings")
        print(f"  ✓ Updated {updated_count} existing settings")
        print(f"  ✓ Total settings: {seeded_count + updated_count}")
    
    print("\n✅ Settings seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_settings())

