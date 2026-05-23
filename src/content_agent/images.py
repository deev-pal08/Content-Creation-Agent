"""Image generation — HTML templates (day cards, code challenges) + AI APIs (infographics, explainers)."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader
from tenacity import retry, stop_after_attempt, wait_exponential

from content_agent.config import BrandColors
from content_agent.models import ImageAsset, ImageGenerator, ImageType, ObsidianNote

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


class ImageProducer:
    def __init__(
        self,
        output_dir: str = "output/images",
        brand_colors: BrandColors | None = None,
        recraft_api_key: str = "",
        ideogram_api_key: str = "",
        openai_api_key: str = "",
    ):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._colors = brand_colors or BrandColors()
        self._recraft_key = recraft_api_key
        self._ideogram_key = ideogram_api_key
        self._openai_key = openai_api_key
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True,
        )

    def generate_day_card(
        self, day_number: int, topic: str, track: str = "",
        key_takeaway: str = "", date: str = "",
    ) -> ImageAsset:
        template = self._jinja_env.get_template("day_card.html")
        html = template.render(
            day_number=day_number,
            topic=topic,
            track=track,
            key_takeaway=key_takeaway,
            date=date,
            colors=self._colors.model_dump(),
        )

        html_path = self._output_dir / f"day_{day_number}_card.html"
        png_path = self._output_dir / f"day_{day_number}_card.png"
        html_path.write_text(html)

        _html_to_png(html_path, png_path)

        return ImageAsset(
            image_type=ImageType.DAY_CARD,
            file_path=str(png_path),
            generator=ImageGenerator.PUPPETEER,
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

        return ImageAsset(
            image_type=ImageType.CODE_CHALLENGE,
            file_path=str(png_path),
            generator=ImageGenerator.PUPPETEER,
            prompt=f"Code challenge: {vulnerability}",
            metadata={"language": language, "vulnerability": vulnerability},
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def generate_infographic(self, topic: str, description: str) -> ImageAsset:
        if not self._recraft_key:
            log.warning("No Recraft API key — skipping infographic generation")
            return ImageAsset(
                image_type=ImageType.INFOGRAPHIC,
                generator=ImageGenerator.RECRAFT,
                prompt=f"Infographic: {topic}",
            )

        prompt = (
            f"Create a clean, professional infographic explaining: {topic}. "
            f"Details: {description}. "
            f"Style: modern, minimal, dark background ({self._colors.primary}), "
            f"accent color ({self._colors.highlight}). "
            f"Include clear labels and a logical flow."
        )

        with httpx.Client(timeout=60) as client:
            resp = client.post(
                "https://external.api.recraft.ai/v1/images/generations",
                headers={"Authorization": f"Bearer {self._recraft_key}"},
                json={
                    "prompt": prompt,
                    "style": "digital_illustration",
                    "size": "1024x1024",
                },
            )
            resp.raise_for_status()

        data = resp.json()
        image_url = data["data"][0]["url"]
        png_path = self._output_dir / f"infographic_{topic[:30].replace(' ', '_')}.png"
        _download_image(image_url, png_path)

        return ImageAsset(
            image_type=ImageType.INFOGRAPHIC,
            file_path=str(png_path),
            generator=ImageGenerator.RECRAFT,
            prompt=prompt,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def generate_concept_explainer(self, topic: str, description: str) -> ImageAsset:
        if not self._ideogram_key:
            log.warning("No Ideogram API key — skipping concept explainer")
            return ImageAsset(
                image_type=ImageType.CONCEPT_EXPLAINER,
                generator=ImageGenerator.IDEOGRAM,
                prompt=f"Concept: {topic}",
            )

        prompt = (
            f"Educational diagram explaining: {topic}. "
            f"{description}. "
            f"Clean layout with clear labels, arrows showing flow, "
            f"dark background, modern style. "
            f"Make all text clearly readable."
        )

        with httpx.Client(timeout=60) as client:
            resp = client.post(
                "https://api.ideogram.ai/generate",
                headers={"Api-Key": self._ideogram_key},
                json={
                    "image_request": {
                        "prompt": prompt,
                        "aspect_ratio": "ASPECT_1_1",
                        "model": "V_2",
                    },
                },
            )
            resp.raise_for_status()

        data = resp.json()
        image_url = data["data"][0]["url"]
        png_path = self._output_dir / f"explainer_{topic[:30].replace(' ', '_')}.png"
        _download_image(image_url, png_path)

        return ImageAsset(
            image_type=ImageType.CONCEPT_EXPLAINER,
            file_path=str(png_path),
            generator=ImageGenerator.IDEOGRAM,
            prompt=prompt,
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

        try:
            card = self.generate_day_card(
                day_number=day_number, topic=topic,
                track=primary_note.track, key_takeaway=takeaway, date=date,
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


def _download_image(url: str, path: Path) -> None:
    with httpx.Client(timeout=30) as client:
        resp = client.get(url)
        resp.raise_for_status()
        path.write_bytes(resp.content)


def _extract_code_block(content: str) -> dict | None:
    import re
    match = re.search(r"```(\w*)\n(.*?)```", content, re.DOTALL)
    if match:
        return {"language": match.group(1) or "python", "code": match.group(2).strip()}
    return None
