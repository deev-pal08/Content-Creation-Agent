"""Content writer — Claude Sonnet (posts, threads, scripts) + Grok (hot takes)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import httpx
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from content_agent.models import ContentPiece, ContentType, ObsidianNote, Platform, TrendItem

log = logging.getLogger(__name__)

LINKEDIN_PROMPT = """Write a LinkedIn post about today's security learning.
You are a security engineer sharing your daily learning journey (Day {day_number}).

Today's learning notes:
{notes_summary}

Trending topics to consider weaving in:
{trends_summary}

Guidelines:
- Professional but authentic tone — not corporate, not casual
- Start with a hook (question, surprising fact, or bold statement)
- Share what you learned and why it matters
- End with a question or call to action for engagement
- 150-300 words. No emojis. No hashtags in the body (they go separately).
- Write as a first-person narrative, not a listicle

Return ONLY the post text, nothing else."""

TWITTER_THREAD_PROMPT = """Write a Twitter/X thread explaining a security concept from today's learning.
Day {day_number} of your security learning journey.

Today's notes:
{notes_summary}

Guidelines:
- 4-6 tweets, each under 280 characters
- First tweet is the hook — make it compelling
- Break down a technical concept simply
- Last tweet: summary + what's next
- Use numbering: 1/, 2/, etc.
- No emojis. No hashtags in thread body.

Return each tweet on its own line, separated by blank lines."""

HOT_TAKE_PROMPT = """Write a spicy, witty hot take tweet about today's security learning.
You're a security engineer who just learned something interesting.

Today's learning:
{notes_summary}

Current trending topics on X:
{trends_summary}

Guidelines:
- One single tweet, under 280 characters
- Be opinionated, witty, slightly provocative
- Reference a trending topic if relevant
- The kind of tweet that makes security people stop scrolling
- No emojis. No hashtags.

Return ONLY the tweet text."""

INSTAGRAM_CAPTION_PROMPT = """Write an Instagram caption for a security learning post.
Day {day_number} of your security journey.

Today's notes:
{notes_summary}

Guidelines:
- 50-100 words
- Accessible to non-experts
- Start with a bold statement about what you learned
- End with engagement prompt
- Conversational tone
- No hashtags in caption (added separately)

Return ONLY the caption text."""

VIDEO_SCRIPT_PROMPT = """Write a 30-60 second video script explaining a security concept from today's learning.

Today's notes:
{notes_summary}

Guidelines:
- Narration script for a short explainer video (Instagram Reel / YouTube Short)
- Start with a hook in the first 3 seconds ("Did you know..." / "Here's how...")
- Explain one concept clearly with a simple example
- End with a takeaway
- Include scene descriptions in [brackets] for visual cues
- Target 80-120 words of narration (roughly 30-45 seconds spoken)

Return the script in this format:
[Scene description]
Narration text

[Scene description]
Narration text
..."""

CODE_CHALLENGE_PROMPT = """You are a security engineer creating a "Spot the Bug" code review challenge based on today's learning.

Today's learning notes:
{notes_summary}

Your task:
1. Analyze what was learned today
2. Decide whether a realistic code review challenge can be created from this topic
3. If yes, write a short, realistic code snippet (8-20 lines) that contains a subtle security vulnerability related to today's learning

If the topic is too theoretical or abstract to create a realistic vulnerable code snippet, respond with exactly: NO_CHALLENGE

Otherwise, respond with ONLY valid JSON (no markdown fencing, no extra text):
{{
    "code": "the vulnerable code snippet",
    "language": "python",
    "vulnerability": "Short vulnerability name (e.g. SQL Injection, SSRF, Path Traversal)",
    "hint": "A one-line hint that points toward the bug without revealing it"
}}

Guidelines for the code:
- Must look like real production code, not a toy example
- The bug should be subtle — something a junior dev might miss in code review
- Use realistic function/variable names
- Keep it 8-20 lines
- Common languages: python, javascript, go, java, php
- The vulnerability MUST relate to what was actually learned today"""

DAILY_UPDATE_PROMPT = """Write a daily update post for Day {day_number} of the security learning journey.

Today's completed tasks and learnings:
{notes_summary}

Guidelines:
- Brief progress update format: "Day {day_number}: [Topic]"
- What you worked on (1-2 sentences)
- Key insight or takeaway (1-2 sentences)
- What's next (1 sentence)
- 80-150 words total
- Authentic, journaling tone

Return ONLY the post text."""


class ContentWriter:
    def __init__(
        self,
        anthropic_api_key: str = "",
        xai_api_key: str = "",
        writer_model: str = "claude-sonnet-4-6",
        hot_take_model: str = "grok-3-mini",
        max_tokens: int = 4096,
    ):
        self._anthropic_key = anthropic_api_key
        self._xai_key = xai_api_key
        self._writer_model = writer_model
        self._hot_take_model = hot_take_model
        self._max_tokens = max_tokens

    def generate_all_content(
        self,
        notes: list[ObsidianNote],
        day_number: int,
        trends: list[TrendItem] | None = None,
        date: str = "",
    ) -> list[ContentPiece]:
        if not notes:
            log.warning("No notes provided — skipping content generation")
            return []

        notes_summary = _build_notes_summary(notes)
        trends_summary = _build_trends_summary(trends or [])
        notes_used = [n.file_path for n in notes]

        pieces: list[ContentPiece] = []

        generators = [
            (self._generate_daily_update, ContentType.DAILY_UPDATE, Platform.TWITTER),
            (self._generate_daily_update, ContentType.DAILY_UPDATE, Platform.LINKEDIN),
            (self._generate_linkedin_post, ContentType.THREAD, Platform.LINKEDIN),
            (self._generate_twitter_thread, ContentType.THREAD, Platform.TWITTER),
            (self._generate_hot_take, ContentType.HOT_TAKE, Platform.TWITTER),
            (self._generate_instagram_caption, ContentType.CAPTION, Platform.INSTAGRAM),
            (self._generate_video_script, ContentType.VIDEO_SCRIPT, Platform.YOUTUBE),
        ]

        for gen_func, content_type, platform in generators:
            try:
                body = gen_func(
                    notes_summary=notes_summary,
                    trends_summary=trends_summary,
                    day_number=day_number,
                )
                pieces.append(ContentPiece(
                    content_type=content_type,
                    platform=platform,
                    title=f"Day {day_number}",
                    body=body,
                    day_number=day_number,
                    generated_date=date or datetime.now(UTC).strftime("%Y-%m-%d"),
                    notes_used=notes_used,
                ))
                log.info("Generated %s for %s", content_type.value, platform.value)
            except Exception as e:
                log.error("Failed to generate %s for %s: %s", content_type.value, platform.value, e)

        return pieces

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _generate_linkedin_post(
        self, notes_summary: str, trends_summary: str, day_number: int,
    ) -> str:
        prompt = LINKEDIN_PROMPT.format(
            day_number=day_number, notes_summary=notes_summary, trends_summary=trends_summary,
        )
        return self._call_claude(prompt)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _generate_twitter_thread(
        self, notes_summary: str, trends_summary: str, day_number: int,
    ) -> str:
        prompt = TWITTER_THREAD_PROMPT.format(
            day_number=day_number, notes_summary=notes_summary,
        )
        return self._call_claude(prompt)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _generate_hot_take(
        self, notes_summary: str, trends_summary: str, day_number: int,
    ) -> str:
        prompt = HOT_TAKE_PROMPT.format(
            notes_summary=notes_summary, trends_summary=trends_summary,
        )
        return self._call_grok(prompt)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _generate_instagram_caption(
        self, notes_summary: str, trends_summary: str, day_number: int,
    ) -> str:
        prompt = INSTAGRAM_CAPTION_PROMPT.format(
            day_number=day_number, notes_summary=notes_summary,
        )
        return self._call_claude(prompt)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _generate_video_script(
        self, notes_summary: str, trends_summary: str, day_number: int,
    ) -> str:
        prompt = VIDEO_SCRIPT_PROMPT.format(notes_summary=notes_summary)
        return self._call_claude(prompt)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _generate_daily_update(
        self, notes_summary: str, trends_summary: str, day_number: int,
    ) -> str:
        prompt = DAILY_UPDATE_PROMPT.format(
            day_number=day_number, notes_summary=notes_summary,
        )
        return self._call_claude(prompt)

    def generate_code_challenge(
        self, notes: list[ObsidianNote],
    ) -> dict | None:
        if not notes:
            return None
        notes_summary = _build_notes_summary(notes)
        prompt = CODE_CHALLENGE_PROMPT.format(notes_summary=notes_summary)
        try:
            raw = self._call_claude(prompt)
        except Exception as e:
            log.error("Code challenge generation failed: %s", e)
            return None

        text = raw.strip()
        if text == "NO_CHALLENGE":
            log.info("Claude decided no code challenge fits today's topic")
            return None

        for fence in ("```json", "```"):
            if text.startswith(fence):
                text = text[len(fence):]
            if text.endswith("```"):
                text = text[:-3]
        text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            log.warning("Failed to parse code challenge JSON: %s", text[:200])
            return None

        required = ("code", "language", "vulnerability", "hint")
        if not all(k in data for k in required):
            log.warning("Code challenge JSON missing required fields")
            return None

        return data

    def _call_claude(self, prompt: str) -> str:
        if not self._anthropic_key:
            raise RuntimeError("No Anthropic API key configured")
        client = Anthropic(api_key=self._anthropic_key)
        response = client.messages.create(
            model=self._writer_model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def _call_grok(self, prompt: str) -> str:
        if not self._xai_key:
            log.warning("No xAI key — falling back to Claude for hot take")
            return self._call_claude(prompt)
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._xai_key}"},
                json={
                    "model": self._hot_take_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.9,
                },
            )
            resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def _build_notes_summary(notes: list[ObsidianNote]) -> str:
    parts = []
    for i, note in enumerate(notes, 1):
        lines = [f"### Task {i}: {note.title}"]
        if note.track:
            lines.append(f"Track: {note.track}")
        if note.task_type:
            lines.append(f"Type: {note.task_type}")
        if note.key_takeaways:
            lines.append("Key Takeaways:")
            for t in note.key_takeaways:
                lines.append(f"  - {t}")
        if note.content:
            content_preview = note.content[:500]
            lines.append(f"Content: {content_preview}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _build_trends_summary(trends: list[TrendItem]) -> str:
    if not trends:
        return "No trending topics available."
    parts = []
    for t in trends[:5]:
        parts.append(f"- {t.topic} (relevance: {t.relevance_score:.1f}): {t.context}")
    return "\n".join(parts)
