# Content Creation Agent

An AI-powered educational content platform that transforms daily Obsidian learning notes into multi-platform social media content. Security + AI topics explained so clearly a 16-year-old can follow — one note in, five content pieces + five image types out.

## What It Does

Write an Obsidian note about what you studied today. The agent reads it (including linked notes), researches current trends, generates educational content for every major platform, creates visual assets, optimizes for SEO, and saves everything to a database ready for scheduling.

**Per day, the agent produces:**
- 5 educational text pieces (daily lesson, deep dive, concept breakdown, surprising fact, micro lesson)
- 1 AI-generated concept art image (GPT-4o)
- 1 day card (concept art + text overlay)
- 1 "Spot the Bug" code challenge image (when the topic fits)
- 1 comparison card — vulnerable vs secure code side-by-side
- 1 key fact card — shareable statistic/fact
- 1 carousel — multi-slide educational breakdown (cover + slides)
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
[3. Write] ── Claude Sonnet 4 (educational content) + Grok 3 Mini (surprising facts)
    |           + Claude generates code challenge, comparison, key fact, carousel data
    v
[4. Images] ── GPT-4o concept art → HTML/CSS overlay → Playwright screenshot
    |           + comparison card, key fact card, carousel slides (all HTML→PNG)
    v
[5. SEO] ── Gemini Flash hashtag optimization + posting time calculation
    |
    v
[6. Persist] ── SQLite (content, images, trends, run history)
    |
    v
[7. Publish] ── Buffer API scheduling (not yet connected)
```

## Educational Content Philosophy

This agent doesn't journal — it teaches. Every piece of content follows these principles:

- **Feynman Technique** — if you can't explain it simply, you don't understand it well enough
- **Analogies are mandatory** — every concept gets a real-world comparison
- **No "I learned" language** — always address the audience directly ("Here's how SSRF works")
- **Accessible to all levels** — a 16-year-old should understand every post
- **Real examples** — concrete code, real attack scenarios, actual defense patterns

## AI Models

| Model | Provider | Role | Cost/day |
|-------|----------|------|----------|
| Claude Sonnet 4 | Anthropic | Educational writing (5 pieces + image content) | ~$0.10 |
| Grok 3 Mini | xAI | X/Twitter trends + surprising facts | ~$0.02 |
| Gemini 2.5 Flash | Google | YouTube trends + SEO/hashtags | ~$0.01 |
| gpt-image-1 | OpenAI | Concept art for day cards | ~$0.07 |
| Perplexity Sonar | Perplexity | Web trend research | ~$0.01 |

**Total: ~$0.21/day (~$6.30/month)** + Buffer scheduling ($15/month)

## Content Types

| Type | Platform | Generator | Description |
|------|----------|-----------|-------------|
| Daily Lesson | Twitter + LinkedIn | Claude | Day N educational card explaining the topic studied |
| Deep Dive | Twitter (thread) | Claude | 4-6 tweet educational breakdown of a concept |
| Concept Breakdown | LinkedIn | Claude | "Here's how X works" with analogies, 150-300 words |
| Surprising Fact | Twitter | Grok | Attention-grabbing fact/stat tied to trends |
| Micro Lesson | Instagram | Claude | 50-100 word accessible educational snippet |
| Code Challenge | Twitter/LinkedIn | Claude + HTML | "Spot the Bug" — realistic vulnerable code image |

## Image Types

| Type | Method | Description |
|------|--------|-------------|
| Day Card | GPT-4o art + HTML overlay | Concept art background with day number + topic text |
| Code Challenge | HTML/CSS → Playwright | Monospace vulnerable code with "Find the vulnerability" |
| Comparison Card | HTML/CSS → Playwright | Red "Vulnerable" vs Green "Secure" side-by-side |
| Key Fact Card | HTML/CSS → Playwright | Bold headline stat with source attribution |
| Carousel | HTML/CSS → Playwright | Multi-slide series: cover + numbered educational slides |

AI models cannot reliably render text. The agent uses HTML/CSS templates for all text-heavy images, screenshotted via Playwright at 1080x1080 for pixel-perfect results.

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
    writer.py         # Educational content writing (Claude, Grok) + image content generation
    images.py         # Image generation (GPT-4o + HTML templates + Playwright)
    seo.py            # SEO optimization (Gemini Flash)
    publisher.py      # Buffer API scheduling
    state/store.py    # SQLite state manager
    templates/
        day_card.html         # Day card with concept art background
        code_challenge.html   # "Spot the Bug" vulnerable code
        comparison_card.html  # Vulnerable vs Secure side-by-side
        key_fact.html         # Bold shareable fact/stat
        carousel_slide.html   # Multi-slide educational series
tests/                # 89 tests
config.yaml           # Pipeline configuration
```

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_writer.py -v
```

89 tests across 8 files covering config validation, data models, SQLite operations, Obsidian parsing, trend research parsing, educational content generation, SEO optimization, and all 5 image template types.

## Roadmap

- [x] Notes ingestion with linked note resolution
- [x] Multi-source trend research (Grok + Perplexity + Gemini)
- [x] 5-piece educational content generation (Claude + Grok)
- [x] AI code challenge generation (Claude decides topic fit)
- [x] Comparison card generation (vulnerable vs secure code)
- [x] Key fact card generation (shareable statistics)
- [x] Carousel generation (multi-slide educational series)
- [x] GPT-4o concept art + HTML/CSS day cards
- [x] 5 HTML/CSS image templates (Playwright rendering)
- [x] SEO/hashtag optimization (Gemini Flash)
- [x] SQLite persistence with day tracking
- [ ] Buffer API integration (post scheduling)
- [ ] Engagement tracking and analytics

## License

MIT
