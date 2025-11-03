# Project Structure

This document describes the comprehensive project and implementation structure for the Job Search Crawler system.

## 📁 Directory Structure

```
js-craw/
├── app/                          # Main application package
│   ├── __init__.py               # Package initialization
│   ├── config.py                 # Configuration & settings (Pydantic)
│   ├── database.py               # Database connection & session management
│   ├── models.py                 # SQLAlchemy ORM models
│   ├── api.py                     # FastAPI routes & endpoints
│   │
│   ├── crawler/                   # Job platform crawlers
│   │   ├── __init__.py
│   │   ├── linkedin_crawler.py    # LinkedIn automation (Selenium)
│   │   ├── indeed_crawler.py      # Indeed automation (Selenium)
│   │   └── orchestrator.py        # Coordinates multi-platform crawling
│   │
│   ├── ai/                        # AI analysis modules
│   │   ├── __init__.py
│   │   └── analyzer.py           # Ollama LLM integration for job analysis
│   │
│   ├── notifications/             # Notification services
│   │   ├── __init__.py
│   │   └── notifier.py            # Push notifications (ntfy/Pushover/Telegram)
│   │
│   └── utils/                     # Utility modules
│       ├── __init__.py
│       └── crypto.py              # Password encryption (Fernet)
│
├── static/                        # Frontend files
│   └── index.html                 # Web dashboard (single-page app)
│
├── scripts/                       # Utility scripts
│   └── diagnose.sh                # Diagnostic and troubleshooting script
│
├── docs/                          # Documentation
│   ├── ARCHITECTURE.md            # Technical architecture & design
│   ├── PROJECT_SUMMARY.md         # Complete feature overview
│   └── SETUP.md                   # Detailed setup guide
│
├── tests/                         # Test files (future)
│
├── main.py                        # Application entry point (FastAPI)
├── Dockerfile                     # Docker image definition
├── docker-compose.yml             # Docker services orchestration
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variables template
├── .gitignore                     # Git ignore rules
├── start.sh                       # Quick start script
├── README.md                      # Main documentation
└── PROJECT_STRUCTURE.md           # This file
```

## 🏗️ Architecture Overview

### Application Layers

1. **API Layer** (`app/api.py`)
   - FastAPI REST endpoints
   - Request/response validation (Pydantic)
   - Database session management

2. **Business Logic Layer**
   - **Orchestrator** (`app/crawler/orchestrator.py`): Coordinates crawling workflow
   - **Crawlers** (`app/crawler/`): Platform-specific job extraction
   - **AI Analyzer** (`app/ai/analyzer.py`): Job matching and analysis
   - **Notifier** (`app/notifications/notifier.py`): Push notifications

3. **Data Layer**
   - **Models** (`app/models.py`): SQLAlchemy ORM models
   - **Database** (`app/database.py`): Connection pooling and session management

4. **Infrastructure Layer**
   - **Config** (`app/config.py`): Environment-based configuration
   - **Crypto** (`app/utils/crypto.py`): Credential encryption

## 🔄 Data Flow

```
User Action / Scheduled Trigger
    ↓
FastAPI Route (app/api.py)
    ↓
CrawlerOrchestrator (app/crawler/orchestrator.py)
    ├─→ Get active searches from DB
    ├─→ Get encrypted credentials
    └─→ Spawn platform crawlers
        ↓
    LinkedInCrawler / IndeedCrawler
        ├─→ Login with Selenium
        ├─→ Execute search
        ├─→ Parse job listings
        └─→ Return raw job data
            ↓
    JobAnalyzer (app/ai/analyzer.py)
        ├─→ Call Ollama API
        ├─→ Generate summary, pros/cons
        ├─→ Calculate match score
        └─→ Return analysis
            ↓
    Database (app/models.py)
        ├─→ Check for duplicates
        ├─→ Save new jobs with analysis
        └─→ Update metadata
            ↓
    NotificationService (app/notifications/notifier.py)
        ├─→ Aggregate new jobs
        ├─→ Format message
        └─→ Send to phone
```

## 📦 Component Details

### Core Components

#### `main.py`
- FastAPI application initialization
- Lifespan management (startup/shutdown)
- APScheduler integration
- CORS configuration
- Static file serving

#### `app/config.py`
- Pydantic Settings for environment variables
- Type-safe configuration
- Default values for development

#### `app/database.py`
- Async SQLAlchemy engine
- Session factory
- Base model class
- Connection pooling

#### `app/models.py`
- **User**: Platform credentials (encrypted)
- **SearchCriteria**: Job search parameters
- **Job**: Job postings with AI analysis
- **FollowUp**: Reminder scheduling
- **CrawlLog**: Execution history

### Crawler Components

#### `app/crawler/orchestrator.py`
- Coordinates multiple platform crawlers
- Manages database transactions
- Handles AI analysis
- Sends notifications
- Logs crawl execution

#### `app/crawler/linkedin_crawler.py`
- Selenium-based LinkedIn automation
- Login handling
- Job search execution
- Job listing extraction

#### `app/crawler/indeed_crawler.py`
- Selenium-based Indeed automation
- No login required (optional)
- Job search execution
- Job listing extraction

### AI Components

#### `app/ai/analyzer.py`
- Ollama API integration
- Prompt engineering for job analysis
- JSON response parsing
- Match score calculation
- Report generation

### Notification Components

#### `app/notifications/notifier.py`
- Multi-platform support (ntfy/Pushover/Telegram)
- Message formatting
- Priority handling
- Error handling

### Utility Components

#### `app/utils/crypto.py`
- Fernet symmetric encryption
- PBKDF2 key derivation
- Password encryption/decryption

## 🐳 Docker Services

### Services in `docker-compose.yml`

1. **postgres**: PostgreSQL database
2. **redis**: Redis cache (for future use)
3. **selenium-chrome**: Selenium Grid Chrome node
4. **ollama**: Local LLM server
5. **job-crawler**: Main application

### Service Dependencies

```
job-crawler
    ├─→ postgres (database)
    ├─→ redis (cache)
    ├─→ selenium-chrome (browser automation)
    └─→ ollama (AI analysis)
```

## 🔌 API Endpoints

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

## 📊 Database Schema

### Tables

1. **users**: Platform credentials (encrypted)
2. **search_criteria**: Job search parameters
3. **jobs**: Job postings with AI analysis
4. **follow_ups**: Reminder scheduling
5. **crawl_logs**: Execution history

### Relationships

```
User (1) ──< (N) SearchCriteria
SearchCriteria (1) ──< (N) Job
SearchCriteria (1) ──< (N) CrawlLog
Job (1) ──< (N) FollowUp
```

## 🔐 Security Features

1. **Credential Encryption**: Fernet (AES-128) with PBKDF2 key derivation
2. **Local AI Processing**: 100% local with Ollama
3. **Encrypted Transit**: HTTPS for notifications
4. **Environment Variables**: Sensitive data in .env (not in code)
5. **Database Authentication**: PostgreSQL with credentials

## 🚀 Deployment

### Local Development

1. Copy `.env.example` to `.env`
2. Configure environment variables
3. Run `./start.sh` or `docker-compose up -d`
4. Access dashboard at http://localhost:8001/static/index.html

### Production Considerations

1. Change `SECRET_KEY` to random string
2. Set `DEBUG=false`
3. Configure proper database credentials
4. Set up reverse proxy (nginx/Caddy)
5. Add authentication to API
6. Use managed database (if needed)
7. Set up monitoring and logging

## 📝 Development Guidelines

### Code Organization

- **Separation of Concerns**: Each module has a single responsibility
- **Async/Await**: All I/O operations use async patterns
- **Type Hints**: Full type annotations for better IDE support
- **Error Handling**: Comprehensive try/except blocks with logging
- **Logging**: Structured logging throughout

### Adding New Features

1. **New Crawler**: Add to `app/crawler/` following existing patterns
2. **New Notification Method**: Extend `app/notifications/notifier.py`
3. **New API Endpoint**: Add to `app/api.py`
4. **New Model**: Add to `app/models.py` and create migration

### Testing

- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- E2E tests: `tests/e2e/`

## 🔄 Local Development Reference

This project structure follows patterns established in `origin/github/nexus.lan`:
- Clear separation of concerns
- Comprehensive documentation
- Scripts for automation
- Docker-based deployment
- Environment-based configuration

## 📚 Additional Resources

- **Architecture Details**: See `docs/ARCHITECTURE.md`
- **Setup Guide**: See `docs/SETUP.md`
- **Feature Overview**: See `docs/PROJECT_SUMMARY.md`
- **API Documentation**: http://localhost:8001/docs (when running)

---

**Last Updated**: 2024
**Version**: 1.0.0

