# AI Filtering Unification

## Overview

All crawlers now use a unified AI filtering system that analyzes jobs in real-time during crawling, ensuring consistent job matching and ranking across all platforms.

## Architecture

### Unified Filtering Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     Crawler Process                          │
│                                                               │
│  1. Crawl Jobs (LinkedIn/Indeed/Greenhouse/Lever/Generic)   │
│           │                                                   │
│           ▼                                                   │
│  2. Apply AI Filter (JobFilter.filter_jobs_batch)           │
│     - Matches against user profile                           │
│     - Scores jobs 0-100                                      │
│     - Marks recommended jobs                                 │
│           │                                                   │
│           ▼                                                   │
│  3. Save Jobs with AI Analysis                               │
│     - ai_match_score                                         │
│     - ai_recommended                                         │
│     - ai_summary, pros, cons                                 │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Key Changes

### 1. JobFilter Class (`app/ai/job_filter.py`)

**New Methods:**
- `filter_job(job_data, user_profile)` - Filter single job in real-time
- `filter_jobs_batch(jobs, user_profile)` - Filter multiple jobs efficiently
- `_get_user_profile_cached()` - Cached user profile for performance

**Features:**
- Real-time AI filtering during crawling
- User profile caching to reduce database queries
- Consistent scoring across all crawler types
- Returns filtered list with AI analysis data included

### 2. CrawlerOrchestrator (`app/crawler/orchestrator.py`)

**Updated Methods:**
- `crawl_all_companies()` - Now applies AI filtering before saving jobs
- `_run_platform_search()` - Applies AI filtering to LinkedIn/Indeed jobs
- `_run_company_search()` - Applies AI filtering to company crawl jobs
- `_process_jobs()` - Accepts pre-filtered jobs with AI data
- `_process_company_jobs()` - Accepts pre-filtered jobs with AI data

**Changes:**
- All crawlers now use `JobFilter.filter_jobs_batch()` before saving
- AI analysis data is preserved from filtering to database
- Consistent filtering across all crawler types

## Benefits

1. **Consistency**: All jobs are analyzed using the same AI criteria
2. **Performance**: User profile cached for all filtering operations
3. **Quality**: Jobs are filtered before saving, reducing database clutter
4. **Flexibility**: Can easily adjust filtering criteria in one place
5. **Transparency**: All jobs have AI match scores and recommendations

## Usage

### Automatic Filtering

All crawlers automatically apply AI filtering:

```python
# In orchestrator:
jobs = await self._crawl_company(company)  # Fetch jobs
filtered_jobs = await self.job_filter.filter_jobs_batch(jobs, user_profile)  # AI filter
new_jobs = await self._process_company_jobs(db, search, company, filtered_jobs, skip_ai_analysis=True)  # Save
```

### Manual Filtering

You can also filter jobs manually:

```python
from app.ai.job_filter import JobFilter

filter = JobFilter()

# Filter single job
result = await filter.filter_job(job_data)
if result['should_keep']:
    # Process job with result['match_score'], result['recommended'], etc.

# Filter multiple jobs
filtered_jobs = await filter.filter_jobs_batch(jobs)
# filtered_jobs contains only jobs that passed filter, with AI data included
```

## AI Analysis Fields

Each job now includes:

- `ai_match_score`: 0-100 match score
- `ai_recommended`: Boolean recommendation flag
- `ai_summary`: Brief summary of the match
- `ai_pros`: List of positive aspects
- `ai_cons`: List of potential concerns
- `ai_keywords_matched`: List of matched keywords

## Configuration

User profile/preferences are stored in the `UserProfile` model:

- `preferences.keywords`: Job keywords/interests
- `preferences.remote_preferred`: Remote work preference
- `preferences.experience_level`: Desired experience level
- `skills`: List of user skills

These are used by the AI to match and score jobs.

## Performance Considerations

1. **Caching**: User profile is cached after first load
2. **Batch Processing**: Multiple jobs are filtered together
3. **Error Handling**: Filtering errors don't block job saving (jobs saved with neutral score)
4. **Parallel Processing**: Can be extended to filter jobs in parallel

## Future Enhancements

1. **Filter Threshold**: Option to filter out low-scoring jobs (< 30)
2. **Custom Criteria**: Allow users to set custom filtering criteria
3. **Learning**: Track which jobs users apply to and adjust scoring
4. **Parallel Filtering**: Filter multiple jobs concurrently for better performance
