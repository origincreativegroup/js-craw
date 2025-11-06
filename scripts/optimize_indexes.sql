-- Database Index Optimization Script
-- This script creates additional indexes for improved query performance on large job datasets

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_jobs_company_status ON jobs(company_id, status);
CREATE INDEX IF NOT EXISTS idx_jobs_discovered_status ON jobs(discovered_at, status);
CREATE INDEX IF NOT EXISTS idx_jobs_ai_score_recommended ON jobs(ai_match_score DESC, ai_recommended) WHERE ai_match_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_jobs_archived_discovered ON jobs(archived_at, discovered_at) WHERE archived_at IS NOT NULL;

-- Index for job search by title (using text search for better performance)
CREATE INDEX IF NOT EXISTS idx_jobs_title_trgm ON jobs USING gin (title gin_trgm_ops);
-- Note: Requires pg_trgm extension: CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Index for URL lookups (for deduplication)
CREATE INDEX IF NOT EXISTS idx_jobs_url_normalized ON jobs(lower(regexp_replace(url, '[?#].*', '')));

-- Index for job filtering by multiple criteria
CREATE INDEX IF NOT EXISTS idx_jobs_company_status_new ON jobs(company_id, status, is_new) WHERE status != 'archived';

-- Index for AI ranking queries
CREATE INDEX IF NOT EXISTS idx_jobs_ai_rank_date ON jobs(ai_rank, ai_selected_date) WHERE ai_rank IS NOT NULL;

-- Index for date range queries
CREATE INDEX IF NOT EXISTS idx_jobs_discovered_at_btree ON jobs USING btree(discovered_at DESC);

-- Index for company-job relationship queries
CREATE INDEX IF NOT EXISTS idx_jobs_company_active ON jobs(company_id, is_new) WHERE archived_at IS NULL;

-- Index for application status queries
CREATE INDEX IF NOT EXISTS idx_applications_job_status ON applications(job_id, status);

-- Index for task queries
CREATE INDEX IF NOT EXISTS idx_tasks_job_status_due ON tasks(job_id, status, due_date);

-- Index for follow-up queries
CREATE INDEX IF NOT EXISTS idx_followups_job_date ON follow_ups(job_id, follow_up_date);

-- Analyze tables to update statistics
ANALYZE jobs;
ANALYZE applications;
ANALYZE tasks;
ANALYZE follow_ups;
ANALYZE companies;

