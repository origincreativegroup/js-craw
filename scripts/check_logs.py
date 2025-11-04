"""Script to check recent crawl logs and diagnose why jobs aren't being saved"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, init_db
from app.models import CrawlLog, Job, Company
from sqlalchemy import select, desc, func


async def check_recent_logs():
    """Check recent crawl logs and job counts"""
    print("Initializing database connection...")
    await init_db()
    
    async with AsyncSessionLocal() as db:
        # Get recent crawl logs (last 20)
        print("\n" + "="*80)
        print("RECENT CRAWL LOGS (Last 20)")
        print("="*80)
        
        result = await db.execute(
            select(CrawlLog)
            .order_by(desc(CrawlLog.started_at))
            .limit(20)
        )
        logs = result.scalars().all()
        
        if not logs:
            print("No crawl logs found")
        else:
            for log in logs:
                company_name = "Unknown"
                if log.company_id:
                    company_result = await db.execute(
                        select(Company).where(Company.id == log.company_id)
                    )
                    company = company_result.scalar_one_or_none()
                    if company:
                        company_name = company.name
                
                status_icon = "✅" if log.status == "completed" else "🔄" if log.status == "running" else "❌"
                print(f"\n{status_icon} {log.platform} - {company_name}")
                print(f"   Status: {log.status}")
                print(f"   Started: {log.started_at}")
                if log.completed_at:
                    duration = (log.completed_at - log.started_at).total_seconds()
                    print(f"   Completed: {log.completed_at} (Duration: {duration:.1f}s)")
                print(f"   Jobs Found: {log.jobs_found}")
                print(f"   New Jobs: {log.new_jobs}")
                if log.error_message:
                    print(f"   ⚠️  Error: {log.error_message}")
        
        # Check job statistics
        print("\n" + "="*80)
        print("JOB STATISTICS")
        print("="*80)
        
        # Total jobs
        result = await db.execute(select(func.count(Job.id)))
        total_jobs = result.scalar()
        print(f"Total jobs in database: {total_jobs}")
        
        # Jobs by company
        result = await db.execute(
            select(Company.id, Company.name, func.count(Job.id).label('job_count'))
            .join(Job, Company.id == Job.company_id, isouter=True)
            .group_by(Company.id, Company.name)
            .order_by(desc('job_count'))
            .limit(10)
        )
        company_jobs = result.all()
        
        print("\nTop 10 companies by job count:")
        for company_id, company_name, job_count in company_jobs:
            print(f"  {company_name}: {job_count} jobs")
        
        # Recent jobs (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        result = await db.execute(
            select(func.count(Job.id))
            .where(Job.discovered_at >= yesterday)
        )
        recent_jobs = result.scalar()
        print(f"\nJobs discovered in last 24 hours: {recent_jobs}")
        
        # Jobs without external_id (shouldn't happen, but check)
        result = await db.execute(
            select(func.count(Job.id))
            .where(Job.external_id.is_(None))
        )
        jobs_without_id = result.scalar()
        if jobs_without_id > 0:
            print(f"⚠️  WARNING: {jobs_without_id} jobs without external_id!")
        
        # Check for duplicate external_ids
        result = await db.execute(
            select(Job.external_id, Job.company_id, func.count(Job.id).label('count'))
            .group_by(Job.external_id, Job.company_id)
            .having(func.count(Job.id) > 1)
            .limit(10)
        )
        duplicates = result.all()
        if duplicates:
            print(f"\n⚠️  Found {len(duplicates)} duplicate external_id + company_id combinations:")
            for ext_id, comp_id, count in duplicates[:5]:
                print(f"  external_id: {ext_id}, company_id: {comp_id}, count: {count}")
        
        # Check recent jobs for a specific company (if we have company_5 or company_8)
        print("\n" + "="*80)
        print("RECENT JOBS BY COMPANY (Last 10 per company)")
        print("="*80)
        
        result = await db.execute(
            select(Company).where(Company.is_active == True).limit(10)
        )
        companies = result.scalars().all()
        
        for company in companies:
            result = await db.execute(
                select(Job)
                .where(Job.company_id == company.id)
                .order_by(desc(Job.discovered_at))
                .limit(10)
            )
            jobs = result.scalars().all()
            print(f"\n{company.name} (ID: {company.id}, Type: {company.crawler_type}):")
            print(f"  Total jobs: {len(jobs)} shown (of {len(jobs)} recent)")
            if jobs:
                for job in jobs[:5]:  # Show first 5
                    print(f"    - {job.title} (ID: {job.id}, external_id: {job.external_id[:50] if job.external_id else 'None'})")
                    print(f"      Discovered: {job.discovered_at}")
            else:
                print("  No jobs found")


if __name__ == "__main__":
    asyncio.run(check_recent_logs())

