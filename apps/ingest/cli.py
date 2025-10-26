"""
CLI for ingest operations: discover and enrich.
Uses Typer for command-line interface.
"""
import json
import logging
import random
import time
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
console = Console(legacy_windows=False, force_terminal=True)


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
    terms: str = typer.Option(
        "presupuesto,gastos,finanzas personales,hábitos,rutina,tareas,dieta,recetas,estudiar,exámenes,facturas,escáner,firma PDF,traductor,recortador de fotos;"
        "orçamento,despesas,finanças pessoais,hábitos,rotina,tarefas,dieta,receitas,estudar,provas,recibos,scanner,assinar PDF,tradutor,remover fundo;"
        "家計簿,予算,習慣,ルーティン,タスク,食事管理,レシピ,勉強,試験対策,領収書,スキャナー,PDF 署名,翻訳,背景削除;"
        "가계부,예산,습관,루틴,할일,식단,레시피,공부,시험,영수증,스캐너,PDF 서명,번역,배경 제거",
        help="Semicolon-separated groups of comma-separated search terms (one group per language). "
             "Covers high-yield categories: finance, habits, routines, tasks, diet, recipes, studying, "
             "exams, receipts, scanning, PDF tools, translation, photo editing."
    ),
    countries: str = typer.Option(
        "ES,MX,AR,CO;BR,PT;JP;KR",
        help="Semicolon-separated groups of comma-separated country codes (aligned with languages)"
    ),
    languages: str = typer.Option(
        "es;pt;ja;ko",
        help="Semicolon-separated language codes (aligned with country groups)"
    ),
    per_term_limit: int = typer.Option(50, help="Max results per search term"),
    max_total: int = typer.Option(600, help="Maximum total apps to discover (stops early if reached)"),
    log_level: str = typer.Option("INFO", help="Log level"),
):
    """
    Discover copyable single-player utility apps across multiple non-English markets.

    Searches for apps matching discovery rules:
    - Single-player utility (no network effects, no real-time social)
    - Low surface area (≤6 core features)
    - Subscription-friendly or clear pricing
    - Evidence of traction (recent reviews/updates)
    - Low integration burden (no bank logins, KYC)
    - Non-English target first
    - Buildable in weeks

    High-yield categories: life/home organization, health (non-diagnostic), learning/exams,
    freelancer tools, personal admin, media micro-editing, PDF/file utilities, travel (lightweight),
    pets/family, religion, hobbies.

    Explicitly excludes: games, dating, social networks, banking, medical diagnosis, logistics,
    marketplaces, UGC platforms.

    Example:
        python -m apps.ingest.cli discover --store apple --max_total 400
        python -m apps.ingest.cli discover --store apple --terms "budget;orçamento" --countries "US;BR" --languages "en;pt"
    """
    setup_logging(log_level)
    logger = logging.getLogger(__name__)

    if store != "apple":
        console.print(f"[red]Error: Only 'apple' store is supported in this version[/red]")
        raise typer.Exit(1)

    # Initialize DB
    init_db()

    # Parse semicolon-separated groups
    term_groups = [group.split(',') for group in terms.split(';')]
    country_groups = [group.split(',') for group in countries.split(';')]
    language_list = languages.split(';')

    if len(term_groups) != len(country_groups) or len(term_groups) != len(language_list):
        console.print(f"[red]Error: terms, countries, and languages must have same number of groups[/red]")
        console.print(f"[dim]Got {len(term_groups)} term groups, {len(country_groups)} country groups, {len(language_list)} languages[/dim]")
        raise typer.Exit(1)

    console.print(f"[cyan]Multi-market discovery: {len(term_groups)} language groups, up to {max_total} apps total[/cyan]")

    # Track seen apps to avoid duplicates within this run
    seen_app_ids = set()
    total_apps = 0
    new_apps = 0
    updated_apps = 0
    skipped_duplicates = 0

    # Get or create store record once
    with get_session() as session:
        store_record = session.exec(select(Store).where(Store.name == store)).first()
        if not store_record:
            store_record = Store(name=store, display_name="Apple App Store")
            session.add(store_record)
            session.commit()
        store_id = store_record.id

    # Triple-nested loop: language → country → term
    for lang_idx, (lang, term_group, country_group) in enumerate(zip(language_list, term_groups, country_groups)):
        console.print(f"[cyan]Language group {lang_idx+1}/{len(language_list)}: {lang} ({len(country_group)} countries, {len(term_group)} terms)[/cyan]")

        for country in country_group:
            country = country.strip()

            for term in term_group:
                term = term.strip()

                if total_apps >= max_total:
                    console.print(f"[yellow]Reached max_total ({max_total}), stopping early[/yellow]")
                    break

                console.print(f"[dim]Searching: '{term}' ({lang}-{country})...[/dim]")

                # Search
                try:
                    results = apple_search_apps(term=term, lang=lang, country=country, limit=per_term_limit)
                except Exception as e:
                    logger.warning(f"Search failed for '{term}' ({lang}-{country}): {e}")
                    continue

                if not results:
                    continue

                # Persist with deduplication
                with get_session() as session:
                    for summary in results:
                        # Check if we've seen this app in this run
                        app_key = f"{store_id}:{summary.store_app_id}"
                        if app_key in seen_app_ids:
                            skipped_duplicates += 1
                            continue

                        seen_app_ids.add(app_key)

                        # Check DB for existing app
                        app_record = session.exec(
                            select(App)
                            .where(App.store_id == store_id)
                            .where(App.store_app_id == summary.store_app_id)
                        ).first()

                        if not app_record:
                            # New app: set first_seen_at
                            app_record = App(
                                store_id=store_id,
                                store_app_id=summary.store_app_id,
                                bundle_or_package_id=summary.bundle_or_package_id,
                                developer=summary.developer,
                                category=summary.category,
                                icon_url=summary.icon_url,
                                first_seen_at=datetime.utcnow(),
                                last_seen_at=datetime.utcnow(),
                            )
                            session.add(app_record)
                            new_apps += 1
                            total_apps += 1
                        else:
                            # Existing app: only update last_seen_at and fill in missing fields
                            app_record.last_seen_at = datetime.utcnow()
                            app_record.category = summary.category or app_record.category
                            if not app_record.icon_url:
                                app_record.icon_url = summary.icon_url
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

                        if total_apps >= max_total:
                            break

                    session.commit()

                # Polite rate limiting: 150-250ms between requests
                time.sleep(random.uniform(0.15, 0.25))

                if total_apps >= max_total:
                    break

            if total_apps >= max_total:
                break

    console.print(f"[green]OK Discovery complete: {new_apps} new apps, {updated_apps} updated, {skipped_duplicates} duplicates skipped[/green]")
    console.print(f"[green]Total unique apps discovered: {total_apps}[/green]")


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
        # Extract the data we need while session is active
        app_data = [(app.id, app.store_app_id) for app in apps_to_enrich]

    if not app_data:
        console.print("[yellow]No apps to enrich[/yellow]")
        return

    console.print(f"[cyan]Enriching {len(app_data)} apps...[/cyan]")

    settings = get_settings()
    enriched_count = 0

    for app_id, store_app_id in app_data:
        console.print(f"[dim]Processing app {store_app_id}...[/dim]")

        # Fetch details
        details = apple_fetch_details(store_app_id, country=country, lang=lang)

        if not details:
            logger.warning(f"Failed to fetch details for {store_app_id}")
            continue

        # Update app locale with full description
        with get_session() as session:
            # Re-fetch app in this session
            app = session.get(App, app_id)

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
            app = session.get(App, app_id)

            for review in apple_fetch_reviews(store_app_id, country=country, page_limit=3):
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
            f"{settings.apple_lookup_url}?id={store_app_id}",
            f"{settings.apple_reviews_url}/id={store_app_id}",
        ]

        with get_session() as session:
            app = session.get(App, app_id)

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
        console.print(f"[green]OK Enriched app {store_app_id} ({review_count} reviews)[/green]")

    console.print(f"[green]OK Enriched {enriched_count} apps total[/green]")

    if translate:
        console.print("[yellow]Translation skipped (not implemented)[/yellow]")

    if compute_signals:
        console.print("[cyan]Computing signals...[/cyan]")
        from apps.core.signals import compute_signals_batch
        with get_session() as session:
            result = compute_signals_batch(session, since=since_date if since else None)
            console.print(f"[green]OK Computed signals for {result['signals_computed']} apps[/green]")


@app.command()
def init():
    """Initialize the database schema."""
    setup_logging("INFO")
    console.print("[cyan]Initializing database...[/cyan]")
    init_db()
    console.print("[green]OK Database initialized[/green]")


if __name__ == "__main__":
    app()
