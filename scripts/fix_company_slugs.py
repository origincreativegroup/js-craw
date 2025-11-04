#!/usr/bin/env python3
"""Fix company slugs for Greenhouse and Lever companies"""
import asyncio
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, init_db
from app.models import Company
from sqlalchemy import select

# Known slug mappings
KNOWN_SLUGS = {
    "GitLab": "gitlab",
    "Plaid": "plaid",
    "Ramp": "ramp",
    "Databricks": "databricks",
    "Netflix": "netflix",
    "Stripe": "stripe",
    "Airbnb": "airbnb",
    "Coinbase": "coinbase",
    "DoorDash": "doordash",
}

def extract_slug_from_url(url: str, company_name: str) -> str:
    """Try to extract slug from URL or generate from company name"""
    url_lower = url.lower()
    
    # Try to extract from Greenhouse URL
    if 'greenhouse.io' in url_lower or 'boards.greenhouse.io' in url_lower:
        match = re.search(r'boards\.greenhouse\.io/([^/]+)', url_lower)
        if match:
            return match.group(1)
    
    # Try to extract from Lever URL
    if 'lever.co' in url_lower or 'jobs.lever.co' in url_lower:
        match = re.search(r'jobs\.lever\.co/([^/]+)', url_lower)
        if match:
            return match.group(1)
    
    # Fallback: generate from company name
    slug = company_name.lower()
    slug = re.sub(r'[^a-z0-9]+', '', slug)
    return slug

async def fix_slugs():
    """Fix missing slugs for companies"""
    await init_db()
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Company).where(
                Company.crawler_type.in_(['greenhouse', 'lever'])
            )
        )
        companies = result.scalars().all()
        
        updated = 0
        for company in companies:
            config = company.crawler_config or {}
            
            # Check if slug is missing or needs update
            if not config.get('slug'):
                # Try known slugs first
                slug = KNOWN_SLUGS.get(company.name)
                
                if not slug:
                    # Extract from URL
                    slug = extract_slug_from_url(company.career_page_url, company.name)
                
                config['slug'] = slug
                company.crawler_config = config
                updated += 1
                print(f"✓ {company.name}: Set slug to '{slug}'")
        
        if updated > 0:
            await db.commit()
            print(f"\n✅ Updated {updated} companies with slugs")
        else:
            print("\n✓ All companies already have slugs configured")

if __name__ == "__main__":
    asyncio.run(fix_slugs())

