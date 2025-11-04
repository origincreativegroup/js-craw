# Career Page Crawler - Design Document

## Problem Statement

LinkedIn and Indeed actively block automated crawlers and require authentication that can lead to account bans. We need a more reliable approach that goes directly to the source: company career pages.

## Solution: Direct Career Page Crawling

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Job Search System                        │
│                                                               │
│  ┌──────────────┐      ┌───────────────────────────────┐   │
│  │   Company    │      │   Career Page Crawler          │   │
│  │   Database   │─────▶│   - Generic parser              │   │
│  │              │      │   - AI-assisted extraction      │   │
│  └──────────────┘      │   - Multi-format support        │   │
│                        └───────────────────────────────┘   │
│                                    │                         │
│                                    ▼                         │
│                        ┌───────────────────────────────┐   │
│                        │   Ollama AI Analyzer           │   │
│                        │   - Job matching                │   │
│                        │   - Content extraction          │   │
│                        │   - Scoring                     │   │
│                        └───────────────────────────────┘   │
│                                    │                         │
│                                    ▼                         │
│                        ┌───────────────────────────────┐   │
│                        │   Notification Service         │   │
│                        │   (ntfy, Pushover, Telegram)   │   │
│                        └───────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## New Database Schema

### Company Model
```python
class Company(Base):
    id: int
    name: str                      # "Stripe", "Google"
    career_page_url: str           # https://stripe.com/jobs
    is_active: bool
    crawler_type: str              # "greenhouse", "lever", "workday", "generic"
    crawler_config: JSON           # Custom parsing rules
    last_crawled_at: datetime
    jobs_found_total: int
    created_at: datetime
```

### Modified SearchCriteria
```python
class SearchCriteria(Base):
    # Remove: platforms field (no more linkedin/indeed)
    # Add: target_companies (JSON list of company IDs)
    target_companies: JSON = None  # [1, 2, 3] or null for all companies
```

### Modified Job Model
```python
class Job(Base):
    # Change: platform → company_id
    company_id: int                # Foreign key to Company
    # Add: career_page_url to track where it was found
    source_url: str                # Direct link to job posting
```

## Career Page Crawler Types

### 1. ATS-Specific Crawlers (Easy)

Many companies use standard applicant tracking systems:

- **Greenhouse**: JSON API available (`/embed/job_board/json?for=<company>`)
- **Lever**: JSON API available (`/v0/postings/<company>`)
- **Workday**: Structured HTML with consistent selectors
- **BambooHR**: Structured XML/JSON feeds
- **SmartRecruiters**: API available

### 2. AI-Assisted Generic Crawler (Flexible)

For custom career pages, use AI to:
1. Identify job listing structure
2. Extract job details from unstructured content
3. Find pagination/navigation

**Approach**:
```python
# 1. Fetch page HTML
html = await fetch_career_page(url)

# 2. Pass to Ollama with structured prompt
prompt = f"""
You are analyzing a company career page. Extract job listings.

HTML:
{html[:10000]}  # Send first 10k chars

Return JSON array:
[
  {{
    "title": "Software Engineer",
    "url": "https://...",
    "location": "Remote",
    "type": "Full-time",
    "description": "..."
  }}
]
"""

# 3. Parse AI response
jobs = await ollama.generate(prompt)
```

### 3. Hybrid Approach (Best)

1. Try ATS-specific crawler if known
2. Fall back to AI-assisted parsing
3. Cache parsing rules for future crawls

## Implementation Plan

### Phase 1: Core Infrastructure (30 min)

1. **Add Company model** to database
2. **Create migration** script
3. **Update API** to manage companies (CRUD)
4. **Seed database** with 10-20 tech companies

### Phase 2: Greenhouse Crawler (30 min)

Start with Greenhouse (very common, easy API):

```python
class GreenhouseCrawler:
    async def fetch_jobs(self, company_name: str):
        url = f"https://boards-api.greenhouse.io/v1/boards/{company_name}/jobs"
        response = await httpx.get(url)
        return response.json()["jobs"]
```

**Companies using Greenhouse**:
- Stripe, Airbnb, Spotify, Coinbase, DoorDash, etc.

### Phase 3: Lever Crawler (20 min)

```python
class LeverCrawler:
    async def fetch_jobs(self, company_name: str):
        url = f"https://api.lever.co/v0/postings/{company_name}"
        response = await httpx.get(url)
        return response.json()
```

**Companies using Lever**:
- Netflix, Figma, Canva, Shopify, etc.

### Phase 4: AI-Assisted Generic Crawler (1 hour)

For companies with custom career pages:

1. Fetch HTML with Playwright
2. Send to Ollama for parsing
3. Extract job details
4. Cache parsing patterns

### Phase 5: Update UI (30 min)

1. Remove credential management (no more logins!)
2. Add company management page
3. Update search criteria to target companies
4. Show which companies are being monitored

## Benefits of This Approach

### ✅ Reliability
- No account bans
- No authentication required
- Public data only

### ✅ Scalability
- Easy to add new companies
- ATS crawlers are fast and stable
- AI fallback for custom pages

### ✅ Maintainability
- Less code to maintain (no Selenium login flows)
- Standard APIs (Greenhouse, Lever)
- AI handles edge cases

### ✅ Performance
- Faster crawls (API vs Selenium)
- No login overhead
- Can crawl companies in parallel

## Example Company List

### Tech Companies (Greenhouse)
- Stripe
- Airbnb
- Coinbase
- DoorDash
- GitLab
- Plaid
- Ramp
- Databricks

### Tech Companies (Lever)
- Netflix
- Figma
- Canva
- Notion
- Linear
- Vercel

### Custom Career Pages (AI-Assisted)
- Smaller startups
- Companies with in-house career sites

## Migration Strategy

### For Existing Users

1. **Keep existing data**: Don't delete Job table
2. **Add company association**: Map old jobs to companies
3. **Disable LinkedIn/Indeed**: Mark as deprecated
4. **Smooth transition**: Both systems work during migration

### Database Migration

```sql
-- Add companies table
CREATE TABLE companies (...);

-- Seed initial companies
INSERT INTO companies ...;

-- Add company_id to jobs table
ALTER TABLE jobs ADD COLUMN company_id INTEGER;

-- Migrate existing data
UPDATE jobs SET company_id = (
  SELECT id FROM companies WHERE name = jobs.company
);
```

## Testing Strategy

### Unit Tests
- Test each ATS crawler separately
- Test AI parsing with sample HTML
- Test company management API

### Integration Tests
- Crawl 3-5 real companies
- Verify job extraction accuracy
- Test notification flow

### E2E Tests
- Add company → Crawl → Match → Notify

## Monitoring

### Metrics to Track
- Crawl success rate per company
- Jobs found per crawl
- AI parsing accuracy
- Crawler failures/errors

### Alerts
- Company site down/changed
- Zero jobs found (might indicate parsing issue)
- AI parsing failures

## Future Enhancements

### Auto-Discovery
Use AI to automatically:
1. Find company career page from company name
2. Detect ATS type
3. Generate parsing rules

### Smart Scheduling
- Crawl more frequently for active companies
- Slow down for companies with few updates
- Prioritize companies matching user criteria

### Community Database
- Share company configurations
- Crowdsource ATS detection
- Build library of parsing rules

## Implementation Checklist

- [ ] Create Company model and migration
- [ ] Build Greenhouse crawler
- [ ] Build Lever crawler
- [ ] Build AI-assisted generic crawler
- [ ] Update orchestrator to use new crawlers
- [ ] Update API endpoints for company management
- [ ] Seed database with 20+ companies
- [ ] Update frontend UI
- [ ] Test with real companies
- [ ] Remove LinkedIn/Indeed code
- [ ] Update documentation

## Timeline Estimate

- **Phase 1-3**: 1-2 hours (ATS crawlers, data models)
- **Phase 4**: 1 hour (AI-assisted crawler)
- **Phase 5**: 30 min (UI updates)
- **Testing**: 30 min

**Total**: ~3-4 hours for MVP

## Questions to Consider

1. Which companies should we seed initially?
2. What job matching criteria are most important?
3. Should we support RSS feeds (some companies have them)?
4. Rate limiting strategy for crawling?

---

**Status**: Design Complete - Ready for Implementation
**Author**: Claude Code
**Date**: 2025-11-03
