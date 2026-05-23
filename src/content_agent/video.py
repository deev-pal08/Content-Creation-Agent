"""Video generation — TTS narration + Remotion assembly."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from content_agent.models import ObsidianNote, VideoAsset

log = logging.getLogger(__name__)


class VideoProducer:
    def __init__(
        self,
        output_dir: str = "output/videos",
        openai_api_key: str = "",
        tts_model: str = "gpt-4o-mini-tts",
        tts_voice: str = "nova",
        width: int = 1080,
        height: int = 1920,
        duration_target: int = 45,
    ):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._openai_key = openai_api_key
        self._tts_model = tts_model
        self._tts_voice = tts_voice
        self._width = width
        self._height = height
        self._duration_target = duration_target

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def generate_narration(self, script: str, output_name: str = "narration") -> str:
        if not self._openai_key:
            log.warning("No OpenAI API key — skipping TTS narration")
            return ""

        narration_text = _extract_narration(script)
        if not narration_text:
            log.warning("No narration text found in script")
            return ""

        client = OpenAI(api_key=self._openai_key)
        audio_path = self._output_dir / f"{output_name}.mp3"

        with client.audio.speech.with_streaming_response.create(
            model=self._tts_model,
            voice=self._tts_voice,
            input=narration_text,
            instructions="Speak clearly and engagingly, like an educator explaining a concept.",
        ) as response:
            response.stream_to_file(str(audio_path))

        log.info("Generated narration: %s", audio_path)
        return str(audio_path)

    def generate_video(
        self,
        script: str,
        narration_path: str = "",
        day_number: int = 0,
        topic: str = "",
    ) -> VideoAsset:
        scenes = _parse_scenes(script)
        video_path = self._output_dir / f"day_{day_number}_video.mp4"

        if not narration_path:
            narration_path = self.generate_narration(
                script, output_name=f"day_{day_number}_narration",
            )

        rendered = _render_with_remotion(
            scenes=scenes,
            narration_path=narration_path,
            output_path=str(video_path),
            width=self._width,
            height=self._height,
            duration_target=self._duration_target,
            topic=topic,
            day_number=day_number,
        )

        return VideoAsset(
            file_path=str(video_path) if rendered else "",
            script=script,
            narration_path=narration_path,
            duration_seconds=self._duration_target,
            scenes=scenes,
        )

    def generate_for_day(
        self,
        script: str,
        notes: list[ObsidianNote],
        day_number: int,
    ) -> VideoAsset:
        topic = notes[0].title if notes else "Security"
        return self.generate_video(
            script=script, day_number=day_number, topic=topic,
        )


def _extract_narration(script: str) -> str:
    lines = []
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            continue
        lines.append(stripped)
    return " ".join(lines)


def _parse_scenes(script: str) -> list[dict]:
    scenes: list[dict] = []
    current_scene: dict | None = None

    for line in script.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            if current_scene:
                scenes.append(current_scene)
            current_scene = {"description": stripped[1:-1], "narration": ""}
        elif current_scene is not None:
            if current_scene["narration"]:
                current_scene["narration"] += " "
            current_scene["narration"] += stripped

    if current_scene:
        scenes.append(current_scene)

    return scenes


def _render_with_remotion(
    scenes: list[dict],
    narration_path: str,
    output_path: str,
    width: int,
    height: int,
    duration_target: int,
    topic: str,
    day_number: int,
) -> bool:
    try:
        props = json.dumps({
            "scenes": scenes,
            "narrationPath": narration_path,
            "topic": topic,
            "dayNumber": day_number,
            "durationInSeconds": duration_target,
        })

        result = subprocess.run(
            [
                "npx", "remotion", "render",
                "--props", props,
                "--width", str(width),
                "--height", str(height),
                "--output", output_path,
            ],
            capture_output=True,
            timeout=120,
            check=True,
        )
        log.info("Video rendered: %s", output_path)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.warning("Remotion render failed (video pipeline not set up): %s", e)
        return False
