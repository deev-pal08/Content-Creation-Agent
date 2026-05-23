"""Obsidian vault notes parser."""

from __future__ import annotations

import re
from pathlib import Path

import frontmatter

from content_agent.models import ObsidianNote


def parse_note(file_path: Path) -> ObsidianNote:
    post = frontmatter.load(str(file_path))
    meta = post.metadata or {}
    content = post.content or ""

    key_takeaways = _extract_section(content, "Key Takeaways")
    connections = _extract_links(content)
    open_questions = _extract_section(content, "Open Questions")

    title = meta.get("title", "") or _extract_title(content) or file_path.stem

    return ObsidianNote(
        file_path=str(file_path),
        title=title,
        track=meta.get("track", ""),
        task_type=meta.get("task_type", ""),
        source_url=meta.get("source_url", ""),
        date=str(meta.get("date", "")),
        difficulty=meta.get("difficulty", ""),
        tags=meta.get("tags", []) or [],
        content=content,
        key_takeaways=key_takeaways,
        connections=connections,
        open_questions=open_questions,
    )


def load_notes_for_date(vault_path: str | Path, date: str, glob: str = "**/*.md") -> list[ObsidianNote]:
    vault = Path(vault_path).expanduser()
    if not vault.exists():
        return []

    notes = []
    for md_file in vault.glob(glob):
        if md_file.name.startswith("."):
            continue
        try:
            note = parse_note(md_file)
        except Exception:
            continue
        if note.date == date:
            notes.append(note)
    return notes


def load_all_notes(vault_path: str | Path, glob: str = "**/*.md") -> list[ObsidianNote]:
    vault = Path(vault_path).expanduser()
    if not vault.exists():
        return []

    notes = []
    for md_file in vault.glob(glob):
        if md_file.name.startswith("."):
            continue
        try:
            notes.append(parse_note(md_file))
        except Exception:
            continue
    return notes


def _extract_title(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped[2:].strip()
    return ""


def _extract_section(content: str, heading: str) -> list[str]:
    items: list[str] = []
    in_section = False
    for line in content.splitlines():
        stripped = line.strip()
        if re.match(rf"^##\s+{re.escape(heading)}", stripped, re.IGNORECASE):
            in_section = True
            continue
        if in_section:
            if stripped.startswith("## "):
                break
            if stripped.startswith("- "):
                items.append(stripped[2:].strip())
    return items


def _extract_links(content: str) -> list[str]:
    return re.findall(r"\[\[([^\]]+)\]\]", content)
