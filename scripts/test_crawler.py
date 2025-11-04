#!/usr/bin/env python3
"""Test script to verify the crawler finds job listings"""
import asyncio
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, init_db
from app.models import Company, Job
from app.crawler.orchestrator import CrawlerOrchestrator
from sqlalchemy import select, func

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def check_companies():
    """Check if there are companies in the database"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.count(Company.id)).where(Company.is_active == True)
        )
        count = result.scalar()
        return count


async def get_test_companies(limit: int = 3):
    """Get a few companies to test with"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Company)
            .where(Company.is_active == True)
            .limit(limit)
        )
        companies = result.scalars().all()
        return companies


async def count_jobs():
    """Count total jobs in database"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(func.count(Job.id)))
        return result.scalar()


async def test_crawler():
    """Test the crawler by running it on a few companies"""
    print("=" * 60)
    print("Testing Job Crawler")
    print("=" * 60)
    
    # Initialize database
    print("\n1. Initializing database...")
    await init_db()
    print("   ✓ Database initialized")
    
    # Check if companies exist
    print("\n2. Checking for companies...")
    company_count = await check_companies()
    print(f"   Found {company_count} active companies")
    
    if company_count == 0:
        print("\n   ⚠️  No companies found in database!")
        print("   Please run: python scripts/seed_companies.py")
        return False
    
    # Get test companies
    print("\n3. Selecting test companies...")
    test_companies = await get_test_companies(limit=3)
    print(f"   Selected {len(test_companies)} companies to test:")
    for company in test_companies:
        print(f"     - {company.name} ({company.crawler_type})")
        print(f"       URL: {company.career_page_url}")
    
    # Check initial job count
    initial_job_count = await count_jobs()
    print(f"\n4. Initial job count: {initial_job_count}")
    
    # Create orchestrator
    print("\n5. Creating crawler orchestrator...")
    orchestrator = CrawlerOrchestrator()
    print("   ✓ Orchestrator created")
    
    # Test crawling a single company first
    print("\n6. Testing single company crawl...")
    if test_companies:
        test_company = test_companies[0]
        print(f"   Testing: {test_company.name}")
        try:
            jobs = await orchestrator._crawl_company(test_company)
            print(f"   ✓ Found {len(jobs)} jobs from {test_company.name}")
            
            if jobs:
                print("\n   Sample job:")
                sample_job = jobs[0]
                print(f"     Title: {sample_job.get('title', 'N/A')}")
                print(f"     Company: {sample_job.get('company', 'N/A')}")
                print(f"     Location: {sample_job.get('location', 'N/A')}")
                print(f"     URL: {sample_job.get('url', 'N/A')[:80]}...")
            else:
                print("   ⚠️  No jobs found for this company")
                print("   This might be normal if:")
                print("     - The company has no open positions")
                print("     - The crawler type needs configuration")
                print("     - The career page URL is incorrect")
        except Exception as e:
            print(f"   ❌ Error crawling {test_company.name}: {e}")
            logger.exception("Crawl error")
            return False
    
    # Test full crawl (all companies)
    print("\n7. Testing full crawl (all companies)...")
    print("   This may take a few minutes...")
    
    try:
        results = await orchestrator.crawl_all_companies()
        print(f"   ✓ Crawl completed!")
        print(f"   Found {len(results)} new jobs")
        
        # Check final job count
        final_job_count = await count_jobs()
        print(f"\n8. Final job count: {final_job_count}")
        print(f"   Jobs added: {final_job_count - initial_job_count}")
        
        if results:
            print("\n   Sample jobs found:")
            for i, job in enumerate(results[:5], 1):
                print(f"     {i}. {job.get('title', 'N/A')} at {job.get('company', 'N/A')}")
                print(f"        Match Score: {job.get('ai_match_score', 'N/A')}")
                print(f"        URL: {job.get('url', 'N/A')[:80]}...")
        else:
            print("\n   ⚠️  No new jobs found")
            print("   This might be normal if all jobs were already in the database")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error during full crawl: {e}")
        logger.exception("Full crawl error")
        return False


async def main():
    """Main entry point"""
    try:
        success = await test_crawler()
        
        print("\n" + "=" * 60)
        if success:
            print("✓ Crawler test completed successfully!")
            print("\nThe crawler is working and can find job listings.")
        else:
            print("⚠️  Crawler test completed with issues.")
            print("\nPlease check the errors above and:")
            print("  - Ensure companies are seeded: python scripts/seed_companies.py")
            print("  - Check database connection settings")
            print("  - Verify company career page URLs are correct")
        print("=" * 60)
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        logger.exception("Fatal error")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

