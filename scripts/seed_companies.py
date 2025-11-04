"""Seed database with companies from companies.csv"""
import asyncio
import csv
import re
import sys
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import parse_qs, urlparse

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


def _slugify_company_name(company_name: str) -> str:
    """Create a slug from a company name for crawler defaults."""

    base_name = company_name.split('(')[0].strip()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", base_name).strip('-').lower()
    return slug


def _extract_greenhouse_slug(url: str, company_name: str) -> Optional[str]:
    """Extract the Greenhouse slug from a career page URL."""

    parsed = urlparse(url)

    query_params = parse_qs(parsed.query)
    slug_candidates = query_params.get('for') or query_params.get('for[]')
    if slug_candidates:
        for candidate in slug_candidates:
            candidate = candidate.strip()
            if candidate:
                return candidate.lower()

    path_parts = [part for part in parsed.path.split('/') if part]
    for part in reversed(path_parts):
        lowered = part.lower()
        if lowered in {"embed", "job_board", "jobs"}:
            continue
        return lowered

    return _slugify_company_name(company_name)


def _extract_lever_slug(url: str, company_name: str) -> str:
    """Extract the Lever slug from a career page URL."""

    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split('/') if part]
    if path_parts:
        return path_parts[0].lower()
    return _slugify_company_name(company_name)


def build_crawler_config(company_name: str, url: str, crawler_type: str) -> Dict:
    """Build crawler configuration details based on detected type."""

    if crawler_type == "greenhouse":
        slug = _extract_greenhouse_slug(url, company_name)
        return {"slug": slug} if slug else {}

    if crawler_type == "lever":
        slug = _extract_lever_slug(url, company_name)
        return {"slug": slug} if slug else {}

    if crawler_type == "workday":
        return {"source": "workday"}

    return {}


# Known company career page URLs (for companies where URL construction might fail)
KNOWN_COMPANY_URLS = {
    "Adobe Inc.": "https://careers.adobe.com",
    "Airbnb": "https://careers.airbnb.com",
    "Amazon": "https://www.amazon.jobs",
    "Apple Inc.": "https://www.apple.com/careers/us/",
    "Atlassian": "https://www.atlassian.com/company/careers",
    "Autodesk": "https://www.autodesk.com/careers",
    "Automattic (WordPress.com)": "https://automattic.com/work-with-us/",
    "Microsoft": "https://careers.microsoft.com",
    "Meta": "https://www.metacareers.com/jobs",
    "Google": "https://careers.google.com/jobs",
    "Netflix": "https://jobs.netflix.com",
    "Figma": "https://www.figma.com/careers",
    "Canva": "https://www.canva.com/careers",
    "Notion": "https://www.notion.so/careers",
    "Linear": "https://linear.app/careers",
    "Vercel": "https://vercel.com/careers",
    "Stripe": "https://stripe.com/jobs",
    "Coinbase": "https://www.coinbase.com/careers",
    "DoorDash": "https://careers.doordash.com",
    "GitLab": "https://about.gitlab.com/jobs",
    "Plaid": "https://plaid.com/careers",
    "Ramp": "https://ramp.com/careers",
    "Databricks": "https://www.databricks.com/company/careers",
}


def construct_career_url(company_name: str) -> Optional[str]:
    """Try to construct a career page URL from company name"""
    # Check known URLs first
    if company_name in KNOWN_COMPANY_URLS:
        return KNOWN_COMPANY_URLS[company_name]
    
    # Clean company name for URL construction
    clean_name = company_name.split('(')[0].strip()  # Remove parentheticals
    clean_name = clean_name.replace(' Inc.', '').replace(' Inc', '').replace(' LLC', '').replace(' Ltd.', '')
    clean_name = clean_name.replace(',', '').replace('.', '').replace(' ', '').lower()
    
    # Common patterns to try (we'll return the first one, caller should validate)
    # Most companies use /careers or /jobs
    return f"https://www.{clean_name}.com/careers"


def parse_companies_csv(csv_path: Path) -> list:
    """Parse companies.csv and return list of company dicts"""
    companies = []
    skipped_no_url = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip empty rows
            if not row.get('Company Name') or not row.get('Career Page URL'):
                continue
            
            company_name = row['Company Name'].strip()
            career_url = row['Career Page URL'].strip()
            
            # Clean up URL (remove extra text after the link)
            if 'http' in career_url.lower():
                # Extract just the URL part
                url_parts = career_url.split()
                for part in url_parts:
                    if part.startswith('http'):
                        career_url = part
                        break
            else:
                # No HTTP URL found, try to construct one
                constructed_url = construct_career_url(company_name)
                if constructed_url:
                    career_url = constructed_url
                    print(f"  🔗 Constructed URL for {company_name}: {career_url}")
                else:
                    skipped_no_url.append(company_name)
                    continue
            
            # Skip if still no valid URL
            if not career_url.startswith('http'):
                skipped_no_url.append(company_name)
                continue
            
            crawler_type = detect_crawler_type(career_url)
            crawler_config = build_crawler_config(company_name, career_url, crawler_type)

            companies.append({
                "name": company_name,
                "career_page_url": career_url,
                "crawler_type": crawler_type,
                "crawler_config": crawler_config
            })
    
    if skipped_no_url:
        print(f"⚠️  Skipped {len(skipped_no_url)} companies without valid HTTP URLs")
        if len(skipped_no_url) <= 10:
            print(f"   Examples: {', '.join(skipped_no_url[:10])}")
        else:
            print(f"   Examples: {', '.join(skipped_no_url[:10])} ... and {len(skipped_no_url) - 10} more")
    
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
