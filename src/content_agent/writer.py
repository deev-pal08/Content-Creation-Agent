"""Content writer — Claude Sonnet (educational posts, threads, scripts) + Grok (surprising facts)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import httpx
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from content_agent.models import ContentPiece, ContentType, ObsidianNote, Platform, TrendItem

log = logging.getLogger(__name__)

DAILY_LESSON_PROMPT = """You are a security educator creating a concise daily lesson for Twitter.
Topic: Day {day_number} of a security + AI education series.

Study material (your source — teach FROM this, do not summarize it):
{notes_summary}

Your job: Teach ONE concept from today's material so clearly that a 16-year-old could explain it to a friend.

Rules:
- Open with a real-world analogy or scenario (not "Today I learned")
- Explain the concept — what it is, why it matters, how it works
- Include one concrete example or real incident
- End with a practical takeaway the reader can use
- 100-200 words. No emojis. No hashtags.
- NEVER use phrases like "I learned", "my journey", "today I explored", "I discovered"
- Write as a teacher, not a student. You are TEACHING, not journaling.
- Tone: clear, direct, genuinely interesting — like a smart friend explaining something cool

Return ONLY the post text."""

DEEP_DIVE_PROMPT = """You are a security educator writing an in-depth LinkedIn lesson.
Day {day_number} of a security + AI education series.

Study material (your source — teach FROM this, do not summarize it):
{notes_summary}

Trending topics to connect if relevant (ignore if they don't fit naturally):
{trends_summary}

Structure your post exactly like this:
1. HOOK (1-2 sentences): A surprising fact, counterintuitive truth, or "what if" scenario that creates curiosity
2. ANALOGY (1-2 sentences): Explain the core concept using a real-world analogy a teenager would understand
3. HOW IT WORKS (3-5 sentences): The technical explanation — clear, specific, with a concrete example
4. WHY IT MATTERS (2-3 sentences): Real-world impact — reference actual breaches, incidents, or statistics if available
5. WHAT YOU CAN DO (1-2 sentences): Actionable defense or takeaway the reader can apply
6. DISCUSSION (1 sentence): End with a thought-provoking question that invites genuine discussion

Rules:
- 250-400 words. No emojis. No hashtags in body.
- NEVER say "I learned", "my journey", "today I discovered"
- Write as an educator who deeply understands this topic
- Use concrete examples, not abstract statements
- A 16-year-old should follow the logic even without knowing all the terms
- If you reference a vulnerability or attack, show HOW it works, not just THAT it exists

Return ONLY the post text."""

CONCEPT_BREAKDOWN_PROMPT = """You are a security educator creating a Twitter thread that teaches a concept step by step.
Day {day_number} of a security + AI education series.

Study material (teach FROM this):
{notes_summary}

Structure:
- Tweet 1: Hook — a surprising claim, question, or scenario that creates curiosity
- Tweets 2-4: Teach the concept progressively. Each tweet adds ONE new idea. Use analogies.
- Tweet 5: Real-world example or consequence (actual breach, real tool, specific scenario)
- Tweet 6: Actionable takeaway — what should the reader do or remember?

Rules:
- 5-6 tweets, each under 280 characters
- Use numbering: 1/, 2/, etc.
- Each tweet must be understandable on its own AND build on the previous
- Use analogies to explain technical concepts ("Think of it like...")
- No emojis. No hashtags.
- NEVER say "I learned", "my journey" — you are TEACHING
- Write so a curious 16-year-old could follow the entire thread

Return each tweet on its own line, separated by blank lines."""

SURPRISING_FACT_PROMPT = """You are a security educator writing a single tweet that stops people mid-scroll.

Study material:
{notes_summary}

Trending topics on X right now:
{trends_summary}

Your job: Extract the most surprising, counterintuitive, or alarming FACT from today's material and present it in a way that educates through shock value.

Rules:
- One single tweet, under 280 characters
- Must be FACTUALLY accurate — based on the study material, not invented
- Format options: "X% of Y...", "Most people think X. Actually, Y.", "Fun fact: [genuinely alarming thing]"
- The reader should learn something real, not just be entertained
- If a trending topic connects naturally, weave it in. If not, skip trends entirely.
- No emojis. No hashtags.
- NOT a personal opinion — a genuine educational fact that surprises

Return ONLY the tweet text."""

MICRO_LESSON_PROMPT = """You are a security educator writing an Instagram caption that teaches one concept.
Day {day_number} of a security + AI education series.

Study material:
{notes_summary}

Your job: Teach exactly ONE concept so simply that someone with zero security knowledge walks away understanding it.

Rules:
- 60-120 words
- Start with a bold, attention-grabbing statement about the concept
- Explain it using a simple analogy or everyday comparison
- Give one specific example
- End with "Now you know" moment or a question that makes the reader feel smart
- Conversational tone — like explaining to a curious friend at a coffee shop
- No hashtags (added separately). No emojis.
- NEVER say "I learned", "my journey", "today I explored"
- A 16-year-old should understand every sentence

Return ONLY the caption text."""

VISUAL_LESSON_PROMPT = """You are a security educator writing a 30-45 second video script that teaches through storytelling.

Study material:
{notes_summary}

Structure your script as a STORY:
1. [Scene 1 — Hook]: Start with a relatable character or scenario. "Imagine you're a developer..." / "Picture this: a user clicks..."
2. [Scene 2 — The Problem]: Show what goes wrong. Make the viewer feel the danger.
3. [Scene 3 — The Explanation]: Break down HOW the vulnerability/concept works. Use the simplest possible language.
4. [Scene 4 — The Impact]: Real-world consequence. Actual numbers, actual breaches, actual stakes.
5. [Scene 5 — The Fix/Takeaway]: What to do about it. One clear, actionable lesson.

Rules:
- Include scene descriptions in [brackets] for visual cues
- Target 80-120 words of narration (30-45 seconds spoken)
- Think Kurzgesagt meets cybersecurity — visual, engaging, educational
- No jargon without immediately explaining it
- A 16-year-old watching this should understand AND find it interesting
- NEVER say "I learned" or "my journey" — you are a teacher

Return the script in this format:
[Scene description]
Narration text

[Scene description]
Narration text
..."""

CODE_CHALLENGE_PROMPT = """You are a security educator creating a "Spot the Bug" code review challenge.

Study material:
{notes_summary}

Your task:
1. Analyze the study material
2. Decide whether a realistic code review challenge can be created from this topic
3. If yes, write a short, realistic code snippet (8-20 lines) that contains a subtle security vulnerability related to the topic

If the topic is too theoretical or abstract for a code challenge, respond with exactly: NO_CHALLENGE

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
- The vulnerability MUST relate to the study material"""

COMPARISON_PROMPT = """You are a security educator creating a "Vulnerable vs Secure" code comparison.

Study material:
{notes_summary}

Your task: Create a side-by-side comparison showing the WRONG way and the RIGHT way to handle a security concern from today's topic.

If the topic doesn't lend itself to a code comparison, respond with exactly: NO_COMPARISON

Otherwise, respond with ONLY valid JSON (no markdown fencing, no extra text):
{{
    "title": "Short title (e.g. 'Input Handling', 'Token Storage', 'Query Construction')",
    "vulnerable_label": "What the bad approach is (e.g. 'String Concatenation')",
    "vulnerable_code": "3-8 lines of vulnerable code",
    "secure_label": "What the good approach is (e.g. 'Parameterized Query')",
    "secure_code": "3-8 lines of secure code",
    "language": "python",
    "explanation": "One sentence explaining why the secure version is better"
}}

Guidelines:
- Both code snippets must be short (3-8 lines each) — they'll be displayed side by side
- Use realistic variable names and patterns
- The difference should be immediately visible when placed side by side
- The explanation should be understandable by a beginner"""

KEY_FACT_PROMPT = """You are a security educator creating a shareable key fact card.

Study material:
{notes_summary}

Your task: Extract the single most important, memorable, shareable fact from today's topic.

Respond with ONLY valid JSON (no markdown fencing, no extra text):
{{
    "headline": "A bold, attention-grabbing statement (8-15 words max)",
    "explanation": "2-3 sentences explaining why this matters. Use simple language. Be specific — numbers, names, real examples.",
    "source": "Where this fact comes from (e.g. 'OWASP Top 10', 'Capital One Breach 2019', research paper name)"
}}

Guidelines:
- The headline should work as a standalone statement someone would screenshot and share
- The explanation adds context without being a full article
- Be factually accurate — base this on the study material
- A 16-year-old should understand both the headline and explanation"""

CAROUSEL_PROMPT = """You are a security educator creating a multi-slide educational carousel for Instagram/LinkedIn.

Study material:
{notes_summary}

Create a 5-6 slide educational breakdown that teaches the concept progressively.

Respond with ONLY valid JSON (no markdown fencing, no extra text):
{{
    "title": "Carousel title (shown on cover slide)",
    "subtitle": "One-line hook or question",
    "slides": [
        {{
            "heading": "Slide heading (3-6 words)",
            "body": "2-4 sentences teaching one specific point. Simple language, concrete examples.",
            "footer": "Optional one-line tip or note"
        }}
    ]
}}

Rules for each slide:
- Each slide teaches exactly ONE idea
- Progressive: slide 2 builds on slide 1, etc.
- Use analogies and examples, not abstract definitions
- A 16-year-old should understand every slide
- Heading should be engaging, not academic (not "Introduction" or "Background")
- 5-6 slides total (not counting cover slide)
- Last slide should be an actionable takeaway or call to action"""


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
            (self._generate_daily_lesson, ContentType.DAILY_LESSON, Platform.TWITTER),
            (self._generate_deep_dive, ContentType.DEEP_DIVE, Platform.LINKEDIN),
            (self._generate_concept_breakdown, ContentType.CONCEPT_BREAKDOWN, Platform.TWITTER),
            (self._generate_surprising_fact, ContentType.SURPRISING_FACT, Platform.TWITTER),
            (self._generate_micro_lesson, ContentType.MICRO_LESSON, Platform.INSTAGRAM),
            (self._generate_visual_lesson, ContentType.VISUAL_LESSON, Platform.YOUTUBE),
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
    def _generate_daily_lesson(
        self, notes_summary: str, trends_summary: str, day_number: int,
    ) -> str:
        prompt = DAILY_LESSON_PROMPT.format(
            day_number=day_number, notes_summary=notes_summary,
        )
        return self._call_claude(prompt)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _generate_deep_dive(
        self, notes_summary: str, trends_summary: str, day_number: int,
    ) -> str:
        prompt = DEEP_DIVE_PROMPT.format(
            day_number=day_number, notes_summary=notes_summary, trends_summary=trends_summary,
        )
        return self._call_claude(prompt)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _generate_concept_breakdown(
        self, notes_summary: str, trends_summary: str, day_number: int,
    ) -> str:
        prompt = CONCEPT_BREAKDOWN_PROMPT.format(
            day_number=day_number, notes_summary=notes_summary,
        )
        return self._call_claude(prompt)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _generate_surprising_fact(
        self, notes_summary: str, trends_summary: str, day_number: int,
    ) -> str:
        prompt = SURPRISING_FACT_PROMPT.format(
            notes_summary=notes_summary, trends_summary=trends_summary,
        )
        return self._call_grok(prompt)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _generate_micro_lesson(
        self, notes_summary: str, trends_summary: str, day_number: int,
    ) -> str:
        prompt = MICRO_LESSON_PROMPT.format(
            day_number=day_number, notes_summary=notes_summary,
        )
        return self._call_claude(prompt)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _generate_visual_lesson(
        self, notes_summary: str, trends_summary: str, day_number: int,
    ) -> str:
        prompt = VISUAL_LESSON_PROMPT.format(notes_summary=notes_summary)
        return self._call_claude(prompt)

    def generate_code_challenge(
        self, notes: list[ObsidianNote],
    ) -> dict | None:
        if not notes:
            return None
        notes_summary = _build_notes_summary(notes)
        prompt = CODE_CHALLENGE_PROMPT.format(notes_summary=notes_summary)
        return self._parse_json_response(prompt, ("code", "language", "vulnerability", "hint"))

    def generate_comparison(
        self, notes: list[ObsidianNote],
    ) -> dict | None:
        if not notes:
            return None
        notes_summary = _build_notes_summary(notes)
        prompt = COMPARISON_PROMPT.format(notes_summary=notes_summary)
        return self._parse_json_response(
            prompt, ("title", "vulnerable_code", "secure_code", "language"),
            no_match_token="NO_COMPARISON",
        )

    def generate_key_fact(
        self, notes: list[ObsidianNote],
    ) -> dict | None:
        if not notes:
            return None
        notes_summary = _build_notes_summary(notes)
        prompt = KEY_FACT_PROMPT.format(notes_summary=notes_summary)
        return self._parse_json_response(prompt, ("headline", "explanation"))

    def generate_carousel(
        self, notes: list[ObsidianNote],
    ) -> dict | None:
        if not notes:
            return None
        notes_summary = _build_notes_summary(notes)
        prompt = CAROUSEL_PROMPT.format(notes_summary=notes_summary)
        return self._parse_json_response(prompt, ("title", "slides"))

    def _parse_json_response(
        self, prompt: str, required_fields: tuple, no_match_token: str = "NO_CHALLENGE",
    ) -> dict | None:
        try:
            raw = self._call_claude(prompt)
        except Exception as e:
            log.error("Generation failed: %s", e)
            return None

        text = raw.strip()
        if text == no_match_token:
            log.info("Claude decided this content type doesn't fit today's topic")
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
            log.warning("Failed to parse JSON response: %s", text[:200])
            return None

        if not all(k in data for k in required_fields):
            log.warning("JSON response missing required fields: %s", required_fields)
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
            log.warning("No xAI key — falling back to Claude for surprising fact")
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
        lines = [f"### Topic {i}: {note.title}"]
        if note.track:
            lines.append(f"Track: {note.track}")
        if note.task_type:
            lines.append(f"Type: {note.task_type}")
        if note.key_takeaways:
            lines.append("Key Takeaways:")
            for t in note.key_takeaways:
                lines.append(f"  - {t}")
        if note.content:
            lines.append(f"Content: {note.content}")
        if note.linked_content:
            lines.append("Linked Notes (detailed references):")
            for link_name, link_body in note.linked_content.items():
                lines.append(f"  --- {link_name} ---")
                lines.append(f"  {link_body}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _build_trends_summary(trends: list[TrendItem]) -> str:
    if not trends:
        return "No trending topics available."
    parts = []
    for t in trends[:5]:
        parts.append(f"- {t.topic} (relevance: {t.relevance_score:.1f}): {t.context}")
    return "\n".join(parts)
