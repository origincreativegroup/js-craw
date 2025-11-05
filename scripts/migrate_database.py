"""Database migration script for Phase 1 enhancements"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import engine, init_db
from sqlalchemy import text


async def run_migration():
    """Run database migrations"""
    print("🔄 Starting database migration...")
    
    async with engine.begin() as conn:
        # Check if user_profiles table exists
        result = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'user_profiles'
                )
            """)
        )
        user_profiles_exists = result.scalar()
        
        result = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'generated_documents'
                )
            """)
        )
        generated_documents_exists = result.scalar()
        
        # Check if new columns exist in jobs table
        result = await conn.execute(
            text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'jobs' 
                AND column_name IN ('ai_rank', 'ai_recommended', 'ai_selected_date')
            """)
        )
        existing_columns = [row[0] for row in result.fetchall()]
        
        # Create new tables if they don't exist
        if not user_profiles_exists:
            print("  Creating user_profiles table...")
            await conn.execute(text("""
                CREATE TABLE user_profiles (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER UNIQUE REFERENCES users(id),
                    base_resume TEXT,
                    skills JSONB,
                    experience JSONB,
                    education JSONB,
                    preferences JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """))
            await conn.execute(text("CREATE INDEX ix_user_profiles_user_id ON user_profiles(user_id)"))
            print("  ✓ user_profiles table created")
        else:
            print("  ⊘ user_profiles table already exists")
        
        if not generated_documents_exists:
            print("  Creating generated_documents table...")
            await conn.execute(text("""
                CREATE TABLE generated_documents (
                    id SERIAL PRIMARY KEY,
                    job_id INTEGER NOT NULL REFERENCES jobs(id),
                    document_type VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    generated_at TIMESTAMP DEFAULT NOW(),
                    file_path VARCHAR(500)
                )
            """))
            await conn.execute(text("CREATE INDEX ix_generated_documents_job_id ON generated_documents(job_id)"))
            await conn.execute(text("CREATE INDEX ix_generated_documents_document_type ON generated_documents(document_type)"))
            await conn.execute(text("CREATE INDEX ix_generated_documents_generated_at ON generated_documents(generated_at)"))
            print("  ✓ generated_documents table created")
        else:
            print("  ⊘ generated_documents table already exists")
        
        # Add new columns to jobs table if they don't exist
        if 'ai_rank' not in existing_columns:
            print("  Adding ai_rank column to jobs table...")
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN ai_rank INTEGER"))
            await conn.execute(text("CREATE INDEX ix_jobs_ai_rank ON jobs(ai_rank)"))
            print("  ✓ ai_rank column added")
        
        if 'ai_recommended' not in existing_columns:
            print("  Adding ai_recommended column to jobs table...")
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN ai_recommended BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("CREATE INDEX ix_jobs_ai_recommended ON jobs(ai_recommended)"))
            print("  ✓ ai_recommended column added")
        
        if 'ai_selected_date' not in existing_columns:
            print("  Adding ai_selected_date column to jobs table...")
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN ai_selected_date TIMESTAMP"))
            await conn.execute(text("CREATE INDEX ix_jobs_ai_selected_date ON jobs(ai_selected_date)"))
            print("  ✓ ai_selected_date column added")
        
        # Make search_criteria_id nullable in jobs table (if not already)
        print("  Checking search_criteria_id constraint in jobs table...")
        result = await conn.execute(text("""
            SELECT is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'jobs' 
            AND column_name = 'search_criteria_id'
        """))
        is_nullable = result.scalar()
        
        if is_nullable == 'NO':
            print("  Making search_criteria_id nullable in jobs table...")
            # First drop the NOT NULL constraint
            await conn.execute(text("ALTER TABLE jobs ALTER COLUMN search_criteria_id DROP NOT NULL"))
            print("  ✓ search_criteria_id is now nullable")
        else:
            print("  ⊘ search_criteria_id is already nullable")
        
        # Add company_id to crawl_logs if it doesn't exist
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'crawl_logs' 
            AND column_name = 'company_id'
        """))
        company_id_exists = result.scalar() is not None
        
        if not company_id_exists:
            print("  Adding company_id column to crawl_logs table...")
            await conn.execute(text("ALTER TABLE crawl_logs ADD COLUMN company_id INTEGER REFERENCES companies(id)"))
            await conn.execute(text("CREATE INDEX ix_crawl_logs_company_id ON crawl_logs(company_id)"))
            print("  ✓ company_id column added to crawl_logs")
        else:
            print("  ⊘ company_id column already exists in crawl_logs")
        
        # Make search_criteria_id nullable in crawl_logs (if not already)
        result = await conn.execute(text("""
            SELECT is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'crawl_logs' 
            AND column_name = 'search_criteria_id'
        """))
        is_nullable = result.scalar()
        
        if is_nullable == 'NO':
            print("  Making search_criteria_id nullable in crawl_logs table...")
            await conn.execute(text("ALTER TABLE crawl_logs ALTER COLUMN search_criteria_id DROP NOT NULL"))
            print("  ✓ search_criteria_id is now nullable in crawl_logs")
        else:
            print("  ⊘ search_criteria_id is already nullable in crawl_logs")
        
        # Check if crawl_fallbacks table exists
        result = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'crawl_fallbacks'
                )
            """)
        )
        crawl_fallbacks_exists = result.scalar()
        
        # Create crawl_fallbacks table if it doesn't exist
        if not crawl_fallbacks_exists:
            print("  Creating crawl_fallbacks table...")
            await conn.execute(text("""
                CREATE TABLE crawl_fallbacks (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES companies(id),
                    method_used VARCHAR(50) NOT NULL,
                    success_count INTEGER DEFAULT 0,
                    last_success_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """))
            await conn.execute(text("CREATE INDEX ix_crawl_fallbacks_company_id ON crawl_fallbacks(company_id)"))
            print("  ✓ crawl_fallbacks table created")
        else:
            print("  ⊘ crawl_fallbacks table already exists")
        
        # Check which new Company columns exist
        result = await conn.execute(
            text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'companies' 
                AND column_name IN (
                    'consecutive_empty_crawls', 
                    'viability_score', 
                    'viability_last_checked',
                    'discovery_source',
                    'last_successful_crawl',
                    'priority_score'
                )
            """)
        )
        existing_company_columns = [row[0] for row in result.fetchall()]
        
        # Add new columns to companies table if they don't exist
        if 'consecutive_empty_crawls' not in existing_company_columns:
            print("  Adding consecutive_empty_crawls column to companies table...")
            await conn.execute(text("ALTER TABLE companies ADD COLUMN consecutive_empty_crawls INTEGER DEFAULT 0"))
            await conn.execute(text("CREATE INDEX ix_companies_consecutive_empty_crawls ON companies(consecutive_empty_crawls)"))
            print("  ✓ consecutive_empty_crawls column added")
        
        if 'viability_score' not in existing_company_columns:
            print("  Adding viability_score column to companies table...")
            await conn.execute(text("ALTER TABLE companies ADD COLUMN viability_score REAL"))
            await conn.execute(text("CREATE INDEX ix_companies_viability_score ON companies(viability_score)"))
            print("  ✓ viability_score column added")
        
        if 'viability_last_checked' not in existing_company_columns:
            print("  Adding viability_last_checked column to companies table...")
            await conn.execute(text("ALTER TABLE companies ADD COLUMN viability_last_checked TIMESTAMP"))
            print("  ✓ viability_last_checked column added")
        
        if 'discovery_source' not in existing_company_columns:
            print("  Adding discovery_source column to companies table...")
            await conn.execute(text("ALTER TABLE companies ADD COLUMN discovery_source VARCHAR(50)"))
            print("  ✓ discovery_source column added")
        
        if 'last_successful_crawl' not in existing_company_columns:
            print("  Adding last_successful_crawl column to companies table...")
            await conn.execute(text("ALTER TABLE companies ADD COLUMN last_successful_crawl TIMESTAMP"))
            await conn.execute(text("CREATE INDEX ix_companies_last_successful_crawl ON companies(last_successful_crawl)"))
            print("  ✓ last_successful_crawl column added")
        
        if 'priority_score' not in existing_company_columns:
            print("  Adding priority_score column to companies table...")
            await conn.execute(text("ALTER TABLE companies ADD COLUMN priority_score REAL DEFAULT 0.0"))
            await conn.execute(text("CREATE INDEX ix_companies_priority_score ON companies(priority_score)"))
            print("  ✓ priority_score column added")
    
        # Check if app_settings table exists
        result = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'app_settings'
                )
            """)
        )
        app_settings_exists = result.scalar()
        
        if not app_settings_exists:
            print("  Creating app_settings table...")
            await conn.execute(text("""
                CREATE TABLE app_settings (
                    key VARCHAR(255) PRIMARY KEY,
                    value JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """))
            await conn.execute(text("CREATE INDEX ix_app_settings_key ON app_settings(key)"))
            print("  ✓ app_settings table created")
        else:
            print("  ✓ app_settings table already exists")
        
        # Check if applications table exists
        result = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'applications'
                )
            """)
        )
        applications_exists = result.scalar()
        
        if not applications_exists:
            print("  Creating applications table...")
            await conn.execute(text("""
                CREATE TABLE applications (
                    id SERIAL PRIMARY KEY,
                    job_id INTEGER NOT NULL REFERENCES jobs(id),
                    status VARCHAR(50) NOT NULL DEFAULT 'queued',
                    application_date TIMESTAMP,
                    portal_url TEXT,
                    confirmation_number VARCHAR(255),
                    resume_version_id INTEGER REFERENCES generated_documents(id),
                    cover_letter_id INTEGER REFERENCES generated_documents(id),
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """))
            await conn.execute(text("CREATE INDEX ix_applications_job_id ON applications(job_id)"))
            await conn.execute(text("CREATE INDEX ix_applications_status ON applications(status)"))
            await conn.execute(text("CREATE INDEX ix_applications_application_date ON applications(application_date)"))
            await conn.execute(text("CREATE INDEX ix_applications_created_at ON applications(created_at)"))
            print("  ✓ applications table created")
        else:
            print("  ⊘ applications table already exists")
        
        # Check if pending_companies table exists
        result = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'pending_companies'
                )
            """)
        )
        pending_companies_exists = result.scalar()
        
        if not pending_companies_exists:
            print("  Creating pending_companies table...")
            await conn.execute(text("""
                CREATE TABLE pending_companies (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    career_page_url TEXT NOT NULL,
                    discovery_source VARCHAR(50) NOT NULL,
                    confidence_score REAL NOT NULL,
                    crawler_type VARCHAR(50) NOT NULL,
                    crawler_config JSONB,
                    discovery_metadata JSONB,
                    status VARCHAR(20) DEFAULT 'pending',
                    reviewed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """))
            await conn.execute(text("CREATE INDEX ix_pending_companies_name ON pending_companies(name)"))
            await conn.execute(text("CREATE INDEX ix_pending_companies_confidence_score ON pending_companies(confidence_score)"))
            await conn.execute(text("CREATE INDEX ix_pending_companies_status ON pending_companies(status)"))
            await conn.execute(text("CREATE INDEX ix_pending_companies_created_at ON pending_companies(created_at)"))
            print("  ✓ pending_companies table created")
        else:
            print("  ⊘ pending_companies table already exists")
        
        # Check if notify_enabled column exists in tasks table
        result = await conn.execute(
            text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'tasks' 
                AND column_name = 'notify_enabled'
            """)
        )
        notify_enabled_exists = result.scalar() is not None
        
        if not notify_enabled_exists:
            print("  Adding notify_enabled column to tasks table...")
            await conn.execute(text("ALTER TABLE tasks ADD COLUMN notify_enabled BOOLEAN DEFAULT TRUE"))
            await conn.execute(text("CREATE INDEX ix_tasks_notify_enabled ON tasks(notify_enabled)"))
            print("  ✓ notify_enabled column added to tasks table")
        else:
            print("  ⊘ notify_enabled column already exists in tasks table")
    
    print("\n✅ Database migration complete!")


if __name__ == "__main__":
    asyncio.run(run_migration())
