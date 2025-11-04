"""Seed database with popular tech companies"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, init_db
from app.models import Company
from sqlalchemy import select


COMPANIES = [
    # Greenhouse Companies
    {"name": "Stripe", "career_page_url": "https://stripe.com/jobs", "crawler_type": "greenhouse", "crawler_config": {"slug": "stripe"}},
    {"name": "Airbnb", "career_page_url": "https://careers.airbnb.com", "crawler_type": "greenhouse", "crawler_config": {"slug": "airbnb"}},
    {"name": "Coinbase", "career_page_url": "https://www.coinbase.com/careers", "crawler_type": "greenhouse", "crawler_config": {"slug": "coinbase"}},
    {"name": "DoorDash", "career_page_url": "https://careers.doordash.com", "crawler_type": "greenhouse", "crawler_config": {"slug": "doordash"}},
    {"name": "GitLab", "career_page_url": "https://about.gitlab.com/jobs", "crawler_type": "greenhouse", "crawler_config": {"slug": "gitlab"}},
    {"name": "Plaid", "career_page_url": "https://plaid.com/careers", "crawler_type": "greenhouse", "crawler_config": {"slug": "plaid"}},
    {"name": "Ramp", "career_page_url": "https://ramp.com/careers", "crawler_type": "greenhouse", "crawler_config": {"slug": "ramp"}},
    {"name": "Databricks", "career_page_url": "https://www.databricks.com/company/careers", "crawler_type": "greenhouse", "crawler_config": {"slug": "databricks"}},

    # Lever Companies
    {"name": "Netflix", "career_page_url": "https://jobs.netflix.com", "crawler_type": "lever", "crawler_config": {"slug": "netflix"}},
    {"name": "Figma", "career_page_url": "https://www.figma.com/careers", "crawler_type": "lever", "crawler_config": {"slug": "figma"}},
    {"name": "Canva", "career_page_url": "https://www.canva.com/careers", "crawler_type": "lever", "crawler_config": {"slug": "canva"}},
    {"name": "Notion", "career_page_url": "https://www.notion.so/careers", "crawler_type": "lever", "crawler_config": {"slug": "notion"}},
    {"name": "Linear", "career_page_url": "https://linear.app/careers", "crawler_type": "lever", "crawler_config": {"slug": "linear"}},
    {"name": "Vercel", "career_page_url": "https://vercel.com/careers", "crawler_type": "lever", "crawler_config": {"slug": "vercel"}},

    # Generic Companies (AI-assisted parsing)
    {"name": "Google", "career_page_url": "https://careers.google.com/jobs/results", "crawler_type": "generic", "crawler_config": {}},
    {"name": "Microsoft", "career_page_url": "https://careers.microsoft.com/us/en/search-results", "crawler_type": "generic", "crawler_config": {}},
    {"name": "Amazon", "career_page_url": "https://www.amazon.jobs/en/search", "crawler_type": "generic", "crawler_config": {}},
    {"name": "Apple", "career_page_url": "https://www.apple.com/careers/us/", "crawler_type": "generic", "crawler_config": {}},
    {"name": "Meta", "career_page_url": "https://www.metacareers.com/jobs", "crawler_type": "generic", "crawler_config": {}},
    {"name": "OpenAI", "career_page_url": "https://openai.com/careers", "crawler_type": "generic", "crawler_config": {}},
    {"name": "Anthropic", "career_page_url": "https://www.anthropic.com/careers", "crawler_type": "generic", "crawler_config": {}},
]


async def seed_companies():
    """Seed database with companies"""
    print("Initializing database...")
    await init_db()

    async with AsyncSessionLocal() as db:
        print(f"\nSeeding {len(COMPANIES)} companies...")

        added = 0
        skipped = 0

        for company_data in COMPANIES:
            # Check if company already exists
            result = await db.execute(
                select(Company).where(Company.name == company_data["name"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"✓ {company_data['name']} already exists (ID: {existing.id})")
                skipped += 1
                continue

            # Create new company
            company = Company(
                name=company_data["name"],
                career_page_url=company_data["career_page_url"],
                crawler_type=company_data["crawler_type"],
                crawler_config=company_data["crawler_config"],
                is_active=True
            )

            db.add(company)
            await db.commit()
            await db.refresh(company)

            print(f"✓ Added {company.name} (ID: {company.id}, Type: {company.crawler_type})")
            added += 1

        print(f"\n✅ Company seeding complete!")
        print(f"  - Added: {added}")
        print(f"  - Skipped (already exists): {skipped}")

        # Print summary
        result = await db.execute(select(Company))
        all_companies = result.scalars().all()

        print(f"\nTotal companies in database: {len(all_companies)}")
        print(f"  - Greenhouse: {len([c for c in all_companies if c.crawler_type == 'greenhouse'])}")
        print(f"  - Lever: {len([c for c in all_companies if c.crawler_type == 'lever'])}")
        print(f"  - Generic: {len([c for c in all_companies if c.crawler_type == 'generic'])}")


if __name__ == "__main__":
    asyncio.run(seed_companies())
