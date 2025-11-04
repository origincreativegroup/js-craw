# Automation Command Center

## Overview

The Automation Command Center is a comprehensive dashboard that provides real-time monitoring, visualization, and full control over automated job crawls. It replaces the basic dashboard with an advanced interface for managing automation workflows.

## Features

### Real-Time Telemetry

- **System Status**: Current automation state (Idle, Running, Paused)
- **Current Run**: Active crawl progress with:
  - Current company being crawled
  - Progress (X of Y companies)
  - Queue length
  - Estimated completion time
- **Next Run**: Scheduled crawl information:
  - Scheduled time
  - Interval setting
  - Automation type

### Automation Health Chips

Color-coded health indicators showing:
- **Universal Crawl**: Overall success rate and interval
- **Per-Crawler Type**: Success rates for Selenium, API, and AI crawlers
- **Metrics**: Success rate, average duration, total runs, error counts

Health Status Colors:
- 🟢 **Green**: Success rate ≥ 90% (Healthy)
- 🟡 **Yellow**: Success rate 70-89% (Warning)
- 🔴 **Red**: Success rate < 70% (Error)

### Timeline/Event Stream

Visual timeline showing automation events from the last 24 hours:
- Recent crawl executions
- Status changes (running, completed, failed)
- Error details
- Duration metrics
- Crawler type classification

### Drill-Down Panels

Expandable panels for detailed analysis:
- **Selenium-Based Crawlers**: Indeed, LinkedIn
- **API-Based Crawlers**: Greenhouse, Lever
- **AI-Assisted Crawlers**: Generic, Workday

Each panel shows:
- Company list with last crawl status
- Success/failure indicators
- Last crawl timestamp
- Error details if failed

### Control Panel

Full automation control capabilities:
- **Interval Adjustment**: Change crawl interval (minimum 1 minute)
- **Pause/Resume**: Temporarily stop or restart scheduled crawls
- **Cancel Running Crawl**: Stop a currently executing crawl
- **Manual Triggers**: Run search-based or universal crawls on demand

## API Endpoints

### Automation Status

```http
GET /api/crawl/status
```

Returns enhanced status with:
- `is_running`: Boolean indicating if crawl is active
- `queue_length`: Number of companies/searches pending
- `current_company`: Name of company currently being crawled
- `progress`: Object with `current` and `total` company counts
- `eta_seconds`: Estimated time to completion
- `run_type`: Type of crawl ('all_companies' or 'search')
- `crawler_health`: Per-crawler-type health metrics

### Scheduler Metadata

```http
GET /api/automation/scheduler
```

Returns:
- `status`: Scheduler state ('running' or 'stopped')
- `next_run`: ISO timestamp of next scheduled run
- `interval_minutes`: Current crawl interval
- `is_paused`: Boolean indicating if scheduler is paused

### Update Interval

```http
PATCH /api/automation/scheduler
Content-Type: application/json

{
  "interval_minutes": 30
}
```

Updates the crawl interval (minimum 1 minute).

### Pause/Resume Scheduler

```http
POST /api/automation/pause
POST /api/automation/resume
```

Pauses or resumes the scheduled crawl automation.

### Cancel Running Crawl

```http
POST /api/crawl/cancel
```

Cancels any currently running crawl operation.

### Event Stream

```http
GET /api/crawl/logs?crawler_type=selenium&status=completed&hours=24&limit=100
```

Query Parameters:
- `crawler_type`: Filter by 'selenium', 'api', or 'ai'
- `status`: Filter by 'running', 'completed', or 'failed'
- `hours`: Hours of history to include (default: 24)
- `limit`: Maximum number of events (default: 100)

Returns detailed event stream with timestamps, durations, and crawler classifications.

## Crawler Type Classification

The system automatically classifies crawlers into three categories:

1. **Selenium-Based**: Indeed, LinkedIn
   - Uses browser automation
   - Slower but more flexible
   - Can handle JavaScript-heavy pages

2. **API-Based**: Greenhouse, Lever
   - Direct API access
   - Fast and reliable
   - Structured data format

3. **AI-Assisted**: Generic, Workday
   - Uses Ollama AI to parse HTML
   - Handles custom page structures
   - Most flexible but slower

## Real-Time Updates

The dashboard uses intelligent polling:
- **Status Updates**: Every 3 seconds when active
- **Scheduler Updates**: Every 10 seconds
- **Timeline Updates**: On manual refresh or tab switch
- **Drill-Down Panels**: Load on demand when expanded

## Usage

### Viewing Automation Status

1. Navigate to the Dashboard tab
2. View the automation header for system status
3. Check health chips for quick overview
4. Review current run card if a crawl is active
5. See next scheduled run information

### Monitoring Crawls

1. Use the timeline to see recent automation events
2. Filter by crawler type or status using the API
3. Expand drill-down panels for detailed company status
4. Watch real-time progress updates during active crawls

### Controlling Automation

1. **Adjust Interval**: Enter new interval in minutes and click "Update"
2. **Pause**: Click "Pause" to temporarily stop scheduled crawls
3. **Resume**: Click "Resume" to restart paused automation
4. **Cancel**: Click "Cancel Running Crawl" to stop active crawl
5. **Manual Trigger**: Use "Run Search Crawl" or "Run Universal Crawl" buttons

## Best Practices

- Monitor health chips regularly to spot issues early
- Use drill-down panels to identify problematic crawlers
- Review timeline for patterns in failures
- Adjust interval based on system load and crawl duration
- Use pause/resume for maintenance windows

## Troubleshooting

### No Data in Timeline
- Check if crawls have run in the last 24 hours
- Verify database connection
- Check crawl logs for errors

### Health Chips Show Errors
- Review drill-down panels for specific company failures
- Check error messages in timeline
- Verify crawler configuration for problematic companies

### Interval Not Updating
- Ensure interval is at least 1 minute
- Check for API errors in browser console
- Verify scheduler is running

## Technical Implementation

### Progress Tracking

The orchestrator tracks:
- Current run type ('all_companies' or 'search')
- Current company index and total companies
- Company name being crawled
- Start time for duration calculation
- Rolling average of crawl durations for ETA

### ETA Calculation

ETA is calculated using:
1. Rolling average of last 10 company crawl durations
2. Remaining companies in queue
3. Formula: `avg_duration * remaining_companies`

### Health Metrics

Health metrics are calculated from recent crawl logs:
- **Success Rate**: (completed / total) * 100
- **Average Duration**: Moving average of crawl durations
- **Error Count**: Number of failed crawls
- **Total Runs**: Total number of crawl attempts

Metrics are calculated per crawler type (Selenium, API, AI) for granular analysis.

