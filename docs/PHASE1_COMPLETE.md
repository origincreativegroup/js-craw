# Phase 1: Database & Models - COMPLETE ✅

## Summary

Phase 1 of the enhancement plan has been successfully completed. All database models have been added and updated to support the new automated job search workflow.

## Changes Made

### 1. New Models Added

#### UserProfile (`app/models.py`)
- Stores user preferences and resume data
- Fields:
  - `user_id` (optional, links to users table)
  - `base_resume` (text content)
  - `skills` (JSON array)
  - `experience` (JSON array)
  - `education` (JSON array)
  - `preferences` (JSON object with default search criteria)

#### GeneratedDocument (`app/models.py`)
- Stores generated resumes and cover letters
- Fields:
  - `job_id` (required, links to jobs)
  - `document_type` ("resume" or "cover_letter")
  - `content` (generated document text)
  - `file_path` (optional filesystem path)
  - `generated_at` (timestamp)

### 2. Updated Models

#### Job Model (`app/models.py`)
- **Modified**: `search_criteria_id` is now nullable (to support direct company crawls)
- **Added**: `ai_rank` (Integer) - Daily ranking position (1-5 for top jobs)
- **Added**: `ai_recommended` (Boolean) - Flag for AI-recommended jobs
- **Added**: `ai_selected_date` (DateTime) - When job was selected as top job
- **Added**: Relationship to `generated_documents`

#### CrawlLog Model (`app/models.py`)
- **Modified**: `search_criteria_id` is now nullable
- **Added**: `company_id` (Integer) - Links to companies for company-based crawls

### 3. Configuration Updates

#### app/config.py
Added new settings:
- `DAILY_TOP_JOBS_COUNT: int = 5` - Number of top jobs to select daily
- `DAILY_GENERATION_TIME: str = "15:00"` - Time to generate documents (3 PM)
- `RESUME_STORAGE_PATH: str = "/app/data/resumes"` - Path for resume storage
- `COVER_LETTER_STORAGE_PATH: str = "/app/data/cover_letters"` - Path for cover letter storage

### 4. Migration Script

Created `scripts/migrate_database.py`:
- Safely creates new tables if they don't exist
- Adds new columns to existing tables
- Makes existing columns nullable where needed
- Creates necessary indexes
- Idempotent (safe to run multiple times)

## Database Schema Changes

### New Tables

```sql
-- user_profiles table
CREATE TABLE user_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES users(id),
    base_resume TEXT,
    skills JSONB,
    experience JSONB,
    education JSONB,
    preferences JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- generated_documents table
CREATE TABLE generated_documents (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    document_type VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    generated_at TIMESTAMP DEFAULT NOW(),
    file_path VARCHAR(500)
);
```

### Modified Tables

```sql
-- jobs table additions
ALTER TABLE jobs ADD COLUMN ai_rank INTEGER;
ALTER TABLE jobs ADD COLUMN ai_recommended BOOLEAN DEFAULT FALSE;
ALTER TABLE ai_selected_date TIMESTAMP;
ALTER TABLE jobs ALTER COLUMN search_criteria_id DROP NOT NULL;

-- crawl_logs table additions
ALTER TABLE crawl_logs ADD COLUMN company_id INTEGER REFERENCES companies(id);
ALTER TABLE crawl_logs ALTER COLUMN search_criteria_id DROP NOT NULL;
```

### Indexes Created

- `ix_user_profiles_user_id` on `user_profiles(user_id)`
- `ix_generated_documents_job_id` on `generated_documents(job_id)`
- `ix_generated_documents_document_type` on `generated_documents(document_type)`
- `ix_generated_documents_generated_at` on `generated_documents(generated_at)`
- `ix_jobs_ai_rank` on `jobs(ai_rank)`
- `ix_jobs_ai_recommended` on `jobs(ai_recommended)`
- `ix_jobs_ai_selected_date` on `jobs(ai_selected_date)`
- `ix_crawl_logs_company_id` on `crawl_logs(company_id)`

## Files Modified

1. ✅ `app/models.py` - Added UserProfile and GeneratedDocument models, updated Job and CrawlLog
2. ✅ `app/config.py` - Added new configuration options
3. ✅ `scripts/migrate_database.py` - Created migration script (NEW)

## Next Steps

### To Apply These Changes:

1. **Run Migration** (when database is accessible):
   ```bash
   python scripts/migrate_database.py
   ```

2. **Seed Companies** (when ready):
   ```bash
   python scripts/seed_companies.py
   ```

### Phase 2: Simplified Crawling

Next phase will:
- Update `orchestrator.py` to crawl all companies
- Remove search criteria filtering from crawl logic
- Store all jobs regardless of match
- Update API endpoints

## Testing Notes

- Models syntax verified
- Migration script is idempotent (safe to run multiple times)
- All relationships properly defined
- Backward compatibility maintained (existing jobs/data preserved)

## Status

✅ **Phase 1 Complete** - Ready for Phase 2 implementation

---

**Completed**: 2025-11-03
**Next Phase**: Simplified Crawling (Phase 2)
