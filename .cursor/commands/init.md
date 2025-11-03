# Project Initialization Command

## Primary Objective

Create a comprehensive project and implementation structure for the Job Search Crawler system.

## Critical Requirement: Check Development Updates

**ALWAYS** check the following location for updated local development before making any changes:

- Path: `origin/github/nexus.lan`
- Note: This location changes frequently, so it must be checked at the start of every session

## Project Structure Overview

### Core Components

1. **FastAPI Backend** (`api.py`, `main.py`)
   - RESTful API endpoints
   - WebSocket support (optional)
   - Dashboard serving

2. **Crawler Module** (`app/crawler/`)
   - LinkedIn crawler (`linkedin_crawler.py`)
   - Indeed crawler (`indeed_crawler.py`)
   - Orchestrator (`orchestrator.py`)

3. **AI Integration** (`app/ai/`)
   - Job analyzer (`analyzer.py`)
   - Ollama integration for local LLM

4. **Database Layer** (`app/database.py`, `app/models.py`)
   - PostgreSQL connection
   - SQLAlchemy models
   - Migration support

5. **Notification Service** (`app/notifications/`)
   - Multi-platform support (ntfy, Pushover, Telegram)
   - Push notification delivery

6. **Utilities** (`app/utils/`)
   - Encryption (`crypto.py`)
   - Helper functions

7. **Configuration** (`app/config.py`)
   - Environment variables
   - Settings management

8. **Frontend** (`static/`)
   - Web dashboard (`index.html`)
   - Responsive UI

## Implementation Checklist

When initializing or restructuring the project, ensure:

### 1. Pre-Init Steps

- [ ] Check `origin/github/nexus.lan` for latest development updates
- [ ] Review ARCHITECTURE.md for current system design
- [ ] Review PROJECT_SUMMARY.md for feature overview
- [ ] Check SETUP.md for configuration requirements

### 2. Project Structure Validation

- [ ] Verify all required directories exist:
  - `app/` (main application)
  - `app/crawler/` (crawler implementations)
  - `app/ai/` (AI analysis)
  - `app/notifications/` (notification services)
  - `app/utils/` (utilities)
  - `static/` (frontend assets)
  - `tests/` (test suite)
  - `docs/` (documentation)
  - `scripts/` (utility scripts)

### 3. Core Files Verification

- [ ] `main.py` - Application entry point
- [ ] `api.py` - FastAPI routes
- [ ] `app/config.py` - Configuration management
- [ ] `app/database.py` - Database connection
- [ ] `app/models.py` - Data models
- [ ] `orchestrator.py` - Crawler orchestration
- [ ] `analyzer.py` - AI job analysis
- [ ] `notifier.py` - Notification service
- [ ] `crypto.py` - Encryption utilities

### 4. Configuration Files

- [ ] `requirements.txt` - Python dependencies
- [ ] `docker-compose.yml` - Service orchestration
- [ ] `Dockerfile` - Container definition
- [ ] `.env.example` - Environment template
- [ ] `start.sh` - Startup script
- [ ] `gitignore` - Git ignore rules

### 5. Documentation

- [ ] `README.md` - Project overview
- [ ] `SETUP.md` - Setup instructions
- [ ] `ARCHITECTURE.md` - System architecture
- [ ] `PROJECT_SUMMARY.md` - Feature summary

## Development Workflow

1. **Always start by checking** `origin/github/nexus.lan` for updates
2. **Review current project state** using documentation files
3. **Identify missing components** or outdated implementations
4. **Implement or update** following the architecture patterns
5. **Verify consistency** across all components
6. **Update documentation** if structure changes

## Key Patterns to Follow

- **Async/Await**: Use async operations for I/O-bound tasks
- **Dependency Injection**: Use FastAPI's dependency system
- **Error Handling**: Implement comprehensive error handling
- **Logging**: Add appropriate logging throughout
- **Type Hints**: Use Python type hints for better code clarity
- **Modular Design**: Keep components loosely coupled
- **Configuration**: Use environment variables for settings

## When Making Changes

1. Check `origin/github/nexus.lan` first
2. Read relevant documentation files
3. Understand the current implementation
4. Make minimal, focused changes
5. Update affected documentation
6. Test changes locally

## Notes

- This is a Docker-based deployment system
- Uses PostgreSQL for data persistence
- Integrates with Ollama for local AI processing
- Supports multiple notification platforms
- Web dashboard provides UI for management
