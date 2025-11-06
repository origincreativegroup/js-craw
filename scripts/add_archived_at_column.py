#!/usr/bin/env python3
"""Add archived_at column to jobs table if it doesn't exist"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, engine
from sqlalchemy import text


async def add_archived_at_column():
    """Add archived_at column to jobs table"""
    async with AsyncSessionLocal() as db:
        try:
            # Check if column exists
            result = await db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'jobs' AND column_name = 'archived_at'
            """))
            exists = result.fetchone()
            
            if exists:
                print("✅ Column 'archived_at' already exists in jobs table")
                return
            
            # Add column
            await db.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN archived_at TIMESTAMP NULL
            """))
            
            # Create index
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_jobs_archived_at 
                ON jobs(archived_at)
            """))
            
            await db.commit()
            print("✅ Successfully added 'archived_at' column to jobs table")
            print("✅ Created index on archived_at column")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ Error adding archived_at column: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(add_archived_at_column())

