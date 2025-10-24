"""
FastAPI application for AppDiscovery REST API.
"""
import json
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import select

from apps.core.db import get_session
from apps.core.models import App, AppLocale, Evidence, Review, Store
from apps.core.signals import compute_signals_for_app
from apps.core.ai_analysis import analyze_app

app = FastAPI(
    title="AppDiscovery API",
    description="App store intelligence platform API",
    version="0.1.0",
)

# Enable CORS for web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    """Root endpoint with API info."""
    return {
        "name": "AppDiscovery API",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "apps": "/apps",
            "app_detail": "/apps/{app_id}",
            "reviews": "/apps/{app_id}/reviews",
            "signals": "/apps/{app_id}/signals",
            "stores": "/stores",
        },
    }


@app.get("/stores")
def list_stores():
    """List all app stores."""
    with get_session() as session:
        stores = session.exec(select(Store)).all()
        return [
            {
                "id": store.id,
                "name": store.name,
                "display_name": store.display_name,
                "enabled": store.enabled,
            }
            for store in stores
        ]


@app.get("/apps")
def list_apps(
    store: Optional[str] = Query(None, description="Filter by store name (apple, google_play)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, le=500, description="Max results"),
    offset: int = Query(0, description="Pagination offset"),
):
    """List apps with filters and pagination."""
    with get_session() as session:
        query = select(App).join(Store)

        # Apply filters
        if store:
            query = query.where(Store.name == store)
        if category:
            query = query.where(App.category == category)

        # Pagination
        query = query.offset(offset).limit(limit)

        apps = session.exec(query).all()

        # Get primary locale for each app
        results = []
        for app in apps:
            primary_locale = session.exec(
                select(AppLocale)
                .where(AppLocale.app_id == app.id)
                .limit(1)
            ).first()

            # Get signals
            evidence = session.exec(
                select(Evidence)
                .where(Evidence.app_id == app.id)
                .order_by(Evidence.fetched_at.desc())
            ).first()

            signals = None
            if evidence and evidence.lang_detect:
                try:
                    lang_detect_data = json.loads(evidence.lang_detect)
                    signals = lang_detect_data.get("signals")
                except json.JSONDecodeError:
                    pass

            # Get review count
            review_count = len(session.exec(
                select(Review).where(Review.app_id == app.id)
            ).all())

            results.append({
                "id": app.id,
                "store_app_id": app.store_app_id,
                "bundle_id": app.bundle_or_package_id,
                "developer": app.developer,
                "category": app.category,
                "title": primary_locale.title_raw if primary_locale else None,
                "icon_url": app.icon_url,
                "locale": primary_locale.locale if primary_locale else None,
                "first_seen_at": app.first_seen_at.isoformat(),
                "last_seen_at": app.last_seen_at.isoformat(),
                "review_count": review_count,
                "signals": signals,
            })

        return {
            "total": len(results),
            "limit": limit,
            "offset": offset,
            "apps": results,
        }


@app.get("/apps/{app_id}")
def get_app_detail(app_id: int):
    """Get detailed app information including all locales."""
    with get_session() as session:
        app = session.get(App, app_id)
        if not app:
            raise HTTPException(status_code=404, detail="App not found")

        # Get store info
        store = session.get(Store, app.store_id)

        # Get all locales
        locales = session.exec(
            select(AppLocale).where(AppLocale.app_id == app_id)
        ).all()

        # Get review count
        review_count = session.exec(
            select(Review).where(Review.app_id == app_id)
        ).all()

        # Get evidence with signals
        evidence = session.exec(
            select(Evidence)
            .where(Evidence.app_id == app_id)
            .order_by(Evidence.fetched_at.desc())
        ).first()

        signals = None
        if evidence and evidence.lang_detect:
            try:
                lang_detect_data = json.loads(evidence.lang_detect)
                signals = lang_detect_data.get("signals")
            except json.JSONDecodeError:
                pass

        return {
            "id": app.id,
            "store": {
                "id": store.id,
                "name": store.name,
                "display_name": store.display_name,
            },
            "store_app_id": app.store_app_id,
            "bundle_id": app.bundle_or_package_id,
            "developer": app.developer,
            "category": app.category,
            "first_seen_at": app.first_seen_at.isoformat(),
            "last_seen_at": app.last_seen_at.isoformat(),
            "locales": [
                {
                    "locale": loc.locale,
                    "title": loc.title_raw,
                    "description": loc.desc_raw,
                    "price": loc.price,
                    "currency": loc.currency,
                }
                for loc in locales
            ],
            "review_count": len(review_count),
            "signals": signals,
        }


@app.get("/apps/{app_id}/reviews")
def get_app_reviews(
    app_id: int,
    limit: int = Query(50, le=500),
    offset: int = Query(0),
):
    """Get reviews for an app."""
    with get_session() as session:
        app = session.get(App, app_id)
        if not app:
            raise HTTPException(status_code=404, detail="App not found")

        query = (
            select(Review)
            .where(Review.app_id == app_id)
            .order_by(Review.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        reviews = session.exec(query).all()

        return {
            "app_id": app_id,
            "total": len(reviews),
            "limit": limit,
            "offset": offset,
            "reviews": [
                {
                    "id": review.id,
                    "rating": review.rating,
                    "title": review.title_raw,
                    "body": review.body_raw,
                    "author": review.author_name,
                    "locale": review.locale,
                    "created_at": review.created_at.isoformat(),
                }
                for review in reviews
            ],
        }


@app.get("/apps/{app_id}/signals")
def get_app_signals(app_id: int, recompute: bool = Query(False)):
    """Get or compute signals for an app."""
    with get_session() as session:
        app = session.get(App, app_id)
        if not app:
            raise HTTPException(status_code=404, detail="App not found")

        if recompute:
            # Compute fresh signals
            signals = compute_signals_for_app(session, app_id)
            return {
                "app_id": app_id,
                "signals": signals,
                "computed": "fresh",
            }
        else:
            # Get cached signals from evidence
            evidence = session.exec(
                select(Evidence)
                .where(Evidence.app_id == app_id)
                .order_by(Evidence.fetched_at.desc())
            ).first()

            signals = None
            if evidence and evidence.lang_detect:
                try:
                    lang_detect_data = json.loads(evidence.lang_detect)
                    signals = lang_detect_data.get("signals")
                except json.JSONDecodeError:
                    pass

            if not signals:
                # Compute if not cached
                signals = compute_signals_for_app(session, app_id)
                return {
                    "app_id": app_id,
                    "signals": signals,
                    "computed": "on_demand",
                }

            return {
                "app_id": app_id,
                "signals": signals,
                "computed": "cached",
            }


@app.get("/apps/{app_id}/ai-insights")
def get_ai_insights(app_id: int):
    """Get AI-powered insights for an app using Gemini and Perplexity."""
    try:
        insights = analyze_app(app_id)
        return {
            "app_id": app_id,
            "insights": insights,
            "success": True
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")


@app.get("/stats")
def get_stats():
    """Get overall stats for the platform."""
    with get_session() as session:
        app_count = len(session.exec(select(App)).all())
        review_count = len(session.exec(select(Review)).all())
        evidence_count = len(session.exec(select(Evidence)).all())

        stores = session.exec(select(Store)).all()
        store_counts = {}
        for store in stores:
            count = len(
                session.exec(
                    select(App).where(App.store_id == store.id)
                ).all()
            )
            store_counts[store.name] = count

        return {
            "total_apps": app_count,
            "total_reviews": review_count,
            "total_evidence": evidence_count,
            "apps_by_store": store_counts,
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
