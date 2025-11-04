"""FastAPI routes"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.models import Job, SearchCriteria, User, FollowUp, CrawlLog, Company
from app.utils.crypto import encrypt_password
from app.crawler.orchestrator import CrawlerOrchestrator

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
            }
            for c in companies
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading companies: {str(e)}")


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


# Job endpoints
@router.get("/jobs")
async def get_jobs(
    status: Optional[str] = None,
    search_id: Optional[int] = None,
    new_only: bool = False,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get jobs with filters"""
    query = select(Job).order_by(desc(Job.discovered_at))
    
    if status:
        query = query.where(Job.status == status)
    if search_id:
        query = query.where(Job.search_criteria_id == search_id)
    if new_only:
        query = query.where(Job.is_new == True)
    
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
    """Re-analyze a job with enhanced company profile analysis"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        from app.ai.analyzer import JobAnalyzer
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
        
        return {
            "job_id": job.id,
            "analysis": profile_analysis
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
    crawl_type: Optional[str] = Query(None, description="Crawl type: 'searches' (default) or 'all'"),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger a crawl.
    
    By default, runs all active searches. If crawl_type="all", crawls all companies
    with AI filtering (base crawling).
    
    Query params:
        crawl_type: "searches" (default) or "all"
    """
    try:
        orchestrator = request.app.state.crawler
        
        # Default to "searches" if not specified
        if crawl_type is None or crawl_type == "searches":
            # Search-based crawling: run all active searches
            results = await orchestrator.run_all_searches()
            return {
                "message": "Search-based crawl completed",
                "new_jobs": len(results),
                "crawl_type": "searches"
            }
        elif crawl_type == "all":
            # Base crawling: crawl all companies and use AI to filter
            results = await orchestrator.crawl_all_companies()
            return {
                "message": "Universal crawl completed (all companies crawled, AI-filtered)",
                "new_jobs": len(results),
                "crawl_type": "universal"
            }
        else:
            raise HTTPException(status_code=400, detail=f"Invalid crawl_type: {crawl_type}. Use 'searches' or 'all'")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, description="Number of recent crawl logs to return")
):
    """Get recent crawl status and logs"""
    try:
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
        
        return {
            "is_running": len(running_logs) > 0,
            "running_count": len(running_logs),
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
                    "error_message": log.error_message
                }
                for log in logs
            ],
            "active_companies": active_companies
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading crawl status: {str(e)}")


# OpenWebUI integration
@router.get("/openwebui")
async def get_openwebui_info(
    request: Request
):
    """Get OpenWebUI access information"""
    from app.config import settings
    
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
        ]
    }

