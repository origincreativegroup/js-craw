"""Database models"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class User(Base):
    """User credentials for job platforms"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), unique=True, nullable=False, index=True)  # linkedin, indeed
    email = Column(String(255), nullable=False)
    encrypted_password = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SearchCriteria(Base):
    """Job search criteria"""
    __tablename__ = "search_criteria"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    keywords = Column(String(500), nullable=False)
    location = Column(String(255), nullable=True)
    remote_only = Column(Boolean, default=False)
    job_type = Column(String(50), nullable=True)  # full-time, part-time, contract, etc.
    experience_level = Column(String(50), nullable=True)  # entry, mid, senior, etc.
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    platforms = Column(JSON, default=["linkedin", "indeed"])  # List of platforms
    is_active = Column(Boolean, default=True, index=True)
    notify_on_new = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    jobs = relationship("Job", back_populates="search_criteria")
    crawl_logs = relationship("CrawlLog", back_populates="search_criteria")


class Job(Base):
    """Job posting"""
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    search_criteria_id = Column(Integer, ForeignKey("search_criteria.id"), nullable=False, index=True)
    platform = Column(String(50), nullable=False, index=True)
    external_id = Column(String(255), nullable=False, index=True)  # Platform-specific ID
    title = Column(String(500), nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    job_type = Column(String(50), nullable=True)
    url = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    posted_date = Column(DateTime, nullable=True)
    
    # AI analysis
    ai_match_score = Column(Float, nullable=True)
    ai_summary = Column(Text, nullable=True)
    ai_pros = Column(JSON, nullable=True)  # List of pros
    ai_cons = Column(JSON, nullable=True)  # List of cons
    ai_keywords_matched = Column(JSON, nullable=True)  # List of matched keywords
    
    # User tracking
    status = Column(String(50), default="new", index=True)  # new, viewed, applied, rejected, saved
    notes = Column(Text, nullable=True)
    is_new = Column(Boolean, default=True, index=True)
    
    discovered_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    search_criteria = relationship("SearchCriteria", back_populates="jobs")
    follow_ups = relationship("FollowUp", back_populates="job")


class FollowUp(Base):
    """Follow-up reminders for jobs"""
    __tablename__ = "follow_ups"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    follow_up_date = Column(DateTime, nullable=False, index=True)
    action_type = Column(String(100), nullable=False)  # apply, interview, follow-up, etc.
    notes = Column(Text, nullable=True)
    completed = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    job = relationship("Job", back_populates="follow_ups")


class CrawlLog(Base):
    """Crawl execution log"""
    __tablename__ = "crawl_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    search_criteria_id = Column(Integer, ForeignKey("search_criteria.id"), nullable=False, index=True)
    platform = Column(String(50), nullable=False)
    started_at = Column(DateTime, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, index=True)  # running, completed, failed
    jobs_found = Column(Integer, default=0)
    new_jobs = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    search_criteria = relationship("SearchCriteria", back_populates="crawl_logs")

