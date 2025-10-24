"""
Smoke tests for ingest functionality.
Tests search, details, reviews, and caching with real API calls (cached).
"""
import os
from datetime import datetime

import pytest

from apps.ingest.cache import HTTPCache, RateLimiter
from apps.ingest.fetchers.appstore import fetch_details, fetch_reviews, search_apps


# Test app IDs (well-known apps)
APPLE_TEST_APP_IDS = {
    "mint": "300238550",  # Mint: Budget & Expense Tracker
    "ynab": "1010865877",  # YNAB (You Need A Budget)
}

# Skip if not in CI or explicit test mode
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SMOKE_TESTS") != "true",
    reason="Smoke tests disabled (set RUN_SMOKE_TESTS=true to run)",
)


class TestCache:
    """Test HTTP cache functionality."""

    def test_cache_key_generation(self, tmp_path):
        """Test that cache keys are generated correctly."""
        cache = HTTPCache(cache_dir=tmp_path, ttl_seconds=3600)

        key1 = cache._compute_key("https://example.com/api", {"q": "test", "limit": 10})
        key2 = cache._compute_key("https://example.com/api", {"limit": 10, "q": "test"})
        key3 = cache._compute_key("https://example.com/api", {"q": "test", "limit": 20})

        # Same params in different order should produce same key
        assert key1 == key2
        # Different params should produce different key
        assert key1 != key3
        # Keys should be hex strings
        assert len(key1) == 64  # SHA256 hex length

    def test_rate_limiter(self):
        """Test rate limiter token bucket."""
        limiter = RateLimiter(requests_per_second=10.0, burst=5)

        # Should allow burst requests immediately
        for _ in range(5):
            limiter.wait_if_needed("https://example.com")

        # Next request should wait (but we won't actually wait in test)
        # Just verify tokens are depleted
        assert limiter.tokens["example.com"] < 1.0


class TestAppleAppStoreFetcher:
    """Test Apple App Store fetcher functions."""

    def test_search_apps(self):
        """Test searching for apps."""
        results = search_apps(term="budget", lang="en", country="US", limit=10)

        assert len(results) > 0
        assert len(results) <= 10

        # Check first result has required fields
        first = results[0]
        assert first.store_app_id
        assert first.title
        assert first.developer
        assert first.locale == "en-US"

    def test_search_apps_spanish(self):
        """Test searching in Spanish locale."""
        results = search_apps(term="gastos", lang="es", country="ES", limit=5)

        assert len(results) > 0
        first = results[0]
        assert first.locale == "es-ES"

    def test_fetch_details(self):
        """Test fetching app details."""
        app_id = APPLE_TEST_APP_IDS["mint"]
        details = fetch_details(app_id, country="US", lang="en")

        assert details is not None
        assert details.store_app_id == app_id
        assert details.title
        assert details.description
        assert len(details.description) > 100  # Should have substantial description
        assert details.developer
        assert details.bundle_or_package_id

    def test_fetch_details_multiple_locales(self):
        """Test fetching details in different locales."""
        app_id = APPLE_TEST_APP_IDS["ynab"]

        # English
        details_en = fetch_details(app_id, country="US", lang="en")
        assert details_en is not None
        assert details_en.locale == "en-US"

        # Spanish
        details_es = fetch_details(app_id, country="ES", lang="es")
        assert details_es is not None
        assert details_es.locale == "es-ES"

    def test_fetch_reviews(self):
        """Test fetching reviews."""
        app_id = APPLE_TEST_APP_IDS["mint"]
        reviews = list(fetch_reviews(app_id, country="US", page_limit=2))

        assert len(reviews) > 0
        assert len(reviews) <= 100  # 2 pages, ~50 reviews per page

        # Check first review
        first = reviews[0]
        assert first.store_review_id
        assert 1 <= first.rating <= 5
        assert first.created_at
        assert isinstance(first.created_at, datetime)

    def test_fetch_reviews_pagination(self):
        """Test that pagination works."""
        app_id = APPLE_TEST_APP_IDS["mint"]

        # Fetch 1 page
        reviews_page1 = list(fetch_reviews(app_id, country="US", page_limit=1))

        # Fetch 2 pages
        reviews_page2 = list(fetch_reviews(app_id, country="US", page_limit=2))

        # Should have more reviews with more pages
        assert len(reviews_page2) >= len(reviews_page1)

    def test_cache_works_for_search(self, tmp_path):
        """Test that search results are cached."""
        cache = HTTPCache(cache_dir=tmp_path, ttl_seconds=3600)

        # Monkey patch the global cache for this test
        import apps.ingest.cache
        original_cache = apps.ingest.cache._cache
        apps.ingest.cache._cache = cache

        try:
            # First call - should hit network
            results1 = search_apps(term="test", lang="en", country="US", limit=5)

            # Second call - should hit cache
            results2 = search_apps(term="test", lang="en", country="US", limit=5)

            # Results should be identical
            assert len(results1) == len(results2)
            if results1:
                assert results1[0].store_app_id == results2[0].store_app_id

            # Check that cache directory has files
            cache_files = list(tmp_path.rglob("*.json"))
            assert len(cache_files) > 0

        finally:
            apps.ingest.cache._cache = original_cache


class TestIdempotency:
    """Test idempotent upserts."""

    def test_search_results_stable(self):
        """Test that searching twice gives consistent results."""
        results1 = search_apps(term="finance", lang="en", country="US", limit=5)
        results2 = search_apps(term="finance", lang="en", country="US", limit=5)

        # Should get same apps (cache will ensure this)
        assert len(results1) == len(results2)
        app_ids1 = {r.store_app_id for r in results1}
        app_ids2 = {r.store_app_id for r in results2}
        assert app_ids1 == app_ids2
