"""
App store fetchers.
Each fetcher implements search, details, and reviews for a specific store.
"""
from typing import Iterator, List

from apps.ingest.types import AppDetails, Review, StoreAppSummary

# Re-export fetcher functions for convenience
from apps.ingest.fetchers.appstore import (
    fetch_details as apple_fetch_details,
    fetch_reviews as apple_fetch_reviews,
    search_apps as apple_search_apps,
)

__all__ = [
    "apple_search_apps",
    "apple_fetch_details",
    "apple_fetch_reviews",
]
