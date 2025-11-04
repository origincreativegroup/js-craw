"""Utility to load companies from CSV as a fallback"""
import csv
import re
import logging
from pathlib import Path
from typing import Dict, Optional, List
from urllib.parse import parse_qs, urlparse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


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


def construct_career_url(company_name: str) -> Optional[str]:
    """Try to construct a career page URL from company name"""
    # Clean company name for URL construction
    clean_name = company_name.split('(')[0].strip()  # Remove parentheticals
    clean_name = clean_name.replace(' Inc.', '').replace(' Inc', '').replace(' LLC', '').replace(' Ltd.', '')
    clean_name = clean_name.replace(',', '').replace('.', '').replace(' ', '').lower()
    
    # Most companies use /careers or /jobs
    return f"https://www.{clean_name}.com/careers"


def parse_companies_csv(csv_path: Path) -> List[Dict]:
    """Parse companies.csv and return list of company dicts"""
    companies = []
    skipped_no_url = []
    
    try:
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
                        logger.debug(f"Constructed URL for {company_name}: {career_url}")
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
            logger.warning(f"Skipped {len(skipped_no_url)} companies without valid HTTP URLs")
    except Exception as e:
        logger.error(f"Error parsing companies.csv: {e}", exc_info=True)
        return []
    
    return companies


async def count_companies(db: AsyncSession, active_only: bool = False) -> int:
    """Count companies in database"""
    try:
        query = select(func.count(Company.id))
        if active_only:
            query = query.where(Company.is_active == True)
        
        result = await db.execute(query)
        return result.scalar() or 0
    except Exception as e:
        logger.error(f"Error counting companies: {e}", exc_info=True)
        return 0


async def load_companies_from_csv(min_companies: int = 10) -> Dict:
    """
    Load companies from companies.csv if database has fewer than min_companies.
    
    Args:
        min_companies: Minimum number of companies to require before loading from CSV
        
    Returns:
        Dictionary with stats about the load operation
    """
    # Find companies.csv file
    project_root = Path(__file__).parent.parent.parent
    csv_path = project_root / "companies.csv"
    
    if not csv_path.exists():
        logger.warning(f"companies.csv not found at {csv_path}")
        return {
            "success": False,
            "reason": "companies.csv not found",
            "added": 0,
            "skipped": 0
        }
    
    async with AsyncSessionLocal() as db:
        # Check current company count
        current_count = await count_companies(db, active_only=True)
        
        if current_count >= min_companies:
            logger.info(f"Database has {current_count} active companies (>= {min_companies}), skipping CSV load")
            return {
                "success": True,
                "reason": "sufficient_companies",
                "current_count": current_count,
                "added": 0,
                "skipped": 0
            }
        
        logger.info(f"Database has only {current_count} active companies, loading from companies.csv...")
        
        # Parse CSV
        companies_data = parse_companies_csv(csv_path)
        
        if not companies_data:
            logger.warning(f"No companies found in {csv_path}")
            return {
                "success": False,
                "reason": "no_companies_in_csv",
                "added": 0,
                "skipped": 0
            }
        
        logger.info(f"Found {len(companies_data)} companies in CSV")
        
        # Load companies
        added_count = 0
        skipped_count = 0
        
        for company_data in companies_data:
            try:
                # Check if company already exists
                result = await db.execute(
                    select(Company).where(Company.name == company_data["name"])
                )
                existing = result.scalar_one_or_none()

                if existing:
                    skipped_count += 1
                    continue

                # Create new company
                company = Company(
                    name=company_data["name"],
                    career_page_url=company_data["career_page_url"],
                    crawler_type=company_data["crawler_type"],
                    crawler_config=company_data["crawler_config"],
                    is_active=True,
                    discovery_source="companies_csv"
                )

                db.add(company)
                await db.commit()
                await db.refresh(company)

                added_count += 1
                logger.debug(f"Added {company.name} (ID: {company.id}, Type: {company.crawler_type})")
            except Exception as e:
                logger.error(f"Error adding company {company_data.get('name', 'unknown')}: {e}")
                await db.rollback()
                skipped_count += 1
        
        # Get final count
        final_count = await count_companies(db, active_only=True)
        
        logger.info(f"Company loading complete: Added {added_count}, Skipped {skipped_count}, Total: {final_count}")
        
        return {
            "success": True,
            "reason": "loaded_from_csv",
            "current_count": current_count,
            "added": added_count,
            "skipped": skipped_count,
            "final_count": final_count
        }

