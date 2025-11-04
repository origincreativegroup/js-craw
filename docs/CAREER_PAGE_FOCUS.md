# Career Page Focus

## Overview

This job crawler **exclusively crawls company career pages directly**, bypassing job boards like LinkedIn and Indeed. This approach is more reliable, avoids anti-bot measures, and gives you direct access to the source.

## Why Career Pages?

### Problems with Job Boards (LinkedIn/Indeed)

1. **Anti-Bot Measures**: LinkedIn and Indeed actively block automated crawlers
2. **Account Bans**: Using Selenium to automate these sites risks account suspension
3. **Rate Limiting**: Strict limits on requests and searches
4. **Delayed Listings**: Job boards may not have all openings immediately
5. **Authentication Required**: Need to maintain accounts and credentials

### Benefits of Direct Career Page Crawling

1. **Reliability**: Career pages are public and designed to be crawled
2. **No Authentication**: No need for accounts or credentials
3. **Complete Coverage**: Access to all job listings, not just what's on job boards
4. **Faster Updates**: Jobs appear on career pages immediately
5. **No Rate Limits**: Can crawl as aggressively as needed

## Supported Crawler Types

### 1. Greenhouse
Companies using Greenhouse.io (e.g., Stripe, Airbnb, GitHub)
- Uses Greenhouse API
- Fast and reliable
- Structured data format

### 2. Lever
Companies using Lever.co (e.g., Netflix, Figma)
- Uses Lever API
- Clean job listings
- Good metadata

### 3. Generic (AI-Assisted)
Any company career page
- Uses Ollama AI to parse HTML
- Extracts job listings from any page structure
- Handles custom formats and designs

## How It Works

1. **Company Database**: Maintain a list of companies you want to monitor
2. **Crawler Selection**: System auto-detects crawler type (Greenhouse/Lever/Generic)
3. **AI Filtering**: All jobs are analyzed by AI for relevance
4. **Direct Access**: Jobs link directly to company career pages

## Adding Companies

Use the web dashboard or API to add companies:
- Company name
- Career page URL
- Crawler type (auto-detected)
- Configuration (if needed)

The system will automatically crawl their career pages and filter jobs using AI.

## AI Filtering

All jobs are analyzed in real-time using Ollama:
- Match score (0-100)
- Recommended flag
- Pros and cons
- Keyword matching
- Summary

Only relevant jobs are saved to the database.

## Future Enhancements

- **Discovery**: Automatically discover companies by industry/keyword
- **More ATS Support**: Workday, SmartRecruiters, etc.
- **Bulk Import**: Import companies from CSV or API
- **Industry Filtering**: Focus on specific industries or locations
