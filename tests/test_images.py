"""Tests for image generation (template rendering only — no API calls)."""

from pathlib import Path

from content_agent.images import _extract_code_block, ImageProducer


def test_extract_code_block_python():
    content = """Some text
```python
def vulnerable():
    query = f"SELECT * FROM users WHERE name = '{user_input}'"
    return query
```
More text"""
    result = _extract_code_block(content)
    assert result is not None
    assert result["language"] == "python"
    assert "vulnerable" in result["code"]
    assert "SELECT" in result["code"]


def test_extract_code_block_no_language():
    content = """```
const x = eval(userInput);
```"""
    result = _extract_code_block(content)
    assert result is not None
    assert result["language"] == "python"  # default
    assert "eval" in result["code"]


def test_extract_code_block_none():
    content = "No code blocks here, just text."
    result = _extract_code_block(content)
    assert result is None


def test_day_card_html_generation(tmp_path):
    producer = ImageProducer(output_dir=str(tmp_path / "images"))
    asset = producer.generate_day_card(
        day_number=42,
        topic="SSRF Deep Dive",
        track="web_appsec",
        key_takeaway="Cloud metadata is the primary target",
        date="2026-05-23",
    )
    assert asset.image_type == "day_card"
    assert asset.generator == "puppeteer"
    assert "42" in asset.prompt

    html_path = tmp_path / "images" / "day_42_card.html"
    assert html_path.exists()
    html_content = html_path.read_text()
    assert "DAY 42" in html_content
    assert "SSRF Deep Dive" in html_content
    assert "web_appsec" in html_content
    assert "Cloud metadata is the primary target" in html_content


def test_code_challenge_html_generation(tmp_path):
    producer = ImageProducer(output_dir=str(tmp_path / "images"))
    code = 'query = f"SELECT * FROM users WHERE name = \'{user_input}\'"'
    asset = producer.generate_code_challenge(
        code=code,
        language="python",
        vulnerability="SQL Injection",
        hint="Look at string formatting",
        day_number=5,
    )
    assert asset.image_type == "code_challenge"
    assert asset.generator == "puppeteer"

    html_path = tmp_path / "images" / "day_5_challenge.html"
    assert html_path.exists()
    html_content = html_path.read_text()
    assert "Spot the Bug" in html_content
    assert "python" in html_content
    assert "DAY 5" in html_content


def test_infographic_no_api_key(tmp_path):
    producer = ImageProducer(output_dir=str(tmp_path / "images"))
    asset = producer.generate_infographic("SSRF", "How SSRF works")
    assert asset.image_type == "infographic"
    assert asset.generator == "recraft"
    assert asset.file_path == ""  # no API key, no file generated


def test_concept_explainer_no_api_key(tmp_path):
    producer = ImageProducer(output_dir=str(tmp_path / "images"))
    asset = producer.generate_concept_explainer("XSS", "Cross-site scripting flow")
    assert asset.image_type == "concept_explainer"
    assert asset.generator == "ideogram"
    assert asset.file_path == ""


def test_generate_all_for_day_empty_notes(tmp_path):
    producer = ImageProducer(output_dir=str(tmp_path / "images"))
    assets = producer.generate_all_for_day([], day_number=1)
    assert assets == []


def test_generate_all_for_day_with_code_challenge(tmp_path):
    from content_agent.models import ObsidianNote
    producer = ImageProducer(output_dir=str(tmp_path / "images"))
    note = ObsidianNote(
        title="SSRF", track="web_appsec", task_type="read",
        date="2026-05-23", file_path="test.md", content="Learned SSRF",
        key_takeaways=["Metadata endpoints"], tags=["ssrf"],
    )
    challenge_data = {
        "code": "resp = requests.get(user_url)",
        "language": "python",
        "vulnerability": "SSRF",
        "hint": "Where does user_url point?",
    }
    assets = producer.generate_all_for_day(
        [note], day_number=3, date="2026-05-23", code_challenge=challenge_data,
    )
    types = [a.image_type for a in assets]
    assert "day_card" in types
    assert "code_challenge" in types


def test_generate_all_for_day_no_code_challenge(tmp_path):
    from content_agent.models import ObsidianNote
    producer = ImageProducer(output_dir=str(tmp_path / "images"))
    note = ObsidianNote(
        title="Crypto History", track="ai_security", task_type="read",
        date="2026-05-23", file_path="test.md", content="Learned history",
        key_takeaways=["Interesting stuff"], tags=[],
    )
    assets = producer.generate_all_for_day(
        [note], day_number=3, date="2026-05-23", code_challenge=None,
    )
    types = [a.image_type for a in assets]
    assert "day_card" in types
    assert "code_challenge" not in types


def test_brand_colors_in_template(tmp_path):
    from content_agent.config import BrandColors
    colors = BrandColors(primary="#000000", highlight="#ff0000")
    producer = ImageProducer(
        output_dir=str(tmp_path / "images"),
        brand_colors=colors,
    )
    producer.generate_day_card(day_number=1, topic="Test")
    html_content = (tmp_path / "images" / "day_1_card.html").read_text()
    assert "#000000" in html_content
    assert "#ff0000" in html_content
