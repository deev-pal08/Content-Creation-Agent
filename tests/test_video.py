"""Tests for video generation (script parsing only — no API calls)."""

from content_agent.video import _extract_narration, _parse_scenes


def test_extract_narration():
    script = """[Hook - dramatic text appearing]
Did you know that SSRF attacks can steal cloud credentials in seconds?

[Diagram - showing SSRF flow]
Server-Side Request Forgery happens when an attacker tricks a server into making requests on their behalf.

[Code example - vulnerable endpoint]
The attacker sends a URL pointing to the cloud metadata service.

[Conclusion - takeaway text]
Always validate and restrict outbound requests from your servers."""
    narration = _extract_narration(script)
    assert "Did you know" in narration
    assert "Server-Side Request Forgery" in narration
    assert "Always validate" in narration
    assert "[Hook" not in narration
    assert "[Diagram" not in narration


def test_extract_narration_empty():
    assert _extract_narration("") == ""


def test_extract_narration_no_scenes():
    narration = _extract_narration("Just plain narration text without scene markers.")
    assert narration == "Just plain narration text without scene markers."


def test_parse_scenes():
    script = """[Hook - text zoom]
Did you know SSRF can steal credentials?

[Diagram - network flow]
An attacker sends a crafted URL to the server.

[Example - code snippet]
The server fetches the attacker's URL without validation."""
    scenes = _parse_scenes(script)
    assert len(scenes) == 3
    assert scenes[0]["description"] == "Hook - text zoom"
    assert "Did you know" in scenes[0]["narration"]
    assert scenes[1]["description"] == "Diagram - network flow"
    assert scenes[2]["description"] == "Example - code snippet"


def test_parse_scenes_empty():
    scenes = _parse_scenes("")
    assert scenes == []


def test_parse_scenes_no_markers():
    scenes = _parse_scenes("Just text without any scene markers.")
    assert scenes == []


def test_parse_scenes_single():
    script = """[Opening]
This is the only scene with some narration content."""
    scenes = _parse_scenes(script)
    assert len(scenes) == 1
    assert scenes[0]["description"] == "Opening"
    assert "only scene" in scenes[0]["narration"]


def test_parse_scenes_multiline_narration():
    script = """[Scene 1]
First line of narration.
Second line of narration.
Third line of narration.

[Scene 2]
Next scene."""
    scenes = _parse_scenes(script)
    assert len(scenes) == 2
    assert "First line" in scenes[0]["narration"]
    assert "Second line" in scenes[0]["narration"]
    assert "Third line" in scenes[0]["narration"]
