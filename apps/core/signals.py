"""
Signals computation for traction metrics.
Computes review windows, rating velocity, and text density.
Stores computed signals as JSON in evidence table.
"""
import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlmodel import Session, select

from apps.core.models import App, AppLocale, DailySnapshot, Evidence, Review

logger = logging.getLogger(__name__)


def compute_review_windows(
    session: Session,
    app_id: int,
    as_of_date: date,
) -> dict:
    """
    Compute review counts for 7-day and 30-day windows.

    Returns:
        {
            "review_7d": int | None,
            "review_30d": int | None,
            "window_used": "7d/30d" | None
        }
    """
    date_7d_ago = as_of_date - timedelta(days=7)
    date_30d_ago = as_of_date - timedelta(days=30)

    # Convert date to datetime for comparison
    date_7d_dt = datetime.combine(date_7d_ago, datetime.min.time())
    date_30d_dt = datetime.combine(date_30d_ago, datetime.min.time())

    # Count reviews in 7-day window
    review_7d = session.exec(
        select(func.count(Review.id))
        .where(Review.app_id == app_id)
        .where(Review.created_at >= date_7d_dt)
    ).one()

    # Count reviews in 30-day window
    review_30d = session.exec(
        select(func.count(Review.id))
        .where(Review.app_id == app_id)
        .where(Review.created_at >= date_30d_dt)
    ).one()

    return {
        "review_7d": review_7d if review_7d > 0 else None,
        "review_30d": review_30d if review_30d > 0 else None,
        "window_used": "7d/30d" if review_7d or review_30d else None,
    }


def compute_rating_velocity(
    session: Session,
    app_id: int,
    as_of_date: date,
) -> Optional[int]:
    """
    Compute rating velocity (day-over-day change in rating count).

    Returns:
        Delta between today and yesterday's rating_total, or None if data missing.
    """
    yesterday = as_of_date - timedelta(days=1)

    # Get today's snapshot
    snapshot_today = session.exec(
        select(DailySnapshot)
        .where(DailySnapshot.app_id == app_id)
        .where(DailySnapshot.date == as_of_date)
    ).first()

    # Get yesterday's snapshot
    snapshot_yesterday = session.exec(
        select(DailySnapshot)
        .where(DailySnapshot.app_id == app_id)
        .where(DailySnapshot.date == yesterday)
    ).first()

    if not snapshot_today or not snapshot_yesterday:
        return None

    if snapshot_today.rating_total is None or snapshot_yesterday.rating_total is None:
        return None

    return snapshot_today.rating_total - snapshot_yesterday.rating_total


def compute_text_density(
    session: Session,
    app_id: int,
) -> Optional[int]:
    """
    Compute text density (character count of description).

    Uses the longest non-English description, or English if no others.

    Returns:
        Character count or None if no descriptions available.
    """
    locales = session.exec(
        select(AppLocale)
        .where(AppLocale.app_id == app_id)
        .where(AppLocale.desc_raw.isnot(None))
    ).all()

    if not locales:
        return None

    # Prefer non-English locales, but fall back to English
    non_en_locales = [l for l in locales if not l.locale.startswith("en")]
    chosen_locales = non_en_locales if non_en_locales else locales

    # Return length of longest description
    max_length = max(len(l.desc_raw or "") for l in chosen_locales)
    return max_length if max_length > 0 else None


def compute_signals_for_app(
    session: Session,
    app_id: int,
    as_of_date: Optional[date] = None,
    recompute_text_density: bool = True,
) -> dict:
    """
    Compute all signals for a single app.

    Returns:
        {
            "review_7d": int | None,
            "review_30d": int | None,
            "rating_velocity_d1": int | None,
            "text_density": int | None,
            "window_used": str | None,
        }
    """
    if as_of_date is None:
        as_of_date = datetime.utcnow().date()

    # Compute review windows
    windows = compute_review_windows(session, app_id, as_of_date)

    # Compute rating velocity
    velocity = compute_rating_velocity(session, app_id, as_of_date)

    # Compute text density
    density = compute_text_density(session, app_id) if recompute_text_density else None

    return {
        "review_7d": windows["review_7d"],
        "review_30d": windows["review_30d"],
        "rating_velocity_d1": velocity,
        "text_density": density,
        "window_used": windows["window_used"],
        "computed_at": datetime.utcnow().isoformat(),
    }


def compute_signals_batch(
    session: Session,
    since: Optional[date] = None,
    recompute_text_density: bool = True,
    dry_run: bool = False,
) -> dict:
    """
    Compute signals for all apps (or apps seen since a date).

    Returns:
        {
            "apps_processed": int,
            "signals_computed": int,
            "dry_run": bool,
        }
    """
    # Build query for apps
    query = select(App)
    if since:
        since_dt = datetime.combine(since, datetime.min.time())
        query = query.where(App.first_seen_at >= since_dt)

    apps = session.exec(query).all()
    today = datetime.utcnow().date()

    apps_processed = 0
    signals_computed = 0

    for app in apps:
        try:
            signals = compute_signals_for_app(
                session,
                app.id,
                as_of_date=today,
                recompute_text_density=recompute_text_density,
            )

            if not dry_run:
                # Store signals in evidence (reuse lang_detect field)
                latest_evidence = session.exec(
                    select(Evidence)
                    .where(Evidence.app_id == app.id)
                    .order_by(Evidence.fetched_at.desc())
                ).first()

                if latest_evidence:
                    # Update existing evidence with signals
                    latest_evidence.lang_detect = json.dumps({"signals": signals})
                else:
                    # Create new evidence entry with just signals
                    evidence = Evidence(
                        app_id=app.id,
                        source_urls=json.dumps([]),
                        lang_detect=json.dumps({"signals": signals}),
                    )
                    session.add(evidence)

                logger.info(
                    f"Signals for app {app.id} ({app.store_app_id}): {signals}"
                )
                signals_computed += 1

            apps_processed += 1

        except Exception as e:
            logger.error(f"Failed to compute signals for app {app.id}: {e}")
            continue

    if not dry_run:
        session.commit()

    return {
        "apps_processed": apps_processed,
        "signals_computed": signals_computed,
        "dry_run": dry_run,
    }
