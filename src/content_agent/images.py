"""Image generation — HTML templates (day cards, code challenges, comparisons, facts, carousels) + GPT-4o concept art."""

from __future__ import annotations

import base64
import logging
import re
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from content_agent.config import BrandColors
from content_agent.models import ImageAsset, ImageGenerator, ImageType, ObsidianNote

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"

ACCENT_THEMES = [
    {"accent": "#4ade80", "accent_dim": "#166534"},   # green
    {"accent": "#a78bfa", "accent_dim": "#5b21b6"},   # violet
    {"accent": "#22d3ee", "accent_dim": "#155e75"},   # cyan
    {"accent": "#fb923c", "accent_dim": "#9a3412"},   # orange
    {"accent": "#f472b6", "accent_dim": "#9d174d"},   # pink
    {"accent": "#facc15", "accent_dim": "#854d0e"},   # yellow
    {"accent": "#38bdf8", "accent_dim": "#075985"},   # sky blue
]


def _accent_for_day(day_number: int) -> dict[str, str]:
    return ACCENT_THEMES[day_number % len(ACCENT_THEMES)]

_screenshot_backend: str | None = None


def _detect_screenshot_backend() -> str:
    global _screenshot_backend
    if _screenshot_backend:
        return _screenshot_backend
    try:
        from playwright.sync_api import sync_playwright
        _screenshot_backend = "playwright"
    except ImportError:
        _screenshot_backend = "puppeteer"
    return _screenshot_backend


class ImageProducer:
    def __init__(
        self,
        output_dir: str = "output/images",
        brand_colors: BrandColors | None = None,
        openai_api_key: str = "",
    ):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._colors = brand_colors or BrandColors()
        self._openai_key = openai_api_key
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True,
        )

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=30))
    def generate_concept_image(
        self, topic: str, takeaway: str, day_number: int,
    ) -> str:
        if not self._openai_key:
            log.warning("No OpenAI API key — skipping concept image generation")
            return ""

        prompt = (
            f"Create a visually striking cybersecurity concept illustration for: {topic}. "
            f"Key concept: {takeaway}. "
            f"Style: dark moody background, modern digital art, cyberpunk-inspired, "
            f"cinematic lighting, abstract visualization of the security concept. "
            f"The image should tell a story about the security topic visually. "
            f"Do NOT include any text, words, labels, or watermarks in the image."
        )

        client = OpenAI(api_key=self._openai_key)
        response = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
            quality="low",
            n=1,
        )

        image_b64 = response.data[0].b64_json
        concept_path = self._output_dir / f"day_{day_number}_concept.png"
        concept_path.write_bytes(base64.b64decode(image_b64))
        log.info("Generated concept image: %s", concept_path)
        return str(concept_path)

    def generate_day_card(
        self, day_number: int, topic: str, track: str = "",
        key_takeaway: str = "", date: str = "",
        concept_image_path: str = "",
    ) -> ImageAsset:
        template = self._jinja_env.get_template("day_card.html")
        bg_image_uri = ""
        if concept_image_path and Path(concept_image_path).exists():
            bg_image_uri = f"file://{Path(concept_image_path).resolve()}"
        html = template.render(
            day_number=day_number,
            topic=topic,
            track=track,
            key_takeaway=key_takeaway,
            date=date,
            colors=self._colors.model_dump(),
            bg_image_uri=bg_image_uri,
        )

        html_path = self._output_dir / f"day_{day_number}_card.html"
        png_path = self._output_dir / f"day_{day_number}_card.png"
        html_path.write_text(html)

        _html_to_png(html_path, png_path)

        backend = _detect_screenshot_backend()
        gen = ImageGenerator.GPT4O if concept_image_path else (
            ImageGenerator.PLAYWRIGHT if backend == "playwright" else ImageGenerator.PUPPETEER
        )

        return ImageAsset(
            image_type=ImageType.DAY_CARD,
            file_path=str(png_path),
            generator=gen,
            prompt=f"Day {day_number}: {topic}",
            metadata={"day_number": day_number, "topic": topic},
        )

    def generate_code_challenge(
        self, code: str, language: str = "python",
        vulnerability: str = "", hint: str = "",
        day_number: int = 0,
    ) -> ImageAsset:
        template = self._jinja_env.get_template("code_challenge.html")
        theme = _accent_for_day(day_number)
        html = template.render(
            code=code,
            language=language,
            vulnerability=vulnerability,
            hint=hint,
            day_number=day_number,
            theme=theme,
            colors=self._colors.model_dump(),
        )

        html_path = self._output_dir / f"day_{day_number}_challenge.html"
        png_path = self._output_dir / f"day_{day_number}_challenge.png"
        html_path.write_text(html)

        _html_to_png(html_path, png_path)

        backend = _detect_screenshot_backend()
        gen = ImageGenerator.PLAYWRIGHT if backend == "playwright" else ImageGenerator.PUPPETEER

        return ImageAsset(
            image_type=ImageType.CODE_CHALLENGE,
            file_path=str(png_path),
            generator=gen,
            prompt=f"Code challenge: {vulnerability}",
            metadata={"language": language, "vulnerability": vulnerability},
        )

    def generate_comparison_card(
        self, title: str, vulnerable_label: str, vulnerable_code: str,
        secure_label: str, secure_code: str, language: str = "python",
        explanation: str = "", day_number: int = 0,
    ) -> ImageAsset:
        template = self._jinja_env.get_template("comparison_card.html")
        theme = _accent_for_day(day_number)
        html = template.render(
            title=title,
            vulnerable_label=vulnerable_label,
            vulnerable_code=vulnerable_code,
            secure_label=secure_label,
            secure_code=secure_code,
            language=language,
            explanation=explanation,
            day_number=day_number,
            theme=theme,
            colors=self._colors.model_dump(),
        )

        html_path = self._output_dir / f"day_{day_number}_comparison.html"
        png_path = self._output_dir / f"day_{day_number}_comparison.png"
        html_path.write_text(html)
        _html_to_png(html_path, png_path)

        backend = _detect_screenshot_backend()
        gen = ImageGenerator.PLAYWRIGHT if backend == "playwright" else ImageGenerator.PUPPETEER
        return ImageAsset(
            image_type=ImageType.COMPARISON_CARD,
            file_path=str(png_path),
            generator=gen,
            prompt=f"Comparison: {title}",
            metadata={"title": title, "language": language},
        )

    def generate_key_fact_card(
        self, headline: str, explanation: str, source: str = "",
        day_number: int = 0,
    ) -> ImageAsset:
        template = self._jinja_env.get_template("key_fact.html")
        profile_path = TEMPLATES_DIR / "assets" / "profile.png"
        profile_uri = f"file://{profile_path.resolve()}" if profile_path.exists() else ""
        html = template.render(
            headline=headline,
            explanation=explanation,
            source=source,
            day_number=day_number,
            profile_image_uri=profile_uri,
            colors=self._colors.model_dump(),
        )

        html_path = self._output_dir / f"day_{day_number}_keyfact.html"
        png_path = self._output_dir / f"day_{day_number}_keyfact.png"
        html_path.write_text(html)
        _html_to_png(html_path, png_path)

        backend = _detect_screenshot_backend()
        gen = ImageGenerator.PLAYWRIGHT if backend == "playwright" else ImageGenerator.PUPPETEER
        return ImageAsset(
            image_type=ImageType.KEY_FACT_CARD,
            file_path=str(png_path),
            generator=gen,
            prompt=f"Key fact: {headline}",
            metadata={"headline": headline},
        )

    def generate_carousel(
        self, carousel_data: dict, day_number: int = 0,
    ) -> list[ImageAsset]:
        template = self._jinja_env.get_template("carousel_slide.html")
        slides = carousel_data.get("slides", [])
        total = len(slides)
        assets: list[ImageAsset] = []
        file_name = carousel_data.get("file_name", "security-lesson.sh")
        theme = _accent_for_day(day_number)

        cover_html = template.render(
            is_cover=True,
            heading=carousel_data.get("title", ""),
            subtitle=carousel_data.get("subtitle", ""),
            file_name=file_name,
            toc_items=carousel_data.get("toc_items", []),
            breadcrumb="// LESSON //",
            tag_pill="SWIPE TO LEARN",
            slide_number=0,
            total_slides=total,
            day_number=day_number,
            theme=theme,
            colors=self._colors.model_dump(),
        )
        cover_html_path = self._output_dir / f"day_{day_number}_carousel_0.html"
        cover_png_path = self._output_dir / f"day_{day_number}_carousel_0.png"
        cover_html_path.write_text(cover_html)
        _html_to_png(cover_html_path, cover_png_path)

        backend = _detect_screenshot_backend()
        gen = ImageGenerator.PLAYWRIGHT if backend == "playwright" else ImageGenerator.PUPPETEER
        assets.append(ImageAsset(
            image_type=ImageType.CAROUSEL_SLIDE,
            file_path=str(cover_png_path),
            generator=gen,
            prompt=f"Carousel cover: {carousel_data.get('title', '')}",
            metadata={"slide": 0, "total": total + 1},
        ))

        for i, slide in enumerate(slides, 1):
            slide_html = template.render(
                is_cover=False,
                heading=slide.get("heading", ""),
                body=slide.get("body", ""),
                file_name=file_name,
                breadcrumb=f"// SLIDE {i:02d} //",
                tag_pill=slide.get("tag", ""),
                terminal_lines=slide.get("terminal_lines", []),
                lesson=slide.get("lesson", ""),
                tags=slide.get("tags", []),
                slide_number=i,
                total_slides=total,
                day_number=day_number,
                theme=theme,
                colors=self._colors.model_dump(),
            )
            html_path = self._output_dir / f"day_{day_number}_carousel_{i}.html"
            png_path = self._output_dir / f"day_{day_number}_carousel_{i}.png"
            html_path.write_text(slide_html)
            _html_to_png(html_path, png_path)

            assets.append(ImageAsset(
                image_type=ImageType.CAROUSEL_SLIDE,
                file_path=str(png_path),
                generator=gen,
                prompt=f"Carousel slide {i}: {slide.get('heading', '')}",
                metadata={"slide": i, "total": total + 1},
            ))

        return assets

    def generate_all_for_day(
        self, notes: list[ObsidianNote], day_number: int, date: str = "",
        code_challenge: dict | None = None,
        comparison: dict | None = None,
        key_fact: dict | None = None,
        carousel: dict | None = None,
    ) -> list[ImageAsset]:
        if not notes:
            return []

        assets: list[ImageAsset] = []
        primary_note = notes[0]
        topic = primary_note.title or primary_note.track or "Security"
        takeaway = primary_note.key_takeaways[0] if primary_note.key_takeaways else ""

        concept_path = ""
        try:
            concept_path = self.generate_concept_image(topic, takeaway, day_number)
            if concept_path:
                log.info("Concept image generated: %s", concept_path)
        except Exception as e:
            log.warning("Concept image generation failed — using plain card: %s", e)

        try:
            card = self.generate_day_card(
                day_number=day_number, topic=topic,
                track=primary_note.track, key_takeaway=takeaway, date=date,
                concept_image_path=concept_path,
            )
            assets.append(card)
        except Exception as e:
            log.error("Day card generation failed: %s", e)

        if code_challenge:
            try:
                challenge = self.generate_code_challenge(
                    code=code_challenge["code"],
                    language=code_challenge.get("language", "python"),
                    vulnerability=code_challenge.get("vulnerability", ""),
                    hint=code_challenge.get("hint", ""),
                    day_number=day_number,
                )
                assets.append(challenge)
            except Exception as e:
                log.error("Code challenge generation failed: %s", e)

        if comparison:
            try:
                comp = self.generate_comparison_card(
                    title=comparison.get("title", ""),
                    vulnerable_label=comparison.get("vulnerable_label", "Vulnerable"),
                    vulnerable_code=comparison.get("vulnerable_code", ""),
                    secure_label=comparison.get("secure_label", "Secure"),
                    secure_code=comparison.get("secure_code", ""),
                    language=comparison.get("language", "python"),
                    explanation=comparison.get("explanation", ""),
                    day_number=day_number,
                )
                assets.append(comp)
            except Exception as e:
                log.error("Comparison card generation failed: %s", e)

        if key_fact:
            try:
                fact = self.generate_key_fact_card(
                    headline=key_fact.get("headline", ""),
                    explanation=key_fact.get("explanation", ""),
                    source=key_fact.get("source", ""),
                    day_number=day_number,
                )
                assets.append(fact)
            except Exception as e:
                log.error("Key fact card generation failed: %s", e)

        if carousel:
            try:
                slides = self.generate_carousel(carousel, day_number=day_number)
                assets.extend(slides)
            except Exception as e:
                log.error("Carousel generation failed: %s", e)

        return assets


def _html_to_png(html_path: Path, png_path: Path) -> None:
    backend = _detect_screenshot_backend()
    if backend == "playwright":
        _html_to_png_playwright(html_path, png_path)
    else:
        _html_to_png_puppeteer(html_path, png_path)


def _html_to_png_playwright(html_path: Path, png_path: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1080, "height": 1080})
            page.goto(f"file://{html_path.resolve()}", wait_until="networkidle")
            page.wait_for_timeout(500)
            page.screenshot(path=str(png_path.resolve()), full_page=True)
            browser.close()
    except Exception as e:
        log.warning("Playwright screenshot failed (falling back to HTML only): %s", e)


def _html_to_png_puppeteer(html_path: Path, png_path: Path) -> None:
    try:
        subprocess.run(
            [
                "node", "-e",
                f"""
const puppeteer = require('puppeteer');
(async () => {{
    const browser = await puppeteer.launch({{headless: true}});
    const page = await browser.newPage();
    await page.setViewport({{width: 1080, height: 1080}});
    await page.goto('file://{html_path.resolve()}');
    await page.screenshot({{path: '{png_path.resolve()}', type: 'png'}});
    await browser.close();
}})();
""",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.warning("Puppeteer screenshot failed (falling back to HTML only): %s", e)


def _extract_code_block(content: str) -> dict | None:
    import re
    match = re.search(r"```(\w*)\n(.*?)```", content, re.DOTALL)
    if match:
        return {"language": match.group(1) or "python", "code": match.group(2).strip()}
    return None
