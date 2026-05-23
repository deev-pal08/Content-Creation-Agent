"""Image generation — HTML templates (day cards, code challenges) + GPT-4o concept art."""

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
        html = template.render(
            code=code,
            language=language,
            vulnerability=vulnerability,
            hint=hint,
            day_number=day_number,
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

    def generate_all_for_day(
        self, notes: list[ObsidianNote], day_number: int, date: str = "",
        code_challenge: dict | None = None,
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
            page.screenshot(path=str(png_path.resolve()))
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
