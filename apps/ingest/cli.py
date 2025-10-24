"""
CLI for ingest operations: discover and enrich.
Uses Typer for command-line interface.
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from sqlmodel import select

from apps.core.config import get_settings
from apps.core.db import get_session, init_db
from apps.core.models import App, AppLocale, DailySnapshot, Evidence, Review, Store
from apps.ingest.fetchers import (
    apple_fetch_details,
    apple_fetch_reviews,
    apple_search_apps,
)
from apps.ingest.types import ReviewSample

app = typer.Typer(help="AppDiscovery ingest commands")
console = Console()


def setup_logging(level: str = "INFO"):
    """Configure logging with rich handler."""
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True, console=console)],
    )


@app.command()
def discover(
    store: str = typer.Option("apple", help="Store to search (apple only for now)"),
    lang: str = typer.Option("es", help="Language code (e.g., es, ja, pt)"),
    country: str = typer.Option("ES", help="Country code (e.g., ES, MX, JP)"),
    q: str = typer.Option(..., help="Search query"),
    limit: int = typer.Option(50, help="Max results per query"),
    log_level: str = typer.Option("INFO", help="Log level"),
):
    """
    Discover apps by searching store and persist to database.

    Example:
        python -m apps.ingest.cli discover --store apple --lang es --country ES --q "gastos" --limit 50
    """
    setup_logging(log_level)
    logger = logging.getLogger(__name__)

    if store != "apple":
        console.print(f"[red]Error: Only 'apple' store is supported in this version[/red]")
        raise typer.Exit(1)

    # Initialize DB
    init_db()

    # Search
    console.print(f"[cyan]Searching {store} for '{q}' ({lang}-{country})...[/cyan]")
    results = apple_search_apps(term=q, lang=lang, country=country, limit=limit)

    if not results:
        console.print("[yellow]No results found[/yellow]")
        return

    console.print(f"[green]Found {len(results)} apps[/green]")

    # Persist to DB
    with get_session() as session:
        # Ensure store exists
        store_record = session.exec(select(Store).where(Store.name == store)).first()
        if not store_record:
            store_record = Store(name=store, display_name="Apple App Store")
            session.add(store_record)
            session.flush()

        new_apps = 0
        updated_apps = 0

        for summary in results:
            # Upsert app
            app_record = session.exec(
                select(App)
                .where(App.store_id == store_record.id)
                .where(App.store_app_id == summary.store_app_id)
            ).first()

            if not app_record:
                app_record = App(
                    store_id=store_record.id,
                    store_app_id=summary.store_app_id,
                    bundle_or_package_id=summary.bundle_or_package_id,
                    developer=summary.developer,
                    category=summary.category,
                )
                session.add(app_record)
                new_apps += 1
            else:
                app_record.last_seen_at = datetime.utcnow()
                app_record.category = summary.category or app_record.category
                updated_apps += 1

            session.flush()

            # Upsert app locale
            locale_record = session.exec(
                select(AppLocale)
                .where(AppLocale.app_id == app_record.id)
                .where(AppLocale.locale == summary.locale)
            ).first()

            if not locale_record:
                locale_record = AppLocale(
                    app_id=app_record.id,
                    locale=summary.locale,
                    title_raw=summary.title,
                    desc_raw="",  # Will be filled by enrich
                    price=summary.price,
                    currency=summary.currency,
                )
                session.add(locale_record)
            else:
                locale_record.title_raw = summary.title
                locale_record.price = summary.price
                locale_record.currency = summary.currency
                locale_record.updated_at = datetime.utcnow()

            # Create/update daily snapshot if rating data available
            if summary.rating_count is not None:
                today = datetime.utcnow().date()
                snapshot = session.exec(
                    select(DailySnapshot)
                    .where(DailySnapshot.app_id == app_record.id)
                    .where(DailySnapshot.date == today)
                ).first()

                if not snapshot:
                    snapshot = DailySnapshot(
                        app_id=app_record.id,
                        date=today,
                        rating_total=summary.rating_count,
                        rating_count=summary.rating_count,
                        rating_avg=summary.rating_avg,
                    )
                    session.add(snapshot)
                else:
                    snapshot.rating_total = summary.rating_count
                    snapshot.rating_count = summary.rating_count
                    snapshot.rating_avg = summary.rating_avg
                    snapshot.fetched_at = datetime.utcnow()

        session.commit()

    console.print(f"[green]✓ Persisted: {new_apps} new apps, {updated_apps} updated[/green]")


@app.command()
def enrich(
    app_ids: Optional[List[int]] = typer.Option(None, help="Specific app IDs to enrich"),
    since: Optional[str] = typer.Option(None, help="Enrich apps seen since this date (YYYY-MM-DD)"),
    store: str = typer.Option("apple", help="Store filter"),
    country: str = typer.Option("US", help="Country for details/reviews"),
    lang: str = typer.Option("en", help="Language for details/reviews"),
    translate: bool = typer.Option(False, help="Run translation (not implemented yet)"),
    compute_signals: bool = typer.Option(False, help="Compute signals (not implemented yet)"),
    log_level: str = typer.Option("INFO", help="Log level"),
):
    """
    Enrich apps with details, reviews, and evidence bundles.

    Example:
        python -m apps.ingest.cli enrich --since 2025-10-24 --country ES --lang es
        python -m apps.ingest.cli enrich --app-ids 123456789 --app-ids 987654321
    """
    setup_logging(log_level)
    logger = logging.getLogger(__name__)

    if store != "apple":
        console.print(f"[red]Error: Only 'apple' store is supported[/red]")
        raise typer.Exit(1)

    init_db()

    # Build query
    with get_session() as session:
        query = select(App).join(Store).where(Store.name == store)

        if app_ids:
            query = query.where(App.id.in_(app_ids))
        elif since:
            since_date = datetime.fromisoformat(since)
            query = query.where(App.first_seen_at >= since_date)
        else:
            # Default: last 7 days
            since_date = datetime.utcnow() - timedelta(days=7)
            query = query.where(App.first_seen_at >= since_date)

        apps_to_enrich = session.exec(query).all()

    if not apps_to_enrich:
        console.print("[yellow]No apps to enrich[/yellow]")
        return

    console.print(f"[cyan]Enriching {len(apps_to_enrich)} apps...[/cyan]")

    settings = get_settings()
    enriched_count = 0

    for app_record in apps_to_enrich:
        console.print(f"[dim]Processing app {app_record.store_app_id}...[/dim]")

        # Fetch details
        details = apple_fetch_details(app_record.store_app_id, country=country, lang=lang)

        if not details:
            logger.warning(f"Failed to fetch details for {app_record.store_app_id}")
            continue

        # Update app locale with full description
        with get_session() as session:
            # Re-fetch app in this session
            app = session.get(App, app_record.id)

            locale_key = f"{lang}-{country}"
            locale_record = session.exec(
                select(AppLocale)
                .where(AppLocale.app_id == app.id)
                .where(AppLocale.locale == locale_key)
            ).first()

            if not locale_record:
                locale_record = AppLocale(
                    app_id=app.id,
                    locale=locale_key,
                    title_raw=details.title,
                    desc_raw=details.description,
                    price=details.price,
                    currency=details.currency,
                    countries=json.dumps(details.countries) if details.countries else None,
                )
                session.add(locale_record)
            else:
                locale_record.desc_raw = details.description
                locale_record.title_raw = details.title
                locale_record.updated_at = datetime.utcnow()

            session.commit()

        # Fetch reviews
        review_samples = []
        review_count = 0

        with get_session() as session:
            app = session.get(App, app_record.id)

            for review in apple_fetch_reviews(app_record.store_app_id, country=country, page_limit=3):
                # Upsert review
                existing = session.exec(
                    select(Review)
                    .where(Review.app_id == app.id)
                    .where(Review.store_review_id == review.store_review_id)
                ).first()

                if not existing:
                    review_record = Review(
                        app_id=app.id,
                        store_review_id=review.store_review_id,
                        locale=review.locale,
                        rating=review.rating,
                        title_raw=review.title,
                        body_raw=review.body,
                        author_name=review.author_name,
                        created_at=review.created_at,
                    )
                    session.add(review_record)
                    review_count += 1

                    # Add to samples (max 10)
                    if len(review_samples) < 10 and review.body:
                        review_samples.append(
                            ReviewSample(
                                rating=review.rating,
                                created_at=review.created_at,
                                body_raw=review.body,
                                locale=review.locale,
                            )
                        )

            session.commit()

        # Create evidence bundle
        source_urls = [
            f"{settings.apple_lookup_url}?id={app_record.store_app_id}",
            f"{settings.apple_reviews_url}/id={app_record.store_app_id}",
        ]

        with get_session() as session:
            app = session.get(App, app_record.id)

            evidence = Evidence(
                app_id=app.id,
                source_urls=json.dumps(source_urls),
                cached_paths=json.dumps([]),  # Paths tracked by cache internally
                review_samples=json.dumps([s.model_dump(mode="json") for s in review_samples]),
                lang_detect=None,  # TODO: implement in translate agent
            )
            session.add(evidence)
            session.commit()

            # Also write to file
            evidence_file = settings.evidence_dir / f"{app.id}.json"
            with open(evidence_file, "w") as f:
                json.dump(
                    {
                        "app_id": app.id,
                        "store_app_id": app.store_app_id,
                        "source_urls": source_urls,
                        "review_samples": [s.model_dump(mode="json") for s in review_samples],
                        "fetched_at": datetime.utcnow().isoformat(),
                    },
                    f,
                    indent=2,
                )

        enriched_count += 1
        console.print(f"[green]✓ Enriched app {app_record.store_app_id} ({review_count} reviews)[/green]")

    console.print(f"[green]✓ Enriched {enriched_count} apps total[/green]")

    if translate:
        console.print("[yellow]Translation skipped (not implemented)[/yellow]")

    if compute_signals:
        console.print("[cyan]Computing signals...[/cyan]")
        from apps.core.signals import compute_signals_batch
        with get_session() as session:
            result = compute_signals_batch(session, since=since_date if since else None)
            console.print(f"[green]✓ Computed signals for {result['signals_computed']} apps[/green]")


@app.command()
def init():
    """Initialize the database schema."""
    setup_logging("INFO")
    console.print("[cyan]Initializing database...[/cyan]")
    init_db()
    console.print("[green]✓ Database initialized[/green]")


if __name__ == "__main__":
    app()
