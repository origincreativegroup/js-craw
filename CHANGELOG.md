# Changelog

## [Unreleased] React TypeScript Frontend Migration

### Major Features

#### 1. Complete Frontend Rewrite
- **Migrated**: From static HTML to modern React TypeScript application
- **Technology Stack**:
  - React 18.2 with TypeScript
  - Vite for fast development and optimized builds
  - React Router for client-side routing
  - Axios for API communication
  - Lucide React for modern iconography
  - Recharts for data visualization
  - Date-fns for date manipulation

#### 2. New Frontend Architecture
- **Component-Based Structure**: Modular, reusable components
  - Layout components (Layout, Card, Button)
  - Job-specific components (JobCard)
  - AI Chat integration (AIChat, OpenWebUIChat)
- **Page Components**: Full-featured pages for all major features
  - Dashboard with real-time statistics
  - Jobs listing with filtering and search
  - Companies management
  - Automation monitoring and control
  - Discovery for job exploration
  - Apply tracking and management
  - Follow-ups and task management
  - Settings configuration
- **Type Safety**: Full TypeScript coverage with proper type definitions
- **API Integration**: Centralized API service layer (`services/api.ts`)

#### 3. Enhanced User Experience
- **Modern UI**: Clean, responsive design with CSS modules
- **Client-Side Routing**: Fast navigation without page reloads
- **Real-Time Updates**: Polling-based updates for live data
- **Better Error Handling**: User-friendly error messages and loading states
- **Improved Performance**: Optimized bundle size with Vite

#### 4. OpenWebUI Integration
- **Added**: `app/services/openwebui_service.py` - OpenWebUI service integration
- **Added**: OpenWebUIChat component for AI chat interface
- **Enhanced**: AI chat capabilities with OpenWebUI backend
- **Updated**: Documentation for OpenWebUI integration

#### 5. Backend Enhancements
- **Enhanced API**: Expanded API endpoints for frontend needs
  - Comprehensive automation endpoints
  - Enhanced status and logging endpoints
  - Company management improvements
- **Database Migrations**: Updated models and migration scripts
- **Configuration**: Added OpenWebUI configuration options

### Technical Details

#### New Files
- `frontend/` - Complete React TypeScript application
  - `src/` - Source code
    - `components/` - Reusable UI components
    - `pages/` - Page components
    - `services/` - API service layer
    - `types/` - TypeScript type definitions
  - `package.json` - Frontend dependencies
  - `vite.config.ts` - Vite build configuration
  - `tsconfig.json` - TypeScript configuration
- `app/services/openwebui_service.py` - OpenWebUI integration service
- `scripts/seed_settings.py` - Settings seeding script
- `search_recipes.json` - Search recipe configurations

#### Modified Files
- `Dockerfile` - Added Node.js build step for frontend compilation
- `app/api.py` - Enhanced API endpoints for frontend integration
- `app/config.py` - Added OpenWebUI configuration
- `app/models.py` - Updated database models
- `app/utils/company_loader.py` - Enhanced company loading utilities
- `main.py` - Updated static file serving
- `scripts/migrate_database.py` - Enhanced migration scripts
- `docs/OPENWEBUI_INTEGRATION.md` - Updated OpenWebUI documentation

#### Build Process
- Frontend builds to `static/` directory using Vite
- Dockerfile now builds frontend during image creation
- Static files served by FastAPI from `/static` mount point
- Production-ready optimized builds with code splitting

### Migration Notes

1. **Backward Compatibility**: Old static HTML remains in `static/` directory until fully migrated
2. **Build Requirements**: Node.js 20+ required for frontend builds
3. **Development**: Use `npm run dev` in `frontend/` directory for local development
4. **Production**: Frontend is automatically built during Docker image creation

---

## [Previous] Automation Command Center UX Overhaul

### Major Features

#### 1. Automation Command Center Dashboard
- **Added**: Complete dashboard overhaul with real-time automation monitoring
- **Features**:
  - Real-time telemetry display (status, current run, next run ETA, queue length)
  - Timeline/event stream visualization of automation events
  - Per-automation health chips with color-coded status indicators
  - Drill-down panels for Selenium-based, API-based, and AI-assisted crawlers
  - Full automation control (pause/resume, adjust interval, cancel crawls)

#### 2. Enhanced Backend API
- **Added**: `/api/automation/scheduler` - Get scheduler metadata and next run time
- **Added**: `PATCH /api/automation/scheduler` - Adjust crawl interval dynamically
- **Added**: `POST /api/automation/pause` - Pause scheduled crawls
- **Added**: `POST /api/automation/resume` - Resume scheduled crawls
- **Added**: `/api/crawl/logs` - Detailed event stream with filtering
- **Enhanced**: `/api/crawl/status` - Now includes:
  - Queue length and current progress
  - ETA calculation for running crawls
  - Per-crawler-type health metrics (success rate, avg duration, error count)
  - Crawler type classification (Selenium, API, AI)

#### 3. Orchestrator Enhancements
- **Added**: Progress tracking (current company X of Y, queue length)
- **Added**: ETA calculation based on rolling average of company crawl durations
- **Added**: Crawler type classification method
- **Added**: Real-time progress state accessible via API

#### 4. Frontend Improvements
- **Replaced**: Dashboard tab with comprehensive Automation Command Center
- **Added**: Real-time polling (status every 3s, scheduler every 10s)
- **Added**: Interactive timeline showing last 24 hours of automation events
- **Added**: Expandable drill-down panels for crawler type analysis
- **Added**: Control panel with interval adjustment and automation controls
- **Added**: Color-coded health indicators (green/yellow/red)

### Technical Details

#### New API Endpoints
- `GET /api/automation/scheduler` - Scheduler metadata
- `PATCH /api/automation/scheduler` - Update interval
- `POST /api/automation/pause` - Pause scheduler
- `POST /api/automation/resume` - Resume scheduler
- `GET /api/crawl/logs` - Event stream with filters

#### Modified Files
- `app/crawler/orchestrator.py` - Added progress tracking and crawler classification
- `app/api.py` - New automation endpoints and enhanced status endpoint
- `main.py` - Exposed scheduler instance to API
- `static/index.html` - Complete dashboard overhaul

### UX Improvements
- Clean, simple interface maintaining existing design system
- Real-time updates without page refresh
- Clear visual hierarchy with color-coded status indicators
- Actionable controls for immediate automation management
- Responsive design for mobile devices

---

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
