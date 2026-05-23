# Content Creation Agent

An AI-powered content pipeline that transforms daily Obsidian learning notes into multi-platform social media content. Built for a 6-month security + AI learning journey — one note in, six content pieces out.

## What It Does

Write an Obsidian note about what you learned today. The agent reads it (including linked notes), researches current trends, generates platform-specific content, creates visual assets, optimizes for SEO, and saves everything to a database ready for scheduling.

**Per day, the agent produces:**
- 6 text content pieces (daily update, LinkedIn post, Twitter thread, hot take, Instagram caption, video script)
- 1 AI-generated concept art image (GPT-4o)
- 1 day card image (concept art + text overlay)
- 1 "Spot the Bug" code challenge image (when the topic fits)
- 1 TTS narration audio file
- Platform-optimized hashtags and posting times

## Architecture

```
Obsidian Note (markdown + YAML frontmatter)
    |
    v
[1. Ingest] ── parse notes + resolve [[linked notes]]
    |
    v
[2. Research] ── Grok (X trends) + Perplexity (web) + Gemini (YouTube)
    |
    v
[3. Write] ── Claude Sonnet 4 (5 pieces) + Grok 3 Mini (hot take)
    |         + Claude generates "Spot the Bug" code challenge
    v
[4. Images] ── GPT-4o concept art → HTML/CSS overlay → Playwright screenshot
    |           + code challenge HTML → Playwright screenshot
    v
[5. Video] ── OpenAI TTS narration → Remotion assembly (WIP)
    |
    v
[6. SEO] ── Gemini Flash hashtag optimization + posting time calculation
    |
    v
[7. Persist] ── SQLite (content, images, videos, trends, run history)
    |
    v
[8. Publish] ── Buffer API scheduling (not yet connected)
```

## AI Models

| Model | Provider | Role | Cost/day |
|-------|----------|------|----------|
| Claude Sonnet 4 | Anthropic | Content writing (5 pieces + code challenge) | ~$0.10 |
| Grok 3 Mini | xAI | X/Twitter trends + hot takes | ~$0.02 |
| Gemini 2.5 Flash | Google | YouTube trends + SEO/hashtags | ~$0.01 |
| gpt-image-1 | OpenAI | Concept art for day cards | ~$0.07 |
| gpt-4o-mini-tts | OpenAI | Video narration | ~$0.02 |
| Perplexity Sonar | Perplexity | Web trend research | ~$0.01 |

**Total: ~$0.25/day (~$7.50/month)** + Buffer scheduling ($15/month)

## Content Types

| Type | Platform | Generator | Description |
|------|----------|-----------|-------------|
| Daily Update | Twitter | Claude | Day N progress post, personal learning narrative |
| LinkedIn Post | LinkedIn | Claude | Thought leadership, professional tone, 150-300 words |
| Twitter Thread | Twitter | Claude | 4-6 tweet educational breakdown of a concept |
| Hot Take | Twitter | Grok | One spicy, scroll-stopping tweet tied to trends |
| Instagram Caption | Instagram | Claude | 50-100 words, accessible to non-experts |
| Video Script | YouTube | Claude | 30-60s narration with scene descriptions |
| Code Challenge | Twitter/LinkedIn | Claude + HTML | "Spot the Bug" — realistic vulnerable code image |

## Image Generation

AI models cannot reliably render text. The agent uses a hybrid approach:

- **GPT-4o** generates artistic concept art (cyberpunk-style, no text) as the day card background
- **HTML/CSS templates** render all text (day number, topic, takeaway, code) with pixel-perfect control
- **Playwright** screenshots the HTML at 1080x1080 to produce the final PNG
- Code challenges use monospace fonts and syntax-aware styling via HTML templates

## Note Intelligence

The agent reads your full Obsidian notes, not just summaries:

- **Full note body** — no truncation, complete learning content
- **Linked notes** — resolves `[[wiki-links]]` and reads the linked note content (one level deep)
- **Key takeaways** — extracted from `## Key Takeaways` section
- **YAML frontmatter** — title, track, task_type, date, tags, difficulty

This means if your main note says "Learned about SQL Injection" and links to `[[union-based-sqli]]` and `[[defense-parameterized-queries]]`, the model reads all three — producing technically rich content instead of surface-level posts.

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js 18+ (for Playwright browsers)
- Obsidian vault with YAML frontmatter notes

### Installation

```bash
git clone https://github.com/deev-pal08/Content-Creation-Agent.git
cd Content-Creation-Agent

# Install Python dependencies
uv sync

# Install Playwright browsers
uv run playwright install chromium
```

### Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Add your API keys to `.env`:
```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
XAI_API_KEY=xai-...
GOOGLE_API_KEY=AI...
PERPLEXITY_API_KEY=pplx-...    # optional — $50 minimum
BUFFER_ACCESS_TOKEN=...         # optional — for post scheduling
```

3. Configure your Obsidian vault path in `config.yaml`:
```yaml
obsidian:
  vault_path: ~/path/to/your/vault
```

### Usage

```bash
# Run the full pipeline for today
uv run content daily --no-publish

# Run for a specific date
uv run content daily --no-publish --date 2026-05-25

# Force regenerate (bypass duplicate detection)
uv run content daily --no-publish --force

# Just ingest notes (no AI calls)
uv run content ingest --date 2026-05-25

# Check pipeline status
uv run content status

# View content history
uv run content history

# See unposted content
uv run content pending

# Preview a specific piece
uv run content preview <id>

# Initialize database and directories
uv run content init
```

## Obsidian Note Format

Notes must have YAML frontmatter with at least a `date` field:

```markdown
---
title: "Prompt Injection Attacks on LLMs"
track: ai_security
task_type: read
date: 2026-05-25
tags: [prompt-injection, llm-security, owasp]
---

## Key Takeaways
- Prompt injection is the #1 vulnerability in LLM applications
- LLMs cannot distinguish between instructions and data

## Notes
Your detailed learning notes here...

See also: [[indirect-prompt-injection]], [[rag-security-defenses]]
```

## Project Structure

```
src/content_agent/
    cli.py            # Click CLI — 7 commands
    config.py         # Pydantic config validation
    models.py         # Data models (ObsidianNote, ContentPiece, ImageAsset, etc.)
    ingest.py         # Obsidian vault parser + linked note resolution
    research.py       # Trend research (Grok, Perplexity, Gemini)
    writer.py         # Content writing (Claude, Grok) + code challenge generation
    images.py         # Image generation (GPT-4o + HTML templates + Playwright)
    video.py          # Video generation (TTS + Remotion)
    seo.py            # SEO optimization (Gemini Flash)
    publisher.py      # Buffer API scheduling
    state/store.py    # SQLite state manager
    templates/        # Jinja2 HTML templates
        day_card.html
        code_challenge.html
tests/                # 90 tests
config.yaml           # Pipeline configuration
```

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_writer.py -v
```

90 tests across 8 files covering config validation, data models, SQLite operations, Obsidian parsing, trend research parsing, code challenge generation, SEO optimization, image template rendering, and video script parsing.

## Roadmap

- [x] Notes ingestion with linked note resolution
- [x] Multi-source trend research (Grok + Perplexity + Gemini)
- [x] 6-piece content generation (Claude + Grok)
- [x] AI code challenge generation (Claude decides topic fit)
- [x] GPT-4o concept art + HTML/CSS day cards
- [x] Code challenge image rendering (Playwright)
- [x] TTS narration generation (OpenAI)
- [x] SEO/hashtag optimization (Gemini Flash)
- [x] SQLite persistence with day tracking
- [ ] Remotion video assembly (React components)
- [ ] Buffer API integration (post scheduling)
- [ ] Engagement tracking and analytics

## License

MIT
