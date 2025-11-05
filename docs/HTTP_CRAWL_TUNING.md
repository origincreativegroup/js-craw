# HTTP and Crawl Tuning

This project exposes configuration knobs to control crawl aggressiveness, resilience and anti-blocking behavior. Configure via environment variables (see .env.example) or your deployment environment.

## Key Settings

- HTTP_RATE_PER_HOST: tokens per second allowed per host (default 1.0)
- HTTP_BURST_PER_HOST: burst capacity per host (default 2)
- HTTP_MAX_RETRIES: max retries for retryable errors (default 3)
- HTTP_INITIAL_BACKOFF_MS: initial backoff in ms (default 300)
- HTTP_MAX_BACKOFF_MS: maximum backoff in ms (default 5000)
- HTTP_REQUEST_TIMEOUT_SECONDS: request timeout (default 20)
- ROBOTS_RESPECT: respect robots.txt (true|false, default true)
- HTTP_USER_AGENTS: JSON array of user-agents to rotate (optional)
- HTTP_PROXIES: JSON array of proxy URLs (optional)
- MAX_CONCURRENT_COMPANY_CRAWLS: orchestrator parallelism (default 5)
- AI_BATCH_SIZE: AI analysis batch size (default 20)

## Suggested defaults

Development:
- HTTP_RATE_PER_HOST=1.0
- HTTP_BURST_PER_HOST=2
- HTTP_MAX_RETRIES=3
- HTTP_INITIAL_BACKOFF_MS=300
- HTTP_MAX_BACKOFF_MS=5000
- HTTP_REQUEST_TIMEOUT_SECONDS=20
- ROBOTS_RESPECT=true
- MAX_CONCURRENT_COMPANY_CRAWLS=3
- AI_BATCH_SIZE=10

Production (moderate):
- HTTP_RATE_PER_HOST=1.0
- HTTP_BURST_PER_HOST=2
- MAX_CONCURRENT_COMPANY_CRAWLS=5
- AI_BATCH_SIZE=20

Aggressive (use carefully, consider proxies):
- HTTP_RATE_PER_HOST=2.0
- HTTP_BURST_PER_HOST=4
- MAX_CONCURRENT_COMPANY_CRAWLS=8
- AI_BATCH_SIZE=30

## .env example

See `.env.example` for a ready-to-copy template.

## Notes

- Keep ROBOTS_RESPECT=true unless you have permission to crawl and understand legal/ethical implications.
- If you add proxies, ensure they are compliant with target sites' terms of service.
- Tuning parallelism may increase the chance of 429/403; the circuit breaker and backoff will mitigate but not eliminate blocks.
