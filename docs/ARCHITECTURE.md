# System Architecture

> **Note:** This architecture document is partially outdated. The system now includes:
> - Company-based crawling (Greenhouse, Lever, Generic, Indeed, LinkedIn)
> - React TypeScript frontend
> - AI job filtering and ranking (hourly)
> - Automated document generation (daily at 3 PM)
> - Task management system
> - Company discovery and lifecycle management
> - See [ENHANCEMENT_PLAN.md](ENHANCEMENT_PLAN.md) for current implementation status

## Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Job Search Crawler                      │
│                                                               │
│  ┌────────────────────────────────────────────────────┐     │
│  │                 Web Dashboard (FastAPI)             │     │
│  │  • React/HTML Frontend                              │     │
│  │  • REST API                                         │     │
│  │  • WebSocket for real-time updates (optional)      │     │
│  └────────────────────────────────────────────────────┘     │
│                           │                                   │
│  ┌────────────────────────────────────────────────────┐     │
│  │              Scheduler (APScheduler)                │     │
│  │  Runs every 30 minutes                              │     │
│  └────────────────────────────────────────────────────┘     │
│                           │                                   │
│         ┌─────────────────┴─────────────────┐               │
│         │                                     │               │
│  ┌──────▼──────┐                     ┌──────▼──────┐       │
│  │   LinkedIn  │                     │   Indeed     │       │
│  │   Crawler   │                     │   Crawler    │       │
│  │  (Selenium) │                     │  (Selenium)  │       │
│  └─────────────┘                     └──────────────┘       │
│         │                                     │               │
│         └─────────────────┬─────────────────┘               │
│                           │                                   │
│                  ┌────────▼────────┐                         │
│                  │  AI Analyzer    │                         │
│                  │    (Ollama)     │                         │
│                  │  • Match scoring │                        │
│                  │  • Job summaries │                        │
│                  │  • Pros/Cons     │                        │
│                  └────────┬────────┘                         │
│                           │                                   │
│                  ┌────────▼────────┐                         │
│                  │   PostgreSQL    │                         │
│                  │   • Jobs        │                         │
│                  │   • Searches    │                         │
│                  │   • Follow-ups  │                         │
│                  └─────────────────┘                         │
│                           │                                   │
│                  ┌────────▼────────┐                         │
│                  │  Notifications  │                         │
│                  │  • ntfy.sh      │────> 📱 Phone          │
│                  │  • Pushover     │                         │
│                  │  • Telegram     │                         │
│                  └─────────────────┘                         │
└───────────────────────────────────────────────────────────────┘
```

## File Structure

```
job-crawler/
├── docker-compose.yml          # Orchestrates all services
├── Dockerfile                  # Main app container
├── requirements.txt            # Python dependencies
├── main.py                     # Application entry point
├── start.sh                    # Quick start script
├── .env.example                # Environment template
├── README.md                   # Full documentation
├── SETUP.md                    # Quick setup guide
│
├── app/
│   ├── __init__.py
│   ├── config.py              # Configuration & settings
│   ├── database.py            # Database connection
│   ├── models.py              # SQLAlchemy models
│   ├── api.py                 # FastAPI routes
│   │
│   ├── crawler/
│   │   ├── __init__.py
│   │   ├── linkedin_crawler.py    # LinkedIn automation
│   │   ├── indeed_crawler.py      # Indeed automation
│   │   └── orchestrator.py        # Coordinates crawlers
│   │
│   ├── ai/
│   │   ├── __init__.py
│   │   └── analyzer.py            # Ollama integration
│   │
│   ├── notifications/
│   │   ├── __init__.py
│   │   └── notifier.py            # Push notifications
│   │
│   └── utils/
│       ├── __init__.py
│       └── crypto.py              # Password encryption
│
└── static/
    └── index.html              # Web dashboard
```

## Data Flow

1. **Scheduled Trigger** (every 30 min)
   └─> Orchestrator

2. **Orchestrator**
   ├─> Retrieves active search criteria from DB
   ├─> Gets encrypted credentials
   └─> Spawns crawlers for each platform

3. **Crawlers** (LinkedIn/Indeed)
   ├─> Login with Selenium
   ├─> Execute searches
   ├─> Parse job listings
   └─> Return raw job data

4. **AI Analyzer**
   ├─> Receives job data
   ├─> Calls Ollama API
   ├─> Generates summary, pros/cons
   ├─> Calculates match score
   └─> Returns analysis

5. **Database**
   ├─> Checks for duplicates
   ├─> Saves new jobs with analysis
   └─> Updates metadata

6. **Notification Service**
   ├─> Aggregates new jobs
   ├─> Formats message
   └─> Sends to phone

7. **Dashboard**
   ├─> User views jobs
   ├─> Updates status
   ├─> Manages searches
   └─> Tracks applications

## API Endpoints

### Search Management
- `GET /api/searches` - List all searches
- `POST /api/searches` - Create new search
- `PATCH /api/searches/{id}` - Update search
- `DELETE /api/searches/{id}` - Delete search

### Job Management
- `GET /api/jobs` - List jobs (with filters)
- `GET /api/jobs/{id}` - Get job details
- `PATCH /api/jobs/{id}` - Update job status

### Follow-ups
- `GET /api/followups` - List follow-ups
- `POST /api/followups` - Create follow-up

### System
- `POST /api/crawl/run` - Trigger manual crawl
- `GET /api/stats` - Dashboard statistics
- `POST /api/credentials` - Save platform credentials

## Database Schema

### Users
- Platform credentials (encrypted)
- Email, password hash
- Active status

### SearchCriteria
- Keywords, location, filters
- Associated platforms
- Active/inactive toggle
- Notification preferences

### Jobs
- Job details (title, company, etc.)
- Platform metadata
- AI analysis results
- User tracking (status, notes)

### FollowUps
- Scheduled reminders
- Action types
- Completion status

### CrawlLogs
- Execution history
- Success/failure tracking
- Error messages

## Security Features

1. **Credential Encryption**: Fernet symmetric encryption
2. **No External Data**: All AI processing local
3. **Encrypted Transit**: HTTPS for notifications
4. **No API Keys Stored**: Uses environment variables
5. **Database Security**: PostgreSQL with authentication

## Performance Considerations

- **Concurrent Crawling**: Uses asyncio for parallel execution
- **Rate Limiting**: Respects platform limits
- **Caching**: Redis for session management
- **Lazy Loading**: Dashboard loads data on demand
- **Database Indexing**: On external_id, discovered_at

## Scalability

Current design handles:
- 10+ active searches
- 1000+ jobs tracked
- 30-minute refresh cycle

To scale further:
- Add Redis job queue (Celery)
- Implement distributed crawling
- Add multiple Selenium nodes
- Use connection pooling
