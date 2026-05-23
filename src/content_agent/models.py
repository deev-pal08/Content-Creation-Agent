"""Pydantic data models for the content pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Platform(StrEnum):
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"


class ContentType(StrEnum):
    DAILY_UPDATE = "daily_update"
    CODE_CHALLENGE = "code_challenge"
    THREAD = "thread"
    HOT_TAKE = "hot_take"
    CAPTION = "caption"
    VIDEO_SCRIPT = "video_script"


class ContentStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    SCHEDULED = "scheduled"
    POSTED = "posted"
    FAILED = "failed"


class ImageType(StrEnum):
    DAY_CARD = "day_card"
    CODE_CHALLENGE = "code_challenge"
    INFOGRAPHIC = "infographic"
    CONCEPT_EXPLAINER = "concept_explainer"


class ImageGenerator(StrEnum):
    SATORI = "satori"
    PUPPETEER = "puppeteer"
    PLAYWRIGHT = "playwright"
    GPT4O = "gpt4o"


# --- Input Models ---


class ObsidianNote(BaseModel):
    file_path: str
    title: str = ""
    track: str = ""
    task_type: str = ""
    source_url: str = ""
    date: str = ""
    difficulty: str = ""
    tags: list[str] = Field(default_factory=list)
    content: str = ""
    key_takeaways: list[str] = Field(default_factory=list)
    connections: list[str] = Field(default_factory=list)
    linked_content: dict[str, str] = Field(default_factory=dict)
    open_questions: list[str] = Field(default_factory=list)


# --- Trend Models ---


class TrendItem(BaseModel):
    topic: str
    relevance_score: float = 0.0
    source: str = ""
    context: str = ""
    hashtags: list[str] = Field(default_factory=list)


class TrendReport(BaseModel):
    platform: str
    trends: list[TrendItem] = Field(default_factory=list)
    generated_at: datetime | None = None


# --- Content Models ---


class ContentPiece(BaseModel):
    content_type: ContentType
    platform: Platform
    title: str = ""
    body: str = ""
    hashtags: list[str] = Field(default_factory=list)
    media_paths: list[str] = Field(default_factory=list)
    status: ContentStatus = ContentStatus.DRAFT
    day_number: int = 0
    generated_date: str = ""
    notes_used: list[str] = Field(default_factory=list)


class ImageAsset(BaseModel):
    image_type: ImageType
    file_path: str = ""
    generator: ImageGenerator
    prompt: str = ""
    metadata: dict = Field(default_factory=dict)


class VideoAsset(BaseModel):
    file_path: str = ""
    script: str = ""
    narration_path: str = ""
    duration_seconds: float = 0.0
    scenes: list[dict] = Field(default_factory=list)


# --- Pipeline Models ---


class DailyPipelineResult(BaseModel):
    date: str
    day_number: int
    notes_ingested: list[ObsidianNote] = Field(default_factory=list)
    trend_reports: list[TrendReport] = Field(default_factory=list)
    content_pieces: list[ContentPiece] = Field(default_factory=list)
    images: list[ImageAsset] = Field(default_factory=list)
    video: VideoAsset | None = None
    total_cost: float = 0.0
