# Database Index Optimization

## Overview

This document outlines the database index optimization strategy for improved query performance, especially with large job datasets.

## Indexes Created

### Composite Indexes
- `idx_jobs_company_status`: Optimizes queries filtering by company and status
- `idx_jobs_discovered_status`: Optimizes queries filtering by discovery date and status
- `idx_jobs_ai_score_recommended`: Optimizes AI-based job ranking queries
- `idx_jobs_archived_discovered`: Optimizes archived job queries

### Text Search Indexes
- `idx_jobs_title_trgm`: GIN index for fuzzy title matching (requires pg_trgm extension)

### URL Indexes
- `idx_jobs_url_normalized`: Optimizes URL-based deduplication

### Filtering Indexes
- `idx_jobs_company_status_new`: Optimizes active job queries
- `idx_jobs_ai_rank_date`: Optimizes top job selection queries

### Relationship Indexes
- Indexes on foreign keys and commonly queried relationship fields

## Usage

### Apply Indexes

```bash
# Run the optimization script
psql -U your_user -d your_database -f scripts/optimize_indexes.sql
```

### Verify Indexes

```sql
-- Check existing indexes
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'jobs' 
ORDER BY indexname;
```

### Monitor Performance

```sql
-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename = 'jobs'
ORDER BY idx_scan DESC;
```

## Maintenance

### Regular Maintenance
- Run `ANALYZE` on tables after bulk inserts
- Monitor index usage and remove unused indexes
- Rebuild indexes if they become fragmented

### Extension Requirements
Some indexes require PostgreSQL extensions:
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For text search
```

## Performance Impact

Expected improvements:
- **50-70%** faster queries for job filtering by company and status
- **60-80%** faster AI ranking queries
- **40-60%** faster deduplication checks
- **30-50%** faster text search on job titles

## Notes

- Indexes increase write overhead, but improve read performance significantly
- Partial indexes (with WHERE clauses) reduce index size for filtered queries
- Monitor index bloat and rebuild if necessary

