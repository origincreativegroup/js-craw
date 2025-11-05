"""Utility to load companies from CSV as a fallback"""
import csv
import re
import logging
from pathlib import Path
from typing import Dict, Optional, List, Tuple
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


def extract_url_from_text(text: str) -> Optional[str]:
    """Extract URL from text using regex patterns"""
    if not text:
        return None
    
    # Pattern to match http:// or https:// URLs
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+[^\s<>"{}|\\^`\[\].,;:]'
    
    # Find all URLs in the text
    matches = re.findall(url_pattern, text)
    if matches:
        # Return the first valid URL, cleaning it up
        url = matches[0].rstrip('.,;:')
        # Validate it's a proper URL
        try:
            parsed = urlparse(url)
            if parsed.scheme and parsed.netloc:
                return url
        except Exception:
            pass
    
    # Also check for URLs without scheme (might be in the text)
    # Look for patterns like "company.com/careers" or "company.com/jobs"
    domain_pattern = r'([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.(?:[a-zA-Z]{2,})(?:/[^\s<>"{}|\\^`\[\]]+)?)'
    domain_matches = re.findall(domain_pattern, text)
    for domain in domain_matches:
        if '/careers' in domain.lower() or '/jobs' in domain.lower() or '/career' in domain.lower():
            url = f"https://{domain.split()[0]}"  # Take first part if there are spaces
            try:
                parsed = urlparse(url)
                if parsed.netloc:
                    return url
            except Exception:
                pass
    
    return None


def validate_url(url: str) -> bool:
    """Validate that a URL is properly formatted"""
    if not url or not isinstance(url, str):
        return False
    
    if not url.startswith(('http://', 'https://')):
        return False
    
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        # Basic validation - must have a domain
        if '.' not in parsed.netloc:
            return False
        return True
    except Exception:
        return False


def parse_companies_csv(csv_path: Path) -> Tuple[List[Dict], Dict]:
    """
    Parse companies.csv and return list of company dicts and parsing statistics.
    
    Returns:
        Tuple of (companies list, stats dict with skipped companies and reasons)
    """
    companies = []
    skipped = {
        "no_url": [],
        "invalid_url": [],
        "empty_name": [],
        "parsing_error": []
    }
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):  # Start at 2 because row 1 is header
                try:
                    # Skip empty rows
                    if not row.get('Company Name') or not row.get('Career Page URL'):
                        if not row.get('Company Name'):
                            skipped["empty_name"].append(f"Row {row_num}: Missing company name")
                        continue
                    
                    company_name = row['Company Name'].strip()
                    career_url_raw = row['Career Page URL'].strip()
                    
                    if not company_name:
                        skipped["empty_name"].append(f"Row {row_num}: Empty company name")
                        continue
                    
                    # Try to extract URL from the raw text
                    career_url = extract_url_from_text(career_url_raw)
                    
                    # If no URL found, try to construct one from company name
                    if not career_url:
                        constructed_url = construct_career_url(company_name)
                        if constructed_url:
                            career_url = constructed_url
                            logger.debug(f"Constructed URL for {company_name}: {career_url}")
                        else:
                            skipped["no_url"].append({
                                "name": company_name,
                                "row": row_num,
                                "raw_url": career_url_raw[:100]  # Truncate long URLs
                            })
                            continue
                    
                    # Validate the URL
                    if not validate_url(career_url):
                        skipped["invalid_url"].append({
                            "name": company_name,
                            "row": row_num,
                            "url": career_url[:100]
                        })
                        continue
                    
                    # Detect crawler type and build config
                    crawler_type = detect_crawler_type(career_url)
                    crawler_config = build_crawler_config(company_name, career_url, crawler_type)

                    companies.append({
                        "name": company_name,
                        "career_page_url": career_url,
                        "crawler_type": crawler_type,
                        "crawler_config": crawler_config
                    })
                    
                except Exception as e:
                    logger.error(f"Error parsing row {row_num}: {e}")
                    skipped["parsing_error"].append({
                        "row": row_num,
                        "error": str(e)
                    })
                    continue
        
        # Log summary
        total_skipped = sum(len(v) for v in skipped.values())
        if total_skipped > 0:
            logger.warning(f"Parsed CSV: {len(companies)} companies loaded, {total_skipped} skipped")
            if skipped["no_url"]:
                logger.warning(f"  - {len(skipped['no_url'])} companies without extractable URLs")
            if skipped["invalid_url"]:
                logger.warning(f"  - {len(skipped['invalid_url'])} companies with invalid URLs")
            if skipped["empty_name"]:
                logger.warning(f"  - {len(skipped['empty_name'])} rows with empty company names")
            if skipped["parsing_error"]:
                logger.warning(f"  - {len(skipped['parsing_error'])} rows with parsing errors")
                
    except FileNotFoundError:
        logger.error(f"CSV file not found: {csv_path}")
        return [], {"error": f"File not found: {csv_path}"}
    except Exception as e:
        logger.error(f"Error parsing companies.csv: {e}", exc_info=True)
        return [], {"error": str(e)}
    
    return companies, skipped


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


async def load_companies_from_csv(min_companies: int = 10, force: bool = False) -> Dict:
    """
    Load companies from companies.csv if database has fewer than min_companies.
    
    Args:
        min_companies: Minimum number of companies to require before loading from CSV
        force: If True, load companies even if threshold is met
        
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
            "error": f"File not found at {csv_path}",
            "added": 0,
            "skipped": 0,
            "parsing_stats": {}
        }
    
    async with AsyncSessionLocal() as db:
        # Check current company count
        current_count = await count_companies(db, active_only=True)
        
        if not force and current_count >= min_companies:
            logger.info(f"Database has {current_count} active companies (>= {min_companies}), skipping CSV load")
            return {
                "success": True,
                "reason": "sufficient_companies",
                "current_count": current_count,
                "added": 0,
                "skipped": 0,
                "parsing_stats": {}
            }
        
        if force:
            logger.info(f"Force loading companies from CSV (current count: {current_count})")
        else:
            logger.info(f"Database has only {current_count} active companies, loading from companies.csv...")
        
        # Parse CSV
        companies_data, parsing_stats = parse_companies_csv(csv_path)
        
        if not companies_data:
            error_msg = parsing_stats.get("error", "No companies found in CSV")
            logger.warning(f"No companies found in {csv_path}: {error_msg}")
            return {
                "success": False,
                "reason": "no_companies_in_csv",
                "error": error_msg,
                "added": 0,
                "skipped": 0,
                "parsing_stats": parsing_stats
            }
        
        logger.info(f"Found {len(companies_data)} companies in CSV")
        
        # Load companies
        added_count = 0
        skipped_count = 0
        errors = []
        
        for company_data in companies_data:
            try:
                # Check if company already exists
                result = await db.execute(
                    select(Company).where(Company.name == company_data["name"])
                )
                existing = result.scalar_one_or_none()

                if existing:
                    skipped_count += 1
                    logger.debug(f"Company '{company_data['name']}' already exists (ID: {existing.id})")
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
                error_msg = f"Error adding company {company_data.get('name', 'unknown')}: {e}"
                logger.error(error_msg)
                errors.append({
                    "name": company_data.get('name', 'unknown'),
                    "error": str(e)
                })
                await db.rollback()
                skipped_count += 1
        
        # Get final count
        final_count = await count_companies(db, active_only=True)
        
        logger.info(f"Company loading complete: Added {added_count}, Skipped {skipped_count}, Total: {final_count}")
        
        result = {
            "success": True,
            "reason": "loaded_from_csv",
            "current_count": current_count,
            "added": added_count,
            "skipped": skipped_count,
            "final_count": final_count,
            "parsing_stats": {
                "skipped_no_url": len(parsing_stats.get("no_url", [])),
                "skipped_invalid_url": len(parsing_stats.get("invalid_url", [])),
                "skipped_empty_name": len(parsing_stats.get("empty_name", [])),
                "parsing_errors": len(parsing_stats.get("parsing_error", []))
            }
        }
        
        if errors:
            result["errors"] = errors[:10]  # Include first 10 errors
            result["error_count"] = len(errors)
        
        if parsing_stats:
            # Include sample skipped entries for debugging
            if parsing_stats.get("no_url") and len(parsing_stats["no_url"]) <= 5:
                result["sample_skipped_no_url"] = parsing_stats["no_url"]
            elif parsing_stats.get("no_url"):
                result["sample_skipped_no_url"] = parsing_stats["no_url"][:5]
        
        return result

