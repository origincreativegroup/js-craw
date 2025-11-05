#!/usr/bin/env python3
"""Script to manually clean up stuck crawl logs"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, init_db
from app.models import CrawlLog
from app.config import settings
from sqlalchemy import select
from datetime import datetime, timedelta


async def cleanup_stuck_logs():
    """Clean up crawl logs that have been stuck in 'running' status"""
    print("Initializing database connection...")
    await init_db()
    
    threshold_minutes = settings.STUCK_LOG_CLEANUP_THRESHOLD_MINUTES
    threshold = datetime.utcnow() - timedelta(minutes=threshold_minutes)
    
    print(f"\n{'='*80}")
    print(f"CLEANING UP STUCK CRAWL LOGS")
    print(f"{'='*80}")
    print(f"Threshold: Logs older than {threshold_minutes} minutes will be marked as failed")
    print(f"Cutoff time: {threshold}")
    print()
    
    async with AsyncSessionLocal() as db:
        # Find all logs that are still 'running' and started before the threshold
        result = await db.execute(
            select(CrawlLog).where(
                CrawlLog.status == 'running',
                CrawlLog.started_at < threshold
            )
        )
        stuck_logs = result.scalars().all()
        
        if not stuck_logs:
            print("✅ No stuck logs found!")
            return
        
        print(f"Found {len(stuck_logs)} stuck log(s):\n")
        
        # Mark each stuck log as failed
        for log in stuck_logs:
            duration_minutes = (datetime.utcnow() - log.started_at).total_seconds() / 60
            print(f"  Log ID {log.id}:")
            print(f"    Company ID: {log.company_id}")
            print(f"    Started: {log.started_at}")
            print(f"    Stuck for: {duration_minutes:.1f} minutes")
            
            log.status = 'failed'
            log.completed_at = datetime.utcnow()
            log.error_message = (
                f"Automatically marked as failed - stuck in 'running' status for "
                f"{duration_minutes:.1f} minutes (threshold: {threshold_minutes} minutes)"
            )
        
        await db.commit()
        
        print(f"\n✅ Successfully cleaned up {len(stuck_logs)} stuck crawl log(s)")
        print(f"\nYou can now check the logs with:")
        print(f"  python scripts/check_logs.py")


if __name__ == "__main__":
    asyncio.run(cleanup_stuck_logs())
