"""FastAPI routes"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.models import Job, SearchCriteria, User, FollowUp, CrawlLog, Company, Task, Application, GeneratedDocument
from app.utils.crypto import encrypt_password
from app.crawler.orchestrator import CrawlerOrchestrator
from app.tasks.task_service import TaskService
from app.ai.task_generator import TaskGenerator

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic models for API
class SearchCriteriaCreate(BaseModel):
    name: str
    keywords: str
    location: Optional[str] = None
    remote_only: bool = False
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    target_companies: Optional[List[int]] = None  # List of company IDs
    platforms: List[str] = []  # Deprecated - no longer used, company-based crawling only
    notify_on_new: bool = True


class SearchCriteriaUpdate(BaseModel):
    name: Optional[str] = None
    keywords: Optional[str] = None
    location: Optional[str] = None
    remote_only: Optional[bool] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    target_companies: Optional[List[int]] = None
    platforms: Optional[List[str]] = None  # Deprecated
    notify_on_new: Optional[bool] = None
    is_active: Optional[bool] = None


class UserCredentials(BaseModel):
    platform: str
    email: str
    password: str


class JobUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class FollowUpCreate(BaseModel):
    job_id: int
    follow_up_date: datetime
    action_type: str
    notes: Optional[str] = None


class CompanyCreate(BaseModel):
    name: str
    career_page_url: str
    crawler_type: str = "generic"  # greenhouse, lever, workday, generic
    crawler_config: Optional[dict] = None
    is_active: bool = True


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    career_page_url: Optional[str] = None
    crawler_type: Optional[str] = None
    crawler_config: Optional[dict] = None
    is_active: Optional[bool] = None


class TaskCreate(BaseModel):
    job_id: int
    task_type: str
    title: str
    due_date: Optional[datetime] = None
    priority: Optional[str] = None
    notes: Optional[str] = None


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[datetime] = None
    title: Optional[str] = None
    notes: Optional[str] = None


class TaskSnooze(BaseModel):
    duration: str = "1d"  # 1h, 1d, 3d, 1w


class BulkTaskAction(BaseModel):
    task_ids: List[int]
    action: str  # complete, cancel, snooze


class ApplicationCreate(BaseModel):
    job_id: int
    status: Optional[str] = "queued"  # queued, drafting, submitted, interviewing, rejected, accepted
    application_date: Optional[datetime] = None
    portal_url: Optional[str] = None
    confirmation_number: Optional[str] = None
    resume_version_id: Optional[int] = None
    cover_letter_id: Optional[int] = None
    notes: Optional[str] = None


class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    application_date: Optional[datetime] = None
    portal_url: Optional[str] = None
    confirmation_number: Optional[str] = None
    resume_version_id: Optional[int] = None
    cover_letter_id: Optional[int] = None
    notes: Optional[str] = None


class JobAction(BaseModel):
    action: str  # queue_application, mark_priority, mark_favorite
    metadata: Optional[dict] = None


class DocumentGenerate(BaseModel):
    document_types: List[str] = ["resume", "cover_letter"]  # Can generate one or both


class DocumentUpdate(BaseModel):
    content: str


# Search Criteria endpoints
@router.get("/searches")
async def get_searches(
    db: AsyncSession = Depends(get_db)
):
    """Get all search criteria"""
    try:
        result = await db.execute(select(SearchCriteria).order_by(desc(SearchCriteria.created_at)))
        searches = result.scalars().all()
        return [
            {
                "id": s.id,
                "name": s.name,
                "keywords": s.keywords,
                "location": s.location,
                "remote_only": s.remote_only,
                "job_type": s.job_type,
                "experience_level": s.experience_level,
                "platforms": s.platforms,
                "target_companies": s.target_companies,
                "is_active": s.is_active,
                "notify_on_new": s.notify_on_new,
                "created_at": s.created_at.isoformat(),
            }
            for s in searches
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading searches: {str(e)}")


@router.post("/searches")
async def create_search(
    search: SearchCriteriaCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create new search criteria"""
    try:
        # Validate target_companies if provided
        if search.target_companies:
            result = await db.execute(
                select(Company).where(Company.id.in_(search.target_companies))
            )
            found_companies = result.scalars().all()
            found_ids = {c.id for c in found_companies}
            missing_ids = set(search.target_companies) - found_ids
            if missing_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Companies not found: {list(missing_ids)}"
                )
        
        # Ensure user_id=1 exists
        result = await db.execute(select(User).where(User.id == 1))
        user = result.scalar_one_or_none()
        if not user:
            # Create default user
            default_user = User(
                id=1,
                platform="default",
                email="default@example.com",
                encrypted_password=""
            )
            db.add(default_user)
            try:
                await db.commit()
            except IntegrityError:
                # User might have been created concurrently
                await db.rollback()
        
        # For simplicity, use user_id=1 (you'd want proper auth here)
        new_search = SearchCriteria(
            user_id=1,
            name=search.name,
            keywords=search.keywords,
            location=search.location,
            remote_only=search.remote_only,
            job_type=search.job_type,
            experience_level=search.experience_level,
            salary_min=search.salary_min,
            salary_max=search.salary_max,
            target_companies=search.target_companies,
            platforms=search.platforms or [],
            notify_on_new=search.notify_on_new
        )
        
        db.add(new_search)
        await db.commit()
        await db.refresh(new_search)
        
        return {"id": new_search.id, "message": "Search criteria created"}
    except HTTPException:
        raise
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Database constraint error: {str(e)}")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.patch("/searches/{search_id}")
async def update_search(
    search_id: int,
    update: SearchCriteriaUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update search criteria"""
    result = await db.execute(select(SearchCriteria).where(SearchCriteria.id == search_id))
    search = result.scalar_one_or_none()
    
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    
    # Update fields
    for field, value in update.dict(exclude_unset=True).items():
        setattr(search, field, value)
    
    await db.commit()
    return {"message": "Search updated"}


@router.delete("/searches/{search_id}")
async def delete_search(
    search_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete search criteria"""
    result = await db.execute(select(SearchCriteria).where(SearchCriteria.id == search_id))
    search = result.scalar_one_or_none()
    
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    
    await db.delete(search)
    await db.commit()
    
    return {"message": "Search deleted"}


# Company endpoints
@router.get("/companies")
async def get_companies(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Get all companies"""
    try:
        query = select(Company).order_by(Company.name)
        if active_only:
            query = query.where(Company.is_active == True)
        
        result = await db.execute(query)
        companies = result.scalars().all()
        
        return [
            {
                "id": c.id,
                "name": c.name,
                "career_page_url": c.career_page_url,
                "crawler_type": c.crawler_type,
                "crawler_config": c.crawler_config,
                "is_active": c.is_active,
                "last_crawled_at": c.last_crawled_at.isoformat() if c.last_crawled_at else None,
                "jobs_found_total": c.jobs_found_total,
                "created_at": c.created_at.isoformat(),
                "consecutive_empty_crawls": c.consecutive_empty_crawls,
                "viability_score": c.viability_score,
                "viability_last_checked": c.viability_last_checked.isoformat() if c.viability_last_checked else None,
                "discovery_source": c.discovery_source,
                "last_successful_crawl": c.last_successful_crawl.isoformat() if c.last_successful_crawl else None,
                "priority_score": c.priority_score,
            }
            for c in companies
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading companies: {str(e)}")


@router.get("/companies/health")
async def get_company_health(
    db: AsyncSession = Depends(get_db)
):
    """Get overall company list health metrics"""
    try:
        from sqlalchemy import func
        
        # Total companies
        result = await db.execute(select(func.count(Company.id)))
        total = result.scalar() or 0
        
        # Active companies
        result = await db.execute(
            select(func.count(Company.id)).where(Company.is_active == True)
        )
        active = result.scalar() or 0
        
        # Companies with high consecutive empty crawls
        result = await db.execute(
            select(func.count(Company.id)).where(
                Company.is_active == True,
                Company.consecutive_empty_crawls >= 2
            )
        )
        needs_attention = result.scalar() or 0
        
        # Companies needing viability check
        result = await db.execute(
            select(func.count(Company.id)).where(
                Company.is_active == True,
                Company.viability_last_checked.is_(None)
            )
        )
        unchecked = result.scalar() or 0
        
        # Average viability score
        result = await db.execute(
            select(func.avg(Company.viability_score)).where(
                Company.is_active == True,
                Company.viability_score.isnot(None)
            )
        )
        avg_viability = result.scalar() or 0.0
        
        return {
            "total_companies": total,
            "active_companies": active,
            "inactive_companies": total - active,
            "needs_attention": needs_attention,
            "unchecked_viability": unchecked,
            "average_viability_score": round(avg_viability, 2) if avg_viability else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading company health: {str(e)}")


@router.get("/companies/discovery/status")
async def get_discovery_status(
    db: AsyncSession = Depends(get_db)
):
    """Get company discovery status and statistics"""
    try:
        from app.models import PendingCompany
        from app.utils.company_loader import count_companies
        from app.config import settings
        
        # Get company counts
        total_companies = await count_companies(db, active_only=False)
        active_companies = await count_companies(db, active_only=True)
        
        # Get pending companies
        pending_result = await db.execute(
            select(func.count(PendingCompany.id)).where(PendingCompany.status == "pending")
        )
        pending_count = pending_result.scalar() or 0
        
        # Get recent pending companies
        recent_pending_result = await db.execute(
            select(PendingCompany)
            .where(PendingCompany.status == "pending")
            .order_by(desc(PendingCompany.created_at))
            .limit(5)
        )
        recent_pending = recent_pending_result.scalars().all()
        
        return {
            "total_companies": total_companies,
            "active_companies": active_companies,
            "target_companies": getattr(settings, "COMPANY_TARGET_COUNT", 4000),
            "pending_count": pending_count,
            "discovery_enabled": getattr(settings, "COMPANY_DISCOVERY_ENABLED", True),
            "discovery_interval_hours": getattr(settings, "COMPANY_DISCOVERY_INTERVAL_HOURS", 6),
            "auto_approve_threshold": getattr(settings, "COMPANY_AUTO_APPROVE_THRESHOLD", 70.0),
            "recent_pending": [
                {
                    "id": p.id,
                    "name": p.name,
                    "career_page_url": p.career_page_url,
                    "discovery_source": p.discovery_source,
                    "confidence_score": p.confidence_score,
                    "created_at": p.created_at.isoformat()
                }
                for p in recent_pending
            ]
        }
    except Exception as e:
        logger.error(f"Error getting discovery status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting discovery status: {str(e)}")


@router.get("/companies/pending")
async def get_pending_companies(
    limit: int = Query(100, description="Maximum number of pending companies to return"),
    db: AsyncSession = Depends(get_db)
):
    """Get all pending companies awaiting approval"""
    try:
        from app.models import PendingCompany
        
        result = await db.execute(
            select(PendingCompany)
            .where(PendingCompany.status == "pending")
            .order_by(desc(PendingCompany.confidence_score))
            .limit(limit)
        )
        pending_companies = result.scalars().all()
        
        return [
            {
                "id": p.id,
                "name": p.name,
                "career_page_url": p.career_page_url,
                "discovery_source": p.discovery_source,
                "confidence_score": p.confidence_score,
                "crawler_type": p.crawler_type,
                "crawler_config": p.crawler_config,
                "discovery_metadata": p.discovery_metadata,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat()
            }
            for p in pending_companies
        ]
    except Exception as e:
        logger.error(f"Error getting pending companies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting pending companies: {str(e)}")


@router.post("/companies/pending/{pending_id}/approve")
async def approve_pending_company(
    pending_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Approve a pending company and add it to the companies table"""
    try:
        from app.services.company_discovery_service import approve_pending_company
        
        result = await approve_pending_company(pending_id, db)
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to approve company"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving pending company: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error approving pending company: {str(e)}")


@router.post("/companies/pending/{pending_id}/reject")
async def reject_pending_company(
    pending_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Reject a pending company"""
    try:
        from app.services.company_discovery_service import reject_pending_company
        
        result = await reject_pending_company(pending_id, db)
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to reject company"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting pending company: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error rejecting pending company: {str(e)}")


@router.post("/companies/{company_id}/analyze-viability")
async def analyze_company_viability(
    company_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Analyze viability of a single company"""
    try:
        from app.services.company_lifecycle import CompanyLifecycleManager
        
        lifecycle_manager = CompanyLifecycleManager()
        result = await lifecycle_manager.analyze_single_company(company_id)
        
        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing company: {str(e)}")



@router.get("/companies/{company_id}")
async def get_company(
    company_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get company details"""
    try:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        return {
            "id": company.id,
            "name": company.name,
            "career_page_url": company.career_page_url,
            "crawler_type": company.crawler_type,
            "crawler_config": company.crawler_config,
            "is_active": company.is_active,
            "last_crawled_at": company.last_crawled_at.isoformat() if company.last_crawled_at else None,
            "jobs_found_total": company.jobs_found_total,
            "created_at": company.created_at.isoformat(),
            "updated_at": company.updated_at.isoformat(),
            "consecutive_empty_crawls": company.consecutive_empty_crawls,
            "viability_score": company.viability_score,
            "viability_last_checked": company.viability_last_checked.isoformat() if company.viability_last_checked else None,
            "discovery_source": company.discovery_source,
            "last_successful_crawl": company.last_successful_crawl.isoformat() if company.last_successful_crawl else None,
            "priority_score": company.priority_score,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading company: {str(e)}")


@router.post("/companies")
async def create_company(
    company: CompanyCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create new company"""
    try:
        new_company = Company(
            name=company.name,
            career_page_url=company.career_page_url,
            crawler_type=company.crawler_type,
            crawler_config=company.crawler_config,
            is_active=company.is_active
        )
        
        db.add(new_company)
        await db.commit()
        await db.refresh(new_company)
        
        return {"id": new_company.id, "message": "Company created"}
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Company already exists or constraint error: {str(e)}")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating company: {str(e)}")


@router.post("/companies/load-from-csv")
async def load_companies_from_csv_endpoint(
    force: bool = Query(False, description="Force reload even if sufficient companies exist"),
    min_companies: int = Query(10, description="Minimum companies required before loading")
):
    """
    Load companies from companies.csv file.
    
    Args:
        force: If True, load even if database has sufficient companies
        min_companies: Minimum number of companies required before loading (ignored if force=True)
    
    Returns:
        Result of the load operation with detailed statistics
    """
    try:
        from app.utils.company_loader import load_companies_from_csv
        
        result = await load_companies_from_csv(
            min_companies=min_companies,
            force=force
        )
        
        if not result.get("success"):
            error_detail = result.get("error") or result.get("reason", "unknown error")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to load companies: {error_detail}",
                headers={"X-Error-Details": str(result)}
            )
        
        return {
            "message": "Companies loaded successfully",
            **result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading companies from CSV: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error loading companies: {str(e)}")


@router.get("/companies/diagnose")
async def diagnose_companies(
    db: AsyncSession = Depends(get_db)
):
    """
    Diagnostic endpoint to check company loading status and identify issues.
    
    Returns:
        Detailed diagnostic information about companies, CSV file, and loading status
    """
    try:
        from app.utils.company_loader import count_companies, parse_companies_csv
        from pathlib import Path
        
        # Get company counts
        total_count = await count_companies(db, active_only=False)
        active_count = await count_companies(db, active_only=True)
        
        # Check CSV file
        project_root = Path(__file__).parent.parent.parent
        csv_path = project_root / "companies.csv"
        csv_exists = csv_path.exists()
        
        csv_stats = {
            "exists": csv_exists,
            "path": str(csv_path),
            "readable": False,
            "parseable": False,
            "companies_found": 0,
            "parsing_errors": {}
        }
        
        if csv_exists:
            try:
                # Test if file is readable
                with open(csv_path, 'r', encoding='utf-8') as f:
                    csv_stats["readable"] = True
                
                # Try to parse it
                companies_data, parsing_stats = parse_companies_csv(csv_path)
                csv_stats["parseable"] = True
                csv_stats["companies_found"] = len(companies_data)
                csv_stats["parsing_errors"] = {
                    "no_url": len(parsing_stats.get("no_url", [])),
                    "invalid_url": len(parsing_stats.get("invalid_url", [])),
                    "empty_name": len(parsing_stats.get("empty_name", [])),
                    "parsing_error": len(parsing_stats.get("parsing_error", []))
                }
                # Include sample errors if any
                if parsing_stats.get("no_url"):
                    csv_stats["sample_no_url"] = parsing_stats["no_url"][:5]
            except Exception as e:
                csv_stats["parse_error"] = str(e)
                logger.error(f"Error parsing CSV during diagnosis: {e}")
        
        # Check database connection
        db_status = "connected"
        try:
            await db.execute(select(func.count(Company.id)))
        except Exception as e:
            db_status = f"error: {str(e)}"
        
        # Get recent companies
        recent_companies_result = await db.execute(
            select(Company)
            .order_by(desc(Company.created_at))
            .limit(5)
        )
        recent_companies = recent_companies_result.scalars().all()
        
        diagnosis = {
            "database": {
                "status": db_status,
                "total_companies": total_count,
                "active_companies": active_count,
                "inactive_companies": total_count - active_count
            },
            "csv_file": csv_stats,
            "recent_companies": [
                {
                    "id": c.id,
                    "name": c.name,
                    "crawler_type": c.crawler_type,
                    "is_active": c.is_active,
                    "created_at": c.created_at.isoformat() if c.created_at else None
                }
                for c in recent_companies
            ],
            "recommendations": []
        }
        
        # Generate recommendations
        if active_count == 0:
            diagnosis["recommendations"].append({
                "severity": "critical",
                "message": "No active companies found. Load companies from CSV using /api/companies/load-from-csv",
                "action": "POST /api/companies/load-from-csv?force=true"
            })
        elif active_count < 10:
            diagnosis["recommendations"].append({
                "severity": "warning",
                "message": f"Only {active_count} active companies. Consider loading more from CSV.",
                "action": "POST /api/companies/load-from-csv?force=true"
            })
        
        if not csv_exists:
            diagnosis["recommendations"].append({
                "severity": "error",
                "message": f"CSV file not found at {csv_path}",
                "action": "Ensure companies.csv exists in the project root"
            })
        elif csv_stats.get("companies_found", 0) == 0:
            diagnosis["recommendations"].append({
                "severity": "warning",
                "message": "CSV file exists but no companies were parsed. Check CSV format.",
                "action": "Review CSV parsing errors in csv_file.parsing_errors"
            })
        
        if csv_stats.get("parsing_errors", {}).get("no_url", 0) > 0:
            diagnosis["recommendations"].append({
                "severity": "info",
                "message": f"{csv_stats['parsing_errors']['no_url']} companies in CSV have no extractable URLs",
                "action": "Review sample_no_url entries to fix CSV data"
            })
        
        return diagnosis
        
    except Exception as e:
        logger.error(f"Error in company diagnosis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error running diagnosis: {str(e)}")


@router.patch("/companies/{company_id}")
async def update_company(
    company_id: int,
    update: CompanyUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update company"""
    try:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Update fields
        for field, value in update.dict(exclude_unset=True).items():
            setattr(company, field, value)
        
        await db.commit()
        return {"message": "Company updated"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating company: {str(e)}")


@router.delete("/companies/{company_id}")
async def delete_company(
    company_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete company"""
    try:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        await db.delete(company)
        await db.commit()
        
        return {"message": "Company deleted"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting company: {str(e)}")


# Company lifecycle management endpoints
@router.post("/companies/discover")
async def discover_companies(
    keywords: Optional[str] = Query(None, description="Search keywords"),
    max_companies: int = Query(50, description="Maximum companies to discover"),
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger company discovery (preview only - doesn't insert)"""
    try:
        from app.crawler.company_discovery import CompanyDiscoveryService
        
        # Get existing company names for deduplication
        result = await db.execute(select(Company.name))
        existing_names = {row[0].lower() for row in result.fetchall()}
        
        discovery_service = CompanyDiscoveryService()
        discovered = await discovery_service.discover_companies(
            keywords=keywords,
            max_companies=max_companies,
            existing_company_names=existing_names
        )
        
        return {
            "discovered": len(discovered),
            "companies": discovered[:10]  # Return first 10 for preview
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error discovering companies: {str(e)}")


@router.post("/companies/discover/run")
async def run_company_discovery(
    keywords: Optional[str] = Query(None, description="Search keywords"),
    max_companies: int = Query(50, description="Maximum companies to discover"),
    db: AsyncSession = Depends(get_db)
):
    """Run company discovery and automatically process/insert discovered companies"""
    try:
        from app.crawler.company_discovery import CompanyDiscoveryService
        from app.services.company_discovery_service import process_and_insert_discovered_companies
        
        # Get existing company names for deduplication
        result = await db.execute(select(Company.name))
        existing_names = {row[0].lower() for row in result.fetchall()}
        
        # Discover companies
        discovery_service = CompanyDiscoveryService()
        discovered = await discovery_service.discover_companies(
            keywords=keywords,
            max_companies=max_companies,
            existing_company_names=existing_names
        )
        
        if not discovered:
            return {
                "message": "No new companies discovered",
                "discovered": 0,
                "auto_approved": 0,
                "pending_added": 0,
                "skipped_existing": 0
            }
        
        # Process and insert discovered companies
        result = await process_and_insert_discovered_companies(discovered, db)
        
        return {
            "message": "Company discovery and processing completed",
            "discovered": len(discovered),
            **result
        }
    except Exception as e:
        logger.error(f"Error running company discovery: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error running company discovery: {str(e)}")


@router.post("/automation/company-refresh")
async def trigger_company_refresh(
    db: AsyncSession = Depends(get_db)
):
    """Trigger daily company refresh workflow"""
    try:
        from app.services.company_lifecycle import CompanyLifecycleManager
        
        lifecycle_manager = CompanyLifecycleManager()
        summary = await lifecycle_manager.refresh_company_list()
        
        return {
            "message": "Company refresh completed",
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing companies: {str(e)}")


@router.get("/automation/company-refresh-config")
async def get_company_refresh_config():
    """Get company refresh configuration"""
    from app.config import settings
    
    return {
        "target_count": settings.COMPANY_TARGET_COUNT,
        "discovery_batch_size": settings.COMPANY_DISCOVERY_BATCH_SIZE,
        "consecutive_empty_threshold": settings.CONSECUTIVE_EMPTY_THRESHOLD,
        "viability_score_threshold": settings.VIABILITY_SCORE_THRESHOLD,
        "refresh_schedule": settings.COMPANY_REFRESH_SCHEDULE,
        "web_search_enabled": settings.WEB_SEARCH_ENABLED
    }


class CompanyRefreshConfigUpdate(BaseModel):
    target_count: Optional[int] = None
    discovery_batch_size: Optional[int] = None
    consecutive_empty_threshold: Optional[int] = None
    viability_score_threshold: Optional[float] = None
    web_search_enabled: Optional[bool] = None


@router.patch("/automation/company-refresh-config")
async def update_company_refresh_config(
    update: CompanyRefreshConfigUpdate
):
    """Update company refresh configuration"""
    from app.config import settings
    
    # Update settings (in-memory only, doesn't persist to .env)
    if update.target_count is not None:
        settings.COMPANY_TARGET_COUNT = update.target_count
    if update.discovery_batch_size is not None:
        settings.COMPANY_DISCOVERY_BATCH_SIZE = update.discovery_batch_size
    if update.consecutive_empty_threshold is not None:
        settings.CONSECUTIVE_EMPTY_THRESHOLD = update.consecutive_empty_threshold
    if update.viability_score_threshold is not None:
        settings.VIABILITY_SCORE_THRESHOLD = update.viability_score_threshold
    if update.web_search_enabled is not None:
        settings.WEB_SEARCH_ENABLED = update.web_search_enabled
    
    return {
        "message": "Configuration updated",
        "config": {
            "target_count": settings.COMPANY_TARGET_COUNT,
            "discovery_batch_size": settings.COMPANY_DISCOVERY_BATCH_SIZE,
            "consecutive_empty_threshold": settings.CONSECUTIVE_EMPTY_THRESHOLD,
            "viability_score_threshold": settings.VIABILITY_SCORE_THRESHOLD,
            "refresh_schedule": settings.COMPANY_REFRESH_SCHEDULE,
            "web_search_enabled": settings.WEB_SEARCH_ENABLED
        }
    }


# Job endpoints
@router.get("/jobs")
async def get_jobs(
    status: Optional[str] = None,
    search_id: Optional[int] = None,
    new_only: bool = False,
    match: Optional[str] = Query(None, description="Filter by match score: 'high' (>=75), 'medium' (50-74), 'low' (<50)"),
    ready_to_apply: Optional[bool] = Query(None, description="Filter jobs ready to apply (match_score >= 70)"),
    sort: Optional[str] = Query("discovered_at", description="Sort field: 'discovered_at', 'ai_match_score', 'posted_date'"),
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get jobs with filters"""
    # Determine sort order
    if sort == "ai_match_score":
        query = select(Job).order_by(desc(Job.ai_match_score))
    elif sort == "posted_date":
        query = select(Job).order_by(desc(Job.posted_date))
    else:  # default to discovered_at
        query = select(Job).order_by(desc(Job.discovered_at))
    
    if status:
        query = query.where(Job.status == status)
    if search_id:
        query = query.where(Job.search_criteria_id == search_id)
    if new_only:
        query = query.where(Job.is_new == True)
    if match == "high":
        query = query.where(Job.ai_match_score >= 75)
    elif match == "medium":
        query = query.where(Job.ai_match_score >= 50, Job.ai_match_score < 75)
    elif match == "low":
        query = query.where(Job.ai_match_score < 50)
    if ready_to_apply is not None:
        if ready_to_apply:
            query = query.where(Job.ai_match_score >= 70)
        else:
            query = query.where((Job.ai_match_score < 70) | (Job.ai_match_score.is_(None)))
    
    query = query.limit(limit)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return [
        {
            "id": j.id,
            "title": j.title,
            "company": j.company,
            "location": j.location,
            "platform": j.platform,
            "url": j.url,
            "status": j.status,
            "is_new": j.is_new,
            "description": j.description,
            "ai_match_score": j.ai_match_score,
            "ai_summary": j.ai_summary,
            "ai_pros": j.ai_pros,
            "ai_cons": j.ai_cons,
            "ai_keywords_matched": j.ai_keywords_matched,
            "posted_date": j.posted_date.isoformat() if j.posted_date else None,
            "discovered_at": j.discovered_at.isoformat(),
        }
        for j in jobs
    ]


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get job details"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Mark as viewed
    if job.is_new:
        job.is_new = False
        await db.commit()
    
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "platform": job.platform,
        "job_type": job.job_type,
        "url": job.url,
        "description": job.description,
        "status": job.status,
        "notes": job.notes,
        "ai_match_score": job.ai_match_score,
        "ai_summary": job.ai_summary,
        "ai_pros": job.ai_pros,
        "ai_cons": job.ai_cons,
        "ai_keywords_matched": job.ai_keywords_matched,
        "posted_date": job.posted_date.isoformat() if job.posted_date else None,
        "discovered_at": job.discovered_at.isoformat(),
    }


@router.post("/jobs/{job_id}/analyze")
async def analyze_job(
    job_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Re-analyze a job with enhanced company profile analysis.

    Persists a concise AI summary on the job and returns non-persisted
    suggested next steps for user action.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        from app.ai.analyzer import JobAnalyzer
        from app.ai.suggestions import build_next_steps
        analyzer = JobAnalyzer()
        
        job_data = {
            'title': job.title,
            'company': job.company,
            'location': job.location,
            'job_type': job.job_type,
            'description': job.description or ''
        }
        
        # Run enhanced company profile analysis
        profile_analysis = await analyzer.analyze_company_job_profile(job_data, job.company)
        # Derive a concise AI summary for the job card
        role_summary = (profile_analysis.get("role_summary") or "").strip()
        company_profile = (profile_analysis.get("company_profile") or "").strip()
        if role_summary:
            derived_summary = role_summary
        elif company_profile:
            derived_summary = company_profile
        else:
            derived_summary = f"{job.title} at {job.company}."

        # Persist summary on job
        job.ai_summary = derived_summary[:600]
        await db.commit()

        # Build suggested next steps (not persisted)
        suggested_next_steps = build_next_steps(job, profile_analysis)

        return {
            "job_id": job.id,
            "analysis": profile_analysis,
            "suggested_next_steps": suggested_next_steps,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing job: {str(e)}")


@router.patch("/jobs/{job_id}")
async def update_job(
    job_id: int,
    update: JobUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update job status/notes"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if update.status:
        job.status = update.status
    if update.notes is not None:
        job.notes = update.notes
    
    await db.commit()
    return {"message": "Job updated"}


# Follow-up endpoints
@router.post("/followups")
async def create_followup(
    followup: FollowUpCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create follow-up reminder"""
    new_followup = FollowUp(
        job_id=followup.job_id,
        follow_up_date=followup.follow_up_date,
        action_type=followup.action_type,
        notes=followup.notes
    )
    
    db.add(new_followup)
    await db.commit()
    
    return {"id": new_followup.id, "message": "Follow-up created"}


@router.get("/followups")
async def get_followups(
    upcoming_only: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """Get follow-ups"""
    query = select(FollowUp).order_by(FollowUp.follow_up_date)
    
    if upcoming_only:
        query = query.where(
            FollowUp.completed == False,
            FollowUp.follow_up_date >= datetime.utcnow()
        )
    
    result = await db.execute(query)
    followups = result.scalars().all()
    
    return [
        {
            "id": f.id,
            "job_id": f.job_id,
            "follow_up_date": f.follow_up_date.isoformat(),
            "action_type": f.action_type,
            "notes": f.notes,
            "completed": f.completed,
        }
        for f in followups
    ]


@router.get("/followups/recommendations")
async def get_followup_recommendations(
    db: AsyncSession = Depends(get_db)
):
    """Get follow-up recommendations for the next 24 hours"""
    try:
        now = datetime.utcnow()
        next_24h = now + timedelta(hours=24)
        
        recommendations = []
        
        # 1. Jobs with status "applied" that don't have a follow-up scheduled
        applied_jobs_query = select(Job).where(
            Job.status == "applied",
            Job.is_new == False
        )
        applied_jobs = (await db.execute(applied_jobs_query)).scalars().all()
        
        # Get existing follow-ups for these jobs
        job_ids = [j.id for j in applied_jobs]
        jobs_with_followups = set()
        if job_ids:
            existing_followups_query = select(FollowUp).where(
                FollowUp.job_id.in_(job_ids),
                FollowUp.completed == False
            )
            existing_followups = (await db.execute(existing_followups_query)).scalars().all()
            jobs_with_followups = {f.job_id for f in existing_followups}
        
        # Jobs needing follow-up
        for job in applied_jobs:
            if job.id not in jobs_with_followups:
                recommendations.append({
                    "type": "follow_up",
                    "priority": "high",
                    "job_id": job.id,
                    "job_title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "applied_at": job.updated_at.isoformat() if job.updated_at else None,
                    "suggested_action": "Schedule follow-up email or call",
                    "ai_match_score": job.ai_match_score,
                })
        
        # 2. Upcoming follow-ups (next 24 hours)
        upcoming_followups_query = select(FollowUp).where(
            FollowUp.completed == False,
            FollowUp.follow_up_date >= now,
            FollowUp.follow_up_date <= next_24h
        ).order_by(FollowUp.follow_up_date)
        upcoming_followups = (await db.execute(upcoming_followups_query)).scalars().all()
        
        for followup in upcoming_followups:
            job_query = select(Job).where(Job.id == followup.job_id)
            job = (await db.execute(job_query)).scalar_one_or_none()
            
            if job:
                recommendations.append({
                    "type": "upcoming_followup",
                    "priority": "high" if (followup.follow_up_date - now).total_seconds() < 3600 else "medium",
                    "followup_id": followup.id,
                    "job_id": job.id,
                    "job_title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "follow_up_date": followup.follow_up_date.isoformat(),
                    "action_type": followup.action_type,
                    "notes": followup.notes,
                    "suggested_action": f"Follow up: {followup.action_type}",
                })
        
        # 3. High-match jobs that haven't been applied to
        high_match_jobs_query = select(Job).where(
            Job.ai_match_score >= 75,
            Job.status == "new"
        ).order_by(desc(Job.ai_match_score)).limit(10)
        high_match_jobs = (await db.execute(high_match_jobs_query)).scalars().all()
        
        for job in high_match_jobs:
            recommendations.append({
                "type": "apply_now",
                "priority": "medium",
                "job_id": job.id,
                "job_title": job.title,
                "company": job.company,
                "location": job.location,
                "ai_match_score": job.ai_match_score,
                "discovered_at": job.discovered_at.isoformat(),
                "suggested_action": "Apply now - high match score",
            })
        
        # Sort by priority (high first, then by date)
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: (priority_order.get(x.get("priority", "low"), 2), x.get("follow_up_date") or x.get("discovered_at") or ""))
        
        return recommendations
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading recommendations: {str(e)}")


# Credentials endpoints
@router.post("/credentials")
async def save_credentials(
    creds: UserCredentials,
    db: AsyncSession = Depends(get_db)
):
    """Save platform credentials"""
    # Check if credentials exist
    result = await db.execute(
        select(User).where(User.platform == creds.platform)
    )
    user = result.scalar_one_or_none()
    
    encrypted = encrypt_password(creds.password)
    
    if user:
        user.email = creds.email
        user.encrypted_password = encrypted
    else:
        user = User(
            platform=creds.platform,
            email=creds.email,
            encrypted_password=encrypted
        )
        db.add(user)
    
    await db.commit()
    return {"message": f"{creds.platform} credentials saved"}


# Manual crawl trigger
@router.post("/crawl/run")
async def trigger_crawl(
    request: Request,
    crawl_type: Optional[str] = Query(None, description="Crawl type: 'searches' or 'all' (default: 'all')"),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger a crawl.
    
    By default, crawls ALL companies (recommended). If crawl_type="searches", runs
    search-based crawling when active searches exist.
    
    Query params:
        crawl_type: "searches" (default) or "all"
    """
    try:
        orchestrator = request.app.state.crawler
        
        # Check if companies exist before crawling
        active_companies_result = await db.execute(
            select(func.count(Company.id)).where(Company.is_active == True)
        )
        active_companies_count = active_companies_result.scalar() or 0
        
        if active_companies_count == 0:
            raise HTTPException(
                status_code=400,
                detail="No active companies found. Please load companies first using POST /api/companies/load-from-csv"
            )
        
        # Default to "all" if not specified
        if crawl_type is None or crawl_type == "all":
            # Base crawling: crawl all companies and use AI to filter
            try:
                results = await orchestrator.crawl_all_companies()
                return {
                    "message": "Universal crawl completed (all companies crawled, AI-filtered)",
                    "new_jobs": len(results),
                    "crawl_type": "universal",
                    "companies_crawled": active_companies_count
                }
            except Exception as e:
                logger.error(f"Error during universal crawl: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Crawl failed: {str(e)}. Check logs for details."
                )
        elif crawl_type == "searches":
            # Check if there are active searches
            searches_result = await db.execute(
                select(func.count(SearchCriteria.id)).where(SearchCriteria.is_active == True)
            )
            active_searches_count = searches_result.scalar() or 0
            
            if active_searches_count == 0:
                raise HTTPException(
                    status_code=400,
                    detail="No active searches found. Create a search first using POST /api/searches, or use crawl_type='all' to crawl all companies."
                )
            
            # Search-based crawling: run all active searches
            try:
                results = await orchestrator.run_all_searches()
                return {
                    "message": "Search-based crawl completed",
                    "new_jobs": len(results),
                    "crawl_type": "searches",
                    "companies_crawled": active_companies_count,
                    "searches_run": active_searches_count
                }
            except Exception as e:
                logger.error(f"Error during search-based crawl: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Crawl failed: {str(e)}. Check logs for details."
                )
        else:
            raise HTTPException(status_code=400, detail=f"Invalid crawl_type: {crawl_type}. Use 'searches' or 'all'")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in crawl trigger: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.post("/crawl/cancel")
async def cancel_crawl(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Cancel any running crawl and prevent overlap."""
    try:
        orchestrator = request.app.state.crawler
        # Signal orchestrator to cancel cooperatively
        orchestrator._cancel_requested = True

        # Mark any running crawl logs as failed/cancelled
        result = await db.execute(
            select(CrawlLog).where(CrawlLog.status == 'running')
        )
        running_logs = result.scalars().all()
        for log in running_logs:
            log.status = 'failed'
            log.completed_at = datetime.utcnow()
            log.error_message = (log.error_message or '') + "\nCancelled by user"
        await db.commit()

        return {"message": f"Cancellation signaled. Marked {len(running_logs)} running logs as cancelled."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling crawl: {str(e)}")


# Dashboard statistics
@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics"""
    try:
        # Total jobs
        result = await db.execute(select(Job))
        total_jobs = len(result.scalars().all())
        
        # New jobs (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        result = await db.execute(
            select(Job).where(Job.discovered_at >= yesterday)
        )
        new_jobs_24h = len(result.scalars().all())
        
        # Jobs by status
        result = await db.execute(select(Job))
        all_jobs = result.scalars().all()
        by_status = {}
        for job in all_jobs:
            status_val = job.status or "new"
            by_status[status_val] = by_status.get(status_val, 0) + 1
        
        # Active searches
        result = await db.execute(
            select(SearchCriteria).where(SearchCriteria.is_active == True)
        )
        active_searches = len(result.scalars().all())
        
        return {
            "total_jobs": total_jobs,
            "new_jobs_24h": new_jobs_24h,
            "jobs_by_status": by_status,
            "active_searches": active_searches
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading statistics: {str(e)}")


# Crawl status endpoint
@router.get("/crawl/status")
async def get_crawl_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, description="Number of recent crawl logs to return")
):
    """Get recent crawl status and logs with enhanced telemetry"""
    try:
        orchestrator = request.app.state.crawler
        
        # Get recent crawl logs
        result = await db.execute(
            select(CrawlLog)
            .order_by(desc(CrawlLog.started_at))
            .limit(limit)
        )
        logs = result.scalars().all()
        
        # Check for any running crawls
        running_result = await db.execute(
            select(CrawlLog).where(CrawlLog.status == 'running')
        )
        running_logs = running_result.scalars().all()
        
        # Get summary statistics
        total_companies = await db.execute(
            select(func.count(Company.id)).where(Company.is_active == True)
        )
        active_companies = total_companies.scalar() or 0
        
        # Get orchestrator progress
        progress = orchestrator.get_current_progress()
        
        # Get crawler type breakdown from recent logs
        crawler_type_stats = {}
        for log in logs[:50]:  # Analyze last 50 logs
            if log.company_id:
                company_result = await db.execute(
                    select(Company).where(Company.id == log.company_id)
                )
                company = company_result.scalar_one_or_none()
                if company:
                    crawler_class = orchestrator.get_crawler_type_classification(company.crawler_type)
                    if crawler_class not in crawler_type_stats:
                        crawler_type_stats[crawler_class] = {'total': 0, 'success': 0, 'failed': 0, 'avg_duration': 0}
                    crawler_type_stats[crawler_class]['total'] += 1
                    if log.status == 'completed':
                        crawler_type_stats[crawler_class]['success'] += 1
                    elif log.status == 'failed':
                        crawler_type_stats[crawler_class]['failed'] += 1
                    if log.completed_at and log.started_at:
                        duration = (log.completed_at - log.started_at).total_seconds()
                        # Simple moving average
                        current_avg = crawler_type_stats[crawler_class]['avg_duration']
                        count = crawler_type_stats[crawler_class]['total']
                        crawler_type_stats[crawler_class]['avg_duration'] = (current_avg * (count - 1) + duration) / count
        
        # Calculate health metrics
        health_metrics = {}
        for crawler_type, stats in crawler_type_stats.items():
            success_rate = (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0
            health_metrics[crawler_type] = {
                'success_rate': round(success_rate, 1),
                'avg_duration_seconds': round(stats['avg_duration'], 1),
                'error_count': stats['failed'],
                'total_runs': stats['total']
            }
        
        return {
            "is_running": len(running_logs) > 0,
            "running_count": len(running_logs),
            "queue_length": progress.get('queue_length', 0),
            "current_company": progress.get('current_company'),
            "progress": progress.get('progress', {'current': 0, 'total': 0}),
            "eta_seconds": progress.get('eta_seconds'),
            "run_type": progress.get('run_type'),
            "recent_logs": [
                {
                    "id": log.id,
                    "company_id": log.company_id,
                    "search_criteria_id": log.search_criteria_id,
                    "platform": log.platform,
                    "status": log.status,
                    "started_at": log.started_at.isoformat() if log.started_at else None,
                    "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                    "jobs_found": log.jobs_found,
                    "new_jobs": log.new_jobs,
                    "error_message": log.error_message,
                    "duration_seconds": (log.completed_at - log.started_at).total_seconds() if log.completed_at and log.started_at else None
                }
                for log in logs
            ],
            "active_companies": active_companies,
            "crawler_health": health_metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading crawl status: {str(e)}")


# Crawl metrics: expose policy registry breaker/rate states
@router.get("/crawl/metrics")
async def get_crawl_metrics(request: Request):
    try:
        orchestrator = request.app.state.crawler
        return {"policies": orchestrator.get_policy_metrics()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Single-company crawl test (debug)
@router.post("/companies/{company_id}/crawl-test")
async def crawl_test_company(company_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    orchestrator = request.app.state.crawler
    try:
        jobs, method_used = await orchestrator.fallback_manager.crawl_with_fallback(company)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Crawl failed: {e}")

    return {
        "company": {"id": company.id, "name": company.name},
        "method": method_used,
        "jobs_found": len(jobs),
        "sample": jobs[:5],
    }


# Scheduler metadata endpoint
@router.get("/automation/scheduler")
async def get_scheduler_metadata(request: Request):
    """Get scheduler status and metadata"""
    try:
        scheduler = request.app.state.scheduler
        from app.config import settings
        
        job = scheduler.get_job("crawl_all_companies")
        
        if not job:
            return {
                "status": "not_configured",
                "next_run": None,
                "interval_minutes": None,
                "is_paused": True
            }
        
        next_run = job.next_run_time.isoformat() if job.next_run_time else None
        
        return {
            "status": "running" if scheduler.running else "stopped",
            "next_run": next_run,
            "interval_minutes": settings.CRAWL_INTERVAL_MINUTES,
            "is_paused": job.next_run_time is None,
            "job_id": job.id,
            "job_name": job.name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading scheduler metadata: {str(e)}")


# Scheduler control endpoints
class SchedulerUpdate(BaseModel):
    interval_minutes: Optional[int] = None


@router.patch("/automation/scheduler")
async def update_scheduler(
    request: Request,
    update: SchedulerUpdate
):
    """Update scheduler interval"""
    try:
        scheduler = request.app.state.scheduler
        orchestrator = request.app.state.crawler
        from app.config import settings
        from apscheduler.triggers.interval import IntervalTrigger
        
        if update.interval_minutes is None:
            raise HTTPException(status_code=400, detail="interval_minutes is required")
        
        if update.interval_minutes < 30:
            raise HTTPException(status_code=400, detail="Interval must be at least 30 minutes")
        
        if update.interval_minutes > 1440:
            raise HTTPException(status_code=400, detail="Interval must be at most 1440 minutes (once per day)")
        
        # Update the job trigger
        scheduler.modify_job(
            "crawl_all_companies",
            trigger=IntervalTrigger(minutes=update.interval_minutes)
        )
        
        # Update settings (in-memory only, doesn't persist to .env)
        settings.CRAWL_INTERVAL_MINUTES = update.interval_minutes
        
        return {
            "message": "Scheduler interval updated",
            "interval_minutes": update.interval_minutes
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating scheduler: {str(e)}")


@router.post("/automation/pause")
async def pause_scheduler(request: Request):
    """Pause the scheduler"""
    try:
        scheduler = request.app.state.scheduler
        scheduler.pause_job("crawl_all_companies")
        return {"message": "Scheduler paused"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error pausing scheduler: {str(e)}")


@router.post("/automation/resume")
async def resume_scheduler(request: Request):
    """Resume the scheduler"""
    try:
        scheduler = request.app.state.scheduler
        scheduler.resume_job("crawl_all_companies")
        return {"message": "Scheduler resumed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resuming scheduler: {str(e)}")


# Cleanup stuck crawl logs endpoint
@router.post("/crawl/cleanup-stuck-logs")
async def cleanup_stuck_logs(request: Request):
    """Manually trigger cleanup of stuck crawl logs"""
    try:
        orchestrator = request.app.state.crawler
        result = await orchestrator.cleanup_stuck_logs()
        return result
    except Exception as e:
        logger.error(f"Error cleaning up stuck logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error cleaning up stuck logs: {str(e)}")


# Enhanced crawl logs endpoint
@router.get("/crawl/logs")
async def get_crawl_logs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    crawler_type: Optional[str] = Query(None, description="Filter by crawler type: selenium, api, ai"),
    status: Optional[str] = Query(None, description="Filter by status: running, completed, failed"),
    limit: int = Query(100, description="Number of logs to return"),
    hours: int = Query(24, description="Hours of history to include")
):
    """Get detailed crawl logs with filtering"""
    try:
        orchestrator = request.app.state.crawler
        from datetime import timedelta
        
        # Build query
        query = select(CrawlLog).where(
            CrawlLog.started_at >= datetime.utcnow() - timedelta(hours=hours)
        )
        
        if status:
            query = query.where(CrawlLog.status == status)
        
        query = query.order_by(desc(CrawlLog.started_at)).limit(limit)
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        # Get company info and classify crawler types
        event_stream = []
        for log in logs:
            company_name = None
            crawler_class = None
            crawler_type_str = None
            
            if log.company_id:
                company_result = await db.execute(
                    select(Company).where(Company.id == log.company_id)
                )
                company = company_result.scalar_one_or_none()
                if company:
                    company_name = company.name
                    crawler_type_str = company.crawler_type
                    crawler_class = orchestrator.get_crawler_type_classification(company.crawler_type)
            
            # Filter by crawler class if specified
            if crawler_type and crawler_class != crawler_type:
                continue
            
            duration = None
            if log.completed_at and log.started_at:
                duration = (log.completed_at - log.started_at).total_seconds()
            
            event_stream.append({
                "id": log.id,
                "timestamp": log.started_at.isoformat() if log.started_at else None,
                "company_id": log.company_id,
                "company_name": company_name,
                "crawler_type": crawler_type_str,
                "crawler_class": crawler_class,
                "status": log.status,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                "duration_seconds": duration,
                "jobs_found": log.jobs_found,
                "new_jobs": log.new_jobs,
                "error_message": log.error_message,
                "search_criteria_id": log.search_criteria_id
            })
        
        return {
            "events": event_stream,
            "total": len(event_stream),
            "filters": {
                "crawler_type": crawler_type,
                "status": status,
                "hours": hours
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading crawl logs: {str(e)}")


# OpenWebUI integration
@router.get("/openwebui")
async def get_openwebui_info(
    request: Request
):
    """Get OpenWebUI access information with health status"""
    from app.config import settings
    from app.services.openwebui_service import get_openwebui_service
    
    service = get_openwebui_service()
    health_status = await service.check_health()
    
    return {
        "enabled": settings.OPENWEBUI_ENABLED,
        "url": settings.OPENWEBUI_URL,
        "ollama_host": settings.OLLAMA_HOST,
        "ollama_model": settings.OLLAMA_MODEL,
        "description": "OpenWebUI provides a chat interface for interacting with Ollama models",
        "features": [
            "Chat with AI about your job searches",
            "Get job search advice",
            "Ask questions about companies",
            "Generate cover letters and resumes",
            "Analyze job descriptions"
        ],
        "health_status": health_status.get("status"),
        "last_checked": health_status.get("last_checked"),
        "capabilities": health_status.get("capabilities", []),
        "auth_status": health_status.get("auth_status")
    }


@router.get("/openwebui/health")
async def get_openwebui_health(
    request: Request
):
    """Get detailed OpenWebUI health check"""
    from app.services.openwebui_service import get_openwebui_service
    
    service = get_openwebui_service()
    return await service.check_health()


class OpenWebUIAuthRequest(BaseModel):
    api_key: Optional[str] = None
    auth_token: Optional[str] = None


@router.post("/openwebui/verify-auth")
async def verify_openwebui_auth(
    auth_request: OpenWebUIAuthRequest,
    request: Request
):
    """Verify OpenWebUI authentication"""
    from app.services.openwebui_service import get_openwebui_service
    
    service = get_openwebui_service()
    return await service.verify_auth(auth_request.api_key, auth_request.auth_token)


@router.get("/openwebui/status")
async def get_openwebui_status(
    request: Request
):
    """Get combined health and auth status"""
    from app.services.openwebui_service import get_openwebui_service
    from app.config import settings
    
    service = get_openwebui_service()
    health = await service.check_health()
    
    # Try to get auth tokens from settings if available
    api_key = getattr(settings, 'OPENWEBUI_API_KEY', None)
    auth_token = getattr(settings, 'OPENWEBUI_AUTH_TOKEN', None)
    
    auth_status = None
    if api_key or auth_token:
        auth_result = await service.verify_auth(api_key, auth_token)
        auth_status = auth_result
    
    return {
        "health": health,
        "auth": auth_status,
        "enabled": settings.OPENWEBUI_ENABLED,
        "url": settings.OPENWEBUI_URL
    }


class OpenWebUIContextRequest(BaseModel):
    job_id: int
    prompt_type: Optional[str] = "analyze"  # analyze, follow_up, interview_prep, cover_letter


@router.post("/openwebui/send-context")
async def send_context_to_openwebui(
    context_request: OpenWebUIContextRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Send job context to OpenWebUI to create a new chat"""
    from app.services.openwebui_service import get_openwebui_service
    from app.config import settings
    
    try:
        # Get job details
        result = await db.execute(select(Job).where(Job.id == context_request.job_id))
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Format job context
        job_context = {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "description": job.description,
            "ai_match_score": job.ai_match_score,
            "ai_summary": job.ai_summary,
            "ai_pros": job.ai_pros,
            "ai_cons": job.ai_cons,
            "url": job.url,
            "status": job.status
        }
        
        context = {
            "job": job_context,
            "prompt_type": context_request.prompt_type
        }
        
        # Get auth tokens from settings
        api_key = getattr(settings, 'OPENWEBUI_API_KEY', None)
        auth_token = getattr(settings, 'OPENWEBUI_AUTH_TOKEN', None)
        
        # Send to OpenWebUI
        service = get_openwebui_service()
        result = await service.send_context(context, api_key, auth_token)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending context to OpenWebUI: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error sending context: {str(e)}")


# Telegram webhook endpoint
@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request
):
    """Handle Telegram webhook updates"""
    try:
        bot_agent = getattr(request.app.state, 'telegram_bot', None)
        if not bot_agent or not bot_agent.application:
            return {"ok": False, "error": "Telegram bot not initialized"}
        
        # Get update data from request body
        update_data = await request.json()
        
        from telegram import Update
        update = Update.de_json(update_data, bot_agent.application.bot)
        
        # Process update
        await bot_agent.application.process_update(update)
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error processing Telegram webhook: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


@router.get("/telegram/webhook")
async def telegram_webhook_info(request: Request):
    """Get Telegram webhook information"""
    from app.config import settings
    
    bot_agent = getattr(request.app.state, 'telegram_bot', None)
    is_active = bot_agent is not None and bot_agent.application is not None
    
    return {
        "enabled": bool(settings.TELEGRAM_BOT_TOKEN),
        "active": is_active,
        "webhook_url": f"{request.base_url}api/telegram/webhook",
        "description": "Telegram bot for interactive job search notifications",
        "features": [
            "Interactive commands (/jobs, /stats, /search, etc.)",
            "Rich notifications with inline buttons",
            "Job detail views and actions",
            "Crawl status and control"
        ]
    }


# Task endpoints
@router.get("/tasks")
async def get_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    job_id: Optional[int] = Query(None, description="Filter by job ID"),
    include_snoozed: bool = Query(True, description="Include snoozed tasks"),
    limit: int = Query(100, description="Maximum number of tasks to return"),
    db: AsyncSession = Depends(get_db)
):
    """List tasks with filters"""
    try:
        tasks = await TaskService.list_tasks(
            db,
            status=status,
            priority=priority,
            task_type=task_type,
            job_id=job_id,
            include_snoozed=include_snoozed,
            limit=limit
        )
        
        return [
            {
                "id": t.id,
                "job_id": t.job_id,
                "task_type": t.task_type,
                "title": t.title,
                "priority": t.priority,
                "status": t.status,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "snooze_until": t.snooze_until.isoformat() if t.snooze_until else None,
                "snooze_count": t.snooze_count,
                "notes": t.notes,
                "recommended_by": t.recommended_by,
                "created_at": t.created_at.isoformat(),
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                "job": {
                    "id": t.job.id,
                    "title": t.job.title,
                    "company": t.job.company,
                    "location": t.job.location
                } if t.job else None
            }
            for t in tasks
        ]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks")
async def create_task(
    task: TaskCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new task"""
    try:
        new_task = await TaskService.create_task(
            db=db,
            job_id=task.job_id,
            task_type=task.task_type,
            title=task.title,
            due_date=task.due_date,
            priority=task.priority,
            notes=task.notes,
            recommended_by="user"
        )
        
        return {
            "id": new_task.id,
            "message": "Task created",
            "task": {
                "id": new_task.id,
                "job_id": new_task.job_id,
                "task_type": new_task.task_type,
                "title": new_task.title,
                "priority": new_task.priority,
                "status": new_task.status,
                "due_date": new_task.due_date.isoformat(),
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get task details"""
    task = await TaskService.get_task(db, task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "id": task.id,
        "job_id": task.job_id,
        "task_type": task.task_type,
        "title": task.title,
        "priority": task.priority,
        "status": task.status,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "snooze_until": task.snooze_until.isoformat() if task.snooze_until else None,
        "snooze_count": task.snooze_count,
        "notes": task.notes,
        "recommended_by": task.recommended_by,
        "ai_insights": task.ai_insights,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "job": {
            "id": task.job.id,
            "title": task.job.title,
            "company": task.job.company,
            "location": task.job.location,
            "url": task.job.url,
            "ai_match_score": task.job.ai_match_score
        } if task.job else None
    }


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: int,
    update: TaskUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a task"""
    try:
        task = await TaskService.update_task(
            db=db,
            task_id=task_id,
            status=update.status,
            priority=update.priority,
            due_date=update.due_date,
            title=update.title,
            notes=update.notes
        )
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {"message": "Task updated", "task_id": task.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/snooze")
async def snooze_task(
    task_id: int,
    snooze: TaskSnooze,
    db: AsyncSession = Depends(get_db)
):
    """Snooze a task"""
    try:
        task = await TaskService.snooze_task(db, task_id, snooze.duration)
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {
            "message": "Task snoozed",
            "task_id": task.id,
            "snooze_until": task.snooze_until.isoformat() if task.snooze_until else None
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error(f"Error snoozing task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/complete")
async def complete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Mark a task as completed"""
    try:
        task = await TaskService.complete_task(db, task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {
            "message": "Task completed",
            "task_id": task.id,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error(f"Error completing task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/recommendations")
async def get_task_recommendations(
    limit: int = Query(10, description="Maximum number of recommendations"),
    db: AsyncSession = Depends(get_db)
):
    """Get AI-generated task recommendations"""
    try:
        recommendations = await TaskGenerator.generate_task_recommendations(db, limit=limit)
        return recommendations
    except Exception as e:
        logger.error(f"Error getting task recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/generate-from-job/{job_id}")
async def generate_tasks_from_job(
    job_id: int,
    force_regenerate: bool = Query(False, description="Force regeneration even if tasks exist"),
    db: AsyncSession = Depends(get_db)
):
    """Generate tasks from job insights"""
    try:
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        tasks = await TaskGenerator.generate_tasks_for_job(db, job, force_regenerate=force_regenerate)
        
        return {
            "message": f"Generated {len(tasks)} tasks",
            "job_id": job_id,
            "tasks": [
                {
                    "id": t.id,
                    "task_type": t.task_type,
                    "title": t.title,
                    "priority": t.priority,
                    "due_date": t.due_date.isoformat()
                }
                for t in tasks
            ]
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Error generating tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/bulk-action")
async def bulk_task_action(
    action: BulkTaskAction,
    db: AsyncSession = Depends(get_db)
):
    """Perform bulk action on tasks"""
    try:
        results = await TaskService.bulk_action(db, action.task_ids, action.action)
        
        return {
            "message": f"Bulk action '{action.action}' completed",
            "success": results["success"],
            "failed": results["failed"],
            "total": len(action.task_ids)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error(f"Error performing bulk action: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/notify")
async def toggle_task_notification(
    task_id: int,
    enabled: bool = Query(True, description="Enable or disable notifications"),
    db: AsyncSession = Depends(get_db)
):
    """Enable/disable notifications for a task"""
    try:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        task.notify_enabled = enabled
        await db.commit()
        
        return {"message": f"Notifications {'enabled' if enabled else 'disabled'}", "task_id": task.id, "notify_enabled": enabled}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error toggling task notification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Application endpoints
@router.post("/jobs/{job_id}/applications")
async def create_application(
    job_id: int,
    application: ApplicationCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new application record for a job"""
    try:
        # Verify job exists
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Verify document IDs if provided
        if application.resume_version_id:
            result = await db.execute(select(GeneratedDocument).where(GeneratedDocument.id == application.resume_version_id))
            if not result.scalar_one_or_none():
                raise HTTPException(status_code=404, detail="Resume document not found")
        
        if application.cover_letter_id:
            result = await db.execute(select(GeneratedDocument).where(GeneratedDocument.id == application.cover_letter_id))
            if not result.scalar_one_or_none():
                raise HTTPException(status_code=404, detail="Cover letter document not found")
        
        new_application = Application(
            job_id=job_id,
            status=application.status,
            application_date=application.application_date,
            portal_url=application.portal_url,
            confirmation_number=application.confirmation_number,
            resume_version_id=application.resume_version_id,
            cover_letter_id=application.cover_letter_id,
            notes=application.notes
        )
        
        db.add(new_application)
        await db.commit()
        await db.refresh(new_application)
        
        return {
            "id": new_application.id,
            "message": "Application created",
            "application": {
                "id": new_application.id,
                "job_id": new_application.job_id,
                "status": new_application.status,
                "application_date": new_application.application_date.isoformat() if new_application.application_date else None,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating application: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/applications")
async def get_applications(
    status: Optional[str] = Query(None, description="Filter by status"),
    job_id: Optional[int] = Query(None, description="Filter by job ID"),
    limit: int = Query(100, description="Maximum number of applications to return"),
    db: AsyncSession = Depends(get_db)
):
    """List applications with optional filters"""
    try:
        query = select(Application).options(selectinload(Application.job)).order_by(desc(Application.created_at))
        
        if status:
            query = query.where(Application.status == status)
        if job_id:
            query = query.where(Application.job_id == job_id)
        
        query = query.limit(limit)
        
        result = await db.execute(query)
        applications = result.scalars().all()
        
        return [
            {
                "id": app.id,
                "job_id": app.job_id,
                "status": app.status,
                "application_date": app.application_date.isoformat() if app.application_date else None,
                "portal_url": app.portal_url,
                "confirmation_number": app.confirmation_number,
                "resume_version_id": app.resume_version_id,
                "cover_letter_id": app.cover_letter_id,
                "notes": app.notes,
                "created_at": app.created_at.isoformat(),
                "updated_at": app.updated_at.isoformat(),
                "job": {
                    "id": app.job.id,
                    "title": app.job.title,
                    "company": app.job.company,
                    "location": app.job.location,
                } if app.job else None
            }
            for app in applications
        ]
    except Exception as e:
        logger.error(f"Error listing applications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/applications/{application_id}")
async def get_application(
    application_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get application details"""
    try:
        result = await db.execute(select(Application).options(selectinload(Application.job)).where(Application.id == application_id))
        app = result.scalar_one_or_none()
        
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        
        return {
            "id": app.id,
            "job_id": app.job_id,
            "status": app.status,
            "application_date": app.application_date.isoformat() if app.application_date else None,
            "portal_url": app.portal_url,
            "confirmation_number": app.confirmation_number,
            "resume_version_id": app.resume_version_id,
            "cover_letter_id": app.cover_letter_id,
            "notes": app.notes,
            "created_at": app.created_at.isoformat(),
            "updated_at": app.updated_at.isoformat(),
            "job": {
                "id": app.job.id,
                "title": app.job.title,
                "company": app.job.company,
                "location": app.job.location,
                "url": app.job.url,
                "ai_match_score": app.job.ai_match_score,
            } if app.job else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading application: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/applications/{application_id}")
async def update_application(
    application_id: int,
    update: ApplicationUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update application status/notes"""
    try:
        result = await db.execute(select(Application).where(Application.id == application_id))
        app = result.scalar_one_or_none()
        
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Verify document IDs if provided
        if update.resume_version_id:
            result = await db.execute(select(GeneratedDocument).where(GeneratedDocument.id == update.resume_version_id))
            if not result.scalar_one_or_none():
                raise HTTPException(status_code=404, detail="Resume document not found")
        
        if update.cover_letter_id:
            result = await db.execute(select(GeneratedDocument).where(GeneratedDocument.id == update.cover_letter_id))
            if not result.scalar_one_or_none():
                raise HTTPException(status_code=404, detail="Cover letter document not found")
        
        # Update fields
        for field, value in update.dict(exclude_unset=True).items():
            setattr(app, field, value)
        
        await db.commit()
        return {"message": "Application updated", "application_id": app.id}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating application: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/applications/{application_id}")
async def delete_application(
    application_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete an application"""
    try:
        result = await db.execute(select(Application).where(Application.id == application_id))
        app = result.scalar_one_or_none()
        
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        
        await db.delete(app)
        await db.commit()
        
        return {"message": "Application deleted"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting application: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/{job_id}/actions")
async def handle_job_action(
    job_id: int,
    action: JobAction,
    db: AsyncSession = Depends(get_db)
):
    """Handle job action intents (queue for application, mark priority, etc.)"""
    try:
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if action.action == "queue_application":
            # Check if application already exists
            result = await db.execute(select(Application).where(Application.job_id == job_id))
            existing_app = result.scalar_one_or_none()
            
            if existing_app:
                return {"message": "Application already exists", "application_id": existing_app.id}
            
            # Create new application with queued status
            new_application = Application(
                job_id=job_id,
                status="queued"
            )
            db.add(new_application)
            await db.commit()
            await db.refresh(new_application)
            
            return {"message": "Job queued for application", "application_id": new_application.id}
        
        elif action.action == "mark_priority":
            # Update job status or create a task
            job.status = "saved"  # Mark as saved/priority
            await db.commit()
            
            return {"message": "Job marked as priority"}
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action.action}")
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error handling job action: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Document generation endpoints
@router.post("/jobs/{job_id}/generate-documents")
async def generate_documents(
    job_id: int,
    generate: DocumentGenerate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Generate resume and/or cover letter for a job"""
    try:
        from app.ai.document_generator import DocumentGenerator
        from app.models import UserProfile
        
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Get or create user profile (for now, use user_id=1)
        result = await db.execute(select(UserProfile).where(UserProfile.user_id == 1))
        user_profile = result.scalar_one_or_none()
        
        if not user_profile:
            raise HTTPException(
                status_code=400,
                detail="User profile not found. Please create a user profile first."
            )
        
        document_generator = DocumentGenerator()
        generated_docs = []
        
        if "resume" in generate.document_types:
            resume_doc = await document_generator.generate_resume(job, user_profile, db)
            if resume_doc:
                generated_docs.append({
                    "id": resume_doc.id,
                    "document_type": resume_doc.document_type,
                    "generated_at": resume_doc.generated_at.isoformat(),
                })
        
        if "cover_letter" in generate.document_types:
            cover_letter_doc = await document_generator.generate_cover_letter(job, user_profile, db)
            if cover_letter_doc:
                generated_docs.append({
                    "id": cover_letter_doc.id,
                    "document_type": cover_letter_doc.document_type,
                    "generated_at": cover_letter_doc.generated_at.isoformat(),
                })
        
        return {
            "message": f"Generated {len(generated_docs)} document(s)",
            "job_id": job_id,
            "documents": generated_docs
        }
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error generating documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}/documents")
async def get_job_documents(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """List all generated documents for a job"""
    try:
        result = await db.execute(
            select(GeneratedDocument)
            .where(GeneratedDocument.job_id == job_id)
            .order_by(desc(GeneratedDocument.generated_at))
        )
        documents = result.scalars().all()
        
        return [
            {
                "id": doc.id,
                "job_id": doc.job_id,
                "document_type": doc.document_type,
                "content": doc.content,
                "generated_at": doc.generated_at.isoformat(),
                "file_path": doc.file_path,
            }
            for doc in documents
        ]
    except Exception as e:
        logger.error(f"Error loading documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{document_id}")
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get document content"""
    try:
        result = await db.execute(select(GeneratedDocument).where(GeneratedDocument.id == document_id))
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "id": doc.id,
            "job_id": doc.job_id,
            "document_type": doc.document_type,
            "content": doc.content,
            "generated_at": doc.generated_at.isoformat(),
            "file_path": doc.file_path,
            "job": {
                "id": doc.job.id,
                "title": doc.job.title,
                "company": doc.job.company,
            } if doc.job else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/documents/{document_id}")
async def update_document(
    document_id: int,
    update: DocumentUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update document content after user edits"""
    try:
        result = await db.execute(select(GeneratedDocument).where(GeneratedDocument.id == document_id))
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc.content = update.content
        await db.commit()
        
        return {"message": "Document updated", "document_id": doc.id}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/{document_id}/finalize")
async def finalize_document(
    document_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Mark document as finalized (lock for submission)"""
    try:
        result = await db.execute(select(GeneratedDocument).where(GeneratedDocument.id == document_id))
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # In a full implementation, you might want to add a "finalized" boolean field
        # For now, we'll just return success
        await db.commit()
        
        return {"message": "Document finalized", "document_id": doc.id}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error finalizing document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Search recipes endpoint
@router.get("/automation/search-recipes")
async def get_search_recipes():
    """Get predefined search recipes for automation"""
    try:
        import json
        from pathlib import Path
        
        recipe_path = Path(__file__).parent.parent / "search_recipes.json"
        
        if not recipe_path.exists():
            # Return default recipes if file doesn't exist yet
            return {
                "recipes": [
                    {
                        "name": "Remote Senior Engineer Blitz",
                        "description": "Target remote senior engineering roles at top tech companies",
                        "keywords": "senior engineer, software engineer, remote",
                        "location": None,
                        "remote_only": True,
                        "job_type": "full-time",
                        "experience_level": "senior",
                        "icon": "rocket"
                    },
                    {
                        "name": "Local Startup Hunt",
                        "description": "Find opportunities at local startups and growing companies",
                        "keywords": "startup, software engineer, developer",
                        "location": "San Francisco",
                        "remote_only": False,
                        "job_type": "full-time",
                        "experience_level": "mid",
                        "icon": "building"
                    }
                ]
            }
        
        with open(recipe_path, "r") as f:
            recipes_data = json.load(f)
        
        return {"recipes": recipes_data.get("recipes", [])}
    
    except Exception as e:
        logger.error(f"Error loading search recipes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Settings endpoints
class SettingsRead(BaseModel):
    """Settings read model - returns all current settings"""
    # Notifications
    notification_method: str
    ntfy_server: str
    ntfy_topic: Optional[str] = None
    pushover_user_key: Optional[str] = None
    pushover_app_token: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_bot_mode: str
    telegram_webhook_url: Optional[str] = None
    
    # Company lifecycle
    company_target_count: int
    company_discovery_batch_size: int
    consecutive_empty_threshold: int
    viability_score_threshold: float
    company_refresh_schedule: str
    web_search_enabled: bool
    
    # Task workspace
    auto_generate_tasks: bool
    task_match_score_threshold: float
    task_reminder_check_interval_minutes: int
    
    # Crawl scheduling
    crawl_interval_minutes: int
    daily_top_jobs_count: int
    daily_generation_time: str
    
    # AI/Ollama
    ollama_host: str
    ollama_model: str
    
    # OpenWebUI
    openwebui_enabled: bool
    openwebui_url: str
    openwebui_api_key: Optional[str] = None
    openwebui_auth_token: Optional[str] = None
    openwebui_username: Optional[str] = None


class SettingsUpdate(BaseModel):
    """Settings update model - all fields optional"""
    # Notifications
    notification_method: Optional[str] = None
    ntfy_server: Optional[str] = None
    ntfy_topic: Optional[str] = None
    pushover_user_key: Optional[str] = None
    pushover_app_token: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_bot_mode: Optional[str] = None
    telegram_webhook_url: Optional[str] = None
    
    # Company lifecycle
    company_target_count: Optional[int] = None
    company_discovery_batch_size: Optional[int] = None
    consecutive_empty_threshold: Optional[int] = None
    viability_score_threshold: Optional[float] = None
    company_refresh_schedule: Optional[str] = None
    web_search_enabled: Optional[bool] = None
    
    # Task workspace
    auto_generate_tasks: Optional[bool] = None
    task_match_score_threshold: Optional[float] = None
    task_reminder_check_interval_minutes: Optional[int] = None
    
    # Crawl scheduling
    crawl_interval_minutes: Optional[int] = None
    daily_top_jobs_count: Optional[int] = None
    daily_generation_time: Optional[str] = None
    
    # AI/Ollama
    ollama_host: Optional[str] = None
    ollama_model: Optional[str] = None
    
    # OpenWebUI
    openwebui_enabled: Optional[bool] = None
    openwebui_url: Optional[str] = None
    openwebui_api_key: Optional[str] = None
    openwebui_auth_token: Optional[str] = None
    openwebui_username: Optional[str] = None


@router.get("/settings")
async def get_settings(request: Request):
    """Get all current settings"""
    from app.config import settings
    
    # Get Telegram bot status
    bot_agent = getattr(request.app.state, 'telegram_bot', None)
    telegram_active = bot_agent is not None and bot_agent.application is not None
    
    return {
        **SettingsRead(
            notification_method=settings.NOTIFICATION_METHOD,
            ntfy_server=settings.NTFY_SERVER,
            ntfy_topic=settings.NTFY_TOPIC,
            pushover_user_key=settings.PUSHOVER_USER_KEY,
            pushover_app_token=settings.PUSHOVER_APP_TOKEN,
            telegram_bot_token=settings.TELEGRAM_BOT_TOKEN,
            telegram_chat_id=settings.TELEGRAM_CHAT_ID,
            telegram_bot_mode=settings.TELEGRAM_BOT_MODE,
            telegram_webhook_url=settings.TELEGRAM_WEBHOOK_URL,
            company_target_count=settings.COMPANY_TARGET_COUNT,
            company_discovery_batch_size=settings.COMPANY_DISCOVERY_BATCH_SIZE,
            consecutive_empty_threshold=settings.CONSECUTIVE_EMPTY_THRESHOLD,
            viability_score_threshold=settings.VIABILITY_SCORE_THRESHOLD,
            company_refresh_schedule=settings.COMPANY_REFRESH_SCHEDULE,
            web_search_enabled=settings.WEB_SEARCH_ENABLED,
            auto_generate_tasks=settings.AUTO_GENERATE_TASKS,
            task_match_score_threshold=settings.TASK_MATCH_SCORE_THRESHOLD,
            task_reminder_check_interval_minutes=settings.TASK_REMINDER_CHECK_INTERVAL_MINUTES,
            crawl_interval_minutes=settings.CRAWL_INTERVAL_MINUTES,
            daily_top_jobs_count=settings.DAILY_TOP_JOBS_COUNT,
            daily_generation_time=settings.DAILY_GENERATION_TIME,
            ollama_host=settings.OLLAMA_HOST,
            ollama_model=settings.OLLAMA_MODEL,
            openwebui_enabled=settings.OPENWEBUI_ENABLED,
            openwebui_url=settings.OPENWEBUI_URL,
            openwebui_api_key=getattr(settings, 'OPENWEBUI_API_KEY', None),
            openwebui_auth_token=getattr(settings, 'OPENWEBUI_AUTH_TOKEN', None),
            openwebui_username=getattr(settings, 'OPENWEBUI_USERNAME', None)
        ).dict(),
        "telegram_active": telegram_active
    }


@router.patch("/settings")
async def update_settings(request: Request, update: SettingsUpdate):
    """Update settings (in-memory only, does not persist to .env)"""
    from app.config import settings
    
    try:
        # Validate and update settings
        updates = update.dict(exclude_unset=True)
        
        # Notification settings
        if "notification_method" in updates:
            if updates["notification_method"] not in ["ntfy", "pushover", "telegram"]:
                raise HTTPException(status_code=400, detail="Invalid notification method. Must be ntfy, pushover, or telegram")
            settings.NOTIFICATION_METHOD = updates["notification_method"]
        
        if "ntfy_server" in updates:
            settings.NTFY_SERVER = updates["ntfy_server"]
        if "ntfy_topic" in updates:
            settings.NTFY_TOPIC = updates["ntfy_topic"]
        if "pushover_user_key" in updates:
            settings.PUSHOVER_USER_KEY = updates["pushover_user_key"]
        if "pushover_app_token" in updates:
            settings.PUSHOVER_APP_TOKEN = updates["pushover_app_token"]
        if "telegram_bot_token" in updates:
            settings.TELEGRAM_BOT_TOKEN = updates["telegram_bot_token"]
        if "telegram_chat_id" in updates:
            settings.TELEGRAM_CHAT_ID = updates["telegram_chat_id"]
        if "telegram_bot_mode" in updates:
            if updates["telegram_bot_mode"] not in ["polling", "webhook"]:
                raise HTTPException(status_code=400, detail="Invalid bot mode. Must be polling or webhook")
            settings.TELEGRAM_BOT_MODE = updates["telegram_bot_mode"]
        if "telegram_webhook_url" in updates:
            settings.TELEGRAM_WEBHOOK_URL = updates["telegram_webhook_url"]
        
        # Company lifecycle settings
        if "company_target_count" in updates:
            if updates["company_target_count"] < 1:
                raise HTTPException(status_code=400, detail="Company target count must be at least 1")
            settings.COMPANY_TARGET_COUNT = updates["company_target_count"]
        if "company_discovery_batch_size" in updates:
            if updates["company_discovery_batch_size"] < 1:
                raise HTTPException(status_code=400, detail="Discovery batch size must be at least 1")
            settings.COMPANY_DISCOVERY_BATCH_SIZE = updates["company_discovery_batch_size"]
        if "consecutive_empty_threshold" in updates:
            if updates["consecutive_empty_threshold"] < 1:
                raise HTTPException(status_code=400, detail="Consecutive empty threshold must be at least 1")
            settings.CONSECUTIVE_EMPTY_THRESHOLD = updates["consecutive_empty_threshold"]
        if "viability_score_threshold" in updates:
            threshold = updates["viability_score_threshold"]
            if threshold < 0 or threshold > 100:
                raise HTTPException(status_code=400, detail="Viability score threshold must be between 0 and 100")
            settings.VIABILITY_SCORE_THRESHOLD = threshold
        if "company_refresh_schedule" in updates:
            settings.COMPANY_REFRESH_SCHEDULE = updates["company_refresh_schedule"]
        if "web_search_enabled" in updates:
            settings.WEB_SEARCH_ENABLED = updates["web_search_enabled"]
        
        # Task workspace settings
        if "auto_generate_tasks" in updates:
            settings.AUTO_GENERATE_TASKS = updates["auto_generate_tasks"]
        if "task_match_score_threshold" in updates:
            threshold = updates["task_match_score_threshold"]
            if threshold < 0 or threshold > 100:
                raise HTTPException(status_code=400, detail="Task match score threshold must be between 0 and 100")
            settings.TASK_MATCH_SCORE_THRESHOLD = threshold
        if "task_reminder_check_interval_minutes" in updates:
            if updates["task_reminder_check_interval_minutes"] < 1:
                raise HTTPException(status_code=400, detail="Task reminder check interval must be at least 1 minute")
            settings.TASK_REMINDER_CHECK_INTERVAL_MINUTES = updates["task_reminder_check_interval_minutes"]
        
        # Crawl scheduling settings
        if "crawl_interval_minutes" in updates:
            if updates["crawl_interval_minutes"] < 30:
                raise HTTPException(status_code=400, detail="Crawl interval must be at least 30 minutes")
            if updates["crawl_interval_minutes"] > 1440:
                raise HTTPException(status_code=400, detail="Crawl interval must be at most 1440 minutes (once per day)")
            settings.CRAWL_INTERVAL_MINUTES = updates["crawl_interval_minutes"]
            # Update scheduler if it exists
            scheduler = getattr(request.app.state, 'scheduler', None)
            if scheduler:
                from apscheduler.triggers.interval import IntervalTrigger
                try:
                    scheduler.modify_job(
                        "crawl_all_companies",
                        trigger=IntervalTrigger(minutes=settings.CRAWL_INTERVAL_MINUTES)
                    )
                except Exception as e:
                    logger.warning(f"Could not update scheduler interval: {e}")
        if "daily_top_jobs_count" in updates:
            if updates["daily_top_jobs_count"] < 1:
                raise HTTPException(status_code=400, detail="Daily top jobs count must be at least 1")
            settings.DAILY_TOP_JOBS_COUNT = updates["daily_top_jobs_count"]
        if "daily_generation_time" in updates:
            # Validate time format HH:MM
            time_str = updates["daily_generation_time"]
            try:
                parts = time_str.split(":")
                if len(parts) != 2:
                    raise ValueError
                hour = int(parts[0])
                minute = int(parts[1])
                if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                    raise ValueError
                settings.DAILY_GENERATION_TIME = time_str
            except ValueError:
                raise HTTPException(status_code=400, detail="Daily generation time must be in HH:MM format (e.g., 15:00)")
        
        # AI/Ollama settings
        if "ollama_host" in updates:
            settings.OLLAMA_HOST = updates["ollama_host"]
        if "ollama_model" in updates:
            settings.OLLAMA_MODEL = updates["ollama_model"]
        
        # OpenWebUI settings
        if "openwebui_enabled" in updates:
            settings.OPENWEBUI_ENABLED = updates["openwebui_enabled"]
        if "openwebui_url" in updates:
            settings.OPENWEBUI_URL = updates["openwebui_url"]
        if "openwebui_api_key" in updates:
            settings.OPENWEBUI_API_KEY = updates["openwebui_api_key"]
        if "openwebui_auth_token" in updates:
            settings.OPENWEBUI_AUTH_TOKEN = updates["openwebui_auth_token"]
        if "openwebui_username" in updates:
            settings.OPENWEBUI_USERNAME = updates["openwebui_username"]
        
        return {
            "message": "Settings updated successfully",
            "updated_fields": list(updates.keys()),
            "note": "Changes are in-memory only and will be lost on restart. Update .env file for persistence."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating settings: {str(e)}")


@router.post("/settings/telegram/test")
async def test_telegram_bot(request: Request):
    """Test Telegram bot connection"""
    from app.config import settings
    
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        raise HTTPException(status_code=400, detail="Telegram bot token and chat ID must be configured")
    
    try:
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": settings.TELEGRAM_CHAT_ID,
                    "text": "✅ Test message from Job Search Crawler!\n\nYour Telegram bot is configured correctly.",
                    "parse_mode": "Markdown"
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Test message sent successfully!"
                }
            else:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                error_desc = error_data.get("description", f"HTTP {response.status_code}")
                return {
                    "success": False,
                    "message": f"Failed to send test message: {error_desc}"
                }
    except Exception as e:
        logger.error(f"Error testing Telegram bot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error testing Telegram bot: {str(e)}")


@router.post("/settings/notifications/test")
async def test_notification(request: Request):
    """Send a test notification using the configured method"""
    from app.config import settings
    from app.notifications.notifier import NotificationService
    
    try:
        notifier = NotificationService()
        
        # Get bot agent if available
        bot_agent = getattr(request.app.state, 'telegram_bot', None)
        if bot_agent:
            notifier._bot_agent = bot_agent
        
        success = await notifier.send_notification(
            title="Test Notification",
            message="This is a test notification from Job Search Crawler. If you received this, your notification settings are working correctly!",
            priority="default"
        )
        
        if success:
            return {
                "success": True,
                "message": f"Test notification sent via {settings.NOTIFICATION_METHOD}"
            }
        else:
            return {
                "success": False,
                "message": f"Failed to send test notification via {settings.NOTIFICATION_METHOD}. Check your configuration."
            }
    except Exception as e:
        logger.error(f"Error testing notification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error testing notification: {str(e)}")


# User Profile endpoints
class UserProfilePreferences(BaseModel):
    """User preferences for job filtering"""
    keywords: Optional[str] = None
    location: Optional[str] = None
    locations: Optional[List[str]] = None  # Multiple locations
    remote_preferred: Optional[bool] = None
    work_type: Optional[str] = None  # "remote", "office", "hybrid", "any"
    experience_level: Optional[str] = None


class UserProfileRead(BaseModel):
    """User profile read model"""
    id: int
    user_id: Optional[int]
    base_resume: Optional[str]
    skills: Optional[List[str]]
    experience: Optional[List[dict]]
    education: Optional[dict]
    preferences: Optional[dict]
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    """User profile update model - all fields optional"""
    base_resume: Optional[str] = None
    skills: Optional[List[str]] = None
    experience: Optional[List[dict]] = None
    education: Optional[dict] = None
    preferences: Optional[UserProfilePreferences] = None


@router.get("/user-profile")
async def get_user_profile(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get current user profile (defaults to user_id=1)"""
    try:
        from app.models import UserProfile
        
        # For now, use user_id=1 (would use actual auth in production)
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == 1)
        )
        user_profile = result.scalar_one_or_none()
        
        if not user_profile:
            # Return empty profile structure
            return {
                "id": None,
                "user_id": 1,
                "base_resume": None,
                "skills": [],
                "experience": [],
                "education": None,
                "preferences": {
                    "keywords": None,
                    "location": None,
                    "locations": [],
                    "remote_preferred": True,
                    "work_type": "any",
                    "experience_level": None
                },
                "created_at": None,
                "updated_at": None
            }
        
        # Convert preferences dict if it exists
        prefs = user_profile.preferences or {}
        
        return {
            "id": user_profile.id,
            "user_id": user_profile.user_id,
            "base_resume": user_profile.base_resume,
            "skills": user_profile.skills or [],
            "experience": user_profile.experience or [],
            "education": user_profile.education,
            "preferences": {
                "keywords": prefs.get("keywords"),
                "location": prefs.get("location"),
                "locations": prefs.get("locations", []),
                "remote_preferred": prefs.get("remote_preferred", True),
                "work_type": prefs.get("work_type", "any"),
                "experience_level": prefs.get("experience_level")
            },
            "created_at": user_profile.created_at.isoformat() if user_profile.created_at else None,
            "updated_at": user_profile.updated_at.isoformat() if user_profile.updated_at else None
        }
    except Exception as e:
        logger.error(f"Error getting user profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting user profile: {str(e)}")


@router.post("/user-profile")
async def create_user_profile(
    request: Request,
    profile: UserProfileUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new user profile"""
    try:
        from app.models import UserProfile
        
        # Check if profile already exists for user_id=1
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == 1)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail="User profile already exists. Use PATCH to update."
            )
        
        # Build preferences dict
        prefs_dict = None
        if profile.preferences:
            prefs_dict = {
                "keywords": profile.preferences.keywords,
                "location": profile.preferences.location,
                "locations": profile.preferences.locations or [],
                "remote_preferred": profile.preferences.remote_preferred if profile.preferences.remote_preferred is not None else True,
                "work_type": profile.preferences.work_type or "any",
                "experience_level": profile.preferences.experience_level
            }
        
        new_profile = UserProfile(
            user_id=1,
            base_resume=profile.base_resume,
            skills=profile.skills,
            experience=profile.experience,
            education=profile.education,
            preferences=prefs_dict
        )
        
        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)
        
        prefs = new_profile.preferences or {}
        return {
            "id": new_profile.id,
            "user_id": new_profile.user_id,
            "base_resume": new_profile.base_resume,
            "skills": new_profile.skills or [],
            "experience": new_profile.experience or [],
            "education": new_profile.education,
            "preferences": {
                "keywords": prefs.get("keywords"),
                "location": prefs.get("location"),
                "locations": prefs.get("locations", []),
                "remote_preferred": prefs.get("remote_preferred", True),
                "work_type": prefs.get("work_type", "any"),
                "experience_level": prefs.get("experience_level")
            },
            "created_at": new_profile.created_at.isoformat() if new_profile.created_at else None,
            "updated_at": new_profile.updated_at.isoformat() if new_profile.updated_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user profile: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating user profile: {str(e)}")


@router.patch("/user-profile")
async def update_user_profile(
    request: Request,
    profile: UserProfileUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update existing user profile"""
    try:
        from app.models import UserProfile
        
        # Get existing profile for user_id=1
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == 1)
        )
        user_profile = result.scalar_one_or_none()
        
        if not user_profile:
            # Create new profile if it doesn't exist
            return await create_user_profile(request, profile, db)
        
        # Update fields if provided
        if profile.base_resume is not None:
            user_profile.base_resume = profile.base_resume
        if profile.skills is not None:
            user_profile.skills = profile.skills
        if profile.experience is not None:
            user_profile.experience = profile.experience
        if profile.education is not None:
            user_profile.education = profile.education
        if profile.preferences is not None:
            # Merge preferences with existing
            existing_prefs = user_profile.preferences or {}
            prefs_dict = {
                "keywords": profile.preferences.keywords if profile.preferences.keywords is not None else existing_prefs.get("keywords"),
                "location": profile.preferences.location if profile.preferences.location is not None else existing_prefs.get("location"),
                "locations": profile.preferences.locations if profile.preferences.locations is not None else existing_prefs.get("locations", []),
                "remote_preferred": profile.preferences.remote_preferred if profile.preferences.remote_preferred is not None else existing_prefs.get("remote_preferred", True),
                "work_type": profile.preferences.work_type if profile.preferences.work_type is not None else existing_prefs.get("work_type", "any"),
                "experience_level": profile.preferences.experience_level if profile.preferences.experience_level is not None else existing_prefs.get("experience_level")
            }
            user_profile.preferences = prefs_dict
        
        user_profile.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(user_profile)
        
        prefs = user_profile.preferences or {}
        return {
            "id": user_profile.id,
            "user_id": user_profile.user_id,
            "base_resume": user_profile.base_resume,
            "skills": user_profile.skills or [],
            "experience": user_profile.experience or [],
            "education": user_profile.education,
            "preferences": {
                "keywords": prefs.get("keywords"),
                "location": prefs.get("location"),
                "locations": prefs.get("locations", []),
                "remote_preferred": prefs.get("remote_preferred", True),
                "work_type": prefs.get("work_type", "any"),
                "experience_level": prefs.get("experience_level")
            },
            "created_at": user_profile.created_at.isoformat() if user_profile.created_at else None,
            "updated_at": user_profile.updated_at.isoformat() if user_profile.updated_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user profile: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating user profile: {str(e)}")


# AI Chat endpoint
class ChatMessage(BaseModel):
    message: str
    job_id: Optional[int] = None
    context: Optional[dict] = None


@router.post("/ai/chat")
async def ai_chat(
    chat: ChatMessage,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """AI chat endpoint for follow-up assistance"""
    try:
        from app.config import settings
        import httpx
        
        # Build context from job if provided
        context_info = ""
        if chat.job_id:
            result = await db.execute(select(Job).where(Job.id == chat.job_id))
            job = result.scalar_one_or_none()
            if job:
                context_info = f"\n\nJob Context:\n- Title: {job.title}\n- Company: {job.company}\n- Location: {job.location}\n- Status: {job.status}\n- Match Score: {job.ai_match_score}%\n- Description: {job.description[:500] if job.description else 'N/A'}"
        
        # Build intelligent prompt
        system_prompt = """You are an AI assistant helping with job search follow-ups and career advice. 
        You provide practical, actionable guidance on:
        - When to follow up on applications
        - How to write effective follow-up emails
        - Interview preparation
        - Career strategy
        
        Be concise, professional, and helpful. Focus on actionable advice."""
        
        user_prompt = f"{chat.message}{context_info}"
        
        # Call Ollama API
        ollama_url = f"{settings.OLLAMA_HOST}/api/chat"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                ollama_url,
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                ai_response = data.get("message", {}).get("content", "I'm sorry, I couldn't generate a response.")
                return {
                    "response": ai_response,
                    "model": settings.OLLAMA_MODEL
                }
            else:
                logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                # Fallback response
                return {
                    "response": "I'm having trouble connecting to the AI service right now. Please try again later, or check your Ollama configuration.",
                    "error": True
                }
                
    except httpx.TimeoutException:
        logger.error("Ollama API timeout")
        return {
            "response": "The AI service is taking too long to respond. Please try again with a simpler question.",
            "error": True
        }
    except Exception as e:
        logger.error(f"Error in AI chat: {e}", exc_info=True)
        return {
            "response": f"I encountered an error: {str(e)}. Please check your Ollama configuration and try again.",
            "error": True
        }

