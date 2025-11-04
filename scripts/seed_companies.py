"""Seed database with companies from companies.csv"""
import asyncio
import csv
import sys
from pathlib import Path
from urllib.parse import urlparse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, init_db
from app.models import Company
from sqlalchemy import select


def detect_crawler_type(url: str) -> str:
    """Auto-detect crawler type from URL"""
    url_lower = url.lower()
    
    # Greenhouse patterns
    if 'greenhouse.io' in url_lower or 'boards.greenhouse.io' in url_lower:
        return "greenhouse"
    
    # Lever patterns
    if 'lever.co' in url_lower or 'jobs.lever.co' in url_lower:
        return "lever"
    
    # Workday patterns
    if 'myworkdayjobs.com' in url_lower or 'workday.com' in url_lower:
        return "workday"
    
    # Default to generic
    return "generic"


def parse_companies_csv(csv_path: Path) -> list:
    """Parse companies.csv and return list of company dicts"""
    companies = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip empty rows
            if not row.get('Company Name') or not row.get('Career Page URL'):
                continue
            
            company_name = row['Company Name'].strip()
            career_url = row['Career Page URL'].strip()
            
            # Clean up URL (remove extra text after the link)
            if 'http' in career_url:
                # Extract just the URL part
                url_parts = career_url.split()
                for part in url_parts:
                    if part.startswith('http'):
                        career_url = part
                        break
            
            # Skip if no valid URL
            if not career_url.startswith('http'):
                continue
            
            crawler_type = detect_crawler_type(career_url)
            
            companies.append({
                "name": company_name,
                "career_page_url": career_url,
                "crawler_type": crawler_type,
                "crawler_config": {}
            })
    
    return companies


async def seed_companies():
    """Seed database with companies from companies.csv"""
    print("Initializing database...")
    await init_db()

    # Find companies.csv file
    project_root = Path(__file__).parent.parent
    csv_path = project_root / "companies.csv"
    
    if not csv_path.exists():
        print(f"❌ Error: {csv_path} not found!")
        return
    
    print(f"Reading companies from {csv_path}...")
    companies_data = parse_companies_csv(csv_path)
    print(f"Found {len(companies_data)} companies in CSV\n")

    async with AsyncSessionLocal() as db:
        added_count = 0
        skipped_count = 0

        for company_data in companies_data:
            # Check if company already exists
            result = await db.execute(
                select(Company).where(Company.name == company_data["name"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                skipped_count += 1
                print(f"⊘ {company_data['name']} already exists (ID: {existing.id})")
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

            added_count += 1
            print(f"✓ Added {company.name} (ID: {company.id}, Type: {company.crawler_type})")

        print(f"\n✅ Company seeding complete!")
        print(f"  - Added: {added_count}")
        print(f"  - Skipped (already exists): {skipped_count}")

        # Print summary
        result = await db.execute(select(Company))
        all_companies = result.scalars().all()

        print(f"\nTotal companies in database: {len(all_companies)}")
        print(f"  - Greenhouse: {len([c for c in all_companies if c.crawler_type == 'greenhouse'])}")
        print(f"  - Lever: {len([c for c in all_companies if c.crawler_type == 'lever'])}")
        print(f"  - Workday: {len([c for c in all_companies if c.crawler_type == 'workday'])}")
        print(f"  - Generic: {len([c for c in all_companies if c.crawler_type == 'generic'])}")


if __name__ == "__main__":
    asyncio.run(seed_companies())
