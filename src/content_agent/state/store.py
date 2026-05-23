"""SQLite-backed state manager for the Content Creation Agent."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS content_pieces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_type TEXT NOT NULL,
    platform TEXT NOT NULL,
    title TEXT DEFAULT '',
    body TEXT NOT NULL,
    hashtags_json TEXT DEFAULT '[]',
    media_paths_json TEXT DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'draft',
    day_number INTEGER NOT NULL,
    generated_date TEXT NOT NULL,
    notes_used_json TEXT DEFAULT '[]',
    scheduled_time TEXT,
    posted_at TEXT,
    buffer_post_id TEXT DEFAULT '',
    post_url TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    generator TEXT NOT NULL,
    prompt TEXT DEFAULT '',
    metadata_json TEXT DEFAULT '{}',
    content_piece_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (content_piece_id) REFERENCES content_pieces(id)
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    script TEXT DEFAULT '',
    narration_path TEXT DEFAULT '',
    duration_seconds REAL DEFAULT 0.0,
    scenes_json TEXT DEFAULT '[]',
    content_piece_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (content_piece_id) REFERENCES content_pieces(id)
);

CREATE TABLE IF NOT EXISTS trend_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    trends_json TEXT NOT NULL,
    generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    day_number INTEGER NOT NULL,
    notes_count INTEGER DEFAULT 0,
    content_count INTEGER DEFAULT 0,
    images_count INTEGER DEFAULT 0,
    video_generated INTEGER DEFAULT 0,
    total_cost REAL DEFAULT 0.0,
    pipeline_result_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS engagement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_piece_id INTEGER NOT NULL,
    likes INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    views INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (content_piece_id) REFERENCES content_pieces(id)
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_content_status ON content_pieces(status);
CREATE INDEX IF NOT EXISTS idx_content_date ON content_pieces(generated_date);
CREATE INDEX IF NOT EXISTS idx_content_platform ON content_pieces(platform);
CREATE INDEX IF NOT EXISTS idx_content_type ON content_pieces(content_type);
CREATE INDEX IF NOT EXISTS idx_daily_runs_date ON daily_runs(date);
CREATE INDEX IF NOT EXISTS idx_images_type ON images(image_type);
"""


class ContentStore:
    def __init__(self, state_dir: str | Path):
        self.state_dir = Path(state_dir)
        self.db_path = self.state_dir / "content.db"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(CREATE_TABLES)
        self._conn.commit()

    # --- Content Pieces ---

    def save_content_piece(
        self,
        content_type: str,
        platform: str,
        body: str,
        day_number: int,
        generated_date: str,
        title: str = "",
        hashtags: list[str] | None = None,
        media_paths: list[str] | None = None,
        notes_used: list[str] | None = None,
        status: str = "draft",
    ) -> int:
        cursor = self._conn.execute(
            """INSERT INTO content_pieces
               (content_type, platform, title, body, hashtags_json,
                media_paths_json, status, day_number, generated_date,
                notes_used_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                content_type, platform, title, body,
                json.dumps(hashtags or []),
                json.dumps(media_paths or []),
                status, day_number, generated_date,
                json.dumps(notes_used or []),
                datetime.now(UTC).isoformat(),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def get_content_for_date(self, date: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM content_pieces WHERE generated_date = ? ORDER BY id",
            (date,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_content_by_id(self, content_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM content_pieces WHERE id = ?", (content_id,),
        ).fetchone()
        return dict(row) if row else None

    def update_content_status(
        self,
        content_id: int,
        status: str,
        post_url: str = "",
        buffer_post_id: str = "",
    ) -> None:
        updates = ["status = ?"]
        params: list[Any] = [status]
        if status == "posted":
            updates.append("posted_at = ?")
            params.append(datetime.now(UTC).isoformat())
        if post_url:
            updates.append("post_url = ?")
            params.append(post_url)
        if buffer_post_id:
            updates.append("buffer_post_id = ?")
            params.append(buffer_post_id)
        params.append(content_id)
        self._conn.execute(
            f"UPDATE content_pieces SET {', '.join(updates)} WHERE id = ?", params,
        )
        self._conn.commit()

    def update_content_media(self, content_id: int, media_paths: list[str]) -> None:
        self._conn.execute(
            "UPDATE content_pieces SET media_paths_json = ? WHERE id = ?",
            (json.dumps(media_paths), content_id),
        )
        self._conn.commit()

    def get_pending_content(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT * FROM content_pieces
               WHERE status IN ('draft', 'reviewed')
               ORDER BY generated_date DESC, id""",
        ).fetchall()
        return [dict(r) for r in rows]

    def get_posted_content(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT * FROM content_pieces WHERE status = 'posted'
               ORDER BY posted_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_content_stats(self) -> dict[str, Any]:
        row = self._conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'posted' THEN 1 ELSE 0 END) as posted,
                SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) as drafts,
                SUM(CASE WHEN status = 'scheduled' THEN 1 ELSE 0 END) as scheduled,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
               FROM content_pieces""",
        ).fetchone()
        return dict(row) if row else {"total": 0, "posted": 0, "drafts": 0, "scheduled": 0}

    def get_platform_stats(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT platform,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'posted' THEN 1 ELSE 0 END) as posted
               FROM content_pieces
               GROUP BY platform ORDER BY total DESC""",
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Images ---

    def save_image(
        self,
        image_type: str,
        file_path: str,
        generator: str,
        prompt: str = "",
        metadata: dict | None = None,
        content_piece_id: int | None = None,
    ) -> int:
        cursor = self._conn.execute(
            """INSERT INTO images
               (image_type, file_path, generator, prompt, metadata_json,
                content_piece_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                image_type, file_path, generator, prompt,
                json.dumps(metadata or {}), content_piece_id,
                datetime.now(UTC).isoformat(),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    # --- Videos ---

    def save_video(
        self,
        file_path: str,
        script: str = "",
        narration_path: str = "",
        duration_seconds: float = 0.0,
        scenes: list[dict] | None = None,
        content_piece_id: int | None = None,
    ) -> int:
        cursor = self._conn.execute(
            """INSERT INTO videos
               (file_path, script, narration_path, duration_seconds,
                scenes_json, content_piece_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                file_path, script, narration_path, duration_seconds,
                json.dumps(scenes or []), content_piece_id,
                datetime.now(UTC).isoformat(),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    # --- Trend Reports ---

    def save_trend_report(self, platform: str, trends: list[dict]) -> int:
        cursor = self._conn.execute(
            "INSERT INTO trend_reports (platform, trends_json, generated_at) VALUES (?, ?, ?)",
            (platform, json.dumps(trends), datetime.now(UTC).isoformat()),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def get_latest_trends(self, platform: str | None = None) -> list[dict[str, Any]]:
        if platform:
            rows = self._conn.execute(
                """SELECT * FROM trend_reports WHERE platform = ?
                   ORDER BY generated_at DESC LIMIT 1""",
                (platform,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT * FROM trend_reports
                   ORDER BY generated_at DESC LIMIT 5""",
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Daily Runs ---

    def save_daily_run(
        self,
        date: str,
        day_number: int,
        notes_count: int = 0,
        content_count: int = 0,
        images_count: int = 0,
        video_generated: bool = False,
        total_cost: float = 0.0,
        pipeline_result: dict | None = None,
    ) -> int:
        cursor = self._conn.execute(
            """INSERT INTO daily_runs
               (date, day_number, notes_count, content_count, images_count,
                video_generated, total_cost, pipeline_result_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                date, day_number, notes_count, content_count, images_count,
                int(video_generated), total_cost,
                json.dumps(pipeline_result or {}),
                datetime.now(UTC).isoformat(),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def run_exists_for_date(self, date: str) -> bool:
        row = self._conn.execute(
            "SELECT id FROM daily_runs WHERE date = ?", (date,),
        ).fetchone()
        return row is not None

    def get_last_run(self) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM daily_runs ORDER BY date DESC LIMIT 1",
        ).fetchone()
        return dict(row) if row else None

    def get_current_day_number(self) -> int:
        row = self._conn.execute(
            "SELECT MAX(day_number) as max_day FROM daily_runs",
        ).fetchone()
        if row and row["max_day"] is not None:
            return row["max_day"] + 1
        return 1

    # --- Engagement ---

    def save_engagement(
        self, content_piece_id: int, likes: int = 0,
        shares: int = 0, comments: int = 0, views: int = 0,
    ) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO engagement
               (content_piece_id, likes, shares, comments, views, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (content_piece_id, likes, shares, comments, views,
             datetime.now(UTC).isoformat()),
        )
        self._conn.commit()

    # --- Meta ---

    def get_meta(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,),
        ).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (key, value),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
