# OpenWebUI Complete Integration Guide

OpenWebUI provides a beautiful, user-friendly chat interface for interacting with Ollama models. This guide covers the complete integration with database persistence, health monitoring, embedded chat interface, workflow automation, and secure authentication.

## Overview

The Job Crawler now features a complete OpenWebUI integration with:

- **Database-backed settings persistence** - Settings survive container restarts
- **Health monitoring** - Automatic health checks every 5 minutes
- **Embedded chat panel** - Minimizable/maximizable iframe chat interface
- **Workflow automation** - Send job context directly to OpenWebUI
- **Full authentication support** - API keys and auth tokens with validation
- **Frontend integration** - Native UI components throughout the app

## Infrastructure

**Service Locations:**
- **OpenWebUI**: `https://ai.lan` (pi-forge:3000)
- **Job Crawler**: `https://js-craw.lan` (pi-forge:8001)
- **Ollama**: `https://ollama.nexus.lan` (ai-srv:11434)

All services are on the same network, accessible via Caddy reverse proxy.

## Quick Start

### 1. Configure OpenWebUI URL

Update your `.env` file:
```env
OPENWEBUI_ENABLED=true
OPENWEBUI_URL=https://ai.lan
```

Or via API:
```bash
curl -X PATCH http://localhost:8001/api/settings \
  -H "Content-Type: application/json" \
  -d '{"openwebui_url": "https://ai.lan"}'
```

### 2. Set Up Authentication (Optional)

If your OpenWebUI requires authentication:

```env
OPENWEBUI_API_KEY=your_api_key_here
OPENWEBUI_AUTH_TOKEN=your_auth_token_here
OPENWEBUI_USERNAME=your_username_here
```

### 3. Run Database Migration

```bash
python scripts/migrate_database.py
python scripts/seed_settings.py
```

### 4. Access OpenWebUI

- **Embedded**: Click "Chat" button on any job card
- **Full Screen**: Use "Open in New Tab" button in chat panel
- **Settings**: Navigate to Settings page to configure and test connection

## Features

### 1. Embedded Chat Panel

The embedded chat panel provides a native chat experience within the job crawler interface:

- **Minimize/Maximize**: Toggle between floating button and full panel
- **Context-Aware**: Automatically includes job details when opened from job cards
- **Responsive**: Works on desktop and mobile devices
- **Persistent**: Chat history preserved across page navigations

**Access Points:**
- Jobs page: "Chat" button on each job card
- Follow-ups page: Toggle between AI Chat and OpenWebUI
- Global: Persistent floating button (coming soon)

### 2. Health Monitoring

Automatic health checks run every 5 minutes and cache results:

**Health Status:**
- `online` - OpenWebUI is accessible
- `online_authenticated` - OpenWebUI is accessible and authenticated
- `offline` - OpenWebUI is not reachable
- `error` - Health check failed
- `disabled` - Integration is disabled

**View Health Status:**
- Settings page: Real-time health indicator
- API: `GET /api/openwebui/health`
- Dashboard: Health status badge

### 3. Workflow Hand-offs

Send job context directly to OpenWebUI with intelligent prompt generation:

**Available Actions:**
- **Analyze**: Analyze job opportunity and provide insights
- **Follow-up**: Generate follow-up email templates
- **Interview Prep**: Generate interview questions and answers
- **Cover Letter**: Create tailored cover letters

**How to Use:**
1. Click "Chat" button on any job card
2. Select prompt type (analyze, follow-up, interview_prep, cover_letter)
3. Job context is automatically sent to OpenWebUI
4. Chat interface opens with pre-seeded context

**API Endpoint:**
```bash
POST /api/openwebui/send-context
{
  "job_id": 123,
  "prompt_type": "analyze"  # or "follow_up", "interview_prep", "cover_letter"
}
```

### 4. Authentication

Full authentication support with token validation:

**Authentication Methods:**
- **API Key**: For programmatic API access
- **Auth Token**: For user session authentication
- **Username**: Optional username for basic auth

**Test Authentication:**
- Settings page: "Test Authentication" button
- API: `POST /api/openwebui/verify-auth`

**Security:**
- Tokens are encrypted in database
- Never exposed in API responses
- Validated before OpenWebUI API calls

### 5. Settings Persistence

All settings are now stored in the database:

**Benefits:**
- Settings survive container restarts
- No need to edit `.env` file for changes
- UI updates settings directly
- Automatic migration from `.env` to database

**Migration:**
1. Run `python scripts/migrate_database.py` to create settings table
2. Run `python scripts/seed_settings.py` to copy current config to database
3. Settings are now persistent

## API Endpoints

### Get OpenWebUI Info
```bash
GET /api/openwebui
```
Returns configuration, health status, and capabilities.

### Health Check
```bash
GET /api/openwebui/health
```
Detailed health check with connectivity and capability information.

### Verify Authentication
```bash
POST /api/openwebui/verify-auth
{
  "api_key": "optional",
  "auth_token": "optional"
}
```
Test authentication credentials.

### Get Status
```bash
GET /api/openwebui/status
```
Combined health and authentication status.

### Send Job Context
```bash
POST /api/openwebui/send-context
{
  "job_id": 123,
  "prompt_type": "analyze"
}
```
Send job context to OpenWebUI to create a new chat.

## Frontend Integration

### Jobs Page
- "Chat" button on each job card opens embedded OpenWebUI chat
- Context automatically includes job details
- Chat panel appears as overlay

### Follow-ups Page
- Toggle between AI Chat and OpenWebUI chat
- Both chat types available in sidebar
- Context-aware based on selected recommendation

### Settings Page
- Configure OpenWebUI URL and authentication
- Real-time health status indicator
- Test connection and authentication buttons
- View capabilities and health details

### Embedded Chat Component
- Minimizable/maximizable interface
- Responsive design
- Auto-authentication via token
- Context injection support

## Configuration

### Environment Variables

```env
# Enable/disable integration
OPENWEBUI_ENABLED=true

# OpenWebUI URL
OPENWEBUI_URL=https://ai.lan

# Authentication (optional)
OPENWEBUI_API_KEY=your_api_key
OPENWEBUI_AUTH_TOKEN=your_auth_token
OPENWEBUI_USERNAME=your_username
```

### Database Settings

Settings are stored in the `app_settings` table. Use the Settings page UI or API to update:

```bash
PATCH /api/settings
{
  "openwebui_url": "https://ai.lan",
  "openwebui_api_key": "new_key"
}
```

## Health Monitoring

### Automatic Health Checks

Health checks run every 5 minutes automatically:
- Tests connectivity to OpenWebUI
- Validates authentication if configured
- Caches results for performance
- Updates status in real-time

### Manual Health Check

```bash
GET /api/openwebui/health
```

### Health Status Indicators

- **Green**: Online and accessible
- **Yellow**: Online but authentication issues
- **Red**: Offline or error
- **Gray**: Disabled

## Workflow Examples

### Example 1: Analyze Job Opportunity

1. Browse jobs on Jobs page
2. Click "Chat" button on a job card
3. OpenWebUI chat opens with job context
4. Ask: "What are the key requirements for this role?"
5. Get AI-powered insights

### Example 2: Generate Follow-up Email

1. Select a job you've applied to
2. Click "Chat" button
3. Select "Follow-up" prompt type (via API or context menu)
4. Job context sent to OpenWebUI
5. Ask: "Help me write a professional follow-up email"
6. Get tailored email template

### Example 3: Interview Preparation

1. Find a job with upcoming interview
2. Open chat for that job
3. Context includes job description and requirements
4. Ask: "What technical questions should I prepare for?"
5. Get interview question suggestions

## Troubleshooting

### OpenWebUI Not Accessible

**Symptoms:** Health status shows "offline"

**Solutions:**
1. Verify OpenWebUI URL is correct: `https://ai.lan`
2. Check OpenWebUI is running: `ssh admin@pi-forge 'docker ps | grep openwebui'`
3. Test connectivity: `curl https://ai.lan/api/v1/config`
4. Check reverse proxy: Verify Caddy configuration on pi-net

### Authentication Failing

**Symptoms:** Health status shows "online" but auth_status is "invalid_token"

**Solutions:**
1. Verify API key or auth token is correct
2. Test authentication in Settings page
3. Check OpenWebUI authentication requirements
4. Ensure token hasn't expired

### Embedded Chat Not Loading

**Symptoms:** Chat panel shows error or blank

**Solutions:**
1. Check browser console for CORS errors
2. Verify OpenWebUI URL is accessible from browser
3. Check iframe sandbox permissions
4. Try "Open in New Tab" to test direct access

### Settings Not Persisting

**Symptoms:** Settings reset after container restart

**Solutions:**
1. Run database migration: `python scripts/migrate_database.py`
2. Seed settings: `python scripts/seed_settings.py`
3. Verify `app_settings` table exists
4. Check database connection

## Security Considerations

1. **Token Encryption**: All authentication tokens are encrypted in database
2. **HTTPS Only**: All OpenWebUI communication uses HTTPS
3. **No Token Exposure**: Tokens never appear in API responses
4. **Input Validation**: All OpenWebUI API inputs are validated
5. **Rate Limiting**: Health checks are rate-limited to prevent abuse

## Database Schema

**app_settings Table:**
```sql
CREATE TABLE app_settings (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Migration Steps

1. **Run Migration:**
   ```bash
   python scripts/migrate_database.py
   ```

2. **Seed Settings:**
   ```bash
   python scripts/seed_settings.py
   ```

3. **Verify:**
   ```bash
   # Check settings table
   psql -d job_crawler -c "SELECT key, value FROM app_settings WHERE key LIKE 'openwebui%';"
   ```

## API Examples

### Get OpenWebUI Status
```bash
curl http://localhost:8001/api/openwebui/status
```

### Send Job to OpenWebUI
```bash
curl -X POST http://localhost:8001/api/openwebui/send-context \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": 123,
    "prompt_type": "analyze"
  }'
```

### Test Authentication
```bash
curl -X POST http://localhost:8001/api/openwebui/verify-auth \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "your_key",
    "auth_token": "your_token"
  }'
```

## Advanced Usage

### Custom Prompt Types

You can extend the prompt types by modifying `app/services/openwebui_service.py`:

```python
def _format_context_prompt(self, context: Dict[str, Any]) -> str:
    prompt_type = context.get("prompt_type", "analyze")
    # Add custom prompt types here
```

### Background Health Checks

Health checks run automatically every 5 minutes. To adjust interval, modify `main.py`:

```python
scheduler.add_job(
    check_openwebui_health,
    trigger=IntervalTrigger(minutes=5),  # Change interval here
    ...
)
```

### Custom Authentication

To add custom authentication methods, extend `OpenWebUIService._get_auth_headers()`:

```python
def _get_auth_headers(self, api_key, auth_token):
    # Add custom auth logic here
    ...
```

## Resources

- **OpenWebUI Documentation**: https://docs.openwebui.com/
- **OpenWebUI API**: https://docs.openwebui.com/api
- **Ollama Documentation**: https://ollama.ai/docs
- **Job Crawler API Docs**: http://localhost:8001/docs

---

**Status**: ✅ Complete Integration Ready  
**Last Updated**: 2025-11-04  
**Version**: 2.0
