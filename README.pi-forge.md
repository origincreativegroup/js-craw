# js-craw on pi-forge

Job Search Crawler configured for Raspberry Pi ARM64 with remote Ollama on ai-srv.

## Key Differences from Standard Setup

This pi-forge deployment differs from the default configuration:

1. **No Local Ollama** - Uses remote Ollama on ai-srv (192.168.50.248:11434)
2. **ARM64 Selenium** - Uses `seleniarm/standalone-chromium` instead of `selenium/standalone-chrome`
3. **llama3.1 Model** - Uses llama3.1 (available on ai-srv) instead of llama2
4. **Docker Build** - Builds locally instead of pulling from registry

## Quick Reference

### Access Points

- **Dashboard**: http://192.168.50.157:8001/static/index.html
- **API Docs**: http://192.168.50.157:8001/docs
- **Health**: http://localhost:8001/health

### Common Commands

```bash
cd ~/docker/js-craw

# Start
docker compose up -d

# Stop
docker compose down

# Logs
docker compose logs -f job-crawler

# Restart
docker compose restart job-crawler

# Rebuild
docker compose up -d --build
```

### Configuration

Location: `/home/admin/docker/js-craw/.env`

Key settings:
```bash
OLLAMA_HOST=http://192.168.50.248:11434
OLLAMA_MODEL=llama3.1
NOTIFICATION_METHOD=ntfy
NTFY_TOPIC=pi-forge-job-alerts
CRAWL_INTERVAL_MINUTES=30
```

## Remote Ollama

**Server**: ai-srv (192.168.50.248)
**Port**: 11434
**Model**: llama3.1

Test connection:
```bash
curl http://192.168.50.248:11434/api/tags
docker exec job-crawler-app python -c "import httpx; r = httpx.get('http://192.168.50.248:11434/api/tags'); print('Status:', r.status_code)"
```

Change model (edit .env then restart):
```bash
OLLAMA_MODEL=mistral:7b
docker compose restart job-crawler
```

## Notifications

Current setup: **ntfy.sh**

1. Install ntfy app on phone
2. Subscribe to: `pi-forge-job-alerts`
3. Job notifications appear automatically

## Services

| Container | Image | Port | Status |
|-----------|-------|------|--------|
| job-crawler-app | Built locally | 8001 | Main app |
| job-crawler-postgres | postgres:15-alpine | 5432 | Database |
| job-crawler-redis | redis:7-alpine | 6379 | Cache |
| job-crawler-selenium | seleniarm/standalone-chromium | 4444 | Browser |

Check status:
```bash
docker compose ps
```

## Database

Connect:
```bash
docker exec -it job-crawler-postgres psql -U postgres -d job_crawler
```

View jobs:
```sql
SELECT id, title, company, location, created_at
FROM jobs
ORDER BY created_at DESC
LIMIT 10;
```

Backup:
```bash
docker exec job-crawler-postgres pg_dump -U postgres job_crawler > backup_$(date +%Y%m%d).sql
```

## Troubleshooting

### Check all services
```bash
docker compose ps
```

### View logs
```bash
docker compose logs --tail=50 job-crawler
```

### Test Ollama
```bash
curl http://192.168.50.248:11434/api/tags
```

### Restart everything
```bash
docker compose down
docker compose up -d
```

### Check resource usage
```bash
docker stats job-crawler-app
```

## Setup History

**Date**: 2025-11-03
**Modified by**: Claude Code
**Changes**:
- Cloned from https://github.com/origincreativegroup/js-craw
- Removed local Ollama service from docker-compose.yml
- Changed to ARM64 Selenium image (seleniarm/standalone-chromium)
- Configured OLLAMA_HOST to point to ai-srv (192.168.50.248:11434)
- Changed to llama3.1 model (available on ai-srv)
- Configured ntfy notifications with topic: pi-forge-job-alerts

**Last Status Check**: November 5, 2025 06:15 CST
- All containers running and healthy
- React TypeScript frontend deployed and operational
- Frontend built and served from static/ directory
- Health endpoint responding correctly
- Latest features: Company data pipeline, enhanced automation control, OpenWebUI integration

## Full Documentation

See main README.md for complete documentation on features, API endpoints, and development.

**Related Services**:
- OpenWebUI: Also uses ai-srv Ollama (port 3000)
- Nextcloud: Available at port 8080 / https://nextcloud.lan
- Portainer: Docker management at port 9000
