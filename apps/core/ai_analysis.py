"""
AI-powered analysis using Gemini and Perplexity APIs.
Precision-first: verifies English equivalents, detects monetization, estimates MRR bands.
All research runs on-demand with in-memory caching (24h TTL).
"""
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple

import requests

from apps.core.config import get_settings
from apps.core.db import get_session
from apps.core.models import App, AppLocale, Review
from sqlmodel import select

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

PERPLEXITY_BASE_URL = "https://api.perplexity.ai/chat/completions"

# Models
MODEL_CHEAP = "sonar"
MODEL_RECALL_BOOST = "sonar-pro"
MODEL_DEEP = "sonar-deep-research"

# Timeouts
CHEAP_TIMEOUT_SEC = 30
DEEP_TIMEOUT_SEC = 75

# Budgets
MAX_CHEAP_CALLS_PER_APP = 6
MAX_DEEP_CALLS_PER_APP_PER_DAY = 2

# Cache TTL
EN_EQ_CACHE_TTL_SECONDS = 24 * 3600  # 24 hours

# Domain filters
SEARCH_DOMAIN_FILTER_STORE = ["apps.apple.com", "play.google.com"]
SEARCH_DOMAIN_FILTER_SOCIAL = [
    "x.com", "twitter.com", "reddit.com", "tiktok.com", "news.ycombinator.com"
]

# English markets for verification bias
EN_MARKETS = ["US", "GB", "CA", "AU"]

# Monetization priors by category (install_to_trial, trial_to_paid, monthly_churn)
MONETIZATION_PRIORS = {
    "Finance": (0.07, 0.45, 0.05),
    "Health & Fitness": (0.08, 0.42, 0.06),
    "Education": (0.05, 0.40, 0.06),
    "default": (0.06, 0.40, 0.06),
}

# In-memory caches
_en_cache: Dict[int, Dict[str, Any]] = {}
_monetization_cache: Dict[int, Dict[str, Any]] = {}
_call_budgets: Dict[int, Dict[str, int]] = {}


# ============================================================================
# CACHE UTILITIES
# ============================================================================

def _check_cache(cache_dict: dict, app_id: int, refresh: bool = False) -> Optional[Dict]:
    """Check if cached result exists and is not expired."""
    if refresh:
        return None

    if app_id not in cache_dict:
        return None

    entry = cache_dict[app_id]
    if datetime.fromisoformat(entry["expires"]) < datetime.utcnow():
        del cache_dict[app_id]
        return None

    return entry["result"]


def _set_cache(cache_dict: dict, app_id: int, result: Dict, ttl_seconds: int):
    """Store result in cache with TTL."""
    expires = (datetime.utcnow() + timedelta(seconds=ttl_seconds)).isoformat()
    cache_dict[app_id] = {"result": result, "expires": expires}


def _check_budget(app_id: int, budget_type: str, max_calls: int) -> bool:
    """Check if we have budget remaining for this call type."""
    if app_id not in _call_budgets:
        _call_budgets[app_id] = {"cheap": 0, "deep": 0, "reset_at": datetime.utcnow()}

    budget = _call_budgets[app_id]

    # Reset daily budgets
    if datetime.utcnow() - budget["reset_at"] > timedelta(days=1):
        budget["cheap"] = 0
        budget["deep"] = 0
        budget["reset_at"] = datetime.utcnow()

    if budget.get(budget_type, 0) >= max_calls:
        return False

    budget[budget_type] = budget.get(budget_type, 0) + 1
    return True


# ============================================================================
# PERPLEXITY UTILITIES
# ============================================================================

def _call_perplexity(
    api_key: str,
    model: str,
    prompt: str,
    timeout: int,
    search_domain_filter: Optional[List[str]] = None,
    search_context_size: str = "low",
    reasoning_effort: Optional[str] = None,
    temperature: float = 0.2,
) -> Optional[Dict[str, Any]]:
    """
    Call Perplexity API with strict JSON response format.
    Returns parsed JSON or None on failure.
    """
    try:
        body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a web research assistant that returns only strict JSON. Never include prose, code fences, or explanations."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        # Add search options
        if search_domain_filter:
            body["search_domain_filter"] = search_domain_filter

        body["web_search_options"] = {
            "search_context_size": search_context_size,
            "language_preference": "en",
        }

        if reasoning_effort:
            body["reasoning_effort"] = reasoning_effort

        response = requests.post(
            PERPLEXITY_BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=body,
            timeout=timeout
        )
        response.raise_for_status()

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        # Strip markdown code fences if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        return json.loads(content.strip())

    except json.JSONDecodeError:
        # Retry once with stricter prompt
        logger.warning("JSON parse failed, retrying with stricter prompt")
        try:
            retry_prompt = prompt + "\n\nIMPORTANT: Return ONLY valid JSON with no code fences, prose, or explanations."
            body["messages"][1]["content"] = retry_prompt

            response = requests.post(
                PERPLEXITY_BASE_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=body,
                timeout=timeout
            )
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            return json.loads(content.strip())

        except Exception as retry_e:
            logger.exception(f"Retry also failed: {retry_e}")
            return None

    except Exception as e:
        logger.exception(f"Perplexity API call failed: {e}")
        return None


# ============================================================================
# ENGLISH EQUIVALENT RESEARCH (8-STAGE PIPELINE)
# ============================================================================

def _check_en_locale_local(app_id: int) -> bool:
    """Stage 0: Check if app has English locale in database."""
    with get_session() as session:
        en_locale = session.exec(
            select(AppLocale)
            .where(AppLocale.app_id == app_id)
            .where(AppLocale.locale.like("en-%"))
        ).first()
        return en_locale is not None


def _research_en_equivalent(
    app_info: Dict[str, Any],
    app_id: int,
    api_key: str
) -> Dict[str, Any]:
    """
    Run 8-stage English equivalent research pipeline.
    Returns comprehensive research result with evidence.
    """
    title = app_info["title"]
    category = app_info["category"]
    description = app_info["description"][:500]

    # Stage 0: Local check
    if _check_en_locale_local(app_id):
        return {
            "has_en_locale": True,
            "has_en_equivalent": True,
            "en_equivalents": [],
            "research_stage": "local_en_locale",
            "research_confidence": 1.0,
            "search_results": [],
            "research_updated_at": datetime.utcnow().isoformat()
        }

    # Prepare base prompt
    base_prompt = f"""Given this mobile app:
Title: {title}
Category: {category}
Description: {description}

Search English markets (United States, United Kingdom, Canada, Australia) for existing English-language apps that solve the same primary job-to-be-done.

Return JSON only:
{{
  "has_en_equivalent": true|false,
  "equivalents": [{{"name": "", "store": "apple|google_play", "link": "", "confidence": 0.0-1.0}}],
  "links": ["..."]
}}

Prefer official App Store or Google Play listings if available."""

    stages = [
        # Stage 1: Cheap proactive
        {
            "name": "cheap_1_proactive",
            "model": MODEL_CHEAP,
            "timeout": CHEAP_TIMEOUT_SEC,
            "prompt": base_prompt,
            "context_size": "low",
            "domain_filter": None,
            "budget_type": "cheap"
        },
        # Stage 2: Store verify
        {
            "name": "cheap_2_store_verify",
            "model": MODEL_RECALL_BOOST,
            "timeout": CHEAP_TIMEOUT_SEC,
            "prompt": base_prompt + "\n\nConsider only results from apps.apple.com or play.google.com and prefer US/GB/CA/AU storefronts.",
            "context_size": "medium",
            "domain_filter": SEARCH_DOMAIN_FILTER_STORE,
            "budget_type": "cheap"
        },
        # Stage 3: Social sweep
        {
            "name": "cheap_3_social",
            "model": MODEL_CHEAP,
            "timeout": CHEAP_TIMEOUT_SEC,
            "prompt": base_prompt + "\n\nConsider only results from x.com, twitter.com, reddit.com, tiktok.com, news.ycombinator.com.",
            "context_size": "low",
            "domain_filter": SEARCH_DOMAIN_FILTER_SOCIAL,
            "budget_type": "cheap"
        },
        # Stage 4: Synonym variant
        {
            "name": "cheap_4_synonym",
            "model": MODEL_CHEAP,
            "timeout": CHEAP_TIMEOUT_SEC,
            "prompt": base_prompt.replace("solve the same primary job-to-be-done", "solve similar problems with different keywords or synonyms"),
            "context_size": "low",
            "domain_filter": None,
            "budget_type": "cheap"
        },
        # Stage 5: Recall boost
        {
            "name": "cheap_5_recall_boost",
            "model": MODEL_RECALL_BOOST,
            "timeout": CHEAP_TIMEOUT_SEC,
            "prompt": base_prompt,
            "context_size": "medium",
            "domain_filter": None,
            "budget_type": "cheap"
        },
        # Stage 6: Final store retry
        {
            "name": "cheap_6_store_retry",
            "model": MODEL_CHEAP,
            "timeout": CHEAP_TIMEOUT_SEC,
            "prompt": base_prompt + "\n\nConsider only results from apps.apple.com or play.google.com.",
            "context_size": "low",
            "domain_filter": SEARCH_DOMAIN_FILTER_STORE,
            "budget_type": "cheap"
        },
        # Stage 7: Deep research 1
        {
            "name": "deep_1_comprehensive",
            "model": MODEL_DEEP,
            "timeout": DEEP_TIMEOUT_SEC,
            "prompt": base_prompt + "\n\nRun a deeper crawl; reconcile conflicting sources; favor official store listings and reputable company pages.",
            "context_size": "high",
            "domain_filter": None,
            "budget_type": "deep",
            "reasoning_effort": "low"
        },
        # Stage 8: Deep research 2
        {
            "name": "deep_2_store_focused",
            "model": MODEL_DEEP,
            "timeout": DEEP_TIMEOUT_SEC,
            "prompt": base_prompt + "\n\nRun a deep store-focused search. Reconcile any conflicting evidence.",
            "context_size": "high",
            "domain_filter": SEARCH_DOMAIN_FILTER_STORE,
            "budget_type": "deep",
            "reasoning_effort": "low"
        }
    ]

    # Track results across stages
    results = []

    for stage in stages:
        # Check budget
        max_calls = MAX_DEEP_CALLS_PER_APP_PER_DAY if stage["budget_type"] == "deep" else MAX_CHEAP_CALLS_PER_APP
        if not _check_budget(app_id, stage["budget_type"], max_calls):
            logger.info(f"Budget exceeded for {stage['budget_type']} calls, skipping {stage['name']}")
            continue

        logger.info(f"Running EN research stage: {stage['name']}")

        result = _call_perplexity(
            api_key=api_key,
            model=stage["model"],
            prompt=stage["prompt"],
            timeout=stage["timeout"],
            search_domain_filter=stage.get("domain_filter"),
            search_context_size=stage.get("context_size", "low"),
            reasoning_effort=stage.get("reasoning_effort"),
        )

        if result:
            result["stage"] = stage["name"]
            results.append(result)

            # Early exit on high-confidence positive
            if result.get("has_en_equivalent") and len(result.get("equivalents", [])) > 0:
                equivalents = result.get("equivalents", [])
                # Check for store links
                has_store_links = any(
                    "apps.apple.com" in eq.get("link", "") or "play.google.com" in eq.get("link", "")
                    for eq in equivalents
                )
                if has_store_links:
                    logger.info(f"High-confidence EN equivalent found at stage {stage['name']}")
                    return {
                        "has_en_locale": False,
                        "has_en_equivalent": True,
                        "en_equivalents": equivalents,
                        "research_stage": stage["name"],
                        "research_confidence": 0.9,
                        "search_results": result.get("links", []),
                        "research_updated_at": datetime.utcnow().isoformat()
                    }

            # Early exit on consistent no-equivalent across multiple stages
            if len(results) >= 3:
                no_equiv_count = sum(1 for r in results if not r.get("has_en_equivalent", False))
                if no_equiv_count >= 3:
                    logger.info("Consistent no-equivalent across 3 stages")
                    return {
                        "has_en_locale": False,
                        "has_en_equivalent": False,
                        "en_equivalents": [],
                        "research_stage": stage["name"],
                        "research_confidence": 0.75,
                        "search_results": result.get("links", []),
                        "research_updated_at": datetime.utcnow().isoformat()
                    }

    # Aggregate results if no early exit
    if not results:
        return {
            "has_en_locale": False,
            "has_en_equivalent": None,
            "en_equivalents": [],
            "research_stage": "all_stages_failed",
            "research_confidence": 0.0,
            "search_results": [],
            "research_updated_at": datetime.utcnow().isoformat()
        }

    # Count votes
    positive_votes = sum(1 for r in results if r.get("has_en_equivalent", False))
    negative_votes = len(results) - positive_votes

    # Aggregate equivalents
    all_equivalents = []
    for r in results:
        all_equivalents.extend(r.get("equivalents", []))

    # Deduplicate by name
    seen_names = set()
    unique_equivalents = []
    for eq in all_equivalents:
        name = eq.get("name", "").lower()
        if name and name not in seen_names:
            seen_names.add(name)
            unique_equivalents.append(eq)

    # Aggregate links
    all_links = []
    for r in results:
        all_links.extend(r.get("links", []))

    # Decision
    has_en_equivalent = positive_votes > negative_votes
    confidence = positive_votes / len(results) if results else 0.0

    # Boost confidence if we have store links
    if unique_equivalents:
        has_store_links = any(
            "apps.apple.com" in eq.get("link", "") or "play.google.com" in eq.get("link", "")
            for eq in unique_equivalents
        )
        if has_store_links:
            confidence = max(confidence, 0.85)

    return {
        "has_en_locale": False,
        "has_en_equivalent": has_en_equivalent,
        "en_equivalents": unique_equivalents[:5],  # Limit to top 5
        "research_stage": "aggregated",
        "research_confidence": min(confidence, 0.95),
        "search_results": all_links[:10],  # Limit to 10 URLs
        "research_updated_at": datetime.utcnow().isoformat()
    }


# ============================================================================
# HYBRID MRR ESTIMATION SYSTEM
# ============================================================================

def _detect_monetization_and_price(
    app_info: Dict[str, Any],
    api_key: str
) -> Dict[str, Any]:
    """Detect monetization type and extract price."""
    title = app_info["title"]
    category = app_info["category"]
    description = app_info["description"][:500]

    prompt = f"""Given this mobile app:
Title: {title}
Category: {category}
Description: {description}

Determine the monetization model and entry price.

Return JSON only:
{{
  "monetization": "subscription|pay_once|ads|unknown",
  "price_usd": 9.99 or null,
  "price_source": "app_store|website|unknown",
  "links": ["..."]
}}

Prefer official App Store, Google Play, or developer website data."""

    result = _call_perplexity(
        api_key=api_key,
        model=MODEL_CHEAP,
        prompt=prompt,
        timeout=CHEAP_TIMEOUT_SEC,
        search_domain_filter=SEARCH_DOMAIN_FILTER_STORE,
        search_context_size="medium"
    )

    if not result:
        return {
            "monetization": "unknown",
            "price_usd": None,
            "price_source": None,
            "evidence_links": []
        }

    return {
        "monetization": result.get("monetization", "unknown"),
        "price_usd": result.get("price_usd"),
        "price_source": result.get("price_source"),
        "evidence_links": result.get("links", [])
    }


def _public_revenue_override(
    app_info: Dict[str, Any],
    api_key: str
) -> Dict[str, Any]:
    """Search for public revenue data."""
    title = app_info["title"]
    developer = app_info["developer"]

    prompt = f"""Search for public revenue data about this mobile app:
App: {title}
Developer: {developer}

Look for monthly revenue, ARR, subscriber counts from credible sources like founder posts, investor decks, or reputable press.

Return JSON only:
{{
  "has_public_revenue": true|false,
  "mrr_usd": 50000.0 or null,
  "subscribers": 10000 or null,
  "links": ["..."]
}}"""

    result = _call_perplexity(
        api_key=api_key,
        model=MODEL_CHEAP,
        prompt=prompt,
        timeout=CHEAP_TIMEOUT_SEC,
        search_context_size="medium"
    )

    if not result or not result.get("has_public_revenue"):
        return {
            "has_public_revenue": False,
            "mrr_usd": None,
            "subscribers": None,
            "links": []
        }

    return result


def _estimate_installs_month(
    app_info: Dict[str, Any],
    api_key: str
) -> Dict[str, Any]:
    """Estimate monthly installs (optional)."""
    title = app_info["title"]
    category = app_info["category"]
    review_count = app_info.get("review_count", 0)

    prompt = f"""Estimate monthly installs for this mobile app:
Title: {title}
Category: {category}
Total Reviews: {review_count}

Return JSON only:
{{
  "installs_low": 10000 or null,
  "installs_mid": 20000 or null,
  "installs_high": 30000 or null,
  "links": ["..."]
}}

Use industry benchmarks and review-to-install ratios."""

    result = _call_perplexity(
        api_key=api_key,
        model=MODEL_CHEAP,
        prompt=prompt,
        timeout=CHEAP_TIMEOUT_SEC,
        search_context_size="low"
    )

    if not result:
        return {
            "installs_low": None,
            "installs_mid": None,
            "installs_high": None,
            "links": []
        }

    return result


def _estimate_mrr_subscription(
    price_usd: float,
    category: str,
    installs_mid: Optional[int]
) -> Tuple[float, float, float, float]:
    """
    Estimate subscription MRR using funnel priors.
    Returns (mrr_low, mrr_mid, mrr_high, confidence).
    """
    # Get priors
    priors = MONETIZATION_PRIORS.get(category, MONETIZATION_PRIORS["default"])
    install_to_trial, trial_to_paid, monthly_churn = priors

    if not installs_mid:
        # Use price-only band with low confidence
        # Assume small base of 100 active subs as floor
        mrr_mid = price_usd * 100
        mrr_low = mrr_mid * 0.5
        mrr_high = mrr_mid * 2.0
        return (mrr_low, mrr_mid, mrr_high, 0.3)

    # Compute funnel
    new_subs = installs_mid * install_to_trial * trial_to_paid
    active_subs = new_subs / monthly_churn  # Steady-state approximation

    mrr_mid = price_usd * active_subs
    mrr_low = mrr_mid * 0.75
    mrr_high = mrr_mid * 1.25

    confidence = 0.6 if installs_mid else 0.4

    return (mrr_low, mrr_mid, mrr_high, confidence)


def _estimate_mrr_payonce(
    price_usd: float,
    installs_mid: Optional[int]
) -> Tuple[float, float, float, float]:
    """
    Estimate pay-once MRR (monthly unit sales × price).
    Returns (mrr_low, mrr_mid, mrr_high, confidence).
    """
    if not installs_mid:
        return (0.0, 0.0, 0.0, 0.1)

    # Assume monthly purchases are a fraction of total installs
    monthly_units = installs_mid * 0.1  # Conservative estimate

    mrr_mid = price_usd * monthly_units
    mrr_low = mrr_mid * 0.75
    mrr_high = mrr_mid * 1.25

    return (mrr_low, mrr_mid, mrr_high, 0.4)


def _estimate_mrr(
    app_info: Dict[str, Any],
    app_id: int,
    api_key: str,
    refresh: bool = False
) -> Dict[str, Any]:
    """
    Hybrid MRR estimation system.
    Returns mrr_low/mid/high, confidence, and supporting data.
    """
    # Check cache
    cached = _check_cache(_monetization_cache, app_id, refresh)
    if cached:
        return cached

    # Detect monetization and price
    monetization_result = _detect_monetization_and_price(app_info, api_key)
    monetization = monetization_result["monetization"]
    price_usd = monetization_result["price_usd"]
    price_source = monetization_result["price_source"]
    evidence_links = monetization_result["evidence_links"]

    # Check for public revenue override
    public_revenue = _public_revenue_override(app_info, api_key)
    if public_revenue["has_public_revenue"] and public_revenue["mrr_usd"]:
        mrr_mid = public_revenue["mrr_usd"]
        result = {
            "monetization": monetization,
            "price_usd": price_usd,
            "price_source": price_source,
            "mrr_low": mrr_mid * 0.85,
            "mrr_mid": mrr_mid,
            "mrr_high": mrr_mid * 1.15,
            "mrr_confidence": 0.9,
            "evidence_links": evidence_links + public_revenue["links"]
        }
        _set_cache(_monetization_cache, app_id, result, EN_EQ_CACHE_TTL_SECONDS)
        return result

    # Estimate installs
    installs_result = _estimate_installs_month(app_info, api_key)
    installs_mid = installs_result.get("installs_mid")
    evidence_links.extend(installs_result.get("links", []))

    # Compute MRR based on monetization type
    if monetization == "subscription" and price_usd:
        mrr_low, mrr_mid, mrr_high, confidence = _estimate_mrr_subscription(
            price_usd, app_info["category"], installs_mid
        )
    elif monetization == "pay_once" and price_usd:
        mrr_low, mrr_mid, mrr_high, confidence = _estimate_mrr_payonce(
            price_usd, installs_mid
        )
    elif monetization == "ads":
        # Insufficient data for ads MRR
        mrr_low = mrr_mid = mrr_high = 0.0
        confidence = 0.2
    else:
        # Unknown monetization
        mrr_low = mrr_mid = mrr_high = 0.0
        confidence = 0.1

    result = {
        "monetization": monetization,
        "price_usd": price_usd,
        "price_source": price_source,
        "mrr_low": round(mrr_low, 2),
        "mrr_mid": round(mrr_mid, 2),
        "mrr_high": round(mrr_high, 2),
        "mrr_confidence": confidence,
        "evidence_links": evidence_links[:10]  # Limit to 10
    }

    _set_cache(_monetization_cache, app_id, result, EN_EQ_CACHE_TTL_SECONDS)
    return result


# ============================================================================
# MAIN ORCHESTRATOR (UPDATED)
# ============================================================================

def analyze_app(app_id: int, refresh: bool = False) -> Dict[str, Any]:
    """
    Analyze an app using AI to provide comprehensive insights.

    Args:
        app_id: App ID to analyze
        refresh: If True, bypass cache and refresh all data

    Returns comprehensive insights dict with all fields.
    """
    start_time = time.time()
    settings = get_settings()

    # Get app data and extract while session is active
    with get_session() as session:
        app = session.get(App, app_id)
        if not app:
            raise ValueError(f"App {app_id} not found")

        # Get all locales
        locales = session.exec(
            select(AppLocale).where(AppLocale.app_id == app_id)
        ).all()

        # Get primary locale for description
        locale = locales[0] if locales else None

        # Get reviews
        reviews = session.exec(
            select(Review)
            .where(Review.app_id == app_id)
            .limit(50)
        ).all()

        # Extract all data while session is active
        title = locale.title_raw if locale else 'Unknown App'
        description = locale.desc_raw if locale else ''
        developer = app.developer or 'Unknown Developer'
        category = app.category
        store_app_id = app.store_app_id

        # Extract review data
        reviews_sample = [
            {"rating": r.rating, "text": (r.body_raw or '')[:200]}
            for r in reviews[:10]
        ]
        review_count = len(reviews)

    # Prepare app info (now outside session, using extracted data)
    app_info = {
        "title": title,
        "description": description[:500] if description else "No description",
        "category": category,
        "store_app_id": store_app_id,
        "developer": developer,
        "review_count": review_count,
        "reviews_sample": reviews_sample
    }

    # Call existing Gemini analysis (keep for UI continuity)
    gemini_result = _analyze_with_gemini(app_info, settings.gemini_api_key)

    # Call existing market insights (keep for UI continuity)
    perplexity_result = _get_market_insights(app_info, settings.perplexity_api_key)

    # NEW: English equivalent research
    en_result = _check_cache(_en_cache, app_id, refresh)
    if not en_result:
        en_result = _research_en_equivalent(app_info, app_id, settings.perplexity_api_key)
        _set_cache(_en_cache, app_id, en_result, EN_EQ_CACHE_TTL_SECONDS)

    # NEW: Hybrid MRR estimation
    mrr_result = _estimate_mrr(app_info, app_id, settings.perplexity_api_key, refresh)

    duration_ms = int((time.time() - start_time) * 1000)

    # Merge all results
    return {
        # Existing fields (kept for backwards compatibility)
        **gemini_result,
        **perplexity_result,

        # NEW: English equivalent fields
        **en_result,

        # NEW: MRR estimation fields
        **mrr_result,

        # Metadata
        "research_duration_ms": duration_ms
    }


# ============================================================================
# EXISTING GEMINI/PERPLEXITY FUNCTIONS (PRESERVED)
# ============================================================================

def _analyze_with_gemini(app_info: Dict, api_key: Optional[str]) -> Dict[str, Any]:
    """Use Gemini to analyze app for MRR, difficulty, and review summary."""
    if not api_key:
        return {
            "mrr_estimate": "N/A",
            "mrr_reasoning": "Gemini API key not configured",
            "difficulty": "Unknown",
            "difficulty_factors": [],
            "review_summary": []
        }

    prompt = f"""Analyze this mobile app and provide:
1. Estimated Monthly Recurring Revenue (MRR) - consider category, review count, typical pricing
2. Rebuild Difficulty (Easy/Medium/Hard) - consider features, complexity
3. Top 3 insights from user reviews

App: {app_info['title']}
Category: {app_info['category']}
Description: {app_info['description']}
Reviews: {app_info['review_count']}
Sample Reviews: {json.dumps(app_info['reviews_sample'])}

Return JSON:
{{
  "mrr_estimate": "$X,XXX",
  "mrr_reasoning": "why",
  "difficulty": "Easy|Medium|Hard",
  "difficulty_factors": ["factor1", "factor2", "factor3"],
  "review_summary": ["insight1", "insight2", "insight3"]
}}"""

    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        response = requests.post(
            url,
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=10
        )
        response.raise_for_status()

        result = response.json()
        text = result['candidates'][0]['content']['parts'][0]['text']

        if '```json' in text:
            text = text.split('```json')[1].split('```')[0]
        elif '```' in text:
            text = text.split('```')[1].split('```')[0]

        return json.loads(text.strip())

    except Exception as e:
        logger.exception("Gemini API request failed")
        return {
            "mrr_estimate": "Error",
            "mrr_reasoning": "AI analysis temporarily unavailable",
            "difficulty": "Unknown",
            "difficulty_factors": [],
            "review_summary": []
        }


def _get_market_insights(app_info: Dict, api_key: Optional[str]) -> Dict[str, Any]:
    """Use Perplexity to get market viability and competitive insights."""
    if not api_key:
        return {
            "market_viability": 0,
            "market_insights": "Perplexity API key not configured"
        }

    prompt = f"""Research the market for a {app_info['category']} mobile app like "{app_info['title']}".
Provide:
1. Market viability score (1-10)
2. Brief competitive landscape (2-3 sentences)
3. Key success factors for this category

Keep it concise."""

    try:
        url = PERPLEXITY_BASE_URL
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL_CHEAP,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=25
        )
        response.raise_for_status()

        result = response.json()
        content = result['choices'][0]['message']['content']

        # Parse viability score
        viability = 5
        if 'viability' in content.lower():
            import re
            numbers = re.findall(r'\b([1-9]|10)\b', content)
            if numbers:
                viability = int(numbers[0])

        return {
            "market_viability": viability,
            "market_insights": content
        }

    except Exception as e:
        logger.exception("Perplexity API request failed")
        return {
            "market_viability": 0,
            "market_insights": "Market analysis temporarily unavailable"
        }
