"""Database models"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey, JSON, LargeBinary
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class User(Base):
    """User credentials (deprecated - kept for backward compatibility)"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), unique=True, nullable=False, index=True)  # Deprecated - no longer used
    email = Column(String(255), nullable=False)
    encrypted_password = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AppSettings(Base):
    """Application settings stored in database"""
    __tablename__ = "app_settings"
    
    key = Column(String(255), primary_key=True, index=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Company(Base):
    """Company with career page"""
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    career_page_url = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    crawler_type = Column(String(50), nullable=False)  # greenhouse, lever, workday, generic, indeed, linkedin
    crawler_config = Column(JSON, nullable=True)  # Custom parsing rules
    last_crawled_at = Column(DateTime, nullable=True)
    jobs_found_total = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Company lifecycle management fields
    consecutive_empty_crawls = Column(Integer, default=0, index=True)  # Track failed crawl streak
    viability_score = Column(Float, nullable=True, index=True)  # AI-assessed health score (0-100)
    viability_last_checked = Column(DateTime, nullable=True)  # Last AI analysis timestamp
    discovery_source = Column(String(50), nullable=True)  # How company was found (linkedin/indeed/web_search/manual)
    last_successful_crawl = Column(DateTime, nullable=True, index=True)  # Last time jobs were found
    priority_score = Column(Float, default=0.0, index=True)  # Crawl priority ranking

    # Relationships
    jobs = relationship("Job", back_populates="company_relation")
    crawl_fallbacks = relationship("CrawlFallback", back_populates="company")


class PendingCompany(Base):
    """Companies discovered but pending approval"""
    __tablename__ = "pending_companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    career_page_url = Column(Text, nullable=False)
    discovery_source = Column(String(50), nullable=False)  # linkedin, indeed, web_search
    confidence_score = Column(Float, nullable=False, index=True)  # AI confidence score 0-100
    crawler_type = Column(String(50), nullable=False)  # greenhouse, lever, workday, generic
    crawler_config = Column(JSON, nullable=True)
    discovery_metadata = Column(JSON, nullable=True)  # Additional discovery metadata
    status = Column(String(20), default="pending", index=True)  # pending, approved, rejected
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
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
    platforms = Column(JSON, default=[])  # Deprecated - no longer used
    target_companies = Column(JSON, nullable=True)  # List of company IDs to monitor
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
    search_criteria_id = Column(Integer, ForeignKey("search_criteria.id"), nullable=True, index=True)  # Now nullable for direct company crawls
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)  # New: for company-based crawls
    platform = Column(String(50), nullable=True, index=True)  # Deprecated - legacy field
    external_id = Column(String(255), nullable=False, index=True)  # Platform-specific ID
    title = Column(String(500), nullable=False)
    company = Column(String(255), nullable=False)  # Company name string
    location = Column(String(255), nullable=True)
    job_type = Column(String(50), nullable=True)
    url = Column(Text, nullable=False)
    source_url = Column(Text, nullable=True)  # New: Direct link to career page posting
    description = Column(Text, nullable=True)
    posted_date = Column(DateTime, nullable=True)

    # AI analysis
    ai_match_score = Column(Float, nullable=True)
    ai_summary = Column(Text, nullable=True)
    ai_pros = Column(JSON, nullable=True)  # List of pros
    ai_cons = Column(JSON, nullable=True)  # List of cons
    ai_keywords_matched = Column(JSON, nullable=True)  # List of matched keywords
    ai_rank = Column(Integer, nullable=True, index=True)  # Daily ranking (1-5 for top 5)
    ai_recommended = Column(Boolean, default=False, index=True)  # AI recommended flag
    ai_selected_date = Column(DateTime, nullable=True, index=True)  # Date selected as top job

    # User tracking
    status = Column(String(50), default="new", index=True)  # new, viewed, applied, rejected, saved, archived
    notes = Column(Text, nullable=True)
    is_new = Column(Boolean, default=True, index=True)
    archived_at = Column(DateTime, nullable=True, index=True)  # When job was archived (90+ days old)

    discovered_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    search_criteria = relationship("SearchCriteria", back_populates="jobs")
    company_relation = relationship("Company", back_populates="jobs")  # Renamed to avoid conflict with company column
    follow_ups = relationship("FollowUp", back_populates="job")
    generated_documents = relationship("GeneratedDocument", back_populates="job")
    tasks = relationship("Task", back_populates="job")
    applications = relationship("Application", back_populates="job")
    feedback = relationship("JobFeedback", back_populates="job")


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
    search_criteria_id = Column(Integer, ForeignKey("search_criteria.id"), nullable=True, index=True)  # Now nullable
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)  # New: for company-based crawls
    platform = Column(String(50), nullable=False)
    started_at = Column(DateTime, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, index=True)  # running, completed, failed
    jobs_found = Column(Integer, default=0)
    new_jobs = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    search_criteria = relationship("SearchCriteria", back_populates="crawl_logs")


class UserProfile(Base):
    """User profile with preferences and resume data"""
    __tablename__ = "user_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True, index=True)  # Optional: link to user if needed
    base_resume = Column(Text, nullable=True)  # User's base resume content
    skills = Column(JSON, nullable=True)  # List of skills
    experience = Column(JSON, nullable=True)  # List of work experience
    education = Column(JSON, nullable=True)  # Education background
    preferences = Column(JSON, nullable=True)  # Default search preferences (keywords, location, etc.)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    documents = relationship("UserDocument", back_populates="profile")


class UserDocument(Base):
    """User-provided documents that can be analyzed and reused"""
    __tablename__ = "user_documents"

    id = Column(Integer, primary_key=True, index=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    raw_file = Column(LargeBinary, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    profile = relationship("UserProfile", back_populates="documents")


class GeneratedDocument(Base):
    """Generated resume or cover letter for a job"""
    __tablename__ = "generated_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    document_type = Column(String(20), nullable=False, index=True)  # "resume" or "cover_letter"
    content = Column(Text, nullable=False)  # Generated document content
    generated_at = Column(DateTime, default=datetime.utcnow, index=True)
    file_path = Column(String(500), nullable=True)  # Optional: path to saved file
    
    # Review workflow
    review_status = Column(String(50), default="pending", index=True)  # pending, approved, rejected, edited
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)  # User notes from review
    edited_content = Column(Text, nullable=True)  # User-edited version
    
    # Relationships
    job = relationship("Job", back_populates="generated_documents")


class CrawlFallback(Base):
    """Track which fallback methods succeeded for each company"""
    __tablename__ = "crawl_fallbacks"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    method_used = Column(String(50), nullable=False)  # career_page, linkedin_fallback, indeed_fallback, ai_web_search
    success_count = Column(Integer, default=0)  # How many times this method succeeded
    last_success_at = Column(DateTime, nullable=True)  # Last time this method worked
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="crawl_fallbacks")


class Task(Base):
    """Task workspace for job-related actions"""
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    
    # Task classification
    task_type = Column(String(50), nullable=False, index=True)  # apply, follow_up, research, network, prepare_interview
    priority = Column(String(20), nullable=False, default="medium", index=True)  # high, medium, low
    status = Column(String(20), nullable=False, default="pending", index=True)  # pending, in_progress, completed, snoozed, cancelled
    
    # Scheduling
    due_date = Column(DateTime, nullable=False, index=True)
    snooze_until = Column(DateTime, nullable=True, index=True)
    snooze_count = Column(Integer, default=0)  # Track how many times task was snoozed
    
    # Task details
    title = Column(String(500), nullable=False)  # Task title/description
    notes = Column(Text, nullable=True)  # Additional notes or context
    
    # Metadata
    recommended_by = Column(String(50), nullable=True)  # AI, system, user
    ai_insights = Column(JSON, nullable=True)  # Store AI insights that led to task creation
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    job = relationship("Job", back_populates="tasks")
    
    # Notifications
    notify_enabled = Column(Boolean, default=True, index=True)  # Enable/disable task notifications


class Application(Base):
    """Application tracking for jobs - full lifecycle beyond simple job status"""
    __tablename__ = "applications"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    
    # Application status tracking
    status = Column(String(50), nullable=False, default="queued", index=True)  # queued, drafting, submitted, interviewing, rejected, accepted
    application_date = Column(DateTime, nullable=True, index=True)  # When application was actually submitted
    
    # Application details
    portal_url = Column(Text, nullable=True)  # Link to application portal
    confirmation_number = Column(String(255), nullable=True)  # Application confirmation/tracking number
    resume_version_id = Column(Integer, ForeignKey("generated_documents.id"), nullable=True)  # Link to resume version used
    cover_letter_id = Column(Integer, ForeignKey("generated_documents.id"), nullable=True)  # Link to cover letter used
    notes = Column(Text, nullable=True)  # Additional notes about the application
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    job = relationship("Job", back_populates="applications")
    resume_document = relationship("GeneratedDocument", foreign_keys=[resume_version_id], post_update=True)
    cover_letter_document = relationship("GeneratedDocument", foreign_keys=[cover_letter_id], post_update=True)


class JobFeedback(Base):
    """User feedback on AI job recommendations"""
    __tablename__ = "job_feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    
    # Feedback data
    feedback_type = Column(String(50), nullable=False, index=True)  # match_score, recommendation, quality
    feedback_value = Column(String(50), nullable=False)  # positive, negative, neutral, or numeric value
    feedback_text = Column(Text, nullable=True)  # Optional text feedback
    ai_match_score_actual = Column(Float, nullable=True)  # User's assessment of actual match score
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    job = relationship("Job", back_populates="feedback")
