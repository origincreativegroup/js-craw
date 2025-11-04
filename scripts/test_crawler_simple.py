#!/usr/bin/env python3
"""Simple test script to verify crawlers can fetch job listings without database"""
import asyncio
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.crawler.greenhouse_crawler import GreenhouseCrawler
from app.crawler.lever_crawler import LeverCrawler
from app.crawler.generic_crawler import GenericCrawler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_greenhouse_crawler():
    """Test Greenhouse crawler with a known company"""
    print("\n" + "=" * 60)
    print("Testing Greenhouse Crawler")
    print("=" * 60)
    
    # Test with Stripe (known Greenhouse user)
    test_cases = [
        ("stripe", "Stripe"),
        ("airbnb", "Airbnb"),
        ("github", "GitHub"),
    ]
    
    for slug, name in test_cases:
        try:
            print(f"\nTesting: {name} (slug: {slug})")
            crawler = GreenhouseCrawler(slug, name)
            jobs = await crawler.fetch_jobs()
            crawler.close()
            
            print(f"  ✓ Found {len(jobs)} jobs")
            
            if jobs:
                print(f"\n  Sample job:")
                sample = jobs[0]
                print(f"    Title: {sample.get('title', 'N/A')}")
                print(f"    Location: {sample.get('location', 'N/A')}")
                print(f"    URL: {sample.get('url', 'N/A')[:80]}...")
                return True
            else:
                print(f"  ⚠️  No jobs found (may be normal if company has no open positions)")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            logger.exception(f"Error testing {name}")
    
    return False


async def test_lever_crawler():
    """Test Lever crawler with a known company"""
    print("\n" + "=" * 60)
    print("Testing Lever Crawler")
    print("=" * 60)
    
    # Test with known Lever companies
    test_cases = [
        ("vercel", "Vercel"),
        ("notion", "Notion"),
        ("linear", "Linear"),
    ]
    
    for slug, name in test_cases:
        try:
            print(f"\nTesting: {name} (slug: {slug})")
            crawler = LeverCrawler(slug, name)
            jobs = await crawler.fetch_jobs()
            crawler.close()
            
            print(f"  ✓ Found {len(jobs)} jobs")
            
            if jobs:
                print(f"\n  Sample job:")
                sample = jobs[0]
                print(f"    Title: {sample.get('title', 'N/A')}")
                print(f"    Location: {sample.get('location', 'N/A')}")
                print(f"    URL: {sample.get('url', 'N/A')[:80]}...")
                return True
            else:
                print(f"  ⚠️  No jobs found (may be normal if company has no open positions)")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            logger.exception(f"Error testing {name}")
    
    return False


async def test_generic_crawler():
    """Test Generic crawler (requires Ollama - may skip if not available)"""
    print("\n" + "=" * 60)
    print("Testing Generic Crawler")
    print("=" * 60)
    print("  ⚠️  Note: Generic crawler requires Ollama and may take longer")
    print("  Skipping for now (requires Ollama service)")
    return None  # Skip for now


async def main():
    """Main test function"""
    print("=" * 60)
    print("Job Crawler Test - Direct Crawler Testing")
    print("=" * 60)
    print("\nThis test verifies that crawlers can fetch jobs from real companies")
    print("without requiring a database connection.\n")
    
    results = {}
    
    # Test Greenhouse
    try:
        results['greenhouse'] = await test_greenhouse_crawler()
    except Exception as e:
        print(f"❌ Greenhouse test failed: {e}")
        results['greenhouse'] = False
    
    # Test Lever
    try:
        results['lever'] = await test_lever_crawler()
    except Exception as e:
        print(f"❌ Lever test failed: {e}")
        results['lever'] = False
    
    # Test Generic (skip for now)
    results['generic'] = None
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for crawler_type, success in results.items():
        if success is True:
            print(f"  ✓ {crawler_type.capitalize()}: Working")
        elif success is False:
            print(f"  ❌ {crawler_type.capitalize()}: Failed or no jobs found")
        else:
            print(f"  ⊘ {crawler_type.capitalize()}: Skipped")
    
    if any(r is True for r in results.values()):
        print("\n✓ At least one crawler is working and can find job listings!")
        return 0
    else:
        print("\n⚠️  No crawlers successfully found jobs.")
        print("This might be normal if:")
        print("  - Test companies have no open positions")
        print("  - Network connectivity issues")
        print("  - Company career page structure changed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

