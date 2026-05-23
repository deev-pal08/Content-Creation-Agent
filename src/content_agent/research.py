"""Trend research engine — Grok (X), Perplexity (web), Gemini (YouTube)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from content_agent.models import TrendItem, TrendReport

log = logging.getLogger(__name__)

TREND_PROMPT_TEMPLATE = """Analyze current trending topics in cybersecurity and AI security.
Focus on topics relevant to: {focus_areas}

Return a JSON array of trending topics, each with:
- "topic": the trending topic name
- "relevance_score": 0.0-1.0 how relevant to security/AI
- "context": why it's trending (1-2 sentences)
- "hashtags": relevant hashtags for this topic

Return ONLY the JSON array, no markdown fencing."""


class TrendResearcher:
    def __init__(
        self,
        xai_api_key: str = "",
        perplexity_api_key: str = "",
        google_api_key: str = "",
        trend_model_x: str = "grok-3-mini",
        trend_model_web: str = "sonar",
        trend_model_youtube: str = "gemini-2.5-flash",
    ):
        self._xai_key = xai_api_key
        self._perplexity_key = perplexity_api_key
        self._google_key = google_api_key
        self._model_x = trend_model_x
        self._model_web = trend_model_web
        self._model_youtube = trend_model_youtube

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def research_x_trends(self, focus_areas: str = "cybersecurity, AI security") -> TrendReport:
        if not self._xai_key:
            log.warning("No xAI API key — skipping X trend research")
            return TrendReport(platform="twitter", generated_at=datetime.now(UTC))

        prompt = TREND_PROMPT_TEMPLATE.format(focus_areas=focus_areas)
        prompt += "\n\nFocus on what's trending on X/Twitter RIGHT NOW in the security community."

        with httpx.Client(timeout=60) as client:
            resp = client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._xai_key}"},
                json={
                    "model": self._model_x,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        trends = _parse_trends(content)
        log.info("X trend research: %d trends found", len(trends))
        return TrendReport(
            platform="twitter", trends=trends, generated_at=datetime.now(UTC),
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def research_web_trends(self, focus_areas: str = "cybersecurity, AI security") -> TrendReport:
        if not self._perplexity_key:
            log.warning("No Perplexity API key — skipping web trend research")
            return TrendReport(platform="web", generated_at=datetime.now(UTC))

        prompt = TREND_PROMPT_TEMPLATE.format(focus_areas=focus_areas)
        prompt += "\n\nSearch across the web, Reddit, and news for trending security topics."

        with httpx.Client(timeout=60) as client:
            resp = client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={"Authorization": f"Bearer {self._perplexity_key}"},
                json={
                    "model": self._model_web,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        trends = _parse_trends(content)
        log.info("Web trend research: %d trends found", len(trends))
        return TrendReport(
            platform="web", trends=trends, generated_at=datetime.now(UTC),
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def research_youtube_trends(
        self, focus_areas: str = "cybersecurity, AI security",
    ) -> TrendReport:
        if not self._google_key:
            log.warning("No Google API key — skipping YouTube trend research")
            return TrendReport(platform="youtube", generated_at=datetime.now(UTC))

        prompt = TREND_PROMPT_TEMPLATE.format(focus_areas=focus_areas)
        prompt += "\n\nFocus on YouTube and Google Search trends in security and AI."

        from google import genai

        client = genai.Client(api_key=self._google_key)
        response = client.models.generate_content(
            model=self._model_youtube,
            contents=prompt,
        )

        trends = _parse_trends(response.text or "")
        log.info("YouTube trend research: %d trends found", len(trends))
        return TrendReport(
            platform="youtube", trends=trends, generated_at=datetime.now(UTC),
        )

    def research_all(
        self, focus_areas: str = "cybersecurity, AI security",
    ) -> list[TrendReport]:
        reports = []
        for method in [self.research_x_trends, self.research_web_trends, self.research_youtube_trends]:
            try:
                reports.append(method(focus_areas))
            except Exception as e:
                log.error("Trend research failed for %s: %s", method.__name__, e)
        return reports


def _parse_trends(content: str) -> list[TrendItem]:
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        items = json.loads(content)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            try:
                items = json.loads(match.group())
            except json.JSONDecodeError:
                return []
        else:
            return []

    if not isinstance(items, list):
        return []

    trends = []
    for item in items:
        if isinstance(item, dict) and "topic" in item:
            trends.append(TrendItem(
                topic=item["topic"],
                relevance_score=float(item.get("relevance_score", 0.0)),
                source=item.get("source", ""),
                context=item.get("context", ""),
                hashtags=item.get("hashtags", []),
            ))
    return trends
