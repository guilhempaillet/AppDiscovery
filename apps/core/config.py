"""
Configuration management for AppDiscovery.
Loads settings from environment variables with .env support.
"""
import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Database
    database_url: str = "sqlite:///./data/appdiscovery.db"

    # Cache
    cache_dir: Path = Path("./data/cache")
    cache_ttl_seconds: int = 86400  # 24 hours

    # Rate limiting
    rate_limit_requests_per_second: float = 2.0
    rate_limit_burst: int = 5

    # Apple App Store
    apple_search_url: str = "https://itunes.apple.com/search"
    apple_lookup_url: str = "https://itunes.apple.com/lookup"
    apple_reviews_url: str = "https://itunes.apple.com/rss/customerreviews"

    # Google Play (gated by compliance_ok flag)
    gp_enabled: bool = False
    gp_base_url: str = "https://play.google.com/store/apps"

    # Evidence
    evidence_dir: Path = Path("./data/cache/evidence")

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # json or text

    # User agent
    user_agent: str = "AppDiscovery/0.1 (Research; +https://github.com/yourusername/appdiscovery)"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
        # Ensure directories exist
        _settings.cache_dir.mkdir(parents=True, exist_ok=True)
        _settings.evidence_dir.mkdir(parents=True, exist_ok=True)
    return _settings
