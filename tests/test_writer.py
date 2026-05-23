"""Tests for ContentWriter — code challenge generation (no API calls)."""

from __future__ import annotations

import json
from unittest.mock import patch

from content_agent.models import ObsidianNote
from content_agent.writer import ContentWriter, _build_notes_summary


def _make_note(**kwargs) -> ObsidianNote:
    defaults = dict(
        title="SSRF Deep Dive",
        track="web_appsec",
        task_type="lab",
        date="2026-05-23",
        file_path="web-appsec/ssrf.md",
        content="Learned about SSRF via cloud metadata endpoints.",
        key_takeaways=["Cloud metadata is the primary SSRF target"],
        tags=["ssrf", "cloud"],
    )
    defaults.update(kwargs)
    return ObsidianNote(**defaults)


def test_generate_code_challenge_valid_json():
    writer = ContentWriter(anthropic_api_key="test-key")
    mock_response = json.dumps({
        "code": "resp = requests.get(user_url)\nreturn resp.text",
        "language": "python",
        "vulnerability": "SSRF",
        "hint": "Where does user_url point to?",
    })
    with patch.object(writer, "_call_claude", return_value=mock_response):
        result = writer.generate_code_challenge([_make_note()])
    assert result is not None
    assert result["language"] == "python"
    assert result["vulnerability"] == "SSRF"
    assert "code" in result
    assert "hint" in result


def test_generate_code_challenge_no_challenge():
    writer = ContentWriter(anthropic_api_key="test-key")
    with patch.object(writer, "_call_claude", return_value="NO_CHALLENGE"):
        result = writer.generate_code_challenge([_make_note(title="History of Cryptography")])
    assert result is None


def test_generate_code_challenge_fenced_json():
    writer = ContentWriter(anthropic_api_key="test-key")
    fenced = '```json\n{"code": "x = eval(s)", "language": "python", "vulnerability": "Code Injection", "hint": "eval is dangerous"}\n```'
    with patch.object(writer, "_call_claude", return_value=fenced):
        result = writer.generate_code_challenge([_make_note()])
    assert result is not None
    assert result["vulnerability"] == "Code Injection"


def test_generate_code_challenge_invalid_json():
    writer = ContentWriter(anthropic_api_key="test-key")
    with patch.object(writer, "_call_claude", return_value="Here is some random text"):
        result = writer.generate_code_challenge([_make_note()])
    assert result is None


def test_generate_code_challenge_missing_fields():
    writer = ContentWriter(anthropic_api_key="test-key")
    partial = json.dumps({"code": "x = 1", "language": "python"})
    with patch.object(writer, "_call_claude", return_value=partial):
        result = writer.generate_code_challenge([_make_note()])
    assert result is None


def test_generate_code_challenge_empty_notes():
    writer = ContentWriter(anthropic_api_key="test-key")
    result = writer.generate_code_challenge([])
    assert result is None


def test_generate_code_challenge_api_error():
    writer = ContentWriter(anthropic_api_key="test-key")
    with patch.object(writer, "_call_claude", side_effect=RuntimeError("API down")):
        result = writer.generate_code_challenge([_make_note()])
    assert result is None


def test_build_notes_summary():
    notes = [_make_note(), _make_note(title="XSS Basics", track="web_appsec")]
    summary = _build_notes_summary(notes)
    assert "SSRF Deep Dive" in summary
    assert "XSS Basics" in summary
    assert "Topic 1" in summary
    assert "Topic 2" in summary


def test_generate_comparison_valid_json():
    writer = ContentWriter(anthropic_api_key="test-key")
    mock_response = json.dumps({
        "title": "Query Construction",
        "vulnerable_label": "String Concatenation",
        "vulnerable_code": "query = f'SELECT * FROM users WHERE name = {name}'",
        "secure_label": "Parameterized Query",
        "secure_code": "cursor.execute('SELECT * FROM users WHERE name = %s', (name,))",
        "language": "python",
        "explanation": "Parameterized queries prevent SQL injection by separating code from data.",
    })
    with patch.object(writer, "_call_claude", return_value=mock_response):
        result = writer.generate_comparison([_make_note()])
    assert result is not None
    assert result["title"] == "Query Construction"
    assert "vulnerable_code" in result
    assert "secure_code" in result


def test_generate_comparison_no_match():
    writer = ContentWriter(anthropic_api_key="test-key")
    with patch.object(writer, "_call_claude", return_value="NO_COMPARISON"):
        result = writer.generate_comparison([_make_note(title="History")])
    assert result is None


def test_generate_key_fact_valid_json():
    writer = ContentWriter(anthropic_api_key="test-key")
    mock_response = json.dumps({
        "headline": "90% of cloud breaches start with SSRF",
        "explanation": "SSRF allows attackers to access internal cloud metadata endpoints.",
        "source": "OWASP Top 10",
    })
    with patch.object(writer, "_call_claude", return_value=mock_response):
        result = writer.generate_key_fact([_make_note()])
    assert result is not None
    assert "90%" in result["headline"]
    assert result["source"] == "OWASP Top 10"


def test_generate_carousel_valid_json():
    writer = ContentWriter(anthropic_api_key="test-key")
    mock_response = json.dumps({
        "title": "Understanding SSRF",
        "subtitle": "How attackers talk to your internal services",
        "slides": [
            {"heading": "What is SSRF?", "body": "Server-Side Request Forgery...", "footer": ""},
            {"heading": "How it works", "body": "The attacker tricks...", "footer": "Think: mail forwarding"},
        ],
    })
    with patch.object(writer, "_call_claude", return_value=mock_response):
        result = writer.generate_carousel([_make_note()])
    assert result is not None
    assert result["title"] == "Understanding SSRF"
    assert len(result["slides"]) == 2


def test_generate_carousel_empty_notes():
    writer = ContentWriter(anthropic_api_key="test-key")
    result = writer.generate_carousel([])
    assert result is None
