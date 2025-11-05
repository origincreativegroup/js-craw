# Job Search Crawler

A comprehensive, production-ready job search automation system that crawls company career pages directly, analyzes jobs using local AI, and sends push notifications to your mobile device.

## 🎯 Features

- **Automated Crawling**: Company career pages and curated job board searches
  every 30 minutes (configurable)
- **AI Analysis**: Local LLM (Ollama) for intelligent job matching and scoring
- **AI Document Generation**: Automatically create tailored resumes and cover letters for top jobs
- **Ollama Verification**: Comprehensive health checks to ensure AI is working correctly
- **Mobile Notifications**: Push alerts via ntfy, Pushover, or Telegram
- **Web Dashboard**: Clean, responsive UI for managing everything
- **Secure Storage**: Encrypted credentials, PostgreSQL database
- **Docker-Based**: One-command deployment

### 🆕 New Features

- **Automation Command Center**: Real-time monitoring and control dashboard
  - Real-time telemetry (status, progress, ETA, queue length)
  - Timeline visualization of automation events
  - Per-automation health chips with color-coded indicators
  - Drill-down panels for crawler type analysis
  - Full automation control (pause/resume, adjust interval, cancel)
- **Document Generator**: Automatically generate tailored resumes and cover letters using AI
- **Ollama Verifier**: Verify and test Ollama connection and functionality
- **Comprehensive Testing**: Full test suite for AI features
- **Batch Processing**: Generate documents for multiple top-matched jobs

See [Automation Command Center](docs/AUTOMATION_COMMAND_CENTER.md), [AI Enhancements Summary](docs/AI_ENHANCEMENTS_SUMMARY.md), and [Ollama Verification Guide](docs/OLLAMA_VERIFICATION_GUIDE.md) for details.

## 📁 Project Structure

```
js-craw/
├── app/                          # Application package
│   ├── __init__.py
│   ├── config.py                  # Configuration settings
│   ├── database.py                # Database connection
│   ├── models.py                  # SQLAlchemy models
│   ├── api.py                     # FastAPI routes
│   ├── crawler/                   # Crawler modules
│   │   ├── __init__.py
│   │   ├── greenhouse_crawler.py  # Greenhouse ATS crawler
│   │   ├── lever_crawler.py       # Lever ATS crawler
│   │   ├── indeed_crawler.py      # Indeed guest search crawler
│   │   ├── linkedin_crawler.py    # LinkedIn guest search crawler
│   │   ├── generic_crawler.py     # AI-assisted generic career page crawler
│   │   └── orchestrator.py        # Coordinates crawlers
│   ├── ai/                        # AI analysis
│   │   ├── __init__.py
│   │   ├── analyzer.py            # Job analysis with Ollama
│   │   ├── job_filter.py          # AI-powered job filtering
│   │   ├── document_generator.py  # Resume/cover letter generation
│   │   └── ollama_verifier.py     # Ollama health checks
│   ├── notifications/             # Notification services
│   │   ├── __init__.py
│   │   └── notifier.py            # Push notifications
│   └── utils/                     # Utilities
│       ├── __init__.py
│       └── crypto.py              # Password encryption
├── static/                        # Frontend files
│   └── index.html                 # Web dashboard
├── scripts/                       # Utility scripts
│   └── diagnose.sh                # Diagnostic script
├── docs/                          # Documentation
│   ├── ARCHITECTURE.md            # Technical architecture
│   ├── PROJECT_SUMMARY.md         # Project overview
│   ├── SETUP.md                   # Setup guide
│   ├── AI_ENHANCEMENTS_SUMMARY.md # AI features summary
│   └── OLLAMA_VERIFICATION_GUIDE.md # Ollama setup & usage guide
├── tests/                         # Test suite
│   └── test_ollama_integration.py # Ollama integration tests
├── verify_ollama.py               # Ollama verification CLI tool
├── main.py                        # Application entry point
├── Dockerfile                     # Docker image definition
├── docker-compose.yml             # Docker services orchestration
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment template
├── start.sh                       # Quick start script
└── README.md                      # This file
```

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- At least 4GB RAM
- 20GB free disk space (for Ollama model)

### 1. Setup

```bash
# Clone or navigate to project
cd js-craw

# Copy environment template
cp .env.example .env

# Edit .env with your settings (especially SECRET_KEY and notification settings)
nano .env
```

### 2. Start Services

```bash
# Make start script executable
chmod +x start.sh

# Start all services
./start.sh
```

Or manually:
```bash
docker-compose up -d
docker exec job-crawler-ollama ollama pull llama2
```

### Refreshing the companies catalog

Use the automated pipeline to ingest crawl data, enforce the 1500-company cap,
and verify each entry before writing `companies.csv`:

```bash
python scripts/crawl_companies.py --seed static/company_sources.json --output companies.csv
```

The pipeline performs three stages:

1. **Collection** – The configured sources defined in
   `app/services/company_sources.py` return structured `CompanyRecord`
   objects for each crawl run.
2. **Filtering** – `CompanyFilteringPipeline` sorts by crawl success and
   priority before truncating the list to the configured cap (default 1500).
3. **Verification** – `CompanyVerifier` keeps entries with crawl results and
   falls back to the AI heuristic for the remainder, discarding companies that
   do not pass the review.

Verbose logging is emitted during each step so you can monitor how many
companies were collected, filtered, and finally written to disk.

### 3. Configure

1. Open http://localhost:8001/static/index.html
2. Go to **Settings** tab
3. Add LinkedIn credentials
4. (Optional) Add Indeed credentials

### 4. Create First Search

1. Go to **Search Criteria** tab
2. Click **+ Add New Search**
3. Fill in:
   - Name: "Software Engineer"
   - Keywords: "python javascript"
   - Location: "Remote" or your city
   - Select platforms
4. Click **Create Search**

### 5. Test It!

Click **"Run Search Now"** in the header.

Within 2-3 minutes, you should:
- See jobs appear in the dashboard
- Receive a notification on your phone

## 📚 Documentation

- **[docs/SETUP.md](docs/SETUP.md)** - Detailed setup guide
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Technical architecture
- **[docs/PROJECT_SUMMARY.md](docs/PROJECT_SUMMARY.md)** - Complete feature overview
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** - CI/CD pipeline and deployment guide
- **[docs/CODEX_CLAUDE_CURSOR_HANDSHAKE.md](docs/CODEX_CLAUDE_CURSOR_HANDSHAKE.md)** - Coordination guide for multi-agent AI workflows

## 🔧 Configuration

### Environment Variables

Key settings in `.env`:

- `SECRET_KEY`: Random string for encryption (required)
- `NOTIFICATION_METHOD`: `ntfy`, `pushover`, or `telegram`
- `CRAWL_INTERVAL_MINUTES`: How often to crawl (default: 30)
- `OLLAMA_MODEL`: AI model to use (default: `llama2`)

See `.env.example` for all options.

### Crawler Types

Use the **Companies** admin view (or seed script) to add different crawler
profiles:

- `greenhouse` / `lever` – require a `slug` in `crawler_config`.
- `generic` – points directly to a custom career page URL.
- `indeed` – expects a JSON config like:
  ```json
  {
    "query": "machine learning engineer",
    "location": "Remote",
    "max_pages": 2,
    "freshness_days": 7,
    "remote_only": true
  }
  ```
- `linkedin` – uses the guest API with a config such as:
  ```json
  {
    "query": "software engineer",
    "location": "United States",
    "max_pages": 3,
    "remote_only": false,
    "filters": {"f_E": "2,3"}
  }
  ```
  The `filters` object lets you pass LinkedIn query parameters (e.g. `{ "f_E": "2,3" }` for mid and senior roles).

The orchestrator merges the jobs found by each crawler into the shared
database so downstream AI analysis and notifications work identically across
sources.

### Notification Setup

#### Option 1: ntfy.sh (Recommended)

1. Install app: https://ntfy.sh/
2. Create a topic name (e.g., `job-alerts-xyz123`)
3. Update `.env`:
   ```
   NOTIFICATION_METHOD=ntfy
   NTFY_TOPIC=job-alerts-xyz123
   ```

#### Option 2: Pushover

1. Create account: https://pushover.net
2. Create application in dashboard
3. Update `.env` with User Key and App Token

#### Option 3: Telegram

1. Message @BotFather on Telegram
2. Create bot and get token
3. Get chat ID from @userinfobot
4. Update `.env` with bot token and chat ID

## 🐳 Docker Services

| Service | Port | Purpose |
|---------|------|---------|
| job-crawler | 8001 | Main application |
| postgres | 5432 | Database |
| redis | 6379 | Cache |
| selenium-chrome | 4444 | Browser automation |
| ollama | 11434 | AI model server |

## 📊 API Endpoints

- `GET /api/searches` - List all searches
- `POST /api/searches` - Create new search
- `GET /api/jobs` - List jobs (with filters)
- `POST /api/crawl/run` - Trigger manual crawl
- `GET /api/stats` - Dashboard statistics
- `POST /api/credentials` - Save platform credentials

Full API docs: http://localhost:8001/docs

## 🛠️ Development

### Local Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with local settings

# Run locally (requires services running via docker-compose)
uvicorn main:app --reload
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest
```

### Project Structure Notes

This project follows a modular structure:
- **app/**: Main application package
  - **crawler/**: Platform-specific crawlers
  - **ai/**: AI analysis modules
  - **notifications/**: Notification services
  - **utils/**: Utility functions
- **static/**: Frontend files
- **scripts/**: Utility scripts
- **docs/**: Documentation

## 🔍 Troubleshooting

### Jobs not found

- Verify credentials are correct
- Try broader keywords
- Check if LinkedIn requires 2FA
- Check Selenium logs: `docker-compose logs selenium-chrome`

### Notifications not working

- Test notification manually
- Verify topic/token in `.env`
- Check phone app is installed
- Check logs: `docker-compose logs job-crawler`

### Ollama slow

- First run downloads 4GB model
- Subsequent runs faster
- Consider using smaller model (mistral)
- Check Ollama logs: `docker-compose logs ollama`

### View Logs

```bash
# All services
docker-compose logs

# Specific service
docker-compose logs job-crawler
docker-compose logs selenium-chrome
docker-compose logs ollama

# Follow live
docker-compose logs -f job-crawler
```

## 📈 Next Steps

1. **Refine searches** - Add more specific criteria
2. **Review jobs** - Check AI match scores
3. **Track applications** - Update job status
4. **Schedule follow-ups** - Set reminders

## 🔐 Security Notes

- **Credentials**: Encrypted with Fernet (AES-128)
- **Data**: Stored locally, never sent to third parties
- **AI**: 100% local processing with Ollama
- **Notifications**: Encrypted in transit (HTTPS)
- **API**: Can add authentication if exposing publicly

## 📝 License

MIT License - see LICENSE file for details

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Add new job platforms
- Improve AI analysis prompts
- Enhance UI/UX
- Add new notification methods
- Optimize performance

## 📞 Support

For issues or questions:
1. Check documentation in `docs/`
2. Review logs with `docker-compose logs`
3. Check troubleshooting section above

---

**Status**: 🟢 Production Ready

**Last Updated**: 2024

