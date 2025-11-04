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
    
    print("\n✅ Database migration complete!")


if __name__ == "__main__":
    asyncio.run(run_migration())
