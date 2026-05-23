# Content Creation Agent

## Project Overview
Multi-modal content creation agent that transforms daily Obsidian learning notes into social media content across Twitter/X, LinkedIn, Instagram, and YouTube. Acts as an automated brand manager and content team.

## Tech Stack
- Python 3.12, managed with uv
- Claude Sonnet 4 (Anthropic SDK) — content writing (posts, threads, captions, scripts)
- Grok 3 Mini (xAI API) — X/Twitter trends + hot takes
- Perplexity Sonar — cross-platform trend research
- Gemini 2.5 Flash (Google GenAI SDK) — YouTube trends + SEO/hashtag optimization
- OpenAI gpt-4o-mini-tts — video narration (TTS)
- Recraft V3 API — infographic image generation
- Ideogram V3 API — concept explainer images
- Playwright (Python) — HTML template → PNG screenshots (day cards, code challenges), Puppeteer (Node.js) fallback
- Remotion (Node.js) — programmatic video rendering
- Buffer API — social media post scheduling
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
- `src/content_agent/models.py` — Data models (ObsidianNote, ContentPiece, ImageAsset, VideoAsset, etc.)
- `src/content_agent/ingest.py` — Obsidian vault notes parser (YAML frontmatter + markdown)
- `src/content_agent/research.py` — Trend research (Grok, Perplexity, Gemini)
- `src/content_agent/writer.py` — Content writing (Claude Sonnet, Grok) + AI code challenge generation
- `src/content_agent/images.py` — Image generation (HTML templates + AI APIs), code challenge rendering
- `src/content_agent/video.py` — Video generation (TTS + Remotion)
- `src/content_agent/seo.py` — SEO & hashtag optimization
- `src/content_agent/publisher.py` — Buffer API post scheduling
- `src/content_agent/state/store.py` — SQLite state manager
- `src/content_agent/templates/` — Jinja2 HTML templates (day_card.html, code_challenge.html)
- `tests/` — test suite (91 tests)

## Key Commands
```bash
uv run content daily                # full pipeline: ingest → research → write → images → video → SEO → publish
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
uv run pytest tests/ -v             # run tests (91 tests)
```

## Pipeline Flow
1. **Ingest**: Read Obsidian notes for target date (YAML frontmatter + markdown parsing)
2. **Research**: Query Grok (X trends), Perplexity (web trends), Gemini (YouTube trends) in parallel
3. **Write**: Generate 7 content pieces via Claude Sonnet + Grok (daily updates, LinkedIn post, Twitter thread, hot take, IG caption, video script) + AI-generated code challenge
4. **Images**: Generate day card (HTML→PNG), code challenge from AI-generated data (HTML→PNG), infographic (Recraft), concept explainer (Ideogram)
5. **Video**: Generate narration (OpenAI TTS), assemble video (Remotion)
6. **SEO**: Optimize hashtags per platform (Gemini Flash), calculate posting times
7. **Persist**: Save all to SQLite (content pieces, images, videos, trends, daily run)
8. **Publish**: Schedule posts via Buffer API at optimal times

## Content Types
- **Daily Update** — Day X progress cards for Twitter + LinkedIn
- **Thread** — Educational thread explaining a concept for Twitter
- **LinkedIn Post** — Thought leadership post for LinkedIn
- **Hot Take** — Witty/edgy tweet via Grok for Twitter
- **Caption** — Instagram caption
- **Video Script** — 30-60s explainer for Reels/Shorts
- **Code Challenge** — "Spot the bug" images for Twitter + LinkedIn (Claude intelligently decides if today's topic suits a code challenge, generates realistic vulnerable code snippet)

## Image Generation Strategy
- Day cards + code challenges: HTML/CSS templates → Playwright screenshot (free, pixel-perfect), Puppeteer fallback
- Infographics: Recraft V3 API (vector SVG, brand style tools)
- Concept explainers: Ideogram V3 API (#1 text rendering)
- AI models cannot reliably render code — always use HTML templates for code

## State (SQLite)
All state in `data/content.db`:
- `content_pieces` — generated content with status tracking
- `images` — generated image assets
- `videos` — generated video assets
- `trend_reports` — trend research results
- `daily_runs` — pipeline run history with day number tracking
- `engagement` — post engagement metrics (likes, shares, comments, views)
- `meta` — key-value metadata

## Environment Variables
- `ANTHROPIC_API_KEY` — Claude Sonnet for content writing
- `OPENAI_API_KEY` — GPT-4o images + TTS narration
- `XAI_API_KEY` — Grok for X trends + hot takes
- `GOOGLE_API_KEY` — Gemini for YouTube trends + SEO
- `PERPLEXITY_API_KEY` — Perplexity Sonar for web trends
- `RECRAFT_API_KEY` — Recraft for infographic images
- `IDEOGRAM_API_KEY` — Ideogram for concept explainer images
- `BUFFER_ACCESS_TOKEN` — Buffer for post scheduling

## Error Handling
- Missing API keys trigger graceful fallbacks (default hashtags, skip image generation, etc.)
- All API calls wrapped with tenacity (3 attempts, exponential backoff)
- Missing Obsidian vault or no notes for date: clear error message + exit
- Dedup: same-day runs blocked unless --force

## Tests
91 tests across 8 test files:
- `test_config.py` (8) — config validation, defaults, time format, YAML loading
- `test_models.py` (10) — all Pydantic models, enums
- `test_store.py` (14) — SQLite CRUD, status updates, stats, day tracking, engagement
- `test_ingest.py` (14) — Obsidian parsing, frontmatter, sections, links, edge cases
- `test_research.py` (8) — trend JSON parsing (clean, fenced, invalid, empty)
- `test_writer.py` (8) — AI code challenge generation, JSON parsing, edge cases, notes summary
- `test_seo.py` (10) — hashtag parsing, posting times, content optimization
- `test_images.py` (11) — code block extraction, HTML template generation, brand colors, code challenge wiring
- `test_video.py` (8) — narration extraction, scene parsing
