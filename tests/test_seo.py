"""Tests for SEO optimizer (hashtag parsing only — no API calls)."""

from content_agent.seo import SEOOptimizer, _parse_hashtags


def test_parse_hashtags_clean_json():
    tags = _parse_hashtags('["cybersecurity", "infosec", "AI"]', [])
    assert tags == ["cybersecurity", "infosec", "AI"]


def test_parse_hashtags_with_hash_symbols():
    tags = _parse_hashtags('["#cybersecurity", "#infosec"]', [])
    assert tags == ["cybersecurity", "infosec"]


def test_parse_hashtags_markdown_fenced():
    content = """```json
["ssrf", "web", "security"]
```"""
    tags = _parse_hashtags(content, [])
    assert tags == ["ssrf", "web", "security"]


def test_parse_hashtags_with_extra_text():
    content = """Here are the hashtags: ["ai", "security"] for your post."""
    tags = _parse_hashtags(content, [])
    assert tags == ["ai", "security"]


def test_parse_hashtags_invalid_returns_fallback():
    fallback = ["default1", "default2"]
    tags = _parse_hashtags("not json", fallback)
    assert tags == fallback


def test_parse_hashtags_empty_returns_fallback():
    fallback = ["cyber"]
    tags = _parse_hashtags("", fallback)
    assert tags == fallback


def test_optimal_posting_time_configured():
    seo = SEOOptimizer(
        posting_times={"twitter": "10:30", "linkedin": "09:00"},
    )
    assert seo.get_optimal_posting_time("twitter") == "10:30"
    assert seo.get_optimal_posting_time("linkedin") == "09:00"


def test_optimal_posting_time_default():
    seo = SEOOptimizer()
    time = seo.get_optimal_posting_time("twitter")
    assert time in ("09:00", "10:00")  # weekday or weekend


def test_optimize_hashtags_no_api_key():
    seo = SEOOptimizer(
        default_hashtags={"twitter": ["cybersecurity", "infosec"]},
    )
    from content_agent.models import ContentPiece, ContentType, Platform
    piece = ContentPiece(
        content_type=ContentType.DAILY_UPDATE,
        platform=Platform.TWITTER,
        body="Day 1: SSRF",
        day_number=1,
    )
    tags = seo.optimize_hashtags(piece)
    assert tags == ["cybersecurity", "infosec"]


def test_optimize_content_assigns_hashtags():
    seo = SEOOptimizer(
        default_hashtags={
            "twitter": ["cyber"],
            "linkedin": ["professional"],
        },
    )
    from content_agent.models import ContentPiece, ContentType, Platform
    pieces = [
        ContentPiece(
            content_type=ContentType.DAILY_UPDATE,
            platform=Platform.TWITTER,
            body="test", day_number=1,
        ),
        ContentPiece(
            content_type=ContentType.THREAD,
            platform=Platform.LINKEDIN,
            body="test", day_number=1,
        ),
    ]
    optimized = seo.optimize_content(pieces)
    assert optimized[0].hashtags == ["cyber"]
    assert optimized[1].hashtags == ["professional"]
