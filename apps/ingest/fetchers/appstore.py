"""
Apple App Store fetcher using iTunes Search API and RSS feeds.
Official endpoints, no scraping required.
"""
import logging
from datetime import datetime
from typing import Iterator, List, Optional
from xml.etree import ElementTree as ET

from apps.core.config import get_settings
from apps.ingest.cache import get_cache
from apps.ingest.types import AppDetails, Review, StoreAppSummary

logger = logging.getLogger(__name__)


def search_apps(
    term: str,
    lang: str = "es",
    country: str = "ES",
    limit: int = 50,
    media: str = "software",
) -> List[StoreAppSummary]:
    """
    Search Apple App Store using iTunes Search API.

    Args:
        term: Search query
        lang: Language code (e.g., "es", "ja")
        country: Country code (e.g., "ES", "MX", "JP")
        limit: Max results (1-200)
        media: Media type, default "software" for apps

    Returns:
        List of app summaries
    """
    settings = get_settings()
    cache = get_cache()

    params = {
        "term": term,
        "country": country,
        "lang": lang,
        "media": media,
        "limit": min(limit, 200),
        "entity": "software",
    }

    status, data, from_cache = cache.get(settings.apple_search_url, params=params)

    if status != 200:
        logger.error(f"Search failed: {status}")
        return []

    if not isinstance(data, dict) or "results" not in data:
        logger.error(f"Unexpected response format: {data}")
        return []

    results = []
    for item in data.get("results", []):
        try:
            summary = StoreAppSummary(
                store_app_id=str(item["trackId"]),
                bundle_or_package_id=item.get("bundleId"),
                title=item.get("trackName", ""),
                developer=item.get("artistName", ""),
                category=item.get("primaryGenreName"),
                price=item.get("price"),
                currency=item.get("currency"),
                rating_avg=item.get("averageUserRating"),
                rating_count=item.get("userRatingCount"),
                icon_url=item.get("artworkUrl100") or item.get("artworkUrl60"),
                locale=f"{lang}-{country}",
            )
            results.append(summary)
        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to parse search result: {e}")
            continue

    logger.info(f"Search '{term}' [{country}/{lang}]: {len(results)} apps (cache={from_cache})")
    return results


def fetch_details(
    app_id: str,
    country: str = "US",
    lang: str = "en",
) -> Optional[AppDetails]:
    """
    Fetch detailed app metadata using iTunes Lookup API.

    Args:
        app_id: Apple App ID (trackId)
        country: Country code
        lang: Language code

    Returns:
        AppDetails or None if not found
    """
    settings = get_settings()
    cache = get_cache()

    params = {
        "id": app_id,
        "country": country,
        "lang": lang,
    }

    status, data, from_cache = cache.get(settings.apple_lookup_url, params=params)

    if status != 200:
        logger.error(f"Lookup failed for {app_id}: {status}")
        return None

    if not isinstance(data, dict) or "results" not in data or not data["results"]:
        logger.warning(f"No results for app {app_id}")
        return None

    item = data["results"][0]

    try:
        details = AppDetails(
            store_app_id=str(item["trackId"]),
            bundle_or_package_id=item.get("bundleId"),
            title=item.get("trackName", ""),
            description=item.get("description", ""),
            developer=item.get("artistName", ""),
            category=item.get("primaryGenreName"),
            price=item.get("price"),
            currency=item.get("currency"),
            rating_avg=item.get("averageUserRating"),
            rating_count=item.get("userRatingCount"),
            icon_url=item.get("artworkUrl100") or item.get("artworkUrl60"),
            countries=[country],
            locale=f"{lang}-{country}",
            version=item.get("version"),
            release_date=_parse_date(item.get("currentVersionReleaseDate")),
        )
        logger.info(f"Fetched details for {app_id} (cache={from_cache})")
        return details

    except (KeyError, ValueError) as e:
        logger.error(f"Failed to parse details for {app_id}: {e}")
        return None


def fetch_reviews(
    app_id: str,
    country: str = "US",
    page: int = 1,
    page_limit: int = 3,
    sort: str = "mostRecent",
) -> Iterator[Review]:
    """
    Fetch reviews using Apple RSS feed.

    Args:
        app_id: Apple App ID
        country: Country code
        page: Page number (1-10)
        page_limit: Max pages to fetch
        sort: Sort order ("mostRecent" or "mostHelpful")

    Yields:
        Review objects
    """
    settings = get_settings()
    cache = get_cache()

    pages_fetched = 0
    for page_num in range(page, page + page_limit):
        if page_num > 10:  # Apple limit
            break

        # RSS URL format
        url = f"{settings.apple_reviews_url}/page={page_num}/id={app_id}/sortby={sort}/xml"

        try:
            status, data, from_cache = cache.get(url)

            if status != 200:
                logger.warning(f"Reviews fetch failed for {app_id} page {page_num}: {status}")
                break

            # Parse RSS XML
            root = ET.fromstring(data if isinstance(data, str) else str(data))

            # Apple RSS uses atom namespace
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)

            if not entries:
                logger.debug(f"No more reviews on page {page_num}")
                break

            pages_fetched += 1

            for entry in entries:
                try:
                    review = _parse_review_entry(entry, ns, country)
                    if review:
                        yield review
                except Exception as e:
                    logger.warning(f"Failed to parse review entry: {e}")
                    continue

        except ET.ParseError as e:
            logger.error(f"XML parse error for {app_id} page {page_num}: {e}")
            break
        except Exception as e:
            logger.error(f"Unexpected error fetching reviews: {e}")
            break

    logger.info(f"Fetched reviews for {app_id}: {pages_fetched} pages")


def _parse_review_entry(entry: ET.Element, ns: dict, country: str) -> Optional[Review]:
    """Parse a single review entry from Apple RSS."""
    try:
        # Review ID from entry id
        review_id_elem = entry.find("atom:id", ns)
        review_id = review_id_elem.text if review_id_elem is not None else ""

        # Rating from im:rating
        rating_elem = entry.find("{http://itunes.apple.com/rss}rating", ns)
        rating = int(rating_elem.text) if rating_elem is not None else 0

        # Title and body
        title_elem = entry.find("atom:title", ns)
        title = title_elem.text if title_elem is not None else None

        content_elem = entry.find("atom:content", ns)
        body = content_elem.text if content_elem is not None else None

        # Author
        author_elem = entry.find("atom:author/atom:name", ns)
        author = author_elem.text if author_elem is not None else None

        # Date
        updated_elem = entry.find("atom:updated", ns)
        created_at = _parse_date(updated_elem.text) if updated_elem is not None else datetime.utcnow()

        # Version
        version_elem = entry.find("{http://itunes.apple.com/rss}version", ns)
        version = version_elem.text if version_elem is not None else None

        return Review(
            store_review_id=review_id,
            rating=rating,
            title=title,
            body=body,
            author_name=author,
            locale=f"en-{country}",  # Apple RSS doesn't include locale
            created_at=created_at,
            version=version,
        )

    except (ValueError, AttributeError) as e:
        logger.warning(f"Failed to parse review entry: {e}")
        return None


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 date string."""
    if not date_str:
        return None
    try:
        # Handle formats like "2024-10-24T12:00:00Z" or "2024-10-24T12:00:00-07:00"
        if date_str.endswith("Z"):
            return datetime.fromisoformat(date_str[:-1])
        return datetime.fromisoformat(date_str.replace("+00:00", "").replace("Z", ""))
    except (ValueError, AttributeError):
        return None
