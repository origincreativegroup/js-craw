# Changelog

## [Planned] Enhanced Automated Job Search System

### Major Changes

#### 1. Simplified Crawling Architecture
- **Changed**: Crawl ALL active companies every time (no search criteria filtering during crawl)
- **Reason**: Build comprehensive job database, let AI filter later
- **Impact**: Simpler code, complete coverage, better AI matching

#### 2. Database Population from CSV
- **Added**: Automated seeding of companies from `companies.csv`
- **Status**: Script exists (`scripts/seed_companies.py`), needs to be run
- **Count**: ~256 companies in CSV file

#### 3. AI-Powered Job Filtering Agent
- **Added**: New `app/ai/job_filter.py` component
- **Purpose**: Analyze all jobs and rank by user preferences
- **Features**:
  - Default user preferences stored in UserProfile
  - Intelligent job ranking (0-100 score)
  - Daily filtering of new jobs
  - Tagging of recommended jobs

#### 4. Automatic Resume & Cover Letter Generation
- **Added**: New `app/ai/document_generator.py` component
- **Purpose**: Generate custom documents for top 5 jobs daily
- **Schedule**: Runs at 3 PM daily
- **Features**:
  - Tailored resume generation
  - Custom cover letter creation
  - Document storage in database/filesystem
  - User profile integration

#### 5. User Profile Management
- **Added**: New `UserProfile` model
- **Stores**:
  - Base resume content
  - Skills, experience, education
  - Default search preferences
  - Application preferences

#### 6. Generated Documents Storage
- **Added**: New `GeneratedDocument` model
- **Stores**:
  - Generated resumes
  - Generated cover letters
  - Associated job IDs
  - Generation timestamps

### Database Schema Changes

#### New Tables
1. **user_profiles**
   - User background information
   - Default preferences
   - Resume base content

2. **generated_documents**
   - Generated resumes and cover letters
   - Links to jobs
   - Document metadata

#### Modified Tables
1. **jobs**
   - Added: `ai_rank` (daily ranking position)
   - Added: `ai_recommended` (boolean flag)
   - Added: `ai_selected_date` (when selected as top job)

### API Changes

#### New Endpoints
- `GET /api/profile` - Get user profile
- `POST /api/profile` - Create/update profile
- `PUT /api/profile/preferences` - Update preferences
- `GET /api/documents` - List generated documents
- `GET /api/documents/{job_id}` - Get documents for job
- `GET /api/documents/{id}/download` - Download document
- `POST /api/documents/generate/{job_id}` - Manual generation
- `GET /api/jobs/top` - Get top 5 jobs of the day
- `GET /api/jobs/recommended` - Get all recommended jobs

#### Modified Endpoints
- `POST /api/crawl/run` - Now crawls all companies (no search criteria needed)

### Configuration Changes

#### New Environment Variables
```env
DAILY_TOP_JOBS_COUNT=5
DAILY_GENERATION_TIME=15:00
RESUME_STORAGE_PATH=/app/data/resumes
COVER_LETTER_STORAGE_PATH=/app/data/cover_letters
```

### Scheduling Changes

#### New Scheduled Jobs
- **Daily at 3 PM**: Generate resumes and cover letters for top 5 jobs
- **Daily at 3:30 PM**: Run AI filtering on all new jobs

#### Modified Jobs
- **Every 30 minutes**: Now crawls ALL active companies (was: crawl based on search criteria)

### Code Structure Changes

#### New Files
- `app/ai/job_filter.py` - Job filtering and ranking agent
- `app/ai/document_generator.py` - Resume/cover letter generation

#### Modified Files
- `app/models.py` - Added UserProfile, GeneratedDocument, updated Job model
- `app/crawler/orchestrator.py` - Simplified to crawl all companies
- `app/config.py` - Added new configuration options
- `app/api.py` - Added new endpoints
- `main.py` - Added new scheduled jobs

### Migration Notes

1. **Backward Compatibility**: Existing search_criteria preserved for reference
2. **Data Migration**: Existing jobs remain, new jobs may not have search_criteria_id
3. **User Profiles**: Need to be created for existing users
4. **Gradual Rollout**: Can run old and new systems in parallel during transition

### Breaking Changes

1. **Crawling Logic**: Search criteria no longer used for filtering during crawl
2. **Job Storage**: All jobs stored regardless of match (filtering happens after)
3. **API Changes**: Some endpoints may return different data structures

### Implementation Phases

1. **Phase 1**: Database models and migrations
2. **Phase 2**: Simplified crawling
3. **Phase 3**: AI filtering agent
4. **Phase 4**: Document generation
5. **Phase 5**: UI updates
6. **Phase 6**: Testing and refinement

### Documentation

- See `docs/ENHANCEMENT_PLAN.md` for detailed implementation plan
- See `docs/ARCHITECTURE.md` for system architecture (to be updated)
- See `README.md` for user documentation (to be updated)

---

**Status**: Planned - Ready for Implementation
**Target Completion**: TBD
