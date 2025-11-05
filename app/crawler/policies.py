import asyncio
import random
import time
from dataclasses import dataclass
from typing import Callable, Awaitable, Optional, Dict

from app.crawler.errors import RetryableError, ThrottledError, ForbiddenError, CaptchaError, CrawlError


@dataclass
class RetryPolicy:
    max_retries: int = 3
    initial_backoff_ms: int = 300
    max_backoff_ms: int = 5000
    jitter_ms: int = 150

    async def retry(self, op: Callable[[], Awaitable]):
        attempt = 0
        backoff = self.initial_backoff_ms
        while True:
            try:
                return await op()
            except ThrottledError as e:
                attempt += 1
                if attempt > self.max_retries:
                    raise
                delay = e.retry_after_seconds * 1000 if e.retry_after_seconds else min(backoff, self.max_backoff_ms)
                await asyncio.sleep((delay + random.randint(0, self.jitter_ms)) / 1000.0)
                backoff = min(backoff * 2, self.max_backoff_ms)
            except (RetryableError,) as e:
                attempt += 1
                if attempt > self.max_retries:
                    raise
                await asyncio.sleep((min(backoff, self.max_backoff_ms) + random.randint(0, self.jitter_ms)) / 1000.0)
                backoff = min(backoff * 2, self.max_backoff_ms)


class TokenBucket:
    def __init__(self, rate_per_sec: float, burst: int):
        self.rate = rate_per_sec
        self.capacity = burst
        self.tokens = burst
        self.timestamp = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.timestamp
            self.timestamp = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            if self.tokens < 1:
                wait = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait)
                self.tokens = 0
            else:
                self.tokens -= 1


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_timeout_seconds: int = 300):
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self.failures: int = 0
        self.opened_at: Optional[float] = None
        self._lock = asyncio.Lock()

    async def on_success(self):
        async with self._lock:
            self.failures = 0
            self.opened_at = None

    async def on_failure(self):
        async with self._lock:
            self.failures += 1
            if self.failures >= self.failure_threshold:
                self.opened_at = time.monotonic()

    async def allow(self) -> bool:
        async with self._lock:
            if self.opened_at is None:
                return True
            if time.monotonic() - self.opened_at >= self.reset_timeout_seconds:
                # half-open
                self.failures = 0
                self.opened_at = None
                return True
            return False


class CrawlPolicy:
    def __init__(
        self,
        retry: RetryPolicy,
        domain_rate_limit: TokenBucket,
        breaker: CircuitBreaker,
    ):
        self.retry_policy = retry
        self.rate_limiter = domain_rate_limit
        self.breaker = breaker

    async def run(self, domain_key: str, op: Callable[[], Awaitable]):
        if not await self.breaker.allow():
            raise CrawlError(f"Circuit open for {domain_key}")

        async def guarded():
            await self.rate_limiter.acquire()
            try:
                result = await op()
                await self.breaker.on_success()
                return result
            except (ThrottledError, ForbiddenError, CaptchaError, RetryableError):
                await self.breaker.on_failure()
                raise
            except Exception:
                # non-classified errors don't trip breaker permanently but still count
                await self.breaker.on_failure()
                raise


class PolicyRegistry:
    """Maintains per-domain policy instances."""

    def __init__(self, rate_per_host: float = 1.0, burst: int = 2, failure_threshold: int = 5, reset_timeout_seconds: int = 300, retry: Optional[RetryPolicy] = None):
        self._buckets: Dict[str, TokenBucket] = {}
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._retry = retry or RetryPolicy()
        self._rate_per_host = rate_per_host
        self._burst = burst
        self._failure_threshold = failure_threshold
        self._reset_timeout_seconds = reset_timeout_seconds

    def get_policy(self, domain_key: str) -> CrawlPolicy:
        bucket = self._buckets.get(domain_key)
        if not bucket:
            bucket = TokenBucket(self._rate_per_host, self._burst)
            self._buckets[domain_key] = bucket
        breaker = self._breakers.get(domain_key)
        if not breaker:
            breaker = CircuitBreaker(self._failure_threshold, self._reset_timeout_seconds)
            self._breakers[domain_key] = breaker
        return CrawlPolicy(self._retry, bucket, breaker)

    def metrics(self) -> Dict[str, Dict[str, float | int | bool]]:
        data: Dict[str, Dict[str, float | int | bool]] = {}
        for domain, breaker in self._breakers.items():
            data[domain] = {
                "failures": breaker.failures,
                "open": breaker.opened_at is not None,
                "opened_seconds_ago": 0.0 if breaker.opened_at is None else (time.monotonic() - breaker.opened_at),
            }
        return data


