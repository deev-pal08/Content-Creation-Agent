"""Pydantic configuration validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator


class ObsidianConfig(BaseModel):
    vault_path: str
    notes_glob: str = "**/*.md"


class LLMConfig(BaseModel):
    writer_model: str = "claude-sonnet-4-6"
    strategy_model: str = "claude-sonnet-4-6"
    trend_model_x: str = "grok-3-mini"
    trend_model_web: str = "sonar"
    trend_model_youtube: str = "gemini-2.5-flash"
    seo_model: str = "gemini-2.5-flash"
    hot_take_model: str = "grok-3-mini"
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "nova"
    max_tokens: int = 4096


class BrandColors(BaseModel):
    primary: str = "#1a1a2e"
    secondary: str = "#16213e"
    accent: str = "#0f3460"
    highlight: str = "#e94560"
    text_light: str = "#ffffff"
    text_dark: str = "#1a1a2e"


class ImageConfig(BaseModel):
    infographic_provider: str = "recraft"
    explainer_provider: str = "ideogram"
    output_dir: str = "output/images"
    brand_colors: BrandColors = BrandColors()


class VideoConfig(BaseModel):
    output_dir: str = "output/videos"
    duration_target: int = 45
    width: int = 1080
    height: int = 1920


class SEOConfig(BaseModel):
    default_hashtags: dict[str, list[str]] = {
        "twitter": ["cybersecurity", "infosec", "AI"],
        "linkedin": ["cybersecurity", "artificialintelligence", "security"],
        "instagram": ["cybersecurity", "infosec", "hacking", "ai"],
    }
    posting_times: dict[str, str] = {
        "twitter": "09:00",
        "linkedin": "08:30",
        "instagram": "12:00",
        "youtube": "14:00",
    }

    @field_validator("posting_times")
    @classmethod
    def validate_posting_times(cls, v: dict[str, str]) -> dict[str, str]:
        import re

        for platform, time_str in v.items():
            if not re.match(r"^\d{2}:\d{2}$", time_str):
                msg = f"Invalid time format for {platform}: {time_str!r}. Must be HH:MM."
                raise ValueError(msg)
        return v


class PublisherConfig(BaseModel):
    buffer_profile_ids: dict[str, str] = {}


class ScheduleConfig(BaseModel):
    daily_time: str = "06:30"
    timezone: str = "Europe/London"

    @field_validator("daily_time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        import re

        if not re.match(r"^\d{2}:\d{2}$", v):
            msg = f"Invalid time format: {v!r}. Must be HH:MM."
            raise ValueError(msg)
        return v


class AppConfig(BaseModel):
    obsidian: ObsidianConfig
    llm: LLMConfig = LLMConfig()
    images: ImageConfig = ImageConfig()
    video: VideoConfig = VideoConfig()
    seo: SEOConfig = SEOConfig()
    publisher: PublisherConfig = PublisherConfig()
    schedule: ScheduleConfig = ScheduleConfig()
    state_dir: str = "data"
    day_counter_start: int = 1
    about_me: str = "AboutMe.md"


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    p = Path(path)
    if not p.exists():
        msg = f"Config file not found: {p}"
        raise FileNotFoundError(msg)
    raw: dict[str, Any] = yaml.safe_load(p.read_text()) or {}
    return AppConfig(**raw)
