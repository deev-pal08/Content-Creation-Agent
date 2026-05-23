"""Tests for Obsidian notes ingestion."""

import pytest

from content_agent.ingest import (
    _extract_links,
    _extract_section,
    _extract_title,
    load_notes_for_date,
    parse_note,
)


@pytest.fixture
def sample_note(tmp_path):
    note = tmp_path / "ssrf_deep_dive.md"
    note.write_text("""---
track: web_appsec
task_type: lab
source_url: https://pentesterlab.com/exercises/ssrf
date: 2026-05-23
difficulty: intermediate
tags: [ssrf, web, cloud]
---

# SSRF Deep Dive

## Key Takeaways
- Cloud metadata endpoints are the primary SSRF target
- IMDS v2 requires a PUT request with a token header
- DNS rebinding can bypass SSRF filters

## What I Did
- Completed PentesterLab SSRF exercise
- Tested against AWS metadata endpoint

## Connections
- Related to [[Cloud Security]]
- Uses techniques from [[DNS Rebinding]]
- Foundation for [[Bug Bounty Methodology]]

## Open Questions
- How effective are allowlists vs blocklists for SSRF prevention?
- Can SSRF be chained with CSRF in modern frameworks?
""")
    return note


@pytest.fixture
def vault_with_notes(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()

    (vault / "note1.md").write_text("""---
track: ai_security
date: 2026-05-23
tags: [prompt-injection]
---

# Prompt Injection Basics

## Key Takeaways
- Direct vs indirect prompt injection
- Instruction hierarchy as defense
""")

    (vault / "note2.md").write_text("""---
track: web_appsec
date: 2026-05-23
tags: [xss]
---

# XSS in React Apps

## Key Takeaways
- dangerouslySetInnerHTML is the main vector
""")

    (vault / "note3.md").write_text("""---
track: cloud_security
date: 2026-05-24
tags: [iam]
---

# IAM Privilege Escalation
""")

    return vault


def test_parse_note(sample_note):
    note = parse_note(sample_note)
    assert note.title == "SSRF Deep Dive"
    assert note.track == "web_appsec"
    assert note.task_type == "lab"
    assert note.date == "2026-05-23"
    assert note.difficulty == "intermediate"
    assert "ssrf" in note.tags
    assert len(note.tags) == 3


def test_parse_note_takeaways(sample_note):
    note = parse_note(sample_note)
    assert len(note.key_takeaways) == 3
    assert "Cloud metadata endpoints are the primary SSRF target" in note.key_takeaways


def test_parse_note_connections(sample_note):
    note = parse_note(sample_note)
    assert len(note.connections) == 3
    assert "Cloud Security" in note.connections
    assert "DNS Rebinding" in note.connections


def test_parse_note_open_questions(sample_note):
    note = parse_note(sample_note)
    assert len(note.open_questions) == 2


def test_load_notes_for_date(vault_with_notes):
    notes = load_notes_for_date(vault_with_notes, "2026-05-23")
    assert len(notes) == 2
    tracks = {n.track for n in notes}
    assert "ai_security" in tracks
    assert "web_appsec" in tracks


def test_load_notes_different_date(vault_with_notes):
    notes = load_notes_for_date(vault_with_notes, "2026-05-24")
    assert len(notes) == 1
    assert notes[0].track == "cloud_security"


def test_load_notes_no_match(vault_with_notes):
    notes = load_notes_for_date(vault_with_notes, "2026-01-01")
    assert len(notes) == 0


def test_load_notes_missing_vault():
    notes = load_notes_for_date("/nonexistent/vault", "2026-05-23")
    assert len(notes) == 0


def test_extract_title():
    assert _extract_title("# My Title\nSome content") == "My Title"
    assert _extract_title("## Not a title\n# Real Title") == "Real Title"
    assert _extract_title("No heading here") == ""


def test_extract_section():
    content = """## Key Takeaways
- First point
- Second point

## Next Section
- Other stuff"""
    items = _extract_section(content, "Key Takeaways")
    assert len(items) == 2
    assert items[0] == "First point"


def test_extract_links():
    content = "Related to [[SSRF]] and [[Cloud Security]], also see [[DNS]]"
    links = _extract_links(content)
    assert len(links) == 3
    assert "SSRF" in links
    assert "Cloud Security" in links


def test_parse_note_without_frontmatter(tmp_path):
    note = tmp_path / "plain.md"
    note.write_text("# Just a Title\n\nSome content without YAML frontmatter.")
    parsed = parse_note(note)
    assert parsed.title == "Just a Title"
    assert parsed.track == ""
    assert parsed.tags == []


def test_parse_note_minimal(tmp_path):
    note = tmp_path / "minimal.md"
    note.write_text("""---
date: 2026-05-23
---
# Minimal Note
""")
    parsed = parse_note(note)
    assert parsed.title == "Minimal Note"
    assert parsed.date == "2026-05-23"


def test_parse_note_with_code_block(tmp_path):
    note = tmp_path / "code.md"
    note.write_text("""---
track: secure_code_review
task_type: code_review
date: 2026-05-23
tags: [sql-injection]
---

# SQL Injection in Login Form

## Key Takeaways
- Parameterized queries prevent SQL injection

```python
# Vulnerable code
query = f"SELECT * FROM users WHERE name = '{user_input}'"
cursor.execute(query)
```
""")
    parsed = parse_note(note)
    assert parsed.task_type == "code_review"
    assert "```python" in parsed.content
