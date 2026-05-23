# Content Creation Agent

## Project Overview
AI-powered educational content platform that transforms daily Obsidian learning notes into engaging, multi-platform social media content. Produces educational content designed for a broad tech audience — security + AI topics explained so clearly a 16-year-old can follow. Content targets Twitter/X, LinkedIn, Instagram, and YouTube.

## Philosophy
- **Educational, not journaling** — "Here's how SSRF works" not "I learned about SSRF"
- **Feynman technique** — explain complex topics using simple analogies and real examples
- **Accessible to all levels** — a 16-year-old should understand every post
- **Never say "I learned"** — always teach the audience directly
- **One-stop security+AI channel** — rich, engaging educational content across all formats

## Tech Stack
- Python 3.12, managed with uv
- Claude Sonnet 4 (Anthropic SDK) — educational content writing
- Grok 3 Mini (xAI API) — X/Twitter trends + surprising facts
- Perplexity Sonar — cross-platform trend research
- Gemini 2.5 Flash (Google GenAI SDK) — YouTube trends + SEO/hashtag optimization
- OpenAI gpt-image-1 — concept art for day cards
- Playwright (Python) — HTML template → PNG screenshots, Puppeteer (Node.js) fallback
- Buffer API — social media post scheduling (not yet connected)
- Jinja2 — HTML template rendering
- Click for CLI
- Pydantic for config validation and data models
- SQLite for state persistence
- tenacity for API retry logic
- httpx for API calls
- python-frontmatter for Obsidian notes parsing
- python-dotenv for auto-loading .env

## Project Structure
- `src/content_agent/` — main package (src layout)
- `src/content_agent/cli.py` — Click CLI (daily, status, history, init, preview, pending, ingest)
- `src/content_agent/config.py` — Pydantic config validation
- `src/content_agent/models.py` — Data models (ObsidianNote, ContentPiece, ImageAsset, etc.)
- `src/content_agent/ingest.py` — Obsidian vault notes parser (YAML frontmatter + markdown) + linked note resolution
- `src/content_agent/research.py` — Trend research (Grok, Perplexity, Gemini)
- `src/content_agent/writer.py` — Educational content writing (Claude Sonnet, Grok) + image content generation
- `src/content_agent/images.py` — Image generation (GPT-4o concept art + HTML templates)
- `src/content_agent/seo.py` — SEO & hashtag optimization
- `src/content_agent/publisher.py` — Buffer API post scheduling
- `src/content_agent/state/store.py` — SQLite state manager
- `src/content_agent/templates/` — Jinja2 HTML templates
  - `day_card.html` — Day number + topic + concept art background
  - `code_challenge.html` — "Spot the Bug" vulnerable code display
  - `comparison_card.html` — Vulnerable vs Secure side-by-side code comparison
  - `key_fact.html` — Bold shareable statistic/fact card
  - `carousel_slide.html` — Multi-slide educational breakdown (cover + slides)
- `tests/` — test suite (89 tests)

## Key Commands
```bash
uv run content daily                # full pipeline: ingest → research → write → images → SEO → persist → publish
uv run content daily --no-publish   # generate without scheduling posts
uv run content daily --force        # regenerate for today
uv run content daily --date 2026-05-23
uv run content ingest               # parse today's Obsidian notes
uv run content ingest --date 2026-05-23
uv run content status               # show pipeline status
uv run content history              # show recent posted content
uv run content pending              # show unposted content
uv run content preview <id>         # preview a content piece
uv run content init                 # initialize DB and output dirs
uv run pytest tests/ -v             # run tests (89 tests)
```

## Pipeline Flow
1. **Ingest**: Read Obsidian notes for target date (YAML frontmatter + markdown parsing), resolve [[linked notes]] one level deep
2. **Research**: Query Grok (X trends), Perplexity (web trends), Gemini (YouTube trends) in parallel
3. **Write**: Generate 5 educational content pieces via Claude Sonnet + Grok + educational image content (code challenge, comparison, key fact, carousel) via Claude
4. **Images**: Generate concept art (GPT-4o gpt-image-1), day card with concept overlay (HTML→PNG), code challenge (HTML→PNG), comparison card (HTML→PNG), key fact card (HTML→PNG), carousel slides (HTML→PNG)
5. **SEO**: Optimize hashtags per platform (Gemini Flash), calculate posting times
6. **Persist**: Save all to SQLite (content pieces, images, trends, daily run)
7. **Publish**: Schedule posts via Buffer API at optimal times

## Content Types (Educational)
- **Daily Lesson** — Day X progress card explaining what was studied, with teaching voice (Twitter + LinkedIn)
- **Deep Dive** — Multi-paragraph educational breakdown of a concept (Twitter thread / LinkedIn article)
- **Concept Breakdown** — "Here's how X works" educational post using analogies (LinkedIn)
- **Surprising Fact** — Attention-grabbing fact/stat via Grok, tied to trends (Twitter)
- **Micro Lesson** — Short, accessible educational snippet for Instagram
- **Code Challenge** — "Spot the Bug" images with realistic vulnerable code (Twitter + LinkedIn)

## Image Types
- **Day Card** — GPT-4o concept art background + HTML text overlay (day number, topic, takeaway)
- **Code Challenge** — Monospace code display with vulnerability hint
- **Comparison Card** — Side-by-side "Vulnerable" (red) vs "Secure" (green) code
- **Key Fact Card** — Bold headline stat/fact with source attribution
- **Carousel Slide** — Multi-slide educational series (cover + numbered slides)

## Image Generation Strategy
- Concept art: GPT-4o (gpt-image-1) — artistic cyberpunk visuals, no text
- Day cards: GPT-4o concept art as background + HTML/CSS text overlay → Playwright screenshot (wait_until=networkidle for image loading)
- Terminal/hacker style: Carousel, Code Challenge, Comparison Card — dark terminal aesthetic with macOS title bar, JetBrains Mono, green accents, terminal code blocks
- Twitter screenshot style: Key Fact Card — pure black bg, profile pic, verified badge, large white text
- All text-heavy images: HTML/CSS templates → Playwright screenshot (full_page=True, dynamic height), Puppeteer fallback
- Templates use min-height: 1080px (not fixed height) — content expands naturally, never clips
- Profile image: `src/content_agent/templates/assets/profile.png`
- Social handle: @techycodec08

## Note Intelligence
- Full note body passed to models (no truncation)
- Linked notes resolved: [[wiki-links]] → find file by stem → read content (one level deep, not recursive)
- Key takeaways extracted from ## Key Takeaways section
- YAML frontmatter: title, track, task_type, date, tags, difficulty

## State (SQLite)
All state in `data/content.db`:
- `content_pieces` — generated content with status tracking
- `images` — generated image assets
- `trend_reports` — trend research results
- `daily_runs` — pipeline run history with day number tracking
- `engagement` — post engagement metrics (likes, shares, comments, views)
- `meta` — key-value metadata

## Environment Variables
- `ANTHROPIC_API_KEY` — Claude Sonnet for content writing
- `OPENAI_API_KEY` — GPT-4o concept images
- `XAI_API_KEY` — Grok for X trends + surprising facts
- `GOOGLE_API_KEY` — Gemini for YouTube trends + SEO
- `PERPLEXITY_API_KEY` — Perplexity Sonar for web trends
- `BUFFER_ACCESS_TOKEN` — Buffer for post scheduling

## Error Handling
- Missing API keys trigger graceful fallbacks (default hashtags, skip image generation, etc.)
- All API calls wrapped with tenacity (3 attempts, exponential backoff)
- Missing Obsidian vault or no notes for date: clear error message + exit
- Dedup: same-day runs blocked unless --force

## Tests
89 tests across 8 test files:
- `test_config.py` (8) — config validation, defaults, time format, YAML loading
- `test_models.py` (9) — all Pydantic models, enums
- `test_store.py` (13) — SQLite CRUD, status updates, stats, day tracking, engagement
- `test_ingest.py` (14) — Obsidian parsing, frontmatter, sections, links, edge cases
- `test_research.py` (8) — trend JSON parsing (clean, fenced, invalid, empty)
- `test_writer.py` (13) — code challenge, comparison, key fact, carousel generation + JSON parsing
- `test_seo.py` (10) — hashtag parsing, posting times, content optimization
- `test_images.py` (14) — code block extraction, HTML template generation, brand colors, all image types
