"""Tests for Pydantic data models."""

from content_agent.models import (
    ContentPiece,
    ContentStatus,
    ContentType,
    DailyPipelineResult,
    ImageAsset,
    ImageGenerator,
    ImageType,
    ObsidianNote,
    Platform,
    TrendItem,
    TrendReport,
    VideoAsset,
)


def test_obsidian_note_defaults():
    note = ObsidianNote(file_path="/vault/test.md")
    assert note.title == ""
    assert note.track == ""
    assert note.tags == []
    assert note.key_takeaways == []
    assert note.connections == []


def test_obsidian_note_full():
    note = ObsidianNote(
        file_path="/vault/ssrf.md",
        title="SSRF Deep Dive",
        track="web_appsec",
        task_type="lab",
        tags=["ssrf", "web"],
        key_takeaways=["Cloud metadata is the primary target"],
        connections=["IMDS", "Cloud Security"],
    )
    assert note.title == "SSRF Deep Dive"
    assert len(note.tags) == 2
    assert "ssrf" in note.tags
    assert len(note.connections) == 2


def test_trend_item():
    item = TrendItem(
        topic="AI Agent Security",
        relevance_score=0.9,
        context="New attack vectors discovered",
        hashtags=["aisecurity", "agents"],
    )
    assert item.relevance_score == 0.9
    assert len(item.hashtags) == 2


def test_trend_report():
    report = TrendReport(
        platform="twitter",
        trends=[TrendItem(topic="Zero-day in Chrome")],
    )
    assert report.platform == "twitter"
    assert len(report.trends) == 1


def test_content_piece_defaults():
    piece = ContentPiece(
        content_type=ContentType.DAILY_UPDATE,
        platform=Platform.TWITTER,
        body="Day 1: Learning SSRF",
        day_number=1,
    )
    assert piece.status == ContentStatus.DRAFT
    assert piece.hashtags == []
    assert piece.media_paths == []
    assert piece.notes_used == []


def test_content_piece_full():
    piece = ContentPiece(
        content_type=ContentType.THREAD,
        platform=Platform.LINKEDIN,
        title="Day 5",
        body="Today I learned about prompt injection...",
        hashtags=["cybersecurity", "AI"],
        day_number=5,
        generated_date="2026-05-23",
        notes_used=["/vault/pi.md"],
    )
    assert piece.platform == Platform.LINKEDIN
    assert piece.day_number == 5
    assert len(piece.hashtags) == 2


def test_image_asset():
    asset = ImageAsset(
        image_type=ImageType.DAY_CARD,
        file_path="/output/day_1.png",
        generator=ImageGenerator.PUPPETEER,
        prompt="Day 1: SSRF",
    )
    assert asset.image_type == ImageType.DAY_CARD
    assert asset.generator == ImageGenerator.PUPPETEER


def test_video_asset():
    asset = VideoAsset(
        script="[Hook] Did you know SSRF can...",
        duration_seconds=45.0,
        scenes=[{"description": "Hook", "narration": "Did you know..."}],
    )
    assert asset.duration_seconds == 45.0
    assert len(asset.scenes) == 1


def test_pipeline_result():
    result = DailyPipelineResult(
        date="2026-05-23",
        day_number=1,
        notes_ingested=[ObsidianNote(file_path="/vault/test.md")],
        content_pieces=[
            ContentPiece(
                content_type=ContentType.DAILY_UPDATE,
                platform=Platform.TWITTER,
                body="test",
                day_number=1,
            ),
        ],
    )
    assert result.day_number == 1
    assert len(result.notes_ingested) == 1
    assert len(result.content_pieces) == 1
    assert result.total_cost == 0.0


def test_str_enums():
    assert str(Platform.TWITTER) == "twitter"
    assert str(ContentType.HOT_TAKE) == "hot_take"
    assert str(ContentStatus.POSTED) == "posted"
    assert str(ImageType.DAY_CARD) == "day_card"
    assert str(ImageGenerator.GPT4O) == "gpt4o"
