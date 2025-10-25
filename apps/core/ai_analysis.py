"""
AI-powered analysis using Gemini and Perplexity APIs.
Provides MRR estimates, rebuild difficulty, review summaries, and market insights.
Multi-stage English-equivalent detection with deep research fallback.
"""
import json
import logging
import time
from typing import Dict, Any, Optional, List

import requests

from apps.core.config import get_settings
from apps.core.db import get_session
from apps.core.models import App, AppLocale, Review
from sqlmodel import select

logger = logging.getLogger(__name__)


def analyze_app(app_id: int) -> Dict[str, Any]:
    """
    Analyze an app using AI to provide insights.

    Returns:
        - mrr_estimate: Estimated monthly recurring revenue
        - mrr_reasoning: Why this estimate
        - difficulty: Easy/Medium/Hard
        - difficulty_factors: List of complexity factors
        - review_summary: 3 key points from reviews
        - market_viability: Score 1-10
        - market_insights: Competitive landscape analysis
        - has_en_locale: Boolean, true if app has English locale
        - has_en_equivalent: Boolean, true if English version exists
        - en_check_confidence: 0-1 confidence score
        - research_stages_run: List of stages executed
        - research_evidence: Evidence from each stage
        - search_results: URLs used in final determination
        - research_duration_ms: Total time spent
    """
    start_time = time.time()
    settings = get_settings()

    # Get app data
    with get_session() as session:
        app = session.get(App, app_id)
        if not app:
            raise ValueError(f"App {app_id} not found")

        # Get all locales for English check
        locales = session.exec(
            select(AppLocale)
            .where(AppLocale.app_id == app_id)
        ).all()

        # Get primary locale for description
        locale = locales[0] if locales else None

        # Get reviews
        reviews = session.exec(
            select(Review)
            .where(Review.app_id == app_id)
            .limit(50)
        ).all()

    # Prepare data for AI
    title = locale.title_raw if locale else 'Unknown App'
    description = locale.desc_raw if locale else ''
    developer = app.developer or 'Unknown Developer'

    app_info = {
        "title": title,
        "description": description[:500] if description else "No description",
        "category": app.category,
        "store_app_id": app.store_app_id,
        "developer": developer,
        "review_count": len(reviews),
        "reviews_sample": [
            {"rating": r.rating, "text": (r.body_raw or '')[:200]}
            for r in reviews[:10]
        ]
    }

    # Call AI services
    gemini_result = _analyze_with_gemini(app_info, settings.gemini_api_key)
    perplexity_result = _get_market_insights(app_info, settings.perplexity_api_key)

    # Multi-stage English-equivalent check
    en_check_result = _check_english_equivalent(
        app_info=app_info,
        locales=locales,
        api_key=settings.perplexity_api_key
    )

    duration_ms = int((time.time() - start_time) * 1000)

    return {
        **gemini_result,
        **perplexity_result,
        **en_check_result,
        "research_duration_ms": duration_ms
    }


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
        # Use POST with JSON body, avoid key in URL
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

        # Extract JSON from markdown code blocks if present
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0]
        elif '```' in text:
            text = text.split('```')[1].split('```')[0]

        return json.loads(text.strip())

    except Exception as e:
        # Log error without exposing API details
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
        url = "https://api.perplexity.ai/chat/completions"
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "sonar",  # Upgraded from deprecated llama-3.1
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=25  # Increased for reliability
        )
        response.raise_for_status()

        result = response.json()
        content = result['choices'][0]['message']['content']

        # Parse viability score from response
        viability = 5  # default
        if 'viability' in content.lower():
            # Simple extraction - look for numbers
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


def _check_english_equivalent(
    app_info: Dict,
    locales: List,
    api_key: Optional[str]
) -> Dict[str, Any]:
    """
    Multi-stage English-equivalent detection.

    Stage 0: Check local locales
    Stage 1: Quick web search
    Stage 2: Store-specific search
    Stage 3: Social media scan
    Stage 4: Deep research (if needed)
    """
    if not api_key:
        return {
            "has_en_locale": False,
            "has_en_equivalent": None,
            "en_check_confidence": 0,
            "research_stages_run": [],
            "research_evidence": {},
            "search_results": []
        }

    stages_run = []
    evidence = {}
    all_search_results = []

    # Stage 0: Local check (free, instant)
    has_en_locale = any(loc.locale.startswith("en-") for loc in locales)
    if has_en_locale:
        return {
            "has_en_locale": True,
            "has_en_equivalent": True,  # Has English locale = English equivalent exists
            "en_check_confidence": 1.0,
            "research_stages_run": ["local"],
            "research_evidence": {"local": "App has English locale"},
            "search_results": []
        }

    stages_run.append("local")
    evidence["local"] = "No English locale found"

    title = app_info["title"]
    developer = app_info["developer"]

    # Stage 1: Quick web search
    web_result = _perplexity_search(
        api_key=api_key,
        model="sonar",
        query=f"Does '{title}' by {developer} have an English version?",
        search_mode="web",
        timeout=25
    )
    stages_run.append("web")
    if web_result:
        evidence["web"] = web_result.get("content", "No response")
        all_search_results.extend(web_result.get("search_results", []))
        web_has_en = web_result.get("has_en_equivalent", None)
        web_confidence = web_result.get("confidence", 0.5)
    else:
        evidence["web"] = "Search failed"
        web_has_en = None
        web_confidence = 0

    # Stage 2: Store-specific search
    store_result = _perplexity_search(
        api_key=api_key,
        model="sonar",
        query=f"Is '{title}' available in English on Apple App Store or Google Play?",
        search_mode="web",
        domain_filter=["apps.apple.com", "play.google.com"],
        timeout=25
    )
    stages_run.append("stores")
    if store_result:
        evidence["stores"] = store_result.get("content", "No response")
        all_search_results.extend(store_result.get("search_results", []))
        store_has_en = store_result.get("has_en_equivalent", None)
        store_confidence = store_result.get("confidence", 0.5)
    else:
        evidence["stores"] = "Search failed"
        store_has_en = None
        store_confidence = 0

    # Stage 3: Social media scan
    social_result = _perplexity_search(
        api_key=api_key,
        model="sonar",
        query=f"Has '{title}' launched in English? Check Twitter, Reddit, Hacker News",
        search_mode="web",
        domain_filter=["twitter.com", "x.com", "reddit.com", "news.ycombinator.com"],
        timeout=25
    )
    stages_run.append("social")
    if social_result:
        evidence["social"] = social_result.get("content", "No response")
        all_search_results.extend(social_result.get("search_results", []))
        social_has_en = social_result.get("has_en_equivalent", None)
        social_confidence = social_result.get("confidence", 0.5)
    else:
        evidence["social"] = "Search failed"
        social_has_en = None
        social_confidence = 0

    # Determine if we need deep research
    responses = [r for r in [web_has_en, store_has_en, social_has_en] if r is not None]
    confidences = [c for c in [web_confidence, store_confidence, social_confidence] if c > 0]

    need_deep_research = (
        len(responses) == 0 or  # All failed
        len(set(responses)) > 1 or  # Conflicting answers
        (confidences and max(confidences) < 0.7)  # Low confidence
    )

    if need_deep_research:
        # Stage 4: Deep research
        deep_result = _perplexity_search(
            api_key=api_key,
            model="sonar-deep-research",
            query=f"Comprehensive research: Does the mobile app '{title}' by {developer} exist in English? Check all app stores, official websites, and announcements.",
            search_mode="web",
            reasoning_effort="low",
            timeout=60
        )
        stages_run.append("deep")
        if deep_result:
            evidence["deep"] = deep_result.get("content", "No response")
            all_search_results.extend(deep_result.get("search_results", []))
            final_has_en = deep_result.get("has_en_equivalent", False)
            final_confidence = deep_result.get("confidence", 0.7)
        else:
            evidence["deep"] = "Deep research failed"
            final_has_en = False
            final_confidence = 0.3
    else:
        # Use consensus from cheap stages
        if responses:
            final_has_en = sum(responses) / len(responses) > 0.5
            final_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        else:
            final_has_en = False
            final_confidence = 0.3

    return {
        "has_en_locale": False,
        "has_en_equivalent": final_has_en,
        "en_check_confidence": final_confidence,
        "research_stages_run": stages_run,
        "research_evidence": evidence,
        "search_results": all_search_results[:10]  # Limit to first 10 URLs
    }


def _perplexity_search(
    api_key: str,
    model: str,
    query: str,
    search_mode: str = "web",
    domain_filter: Optional[List[str]] = None,
    reasoning_effort: Optional[str] = None,
    timeout: int = 25
) -> Optional[Dict[str, Any]]:
    """
    Call Perplexity API with optional domain filtering and reasoning effort.

    Returns dict with:
        - content: AI response text
        - has_en_equivalent: bool (parsed from response)
        - confidence: float 0-1
        - search_results: list of URLs
    """
    try:
        url = "https://api.perplexity.ai/chat/completions"

        # Build request body
        body = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": f"""{query}

Respond with JSON:
{{
  "has_en_equivalent": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}"""
            }]
        }

        # Add Perplexity-specific parameters via extra fields
        if domain_filter:
            body["search_domain_filter"] = domain_filter
        if reasoning_effort:
            body["reasoning_effort"] = reasoning_effort

        response = requests.post(
            url,
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

        # Extract search_results if available
        search_results = []
        if "citations" in result:  # Fallback for older API
            search_results = result["citations"]
        elif "search_results" in result:  # New API format
            search_results = [r.get("url", "") for r in result["search_results"]]

        # Try to parse JSON from response
        try:
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                json_str = content

            parsed = json.loads(json_str.strip())
            has_en = parsed.get("has_en_equivalent", False)
            confidence = parsed.get("confidence", 0.5)
        except (json.JSONDecodeError, IndexError):
            # Fallback: parse from text
            has_en = "true" in content.lower() or "yes" in content.lower()
            confidence = 0.6 if has_en else 0.5

        return {
            "content": content,
            "has_en_equivalent": has_en,
            "confidence": confidence,
            "search_results": search_results
        }

    except Exception as e:
        logger.exception(f"Perplexity search failed for query: {query[:50]}...")
        return None
