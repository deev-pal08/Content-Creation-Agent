"""Click CLI — all commands for the Content Creation Agent."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime

import click
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def _load_config():
    from content_agent.config import load_config
    try:
        return load_config()
    except FileNotFoundError:
        click.echo("Error: config.yaml not found. Copy config.example.yaml to config.yaml.", err=True)
        sys.exit(1)


def _get_store(cfg):
    from content_agent.state.store import ContentStore
    return ContentStore(cfg.state_dir)


@click.group()
def cli():
    """Content Creation Agent — Obsidian notes to social media content."""


@cli.command()
@click.option("--no-publish", is_flag=True, help="Generate content without scheduling posts")
@click.option("--force", is_flag=True, help="Regenerate even if a run exists for today")
@click.option("--date", default=None, help="Generate for a specific date (YYYY-MM-DD)")
def daily(no_publish: bool, force: bool, date: str | None):
    """Run the full daily content pipeline."""
    cfg = _load_config()
    store = _get_store(cfg)

    target_date = date or datetime.now(UTC).strftime("%Y-%m-%d")

    if store.run_exists_for_date(target_date) and not force:
        click.echo(f"Pipeline already ran for {target_date}. Use --force to regenerate.")
        sys.exit(0)

    day_number = store.get_current_day_number()
    if date:
        last_run = store.get_last_run()
        if last_run:
            day_number = last_run["day_number"] + 1

    click.echo(f"Day {day_number} — {target_date}")
    click.echo("=" * 40)

    # Step 1: Ingest notes
    click.echo("\n1. Ingesting Obsidian notes...")
    from content_agent.ingest import load_notes_for_date
    notes = load_notes_for_date(cfg.obsidian.vault_path, target_date, cfg.obsidian.notes_glob)
    if not notes:
        click.echo(f"   No notes found for {target_date} in {cfg.obsidian.vault_path}")
        click.echo("   Tip: Make sure your notes have 'date: {target_date}' in YAML frontmatter")
        sys.exit(1)
    click.echo(f"   Found {len(notes)} note(s)")
    for n in notes:
        click.echo(f"   - {n.title} [{n.track}]")

    # Step 2: Research trends
    click.echo("\n2. Researching trends...")
    from content_agent.research import TrendResearcher
    researcher = TrendResearcher(
        xai_api_key=os.getenv("XAI_API_KEY", ""),
        perplexity_api_key=os.getenv("PERPLEXITY_API_KEY", ""),
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        trend_model_x=cfg.llm.trend_model_x,
        trend_model_web=cfg.llm.trend_model_web,
        trend_model_youtube=cfg.llm.trend_model_youtube,
    )
    focus = ", ".join(set(n.track for n in notes if n.track)) or "cybersecurity, AI security"
    trend_reports = researcher.research_all(focus)
    all_trends = [t for r in trend_reports for t in r.trends]
    click.echo(f"   Found {len(all_trends)} trend(s) across {len(trend_reports)} source(s)")

    # Step 3: Generate content
    click.echo("\n3. Writing content...")
    from content_agent.writer import ContentWriter
    writer = ContentWriter(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        xai_api_key=os.getenv("XAI_API_KEY", ""),
        writer_model=cfg.llm.writer_model,
        hot_take_model=cfg.llm.hot_take_model,
        max_tokens=cfg.llm.max_tokens,
    )
    pieces = writer.generate_all_content(notes, day_number, all_trends, target_date)
    click.echo(f"   Generated {len(pieces)} content piece(s)")
    for p in pieces:
        click.echo(f"   - {p.content_type.value} for {p.platform.value}")

    # Step 3b: Generate educational image content (Claude decides what fits)
    click.echo("\n   Generating educational image content...")
    code_challenge = writer.generate_code_challenge(notes)
    if code_challenge:
        click.echo(f"   Code challenge: {code_challenge['vulnerability']} ({code_challenge['language']})")
    else:
        click.echo("   No code challenge for today's topic")

    comparison = writer.generate_comparison(notes)
    if comparison:
        click.echo(f"   Comparison card: {comparison.get('title', 'untitled')}")
    else:
        click.echo("   No comparison card for today's topic")

    key_fact = writer.generate_key_fact(notes)
    if key_fact:
        click.echo(f"   Key fact: {key_fact.get('headline', '')[:60]}...")
    else:
        click.echo("   No key fact generated")

    carousel = writer.generate_carousel(notes)
    if carousel:
        click.echo(f"   Carousel: {carousel.get('title', '')} ({len(carousel.get('slides', []))} slides)")
    else:
        click.echo("   No carousel generated")

    # Step 4: Generate images
    click.echo("\n4. Generating images...")
    from content_agent.images import ImageProducer
    img_producer = ImageProducer(
        output_dir=cfg.images.output_dir,
        brand_colors=cfg.images.brand_colors,
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    )
    images = img_producer.generate_all_for_day(
        notes, day_number, target_date,
        code_challenge=code_challenge,
        comparison=comparison,
        key_fact=key_fact,
        carousel=carousel,
    )
    click.echo(f"   Generated {len(images)} image(s)")
    for img in images:
        click.echo(f"   - {img.image_type.value} via {img.generator.value}")

    # Step 5: Generate video
    click.echo("\n5. Generating video...")
    video_asset = None
    video_scripts = [p for p in pieces if p.content_type == "visual_lesson"]
    if video_scripts:
        from content_agent.video import VideoProducer
        vid_producer = VideoProducer(
            output_dir=cfg.video.output_dir,
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            tts_model=cfg.llm.tts_model,
            tts_voice=cfg.llm.tts_voice,
            width=cfg.video.width,
            height=cfg.video.height,
            duration_target=cfg.video.duration_target,
        )
        video_asset = vid_producer.generate_for_day(
            video_scripts[0].body, notes, day_number,
        )
        if video_asset.file_path:
            click.echo(f"   Video rendered: {video_asset.file_path}")
        else:
            click.echo("   Video script generated (Remotion rendering not available)")
    else:
        click.echo("   No video script generated")

    # Step 6: SEO optimization
    click.echo("\n6. Optimizing SEO & hashtags...")
    from content_agent.seo import SEOOptimizer
    seo = SEOOptimizer(
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        seo_model=cfg.llm.seo_model,
        default_hashtags=cfg.seo.default_hashtags,
        posting_times=cfg.seo.posting_times,
    )
    pieces = seo.optimize_content(pieces, all_trends)
    click.echo("   Hashtags assigned to all content pieces")

    # Step 7: Persist to DB
    click.echo("\n7. Saving to database...")
    content_ids = []
    for piece in pieces:
        cid = store.save_content_piece(
            content_type=piece.content_type.value,
            platform=piece.platform.value,
            body=piece.body,
            day_number=day_number,
            generated_date=target_date,
            title=piece.title,
            hashtags=piece.hashtags,
            media_paths=piece.media_paths,
            notes_used=piece.notes_used,
            status="draft",
        )
        content_ids.append(cid)

    for img in images:
        store.save_image(
            image_type=img.image_type.value,
            file_path=img.file_path,
            generator=img.generator.value,
            prompt=img.prompt,
            metadata=img.metadata,
        )

    if video_asset:
        store.save_video(
            file_path=video_asset.file_path,
            script=video_asset.script,
            narration_path=video_asset.narration_path,
            duration_seconds=video_asset.duration_seconds,
            scenes=video_asset.scenes,
        )

    for report in trend_reports:
        store.save_trend_report(
            report.platform,
            [t.model_dump() for t in report.trends],
        )

    store.save_daily_run(
        date=target_date,
        day_number=day_number,
        notes_count=len(notes),
        content_count=len(pieces),
        images_count=len(images),
        video_generated=video_asset is not None and bool(video_asset.file_path),
    )
    click.echo(f"   Saved {len(pieces)} pieces, {len(images)} images, {len(trend_reports)} trend reports")

    # Step 8: Publish
    if no_publish:
        click.echo("\n8. Skipping publish (--no-publish)")
    else:
        click.echo("\n8. Scheduling posts...")
        from content_agent.publisher import BufferPublisher
        publisher = BufferPublisher(
            access_token=os.getenv("BUFFER_ACCESS_TOKEN", ""),
            profile_ids=cfg.publisher.buffer_profile_ids,
        )
        if publisher.has_credentials():
            posting_times = {p: seo.get_optimal_posting_time(p) for p in ["twitter", "linkedin", "instagram", "youtube"]}
            results = publisher.publish_all(pieces, posting_times)
            scheduled = sum(1 for r in results if r and "error" not in r)
            click.echo(f"   Scheduled {scheduled}/{len(pieces)} posts")
            for cid in content_ids:
                store.update_content_status(cid, "scheduled")
        else:
            click.echo("   No Buffer credentials — content saved as drafts")

    # Summary
    click.echo("\n" + "=" * 40)
    click.echo(f"Day {day_number} complete!")
    click.echo(f"  Notes: {len(notes)}")
    click.echo(f"  Content pieces: {len(pieces)}")
    click.echo(f"  Images: {len(images)}")
    click.echo(f"  Video: {'Yes' if video_asset and video_asset.file_path else 'Script only'}")

    store.close()


@cli.command()
def status():
    """Show content pipeline status."""
    cfg = _load_config()
    store = _get_store(cfg)

    stats = store.get_content_stats()
    click.echo("Content Pipeline Status")
    click.echo("=" * 40)
    click.echo(f"  Total pieces: {stats['total']}")
    click.echo(f"  Posted: {stats['posted']}")
    click.echo(f"  Drafts: {stats['drafts']}")
    click.echo(f"  Scheduled: {stats['scheduled']}")

    last_run = store.get_last_run()
    if last_run:
        click.echo(f"\nLast run: Day {last_run['day_number']} ({last_run['date']})")
        click.echo(f"  Notes: {last_run['notes_count']}")
        click.echo(f"  Content: {last_run['content_count']}")
        click.echo(f"  Images: {last_run['images_count']}")
    else:
        click.echo("\nNo runs yet.")

    platform_stats = store.get_platform_stats()
    if platform_stats:
        click.echo("\nBy Platform:")
        for ps in platform_stats:
            click.echo(f"  {ps['platform']}: {ps['posted']}/{ps['total']} posted")

    store.close()


@cli.command()
@click.option("--limit", default=20, help="Number of recent items to show")
def history(limit: int):
    """Show recent content history."""
    cfg = _load_config()
    store = _get_store(cfg)

    posted = store.get_posted_content(limit)
    if not posted:
        click.echo("No posted content yet.")
        store.close()
        return

    click.echo(f"Recent Content ({len(posted)} items)")
    click.echo("=" * 60)
    for p in posted:
        hashtags = json.loads(p["hashtags_json"]) if p["hashtags_json"] else []
        click.echo(f"\n  [{p['platform']}] {p['content_type']} — Day {p['day_number']}")
        click.echo(f"  Posted: {p['posted_at'] or 'N/A'}")
        preview = p["body"][:100] + "..." if len(p["body"]) > 100 else p["body"]
        click.echo(f"  {preview}")
        if hashtags:
            click.echo(f"  #{' #'.join(hashtags[:5])}")

    store.close()


@cli.command()
def init():
    """Initialize the database and output directories."""
    cfg = _load_config()
    store = _get_store(cfg)

    from pathlib import Path
    Path(cfg.images.output_dir).mkdir(parents=True, exist_ok=True)
    Path(cfg.video.output_dir).mkdir(parents=True, exist_ok=True)

    click.echo("Content Creation Agent initialized.")
    click.echo(f"  Database: {store.db_path}")
    click.echo(f"  Image output: {cfg.images.output_dir}")
    click.echo(f"  Video output: {cfg.video.output_dir}")
    click.echo(f"  Obsidian vault: {cfg.obsidian.vault_path}")

    store.close()


@cli.command()
@click.argument("content_id", type=int)
def preview(content_id: int):
    """Preview a content piece by ID."""
    cfg = _load_config()
    store = _get_store(cfg)

    piece = store.get_content_by_id(content_id)
    if not piece:
        click.echo(f"Content piece {content_id} not found.", err=True)
        sys.exit(1)

    click.echo(f"Content #{piece['id']}")
    click.echo(f"  Type: {piece['content_type']}")
    click.echo(f"  Platform: {piece['platform']}")
    click.echo(f"  Day: {piece['day_number']}")
    click.echo(f"  Status: {piece['status']}")
    click.echo(f"  Date: {piece['generated_date']}")
    click.echo()
    click.echo(piece["body"])

    hashtags = json.loads(piece["hashtags_json"]) if piece["hashtags_json"] else []
    if hashtags:
        click.echo(f"\nHashtags: #{' #'.join(hashtags)}")

    media = json.loads(piece["media_paths_json"]) if piece["media_paths_json"] else []
    if media:
        click.echo(f"\nMedia: {', '.join(media)}")

    store.close()


@cli.command()
def pending():
    """Show all pending (unposted) content."""
    cfg = _load_config()
    store = _get_store(cfg)

    items = store.get_pending_content()
    if not items:
        click.echo("No pending content.")
        store.close()
        return

    click.echo(f"Pending Content ({len(items)} items)")
    click.echo("=" * 50)
    for p in items:
        preview = p["body"][:80] + "..." if len(p["body"]) > 80 else p["body"]
        click.echo(f"  #{p['id']} [{p['platform']}] {p['content_type']} Day {p['day_number']}: {preview}")

    store.close()


@cli.command()
@click.option("--date", default=None, help="Show notes for specific date (YYYY-MM-DD)")
def ingest(date: str | None):
    """Parse and display Obsidian notes for a date."""
    cfg = _load_config()
    target_date = date or datetime.now(UTC).strftime("%Y-%m-%d")

    from content_agent.ingest import load_notes_for_date
    notes = load_notes_for_date(cfg.obsidian.vault_path, target_date, cfg.obsidian.notes_glob)

    if not notes:
        click.echo(f"No notes found for {target_date}")
        return

    click.echo(f"Notes for {target_date} ({len(notes)} found)")
    click.echo("=" * 50)
    for note in notes:
        click.echo(f"\n  {note.title}")
        click.echo(f"  Track: {note.track or 'N/A'}")
        click.echo(f"  Type: {note.task_type or 'N/A'}")
        click.echo(f"  Tags: {', '.join(note.tags) if note.tags else 'None'}")
        if note.key_takeaways:
            click.echo("  Takeaways:")
            for t in note.key_takeaways:
                click.echo(f"    - {t}")
