"""
Database models for AppDiscovery.
Uses SQLModel for type-safe ORM with Pydantic integration.
"""
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import JSON, Column, Index, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class Store(SQLModel, table=True):
    """App store metadata (apple, google_play, etc.)."""
    __tablename__ = "stores"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)  # "apple" | "google_play"
    display_name: str
    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    apps: List["App"] = Relationship(back_populates="store")


class App(SQLModel, table=True):
    """Core app record, one per unique (store, store_app_id)."""
    __tablename__ = "apps"
    __table_args__ = (
        UniqueConstraint("store_id", "store_app_id", name="uq_app_store_id"),
        Index("ix_app_bundle_id", "bundle_or_package_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    store_id: int = Field(foreign_key="stores.id", index=True)
    store_app_id: str = Field(index=True)  # e.g., "123456789" for Apple
    bundle_or_package_id: Optional[str] = None  # e.g., "com.example.app"
    developer: Optional[str] = None
    category: Optional[str] = None
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    store: Store = Relationship(back_populates="apps")
    locales: List["AppLocale"] = Relationship(back_populates="app")
    reviews: List["Review"] = Relationship(back_populates="app")
    snapshots: List["DailySnapshot"] = Relationship(back_populates="app")
    evidences: List["Evidence"] = Relationship(back_populates="app")


class AppLocale(SQLModel, table=True):
    """Localized app metadata (title, description) in original language."""
    __tablename__ = "app_locales"
    __table_args__ = (
        UniqueConstraint("app_id", "locale", name="uq_app_locale"),
        Index("ix_app_locale_locale", "locale"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    app_id: int = Field(foreign_key="apps.id", index=True)
    locale: str  # BCP-47, e.g., "es-MX"
    title_raw: str
    desc_raw: Optional[str] = None

    # Translation fields (null until translated)
    title_en: Optional[str] = None
    desc_en: Optional[str] = None
    translation_provider: Optional[str] = None  # "deepl" | "llm" | "null"
    translated_at: Optional[datetime] = None

    # Pricing
    price: Optional[float] = None
    currency: Optional[str] = None

    # Metadata
    countries: Optional[str] = Field(default=None, sa_column=Column(JSON))  # List[str] as JSON
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    app: App = Relationship(back_populates="locales")


class Review(SQLModel, table=True):
    """App store reviews, raw text only."""
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("app_id", "store_review_id", name="uq_review_store_id"),
        Index("ix_review_created_at", "created_at"),
        Index("ix_review_locale", "locale"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    app_id: int = Field(foreign_key="apps.id", index=True)
    store_review_id: str  # Platform-specific review ID
    locale: str  # BCP-47
    rating: int  # 1-5
    title_raw: Optional[str] = None
    body_raw: Optional[str] = None

    # Translation fields
    title_en: Optional[str] = None
    body_en: Optional[str] = None
    translation_provider: Optional[str] = None
    translated_at: Optional[datetime] = None

    # Metadata
    author_name: Optional[str] = None  # Display name only (public)
    created_at: datetime
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    app: App = Relationship(back_populates="reviews")


class DailySnapshot(SQLModel, table=True):
    """Daily aggregate stats per app (rating counts, totals)."""
    __tablename__ = "daily_snapshots"
    __table_args__ = (
        UniqueConstraint("app_id", "date", name="uq_snapshot_app_date"),
        Index("ix_snapshot_date", "date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    app_id: int = Field(foreign_key="apps.id", index=True)
    date: date

    # Aggregates
    rating_total: Optional[int] = None  # Total number of ratings
    rating_count: Optional[int] = None  # Same as rating_total (for compatibility)
    rating_avg: Optional[float] = None  # Average rating

    # Fetched metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    app: App = Relationship(back_populates="snapshots")


class Evidence(SQLModel, table=True):
    """Evidence bundles: source URLs, cached paths, review samples."""
    __tablename__ = "evidence"
    __table_args__ = (
        Index("ix_evidence_app_id", "app_id"),
        Index("ix_evidence_fetched_at", "fetched_at"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    app_id: int = Field(foreign_key="apps.id")  # Index defined in __table_args__

    # Evidence data (JSON)
    source_urls: str = Field(sa_column=Column(JSON))  # List[str]
    cached_paths: Optional[str] = Field(default=None, sa_column=Column(JSON))  # List[str]
    review_samples: Optional[str] = Field(default=None, sa_column=Column(JSON))  # List[dict]
    lang_detect: Optional[str] = Field(default=None, sa_column=Column(JSON))  # {detected: str, confidence: float}

    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    app: App = Relationship(back_populates="evidences")
