"""Tests for SQLite state store."""

import json

import pytest

from content_agent.state.store import ContentStore


@pytest.fixture
def store(tmp_path):
    s = ContentStore(tmp_path / "data")
    yield s
    s.close()


def test_save_and_get_content_piece(store):
    cid = store.save_content_piece(
        content_type="daily_update",
        platform="twitter",
        body="Day 1: Learned about SSRF",
        day_number=1,
        generated_date="2026-05-23",
        title="Day 1",
        hashtags=["cybersecurity", "ssrf"],
        notes_used=["/vault/ssrf.md"],
    )
    assert cid > 0

    piece = store.get_content_by_id(cid)
    assert piece is not None
    assert piece["body"] == "Day 1: Learned about SSRF"
    assert piece["day_number"] == 1
    assert piece["status"] == "draft"
    assert json.loads(piece["hashtags_json"]) == ["cybersecurity", "ssrf"]
    assert json.loads(piece["notes_used_json"]) == ["/vault/ssrf.md"]


def test_content_status_updates(store):
    cid = store.save_content_piece(
        content_type="thread", platform="linkedin",
        body="Thread content", day_number=1, generated_date="2026-05-23",
    )
    assert store.get_content_by_id(cid)["status"] == "draft"

    store.update_content_status(cid, "scheduled")
    assert store.get_content_by_id(cid)["status"] == "scheduled"

    store.update_content_status(cid, "posted", post_url="https://x.com/post/123")
    piece = store.get_content_by_id(cid)
    assert piece["status"] == "posted"
    assert piece["post_url"] == "https://x.com/post/123"
    assert piece["posted_at"] is not None


def test_content_for_date(store):
    store.save_content_piece(
        content_type="daily_update", platform="twitter",
        body="Day 1", day_number=1, generated_date="2026-05-23",
    )
    store.save_content_piece(
        content_type="thread", platform="linkedin",
        body="Thread", day_number=1, generated_date="2026-05-23",
    )
    store.save_content_piece(
        content_type="daily_update", platform="twitter",
        body="Day 2", day_number=2, generated_date="2026-05-24",
    )

    day1 = store.get_content_for_date("2026-05-23")
    assert len(day1) == 2

    day2 = store.get_content_for_date("2026-05-24")
    assert len(day2) == 1


def test_pending_and_posted_content(store):
    cid1 = store.save_content_piece(
        content_type="daily_update", platform="twitter",
        body="Draft post", day_number=1, generated_date="2026-05-23",
    )
    cid2 = store.save_content_piece(
        content_type="thread", platform="linkedin",
        body="Posted thread", day_number=1, generated_date="2026-05-23",
    )
    store.update_content_status(cid2, "posted")

    pending = store.get_pending_content()
    assert len(pending) == 1
    assert pending[0]["id"] == cid1

    posted = store.get_posted_content()
    assert len(posted) == 1
    assert posted[0]["id"] == cid2


def test_content_stats(store):
    store.save_content_piece(
        content_type="daily_update", platform="twitter",
        body="1", day_number=1, generated_date="2026-05-23",
    )
    cid2 = store.save_content_piece(
        content_type="thread", platform="linkedin",
        body="2", day_number=1, generated_date="2026-05-23",
    )
    store.update_content_status(cid2, "posted")

    stats = store.get_content_stats()
    assert stats["total"] == 2
    assert stats["posted"] == 1
    assert stats["drafts"] == 1


def test_platform_stats(store):
    store.save_content_piece(
        content_type="daily_update", platform="twitter",
        body="t1", day_number=1, generated_date="2026-05-23",
    )
    store.save_content_piece(
        content_type="hot_take", platform="twitter",
        body="t2", day_number=1, generated_date="2026-05-23",
    )
    store.save_content_piece(
        content_type="thread", platform="linkedin",
        body="l1", day_number=1, generated_date="2026-05-23",
    )

    pstats = store.get_platform_stats()
    twitter_stat = next(p for p in pstats if p["platform"] == "twitter")
    assert twitter_stat["total"] == 2


def test_save_and_get_image(store):
    iid = store.save_image(
        image_type="day_card",
        file_path="/output/day_1.png",
        generator="puppeteer",
        prompt="Day 1 card",
        metadata={"day_number": 1},
    )
    assert iid > 0


def test_trend_report_save_and_get(store):
    tid = store.save_trend_report("twitter", [
        {"topic": "AI Security", "relevance_score": 0.9, "context": "New attacks"},
        {"topic": "Zero Trust", "relevance_score": 0.7, "context": "Enterprise adoption"},
    ])
    assert tid > 0

    trends = store.get_latest_trends("twitter")
    assert len(trends) == 1
    items = json.loads(trends[0]["trends_json"])
    assert len(items) == 2
    assert items[0]["topic"] == "AI Security"


def test_daily_run_tracking(store):
    assert not store.run_exists_for_date("2026-05-23")

    rid = store.save_daily_run(
        date="2026-05-23", day_number=1,
        notes_count=3, content_count=7, images_count=2,
    )
    assert rid > 0
    assert store.run_exists_for_date("2026-05-23")

    last = store.get_last_run()
    assert last is not None
    assert last["day_number"] == 1
    assert last["notes_count"] == 3


def test_day_number_tracking(store):
    assert store.get_current_day_number() == 1

    store.save_daily_run(date="2026-05-23", day_number=1)
    assert store.get_current_day_number() == 2

    store.save_daily_run(date="2026-05-24", day_number=2)
    assert store.get_current_day_number() == 3


def test_meta_store(store):
    assert store.get_meta("brand_voice") is None

    store.set_meta("brand_voice", "professional, authentic, technical")
    assert store.get_meta("brand_voice") == "professional, authentic, technical"

    store.set_meta("brand_voice", "updated voice")
    assert store.get_meta("brand_voice") == "updated voice"


def test_engagement_tracking(store):
    cid = store.save_content_piece(
        content_type="daily_update", platform="twitter",
        body="test", day_number=1, generated_date="2026-05-23",
    )
    store.save_engagement(cid, likes=42, shares=10, comments=5, views=1200)

    # Verify no error on second call (upsert)
    store.save_engagement(cid, likes=50, shares=15, comments=8, views=2000)


def test_update_content_media(store):
    cid = store.save_content_piece(
        content_type="daily_update", platform="twitter",
        body="test", day_number=1, generated_date="2026-05-23",
    )
    store.update_content_media(cid, ["/output/img1.png", "/output/img2.png"])

    piece = store.get_content_by_id(cid)
    media = json.loads(piece["media_paths_json"])
    assert len(media) == 2
    assert media[0] == "/output/img1.png"
