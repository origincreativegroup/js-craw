# Debugging and Testing Pipeline Documentation

## Overview

This pipeline provides comprehensive debugging, testing, and failure handling for the development workflow:
**Cursor/Claude/Codex → GitHub → pi-forge (auto-pull) → Testing → Deployment**

## Architecture

```
┌─────────────────┐
│  Development    │
│  (Cursor/       │
│   Claude/       │
│   Codex)        │
└────────┬────────┘
         │
         │ git push
         ▼
┌─────────────────┐
│   GitHub        │
│   Repository     │
└────────┬────────┘
         │
         │ GitHub Actions
         │ (self-hosted runner)
         ▼
┌─────────────────┐
│   pi-forge      │
│   (Auto-pull)    │
└────────┬────────┘
         │
         ├─► Pre-deployment Tests
         │
         ├─► Build Docker Images
         │
         ├─► Deploy Containers
         │
         ├─► Post-deployment Tests
         │
         └─► Failure Handling
              ├─► Generate Logs
              ├─► Commit to GitHub
              └─► Send Notification
```

## Components

### 1. Debug Test Runner (`scripts/deployment/debug_test_runner.py`)

Comprehensive test suite that runs before and after deployment.

#### Features:
- **Environment Checks**: Python version, directories, environment variables
- **Dependency Checks**: Verifies all required packages are installed
- **Code Quality**: Syntax checking, import validation
- **Configuration Checks**: Validates config files and settings
- **Database Connectivity**: Tests database connection
- **Docker Services**: Checks container status
- **Unit Tests**: Runs pytest test suite
- **Integration Tests**: Extended integration testing
- **API Health Checks**: Verifies API endpoints
- **Service Connectivity**: Tests external service connections

#### Usage:

```bash
# Run all tests
python3 scripts/deployment/debug_test_runner.py

# Output JSON results
python3 scripts/deployment/debug_test_runner.py --json

# Specify project root
python3 scripts/deployment/debug_test_runner.py --project-root /path/to/project
```

#### Output:
- JSON results: `logs/deployment/test_results_{timestamp}.json`
- Human-readable summary: `logs/deployment/test_summary_{timestamp}.txt`
- Latest results: `logs/deployment/test_results_latest.json`

### 2. Failure Handler (`scripts/deployment/failure_handler.py`)

Handles deployment failures by generating logs, committing to GitHub, and sending notifications.

#### Features:
- **Failure Logging**: Comprehensive failure reports with context
- **GitHub Integration**: Automatically commits failure reports to repo
- **Push Notifications**: Sends Telegram notifications on failure
- **Context Collection**: Gathers git info, system info, Docker status
- **Error Classification**: Categorizes failures (build, test, deployment)

#### Usage:

```bash
# Handle a failure
python3 scripts/deployment/failure_handler.py \
    "test_failure" \
    "Unit tests failed" \
    --test-results /path/to/test_results.json \
    --stack-trace "traceback here" \
    --context '{"key": "value"}'
```

#### Output:
- Failure logs: `logs/deployment/failures/failure_{timestamp}.json`
- GitHub commit: `deployment-failures/failure_{timestamp}.md`
- Telegram notification: Sent to configured chat

### 3. GitHub Listener (`scripts/deployment/github_listener.py`)

Monitors GitHub repository for changes and automatically pulls code.

#### Features:
- **Auto-polling**: Checks repository at configurable intervals
- **Auto-pull**: Automatically pulls new commits
- **Test Integration**: Runs tests after pulling code
- **Failure Handling**: Handles test failures automatically

#### Usage:

```bash
# Start listener
python3 scripts/deployment/github_listener.py \
    --repo-path /home/admin/js-craw \
    --repo-url https://github.com/user/js-craw.git \
    --branch main \
    --interval 60

# Skip tests
python3 scripts/deployment/github_listener.py \
    --repo-path /home/admin/js-craw \
    --no-tests

# Skip failure handling
python3 scripts/deployment/github_listener.py \
    --repo-path /home/admin/js-craw \
    --no-handle-failures
```

#### Running as a Service:

Create a systemd service file:

```ini
[Unit]
Description=GitHub Repository Listener
After=network.target

[Service]
Type=simple
User=admin
WorkingDirectory=/home/admin/js-craw
ExecStart=/usr/bin/python3 /home/admin/js-craw/scripts/deployment/github_listener.py \
    --repo-path /home/admin/js-craw \
    --branch main \
    --interval 60
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable github-listener
sudo systemctl start github-listener
sudo systemctl status github-listener
```

### 4. Enhanced GitHub Actions Workflow

The workflow (`.github/workflows/deploy-pi-forge.yml`) has been enhanced with:

#### Pre-deployment Tests
- Runs test suite before building
- Continues even if tests fail (warns only)

#### Post-deployment Tests
- Runs comprehensive test suite after deployment
- Fails workflow if tests fail

#### Failure Handling
- Automatically detects failure type
- Collects test results and context
- Runs failure handler script
- Commits failure report to GitHub
- Sends push notification

## Workflow

### Successful Deployment

1. **Code Push**: Developer pushes to `main` branch
2. **GitHub Actions**: Workflow triggers on self-hosted runner
3. **Pre-deployment Tests**: Run test suite (warnings only)
4. **Build**: Docker images built
5. **Deploy**: Containers started
6. **Post-deployment Tests**: Comprehensive test suite
7. **Verification**: Health checks pass
8. **Success**: Deployment marker created

### Failed Deployment

1. **Code Push**: Developer pushes to `main` branch
2. **GitHub Actions**: Workflow triggers
3. **Failure Detection**: Step fails (build, deploy, or test)
4. **Failure Handler**:
   - Generates detailed failure log
   - Collects git info, system info, Docker status
   - Saves log files
   - Commits failure report to GitHub
   - Sends Telegram notification
5. **Developer Notification**: Gets push notification with failure details

## Configuration

### Environment Variables

The scripts use existing configuration from `app/config.py`:

- `TELEGRAM_BOT_TOKEN`: Telegram bot token (for notifications)
- `TELEGRAM_CHAT_ID`: Telegram chat ID (for notifications)
- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis connection string
- `OLLAMA_HOST`: Ollama service URL

### GitHub Secrets

For the GitHub Actions workflow, ensure these are configured:
- `PI_FORGE_SSH_KEY`: SSH key for pi-forge access
- `PI_FORGE_SSH_USER`: SSH user (default: admin)
- `PI_FORGE_HOST`: pi-forge hostname/IP

## Failure Reports

Failure reports are stored in two locations:

### 1. Local Logs
- **Location**: `logs/deployment/failures/`
- **Format**: JSON and text files
- **Content**: Full failure details, stack traces, context

### 2. GitHub Repository
- **Location**: `deployment-failures/`
- **Format**: Markdown summary + JSON full log
- **Content**: Formatted failure report, commit info, test results

### Example Failure Report Structure

```
deployment-failures/
├── failure_20250103_143022.md    # Human-readable summary
└── failure_20250103_143022.json  # Full log data
```

The markdown file includes:
- Error type and message
- Git commit information
- Test results summary
- Docker service status
- Link to full JSON log

## Notification System

### Telegram Notifications

When a deployment fails, you'll receive a Telegram message with:
- Error type and message
- Commit SHA and message
- Timestamp
- Link to GitHub commit

### Setting Up Telegram

1. Create a Telegram bot via [@BotFather](https://t.me/botfather)
2. Get your chat ID
3. Set environment variables:
   ```bash
   export TELEGRAM_BOT_TOKEN="your_bot_token"
   export TELEGRAM_CHAT_ID="your_chat_id"
   ```

## Testing the Pipeline

### Manual Test Run

```bash
# Run test suite manually
cd /home/admin/js-craw
python3 scripts/deployment/debug_test_runner.py --json

# Simulate a failure
python3 scripts/deployment/failure_handler.py \
    "test_failure" \
    "Manual test failure" \
    --test-results logs/deployment/test_results_latest.json
```

### Trigger Test Deployment

```bash
# Make a small change
cd /path/to/js-craw
echo "# Test" >> README.md
git add README.md
git commit -m "Test deployment pipeline"
git push origin main

# Watch GitHub Actions
# Check for notifications
```

## Troubleshooting

### Tests Fail to Run

**Issue**: Test runner can't find dependencies
**Solution**: Install test dependencies
```bash
pip install pytest requests
```

### GitHub Commit Fails

**Issue**: Failure handler can't commit to GitHub
**Solution**: 
- Ensure git is configured: `git config user.email` and `git config user.name`
- Check repository has write access
- Verify SSH keys are set up

### Notifications Not Sending

**Issue**: Telegram notifications not received
**Solution**:
- Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set
- Check bot token is valid
- Verify chat ID is correct (use [@userinfobot](https://t.me/userinfobot))

### GitHub Listener Not Pulling

**Issue**: Listener not detecting changes
**Solution**:
- Check repository URL is correct
- Verify branch name matches
- Check network connectivity
- Review listener logs

## Best Practices

1. **Run Tests Locally**: Test changes before pushing
2. **Monitor Notifications**: Stay aware of deployment status
3. **Review Failure Reports**: Check `deployment-failures/` for detailed errors
4. **Keep Dependencies Updated**: Ensure test dependencies are current
5. **Monitor Logs**: Check `logs/deployment/` for test results

## Integration with CI/CD

The pipeline integrates seamlessly with existing CI/CD:

- **GitHub Actions**: Enhanced workflow with testing
- **Self-hosted Runner**: Runs on pi-forge
- **Docker**: Automated builds and deployments
- **Health Checks**: Verifies deployment success

## Future Enhancements

Potential improvements:
- [ ] Webhook-based GitHub listener (instead of polling)
- [ ] Additional notification channels (Email, Slack, etc.)
- [ ] Automated rollback on failure
- [ ] Performance metrics collection
- [ ] Test coverage reporting
- [ ] Integration with monitoring tools

## Support

For issues or questions:
1. Check logs in `logs/deployment/`
2. Review failure reports in `deployment-failures/`
3. Check GitHub Actions workflow logs
4. Review Telegram notifications for error details

