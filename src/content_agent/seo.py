"""SEO & hashtag optimization — Gemini Flash for metadata, rule-based posting times."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from tenacity import retry, stop_after_attempt, wait_exponential

from content_agent.models import ContentPiece, Platform, TrendItem

log = logging.getLogger(__name__)

HASHTAG_PROMPT = """Given this social media post for {platform}, suggest 5-10 relevant hashtags.

Post content:
{content}

Current trending topics:
{trends}

Default hashtags for this platform: {defaults}

Rules:
- Mix trending and evergreen hashtags
- Platform-specific: {platform_rules}
- Return ONLY a JSON array of hashtag strings (without the # symbol)
- Order by relevance (most relevant first)"""

PLATFORM_RULES = {
    "twitter": "3-5 hashtags max. Short, punchy. Include niche security hashtags.",
    "linkedin": "3-5 hashtags. Professional. Include industry terms.",
    "instagram": "10-15 hashtags. Mix broad and niche. Include community hashtags.",
    "youtube": "5-8 tags. Keyword-rich for search discovery.",
}

OPTIMAL_POSTING_TIMES = {
    "twitter": {"weekday": "09:00", "weekend": "10:00"},
    "linkedin": {"weekday": "08:30", "weekend": "10:00"},
    "instagram": {"weekday": "12:00", "weekend": "11:00"},
    "youtube": {"weekday": "14:00", "weekend": "10:00"},
}


class SEOOptimizer:
    def __init__(
        self,
        google_api_key: str = "",
        seo_model: str = "gemini-2.5-flash",
        default_hashtags: dict[str, list[str]] | None = None,
        posting_times: dict[str, str] | None = None,
    ):
        self._google_key = google_api_key
        self._seo_model = seo_model
        self._default_hashtags = default_hashtags or {}
        self._posting_times = posting_times or {}

    def optimize_hashtags(
        self,
        piece: ContentPiece,
        trends: list[TrendItem] | None = None,
    ) -> list[str]:
        platform = piece.platform.value
        defaults = self._default_hashtags.get(platform, [])

        if not self._google_key:
            log.info("No Google API key — using default hashtags for %s", platform)
            return defaults

        try:
            return self._generate_hashtags(piece, trends or [], defaults)
        except Exception as e:
            log.error("Hashtag optimization failed: %s — using defaults", e)
            return defaults

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _generate_hashtags(
        self,
        piece: ContentPiece,
        trends: list[TrendItem],
        defaults: list[str],
    ) -> list[str]:
        platform = piece.platform.value
        trends_text = "\n".join(
            f"- {t.topic}: {t.context}" for t in trends[:5]
        ) or "No trending data available"

        prompt = HASHTAG_PROMPT.format(
            platform=platform,
            content=piece.body[:500],
            trends=trends_text,
            defaults=", ".join(defaults),
            platform_rules=PLATFORM_RULES.get(platform, ""),
        )

        from google import genai

        client = genai.Client(api_key=self._google_key)
        response = client.models.generate_content(
            model=self._seo_model,
            contents=prompt,
        )

        return _parse_hashtags(response.text or "", defaults)

    def get_optimal_posting_time(self, platform: str) -> str:
        configured = self._posting_times.get(platform)
        if configured:
            return configured

        day = datetime.now().weekday()
        is_weekend = day >= 5
        times = OPTIMAL_POSTING_TIMES.get(platform, {"weekday": "09:00", "weekend": "10:00"})
        return times["weekend"] if is_weekend else times["weekday"]

    def optimize_content(
        self,
        pieces: list[ContentPiece],
        trends: list[TrendItem] | None = None,
    ) -> list[ContentPiece]:
        for piece in pieces:
            hashtags = self.optimize_hashtags(piece, trends)
            piece.hashtags = hashtags
        return pieces


def _parse_hashtags(content: str, fallback: list[str]) -> list[str]:
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        tags = json.loads(content)
        if isinstance(tags, list):
            return [str(t).lstrip("#") for t in tags if t]
    except json.JSONDecodeError:
        pass

    import re
    match = re.search(r"\[.*?\]", content, re.DOTALL)
    if match:
        try:
            tags = json.loads(match.group())
            if isinstance(tags, list):
                return [str(t).lstrip("#") for t in tags if t]
        except json.JSONDecodeError:
            pass

    return fallback
