import typing as _t


class CrawlError(Exception):
    """Base error for crawl operations."""


class RetryableError(CrawlError):
    """Transient error that should be retried (network, timeouts)."""


class ThrottledError(CrawlError):
    """HTTP 429 / rate limited."""
    retry_after_seconds: _t.Optional[int]

    def __init__(self, message: str = "Throttled", retry_after_seconds: _t.Optional[int] = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ForbiddenError(CrawlError):
    """HTTP 403 / access denied (often anti-bot)."""


class CaptchaError(CrawlError):
    """Captcha detected; require cooldown or alternate method."""


class ParseError(CrawlError):
    """Content fetched but parsing failed."""


def classify_http_status(status_code: int) -> _t.Type[CrawlError] | None:
    if status_code == 429:
        return ThrottledError
    if status_code == 403:
        return ForbiddenError
    if 500 <= status_code < 600:
        return RetryableError
    return None


