"""Tests for trend research (JSON parsing only — no API calls)."""

from content_agent.research import _parse_trends


def test_parse_trends_clean_json():
    content = """[
        {"topic": "AI Security", "relevance_score": 0.9, "context": "New attacks"},
        {"topic": "Zero Trust", "relevance_score": 0.7, "context": "Enterprise push"}
    ]"""
    trends = _parse_trends(content)
    assert len(trends) == 2
    assert trends[0].topic == "AI Security"
    assert trends[0].relevance_score == 0.9
    assert trends[1].topic == "Zero Trust"


def test_parse_trends_markdown_fenced():
    content = """```json
[
    {"topic": "SSRF", "relevance_score": 0.8, "context": "Cloud metadata"}
]
```"""
    trends = _parse_trends(content)
    assert len(trends) == 1
    assert trends[0].topic == "SSRF"


def test_parse_trends_with_extra_text():
    content = """Here are the trending topics:
[{"topic": "Prompt Injection", "relevance_score": 0.95, "context": "LLM attacks"}]
Hope this helps!"""
    trends = _parse_trends(content)
    assert len(trends) == 1
    assert trends[0].topic == "Prompt Injection"


def test_parse_trends_invalid_json():
    trends = _parse_trends("This is not JSON at all")
    assert trends == []


def test_parse_trends_empty():
    trends = _parse_trends("")
    assert trends == []


def test_parse_trends_with_hashtags():
    content = """[{
        "topic": "AI Agent Security",
        "relevance_score": 0.85,
        "context": "New framework vulnerabilities",
        "hashtags": ["aisecurity", "agents", "llm"]
    }]"""
    trends = _parse_trends(content)
    assert len(trends) == 1
    assert trends[0].hashtags == ["aisecurity", "agents", "llm"]


def test_parse_trends_missing_fields():
    content = '[{"topic": "Minimal"}]'
    trends = _parse_trends(content)
    assert len(trends) == 1
    assert trends[0].topic == "Minimal"
    assert trends[0].relevance_score == 0.0
    assert trends[0].context == ""


def test_parse_trends_not_a_list():
    content = '{"topic": "Single object, not array"}'
    trends = _parse_trends(content)
    assert trends == []
