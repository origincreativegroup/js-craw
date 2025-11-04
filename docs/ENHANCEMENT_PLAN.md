# Enhancement Plan: Simplified Crawling & AI-Powered Application Generation

## Overview

This document outlines the planned enhancements to transform the job search crawler into a fully automated system that:
1. Crawls all companies from CSV automatically
2. Builds a comprehensive job database
3. Uses AI to filter and rank jobs based on criteria
4. Automatically generates custom resumes and cover letters for top 5 jobs daily at 3 PM

## Current State

### Existing Features
- ✅ Company-based crawling (Greenhouse, Lever, Generic)
- ✅ Search criteria with keywords, location, remote preferences
- ✅ AI job analysis and match scoring
- ✅ Database storage for companies and jobs
- ✅ Web dashboard for viewing jobs
- ✅ Notification system

### Current Limitations
- Requires manual search criteria configuration
- Doesn't crawl all companies automatically
- No automatic resume/cover letter generation
- AI analysis happens but doesn't drive application workflow

## Planned Changes

### 1. Simplified Crawling Strategy

**Current Approach:**
- User creates search criteria with keywords/location
- Crawler runs searches based on criteria
- Jobs filtered by search parameters

**New Approach:**
- **Crawl ALL active companies every time** (no keyword/location filtering during crawl)
- Store ALL jobs in database regardless of match
- Let AI filter and rank jobs AFTER they're in the database
- This ensures comprehensive coverage and no missed opportunities

**Benefits:**
- Simpler logic: just crawl everything
- Complete job database for AI to analyze
- No need for complex search criteria matching during crawl
- AI can do more sophisticated matching later

### 2. Database Population from companies.csv

**Action Items:**
- ✅ Script already exists: `scripts/seed_companies.py`
- Ensure all companies from CSV are in database
- Set all companies to `is_active=True` by default
- Track which companies are successfully crawled

**Implementation:**
```python
# Run seed script to populate database
python scripts/seed_companies.py
```

### 3. Enhanced AI Job Filtering Agent

**New Component: `app/ai/job_filter.py`**

**Purpose:**
- Analyze all new jobs in database
- Score jobs based on user preferences (stored as "default criteria")
- Rank jobs and mark top matches
- Create daily "best matches" list

**Features:**
- User-defined default criteria (keywords, location preferences, experience level, etc.)
- AI analyzes job descriptions against criteria
- Match score calculation (0-100)
- Tag jobs as "recommended", "top_match", etc.
- Store recommendations in database

**Database Changes:**
```python
# Add to Job model
ai_rank = Column(Integer, nullable=True)  # Daily ranking (1-5 for top 5)
ai_recommended = Column(Boolean, default=False)  # AI recommended flag
ai_selected_date = Column(DateTime, nullable=True)  # Date selected as top job
```

### 4. Automatic Resume & Cover Letter Generation

**New Component: `app/ai/document_generator.py`**

**Purpose:**
- Generate custom resume for each of top 5 jobs
- Generate custom cover letter for each job
- Tailor content based on job description
- Store generated documents

**Workflow:**
1. **3 PM Daily Trigger** (APScheduler cron job)
2. Query top 5 jobs from today with highest AI match scores
3. For each job:
   - Load user's base resume/background
   - Generate tailored resume highlighting relevant skills/experience
   - Generate cover letter addressing job requirements
   - Save documents to database/filesystem

**Database Changes:**
```python
# New model: GeneratedDocument
class GeneratedDocument(Base):
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    document_type = Column(String(20))  # "resume" or "cover_letter"
    content = Column(Text)  # Generated document content
    generated_at = Column(DateTime, default=datetime.utcnow)
    file_path = Column(String(500))  # Optional: path to saved file
```

**User Profile Data:**
```python
# New model: UserProfile
class UserProfile(Base):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    base_resume = Column(Text)  # User's base resume content
    skills = Column(JSON)  # List of skills
    experience = Column(JSON)  # List of work experience
    education = Column(JSON)  # Education background
    preferences = Column(JSON)  # Default search preferences
    updated_at = Column(DateTime, default=datetime.utcnow)
```

### 5. Simplified Orchestrator Logic

**Current:**
```python
async def run_all_searches(self):
    # Get active search criteria
    # For each search, crawl platforms with criteria
    # Filter jobs by search criteria
```

**New:**
```python
async def crawl_all_companies(self):
    # Get all active companies
    # For each company, crawl all jobs (no filtering)
    # Store ALL jobs in database
    # Trigger AI filtering agent after crawl
```

### 6. Default Search Criteria

**New Model/Storage:**
- Store "default preferences" in UserProfile
- Used by AI filter to rank jobs
- Not used during crawl (we crawl everything)

**Default Criteria Fields:**
- Keywords/skills user wants in jobs
- Preferred locations (if any)
- Remote preference
- Experience level preference
- Salary range (if specified)
- Company preferences (industries, etc.)

## Implementation Plan

### Phase 1: Database & Models
1. ✅ Seed companies from CSV
2. Add `UserProfile` model
3. Add `GeneratedDocument` model
4. Add fields to `Job` model for ranking
5. Create database migrations

### Phase 2: Simplified Crawling
1. Update `orchestrator.py` to crawl all companies
2. Remove search criteria filtering from crawl
3. Store all jobs regardless of match
4. Update API endpoints

### Phase 3: AI Filtering Agent
1. Create `app/ai/job_filter.py`
2. Implement default criteria storage
3. Implement job ranking algorithm
4. Create daily filtering job

### Phase 4: Document Generation
1. Create `app/ai/document_generator.py`
2. Implement resume generation
3. Implement cover letter generation
4. Add file storage for documents
5. Create 3 PM scheduled job

### Phase 5: UI Updates
1. Add user profile management page
2. Show top 5 jobs prominently
3. Display generated documents
4. Download documents functionality

### Phase 6: Testing & Refinement
1. Test full workflow
2. Validate document quality
3. Tune AI prompts
4. Performance optimization

## File Structure Changes

```
app/
├── ai/
│   ├── analyzer.py          # Existing: job analysis
│   ├── job_filter.py        # NEW: Job filtering and ranking
│   └── document_generator.py # NEW: Resume/cover letter generation
├── models.py                # UPDATED: New models
├── crawler/
│   └── orchestrator.py      # UPDATED: Simplified crawling
└── api.py                   # UPDATED: New endpoints
```

## Configuration Changes

### New Environment Variables
```env
# Document generation
RESUME_STORAGE_PATH=/app/data/resumes
COVER_LETTER_STORAGE_PATH=/app/data/cover_letters
DAILY_TOP_JOBS_COUNT=5
DAILY_GENERATION_TIME=15:00  # 3 PM
```

### Settings Updates
```python
# app/config.py
DAILY_TOP_JOBS_COUNT: int = 5
DAILY_GENERATION_TIME: str = "15:00"  # 3 PM
RESUME_STORAGE_PATH: str = "/app/data/resumes"
COVER_LETTER_STORAGE_PATH: str = "/app/data/cover_letters"
```

## Database Schema Updates

### New Tables

#### user_profiles
```sql
CREATE TABLE user_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    base_resume TEXT,
    skills JSONB,
    experience JSONB,
    education JSONB,
    preferences JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### generated_documents
```sql
CREATE TABLE generated_documents (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id),
    document_type VARCHAR(20),  -- 'resume' or 'cover_letter'
    content TEXT,
    file_path VARCHAR(500),
    generated_at TIMESTAMP DEFAULT NOW()
);
```

### Updated Tables

#### jobs
```sql
ALTER TABLE jobs ADD COLUMN ai_rank INTEGER;
ALTER TABLE jobs ADD COLUMN ai_recommended BOOLEAN DEFAULT FALSE;
ALTER TABLE jobs ADD COLUMN ai_selected_date TIMESTAMP;
```

## API Endpoints

### New Endpoints

#### User Profile
- `GET /api/profile` - Get user profile
- `POST /api/profile` - Create/update user profile
- `PUT /api/profile/preferences` - Update preferences

#### Generated Documents
- `GET /api/documents` - List all generated documents
- `GET /api/documents/{job_id}` - Get documents for a job
- `GET /api/documents/{id}/download` - Download document
- `POST /api/documents/generate/{job_id}` - Manually generate documents

#### Top Jobs
- `GET /api/jobs/top` - Get top 5 jobs of the day
- `GET /api/jobs/recommended` - Get all AI-recommended jobs

### Updated Endpoints
- `POST /api/crawl/run` - Now crawls all companies (no search criteria needed)

## Scheduling Changes

### Current Schedule
- Every 30 minutes: Crawl based on search criteria

### New Schedule
- Every 30 minutes: Crawl ALL active companies
- Daily at 3 PM: Generate documents for top 5 jobs
- Daily at 3:30 PM: Run AI filtering on all new jobs

## Migration Strategy

1. **Backward Compatibility**
   - Keep search_criteria table (for reference/history)
   - Jobs still linked to search_criteria (but may be null for new jobs)
   - Gradual migration

2. **Data Migration**
   - Create user profiles for existing users
   - Mark existing high-score jobs as recommended
   - Preserve all existing data

3. **Rollout**
   - Deploy database changes first
   - Deploy simplified crawler
   - Deploy AI filter
   - Deploy document generator
   - Update UI

## Success Metrics

- **Crawl Coverage**: All active companies crawled successfully
- **Job Database**: Comprehensive database of all jobs from all companies
- **AI Accuracy**: Top 5 jobs are highly relevant matches
- **Document Quality**: Generated resumes/cover letters are professional and tailored
- **Automation**: Zero manual intervention needed for daily workflow

## Risks & Mitigations

### Risk: Too Many Jobs in Database
**Mitigation**: 
- Implement job deduplication
- Archive old jobs (older than 90 days)
- Index optimization

### Risk: AI Filter Quality
**Mitigation**:
- Allow manual override
- Continuous prompt improvement
- User feedback loop

### Risk: Document Generation Quality
**Mitigation**:
- Allow user to review/edit before sending
- Template system for consistency
- Human review of first few documents

### Risk: Resource Usage
**Mitigation**:
- Rate limiting on crawls
- Batch processing for AI
- Efficient document storage

## Timeline Estimate

- **Phase 1** (Database): 1 hour
- **Phase 2** (Crawling): 2 hours
- **Phase 3** (AI Filter): 3 hours
- **Phase 4** (Documents): 4 hours
- **Phase 5** (UI): 2 hours
- **Phase 6** (Testing): 2 hours

**Total**: ~14 hours

## Next Steps

1. ✅ Review and approve this plan
2. Implement Phase 1 (Database & Models)
3. Implement Phase 2 (Simplified Crawling)
4. Implement Phase 3 (AI Filtering)
5. Implement Phase 4 (Document Generation)
6. Implement Phase 5 (UI Updates)
7. Testing and refinement
8. Deploy to production

---

**Status**: Plan Documented - Ready for Implementation
**Last Updated**: 2025-11-03
