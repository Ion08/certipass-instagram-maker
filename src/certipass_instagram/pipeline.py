"""Orchestrate research, image generation and static post publishing."""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .ai import CodexGenerator
from .imagegen import OpenRouterConfig, OpenRouterImageGenerator
from .ledger import ContentLedger
from .models import ContentDraft
from .render import render_carousel
from .research import fetch_snapshot


class PipelineError(RuntimeError):
    pass


def local_today() -> date:
    return datetime.now(ZoneInfo("Europe/Chisinau")).date()


def create_draft(*, day: date | None = None, ledger_path: str | Path = "data/ledger.json",
                 output_dir: str | Path = "artifacts", generator: CodexGenerator | None = None,
                 image_generator: OpenRouterImageGenerator | None = None,
                 render: bool = True) -> tuple[ContentDraft, list[Path]]:
    """Research, write and render a reviewable image post or carousel."""
    target_day = day or local_today()
    ledger = ContentLedger(ledger_path)
    records = ledger.list_records()
    recent = [f"{r.get('topic', '')}: {r.get('hook', '')}" for r in records[-60:]]
    pages = fetch_snapshot()
    if not any(page.url.startswith("https://www.certipass.md/") for page in pages):
        raise PipelineError("Could not read certiPass.md for current brand/product facts; no draft was generated.")
    if not any(page.url.startswith("https://docs.python.org/") or page.url.startswith("https://www.sqlite.org/")
               or page.url.startswith("https://developer.mozilla.org/") for page in pages):
        raise PipelineError("No current technical reference was reachable; no draft was generated.")
    draft = (generator or CodexGenerator()).generate(
        day=target_day, evidence=[page.evidence() for page in pages], recent_topics=recent,
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{draft.id}.json"
    image_paths: list[Path] = []
    if render:
        image_generator = image_generator or OpenRouterImageGenerator(OpenRouterConfig.from_env())
        art_dir = output_dir / "artwork"
        art_dir.mkdir(parents=True, exist_ok=True)
        sources = []
        for index, slide in enumerate(draft.slides, 1):
            artwork_path = art_dir / f"{draft.id}-art-{index:02d}.png"
            try:
                artwork_path.write_bytes(image_generator.generate(slide.image_prompt))
            except Exception:
                # Keep credential-bearing provider exceptions out of Actions logs.
                raise PipelineError(f"Image generation failed on slide {index}; no post was published.") from None
            sources.append(artwork_path)
        image_paths = render_carousel(draft, sources, output_dir)
        draft = ContentDraft.from_dict({**draft.to_dict(), "asset_paths": [str(p) for p in image_paths]})
    ledger.reserve(draft)
    json_path.write_text(json.dumps(draft.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return draft, image_paths


def next_content_type(records: list[dict], day: date) -> str:
    """Rotate post types so adjacent publishing days differ."""
    sequence = ("meme", "educational", "informative")
    prior = [row for row in records if row.get("publish_date", "") < day.isoformat()
             and row.get("content_type") in sequence]
    if prior:
        previous = prior[-1]["content_type"]
        return sequence[(sequence.index(previous) + 1) % len(sequence)]
    # Stable starting point across retries, without always beginning on the same type.
    return sequence[day.toordinal() % len(sequence)]


def create_daily_post(*, day: date | None = None, ledger_path: str | Path = "data/ledger.json",
                      output_dir: str | Path = "artifacts", generator: CodexGenerator | None = None,
                      image_generator: OpenRouterImageGenerator | None = None
                      ) -> tuple[ContentDraft, list[Path]]:
    """Create exactly one pastel-editorial Instagram image post for a date."""
    target_day = day or local_today()
    ledger = ContentLedger(ledger_path)
    records = ledger.list_records()
    if any(row.get("publish_date") == target_day.isoformat() for row in records):
        raise PipelineError("A post is already drafted for this date; refusing to generate a second one.")
    content_type = next_content_type(records, target_day)
    recent_history = [
        {key: str(row.get(key, "")) for key in
         ("publish_date", "content_type", "topic", "hook", "character", "visual_motif", "caption")}
        for row in records[-90:]
    ]
    pages = fetch_snapshot()
    if not any(page.url.startswith("https://www.certipass.md/") for page in pages):
        raise PipelineError("Could not read certiPass.md for current brand/product facts; no daily post was generated.")
    if not any(page.url.startswith(("https://docs.python.org/", "https://www.sqlite.org/", "https://developer.mozilla.org/"))
               for page in pages):
        raise PipelineError("No current technical reference was reachable; no daily post was generated.")
    draft = (generator or CodexGenerator()).generate_daily_post(
        day=target_day, content_type=content_type,
        evidence=[page.evidence() for page in pages], recent_history=recent_history,
    )
    if draft.content_type != content_type or draft.publish_date != target_day or len(draft.slides) != 1:
        raise PipelineError("The daily generator must return one post in the planned format for the requested date.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    image_generator = image_generator or OpenRouterImageGenerator(OpenRouterConfig.from_env())
    art_dir = output_dir / "artwork"
    art_dir.mkdir(parents=True, exist_ok=True)
    art_path = art_dir / f"{draft.id}-art-01.png"
    try:
        art_path.write_bytes(image_generator.generate(draft.slides[0].image_prompt))
    except Exception:
        raise PipelineError(f"Image generation failed for the {draft.content_type} post; nothing was published.") from None
    image_paths = render_carousel(draft, [art_path], output_dir)
    draft = ContentDraft.from_dict({**draft.to_dict(), "asset_paths": [str(path) for path in image_paths]})
    ledger.reserve(draft)
    path = output_dir / f"{draft.id}.json"
    path.write_text(json.dumps(draft.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return draft, image_paths


def load_draft(path: str | Path) -> ContentDraft:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return ContentDraft.from_dict(raw)
    except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
        raise PipelineError("Could not load the content draft") from exc


def publish_draft(*, draft_path: str | Path, media_urls: list[str], ledger_path: str | Path = "data/ledger.json",
                  confirm: bool = False) -> str:
    """Publish an already-reviewed static image post or carousel through Meta."""
    if not confirm or os.environ.get("INSTAGRAM_PUBLISH_ENABLED") != "true":
        raise PipelineError("Publishing is disabled. Review every image, pass --confirm-publish, and set INSTAGRAM_PUBLISH_ENABLED=true.")
    if os.environ.get("INSTAGRAM_APP_LIVE_APPROVED") != "true":
        raise PipelineError("Meta app is not marked live/approved. Publishing remains disabled.")
    if not media_urls or any(not url.startswith("https://") for url in media_urls):
        raise PipelineError("Meta must fetch each PNG from a public HTTPS URL; configure image hosting first.")
    from .meta import (InstagramPublisher, MetaAmbiguousPublishError,
                       MetaConfig, MetaTerminalError, MetaTransientError)
    import time

    draft = load_draft(draft_path)
    ledger = ContentLedger(ledger_path)
    row = ledger.get(draft.id)
    if row["status"] != "READY":
        raise PipelineError("Draft must be explicitly marked READY in the ledger before publishing.")
    publisher = InstagramPublisher(MetaConfig.from_env(dry_run=False))
    if len(media_urls) != len(draft.slides):
        raise PipelineError("Provide one public image URL for each post/carousel slide.")
    container_id = publisher.create_post(image_urls=media_urls, caption=draft.caption)
    if not container_id:
        raise PipelineError("Meta did not return a container ID.")
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        status = publisher.get_container_status(container_id)
        if status == "FINISHED":
            break
        if status in {"ERROR", "EXPIRED"}:
            raise PipelineError(f"Meta image processing stopped with status {status}.")
        time.sleep(10)
    else:
        raise PipelineError("Meta image processing timed out; check the container before retrying.")
    ledger.begin_publishing(draft.id)
    try:
        media_id = publisher.publish_post(container_id)
    except MetaAmbiguousPublishError:
        ledger.mark_ambiguous(draft.id)
        raise
    except (MetaTerminalError, MetaTransientError):
        ledger.update_status(draft.id, "FAILED")
        raise
    if not media_id:
        ledger.mark_ambiguous(draft.id)
        raise PipelineError("Publish result is ambiguous; reconcile in Meta before retrying.")
    ledger.update_status(draft.id, "PUBLISHED", instagram_media_id=media_id)
    return media_id
