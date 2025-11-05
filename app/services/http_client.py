import asyncio
import random
import re
from typing import Optional, Dict, Tuple

import httpx

from app.config import settings
from app.crawler.errors import RetryableError, ThrottledError, ForbiddenError


_etag_cache: Dict[str, Tuple[str, Optional[str]]] = {}
_robots_cache: Dict[str, Dict[str, bool]] = {}
_ua_pool = [
    # Minimal UA pool; can be overridden by settings
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
]


def _choose_user_agent() -> str:
    pool = getattr(settings, "HTTP_USER_AGENTS", None) or _ua_pool
    return random.choice(pool)


def _extract_host(url: str) -> str:
    m = re.match(r"https?://([^/]+)/?", url)
    return m.group(1).lower() if m else ""


async def _fetch_robots(client: httpx.AsyncClient, host: str) -> Dict[str, bool]:
    if host in _robots_cache:
        return _robots_cache[host]
    robots_url = f"https://{host}/robots.txt"
    rules: Dict[str, bool] = {}
    try:
        r = await client.get(robots_url, timeout=10)
        if r.status_code == 200 and r.text:
            for line in r.text.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.lower().startswith('disallow:'):
                    path = line.split(':', 1)[1].strip()
                    if path:
                        rules[path] = True
    except Exception:
        pass
    _robots_cache[host] = rules
    return rules


def _is_disallowed(rules: Dict[str, bool], path: str) -> bool:
    # naive prefix match
    for dis in rules.keys():
        if path.startswith(dis):
            return True
    return False


class HttpClient:
    def __init__(self):
        self._client = httpx.AsyncClient(follow_redirects=True)

    async def close(self):
        await self._client.aclose()

    async def get(self, url: str, headers: Optional[Dict[str, str]] = None, use_cache_headers: bool = True) -> httpx.Response:
        host = _extract_host(url)
        hdrs = {"User-Agent": _choose_user_agent(), "Accept-Encoding": "gzip, deflate, br"}
        if headers:
            hdrs.update(headers)

        # robots.txt respect
        if getattr(settings, 'ROBOTS_RESPECT', True):
            rules = await _fetch_robots(self._client, host)
            path = url.split(host, 1)[-1]
            if _is_disallowed(rules, path):
                raise ForbiddenError("robots.txt disallows this path")

        # Conditional headers (ETag/Last-Modified)
        if use_cache_headers and url in _etag_cache:
            etag, last_mod = _etag_cache[url]
            if etag:
                hdrs['If-None-Match'] = etag
            if last_mod:
                hdrs['If-Modified-Since'] = last_mod

        # Optional proxy support
        proxies = None
        proxy_list = getattr(settings, 'HTTP_PROXIES', None) or []
        if proxy_list:
            proxies = random.choice(proxy_list)

        try:
            r = await self._client.get(url, headers=hdrs, timeout=settings.HTTP_REQUEST_TIMEOUT_SECONDS, proxies=proxies)
        except httpx.TimeoutException as e:
            raise RetryableError(str(e))
        except httpx.TransportError as e:
            raise RetryableError(str(e))

        # Cache ETag / Last-Modified
        if r.status_code == 200:
            _etag_cache[url] = (r.headers.get('ETag'), r.headers.get('Last-Modified'))
        elif r.status_code == 304:
            # Not modified — return as-is for caller to handle
            pass
        elif r.status_code == 429:
            retry_after = None
            try:
                retry_after = int(r.headers.get('Retry-After', ''))
            except Exception:
                retry_after = None
            raise ThrottledError(retry_after_seconds=retry_after)
        elif r.status_code == 403:
            raise ForbiddenError("403 Forbidden")
        elif 500 <= r.status_code < 600:
            raise RetryableError(f"{r.status_code}")

        return r


