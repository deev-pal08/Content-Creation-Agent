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
    assert asset.generator in ("puppeteer", "playwright")
    assert "42" in asset.prompt

    html_path = tmp_path / "images" / "day_42_card.html"
    assert html_path.exists()
    html_content = html_path.read_text()
    assert "DAY 42" in html_content
    assert "SSRF Deep Dive" in html_content
    assert "web_appsec" in html_content
    assert "Cloud metadata is the primary target" in html_content


def test_day_card_with_concept_image(tmp_path):
    concept_path = tmp_path / "concept.png"
    concept_path.write_bytes(b"fake png data")
    producer = ImageProducer(output_dir=str(tmp_path / "images"))
    asset = producer.generate_day_card(
        day_number=1, topic="Test", concept_image_path=str(concept_path),
    )
    assert asset.generator == "gpt4o"
    html_content = (tmp_path / "images" / "day_1_card.html").read_text()
    assert "background-image" in html_content


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
    assert asset.generator in ("puppeteer", "playwright")

    html_path = tmp_path / "images" / "day_5_challenge.html"
    assert html_path.exists()
    html_content = html_path.read_text()
    assert "Spot the Bug" in html_content
    assert "python" in html_content
    assert "Day 5" in html_content


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


def test_comparison_card_html_generation(tmp_path):
    producer = ImageProducer(output_dir=str(tmp_path / "images"))
    asset = producer.generate_comparison_card(
        title="Query Construction",
        vulnerable_label="String Concatenation",
        vulnerable_code="query = f'SELECT * FROM users WHERE name = {name}'",
        secure_label="Parameterized Query",
        secure_code="cursor.execute('SELECT * FROM users WHERE name = %s', (name,))",
        language="python",
        explanation="Parameterized queries separate code from data.",
        day_number=7,
    )
    assert asset.image_type == "comparison_card"
    assert asset.generator in ("puppeteer", "playwright")

    html_path = tmp_path / "images" / "day_7_comparison.html"
    assert html_path.exists()
    html_content = html_path.read_text()
    assert "Vulnerable" in html_content
    assert "Secure" in html_content
    assert "Day 7" in html_content


def test_key_fact_card_html_generation(tmp_path):
    producer = ImageProducer(output_dir=str(tmp_path / "images"))
    asset = producer.generate_key_fact_card(
        headline="90% of cloud breaches start with SSRF",
        explanation="SSRF lets attackers access internal metadata endpoints.",
        source="OWASP Top 10",
        day_number=3,
    )
    assert asset.image_type == "key_fact_card"
    assert asset.generator in ("puppeteer", "playwright")

    html_path = tmp_path / "images" / "day_3_keyfact.html"
    assert html_path.exists()
    html_content = html_path.read_text()
    assert "90%" in html_content
    assert "OWASP" in html_content


def test_carousel_html_generation(tmp_path):
    producer = ImageProducer(output_dir=str(tmp_path / "images"))
    carousel_data = {
        "title": "Understanding SSRF",
        "subtitle": "How attackers talk to your internal services",
        "file_name": "ssrf-guide.sh",
        "toc_items": ["What is SSRF?", "How it works"],
        "slides": [
            {"heading": "What is SSRF?", "body": "Server-Side Request Forgery explained.", "tag": "BASICS", "terminal_lines": ["> # example"], "lesson": "SSRF is dangerous", "tags": ["ssrf"]},
            {"heading": "How it works", "body": "The attacker tricks the server.", "tag": "ATTACK", "terminal_lines": ["> # curl internal"], "lesson": "Always validate URLs", "tags": ["defense"]},
        ],
    }
    assets = producer.generate_carousel(carousel_data, day_number=4)
    assert len(assets) == 3  # 1 cover + 2 slides
    assert all(a.image_type == "carousel_slide" for a in assets)

    cover_html = (tmp_path / "images" / "day_4_carousel_0.html").read_text()
    assert "Understanding SSRF" in cover_html
    assert "SWIPE TO LEARN" in cover_html
    assert "ssrf-guide.sh" in cover_html

    slide_html = (tmp_path / "images" / "day_4_carousel_1.html").read_text()
    assert "What is SSRF?" in slide_html
    assert "BASICS" in slide_html


def test_generate_all_with_all_image_types(tmp_path):
    from content_agent.models import ObsidianNote
    producer = ImageProducer(output_dir=str(tmp_path / "images"))
    note = ObsidianNote(
        title="SSRF", track="web_appsec", task_type="read",
        date="2026-05-23", file_path="test.md", content="Learned SSRF",
        key_takeaways=["Metadata endpoints"], tags=["ssrf"],
    )
    assets = producer.generate_all_for_day(
        [note], day_number=5, date="2026-05-23",
        code_challenge={"code": "requests.get(url)", "language": "python", "vulnerability": "SSRF", "hint": "Check URL"},
        comparison={"title": "URL Validation", "vulnerable_label": "None", "vulnerable_code": "get(url)", "secure_label": "Allowlist", "secure_code": "if url in ALLOWED: get(url)", "language": "python", "explanation": "Validate URLs"},
        key_fact={"headline": "SSRF is #1", "explanation": "Most common cloud attack", "source": "OWASP"},
        carousel={"title": "SSRF Guide", "subtitle": "Learn SSRF", "file_name": "ssrf.sh", "toc_items": ["Slide 1"], "slides": [{"heading": "Slide 1", "body": "Content", "tag": "BASICS", "terminal_lines": ["> # test"], "lesson": "Learn it", "tags": ["ssrf"]}]},
    )
    types = [a.image_type for a in assets]
    assert "day_card" in types
    assert "code_challenge" in types
    assert "comparison_card" in types
    assert "key_fact_card" in types
    assert "carousel_slide" in types
