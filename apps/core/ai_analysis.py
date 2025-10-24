"""
AI-powered analysis using Gemini and Perplexity APIs.
Provides MRR estimates, rebuild difficulty, review summaries, and market insights.
"""
import json
import logging
from typing import Dict, Any, Optional

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
    """
    settings = get_settings()

    # Get app data
    with get_session() as session:
        app = session.get(App, app_id)
        if not app:
            raise ValueError(f"App {app_id} not found")

        # Get app locale for description
        locale = session.exec(
            select(AppLocale)
            .where(AppLocale.app_id == app_id)
        ).first()

        # Get reviews
        reviews = session.exec(
            select(Review)
            .where(Review.app_id == app_id)
            .limit(50)
        ).all()

    # Prepare data for AI
    title = locale.title_raw if locale else 'Unknown App'
    description = locale.desc_raw if locale else ''

    app_info = {
        "title": title,
        "description": description[:500] if description else "No description",
        "category": app.category,
        "store_app_id": app.store_app_id,
        "review_count": len(reviews),
        "reviews_sample": [
            {"rating": r.rating, "text": r.text[:200]}
            for r in reviews[:10]
        ]
    }

    # Call both AI services
    gemini_result = _analyze_with_gemini(app_info, settings.gemini_api_key)
    perplexity_result = _get_market_insights(app_info, settings.perplexity_api_key)

    return {
        **gemini_result,
        **perplexity_result
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
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
        response = requests.post(
            url,
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
        logger.error(f"Gemini API error: {e}")
        return {
            "mrr_estimate": "Error",
            "mrr_reasoning": str(e),
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
                "model": "llama-3.1-sonar-small-128k-online",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=15
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
        logger.error(f"Perplexity API error: {e}")
        return {
            "market_viability": 0,
            "market_insights": f"Error: {str(e)}"
        }
