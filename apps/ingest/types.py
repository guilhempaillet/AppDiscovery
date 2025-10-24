"""
Pydantic types for ingest operations.
These are transport/validation types, not DB models.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class StoreAppSummary(BaseModel):
    """Summary from app store search results."""
    store_app_id: str
    bundle_or_package_id: Optional[str] = None
    title: str
    developer: str
    category: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    rating_avg: Optional[float] = None
    rating_count: Optional[int] = None
    locale: str = "en"  # Locale of the search


class AppDetails(BaseModel):
    """Detailed app metadata from store."""
    store_app_id: str
    bundle_or_package_id: Optional[str] = None
    title: str
    description: str
    developer: str
    category: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    rating_avg: Optional[float] = None
    rating_count: Optional[int] = None
    countries: Optional[List[str]] = None
    locale: str = "en"
    version: Optional[str] = None
    release_date: Optional[datetime] = None


class Review(BaseModel):
    """Individual review from app store."""
    store_review_id: str
    rating: int = Field(ge=1, le=5)
    title: Optional[str] = None
    body: Optional[str] = None
    author_name: Optional[str] = None
    locale: str
    created_at: datetime
    version: Optional[str] = None  # App version at time of review


class ReviewSample(BaseModel):
    """Simplified review for evidence bundles."""
    rating: int
    created_at: datetime
    body_raw: str
    locale: str


class Evidence(BaseModel):
    """Evidence bundle for an app."""
    app_id: int
    source_urls: List[str]
    fetched_at: datetime
    cached_paths: List[str] = []
    review_samples: List[ReviewSample] = []
    lang_detect: Optional[dict] = None  # {detected: str, confidence: float}
