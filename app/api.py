"""FastAPI routes"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.models import Job, SearchCriteria, User, FollowUp, CrawlLog
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
    platforms: List[str] = ["linkedin", "indeed"]
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
    platforms: Optional[List[str]] = None
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


# Search Criteria endpoints
@router.get("/searches")
async def get_searches(
    db: AsyncSession = Depends(get_db)
):
    """Get all search criteria"""
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
            "is_active": s.is_active,
            "notify_on_new": s.notify_on_new,
            "created_at": s.created_at.isoformat(),
        }
        for s in searches
    ]


@router.post("/searches")
async def create_search(
    search: SearchCriteriaCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create new search criteria"""
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
        platforms=search.platforms,
        notify_on_new=search.notify_on_new
    )
    
    db.add(new_search)
    await db.commit()
    await db.refresh(new_search)
    
    return {"id": new_search.id, "message": "Search criteria created"}


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
            "ai_match_score": j.ai_match_score,
            "ai_summary": j.ai_summary,
            "ai_pros": j.ai_pros,
            "ai_cons": j.ai_cons,
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
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger a crawl"""
    try:
        orchestrator = request.app.state.crawler
        results = await orchestrator.run_all_searches()
        
        return {
            "message": "Crawl completed",
            "new_jobs": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Dashboard statistics
@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics"""
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
        by_status[job.status] = by_status.get(job.status, 0) + 1
    
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

