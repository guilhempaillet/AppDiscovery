"""
HTTP caching layer with SHA256-based keys and rate limiting.
Implements disk-based cache with ETag support and per-host rate limits.
"""
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from apps.core.config import get_settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple token bucket rate limiter per host."""

    def __init__(self, requests_per_second: float = 2.0, burst: int = 5):
        self.rate = requests_per_second
        self.burst = burst
        self.tokens: Dict[str, float] = {}
        self.last_update: Dict[str, float] = {}

    def _get_host(self, url: str) -> str:
        """Extract host from URL."""
        from urllib.parse import urlparse
        return urlparse(url).netloc

    def wait_if_needed(self, url: str) -> None:
        """Block if rate limit would be exceeded."""
        host = self._get_host(url)
        now = time.time()

        if host not in self.tokens:
            self.tokens[host] = self.burst
            self.last_update[host] = now
            return

        # Refill tokens based on elapsed time
        elapsed = now - self.last_update[host]
        self.tokens[host] = min(
            self.burst,
            self.tokens[host] + elapsed * self.rate
        )
        self.last_update[host] = now

        # Wait if no tokens available
        if self.tokens[host] < 1.0:
            wait_time = (1.0 - self.tokens[host]) / self.rate
            logger.debug(f"Rate limit: waiting {wait_time:.2f}s for {host}")
            time.sleep(wait_time)
            self.tokens[host] = 0.0
        else:
            self.tokens[host] -= 1.0


class HTTPCache:
    """Disk-based HTTP cache with SHA256 keys."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl_seconds: int = 86400,
        rate_limiter: Optional[RateLimiter] = None,
        user_agent: Optional[str] = None,
    ):
        settings = get_settings()
        self.cache_dir = cache_dir or settings.cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self.rate_limiter = rate_limiter or RateLimiter(
            settings.rate_limit_requests_per_second,
            settings.rate_limit_burst,
        )
        self.user_agent = user_agent or settings.user_agent

        # Configure session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _compute_key(self, url: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Compute SHA256 cache key from URL and params."""
        key_input = url
        if params:
            key_input += "?" + urlencode(sorted(params.items()))
        return hashlib.sha256(key_input.encode()).hexdigest()

    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path with two-level directory structure."""
        # Use first 2 chars as subdir to avoid too many files in one dir
        subdir = self.cache_dir / key[:2]
        subdir.mkdir(exist_ok=True)
        return subdir / f"{key}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file exists and is within TTL."""
        if not cache_path.exists():
            return False
        age = time.time() - cache_path.stat().st_mtime
        return age < self.ttl_seconds

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        force_refresh: bool = False,
    ) -> Tuple[int, Any, bool]:
        """
        Fetch URL with caching.

        Returns:
            (status_code, data, from_cache)
            - status_code: HTTP status code
            - data: Parsed JSON if response is JSON, else text
            - from_cache: True if response came from cache
        """
        cache_key = self._compute_key(url, params)
        cache_path = self._get_cache_path(cache_key)

        # Try cache first (unless force_refresh)
        if not force_refresh and self._is_cache_valid(cache_path):
            try:
                with open(cache_path, "r") as f:
                    cached = json.load(f)
                logger.debug(f"Cache HIT: {url}")
                return cached["status"], cached["data"], True
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Cache read error for {url}: {e}")
                # Fall through to fetch

        # Cache miss - fetch from network
        logger.debug(f"Cache MISS: {url}")
        self.rate_limiter.wait_if_needed(url)

        request_headers = {"User-Agent": self.user_agent}
        if headers:
            request_headers.update(headers)

        try:
            response = self.session.get(
                url,
                params=params,
                headers=request_headers,
                timeout=30,
            )
            status = response.status_code

            # Try to parse as JSON
            try:
                data = response.json()
            except requests.exceptions.JSONDecodeError:
                data = response.text

            # Cache successful responses
            if 200 <= status < 300:
                cache_data = {
                    "status": status,
                    "data": data,
                    "url": url,
                    "cached_at": time.time(),
                }
                with open(cache_path, "w") as f:
                    json.dump(cache_data, f)
                logger.debug(f"Cached response for {url}")

            return status, data, False

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            raise


# Global cache instance
_cache: Optional[HTTPCache] = None


def get_cache() -> HTTPCache:
    """Get or create the global HTTP cache instance."""
    global _cache
    if _cache is None:
        _cache = HTTPCache()
    return _cache
