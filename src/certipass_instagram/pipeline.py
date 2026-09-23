"""Orchestrate a single local content-and-Reel draft; publishing is opt-in."""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .ai import CodexGenerator
from .ledger import ContentLedger
from .models import ContentDraft
from .render import render_reel
from .research import fetch_snapshot


class PipelineError(RuntimeError):
    pass


def local_today() -> date:
    return datetime.now(ZoneInfo("Europe/Chisinau")).date()


def create_draft(*, day: date | None = None, ledger_path: str | Path = "data/ledger.json",
                 output_dir: str | Path = "artifacts", generator: CodexGenerator | None = None,
                 render: bool = True) -> tuple[ContentDraft, Path | None]:
    """Research, generate, reserve the day and render a reviewable MP4 locally."""
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
    ledger.reserve(draft)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"reel-{target_day.isoformat()}.json"
    json_path.write_text(json.dumps(draft.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    video_path: Path | None = None
    if render:
        video_path = output_dir / f"reel-{target_day.isoformat()}.mp4"
        render_reel(draft, video_path)
    return draft, video_path


def load_draft(path: str | Path) -> ContentDraft:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return ContentDraft.from_dict(raw)
    except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
        raise PipelineError("Could not load the content draft") from exc


def publish_draft(*, draft_path: str | Path, media_url: str, ledger_path: str | Path = "data/ledger.json",
                  confirm: bool = False) -> str:
    """Publish an already-reviewed Reel; two explicit gates prevent accidental posts."""
    if not confirm or os.environ.get("INSTAGRAM_PUBLISH_ENABLED") != "true":
        raise PipelineError("Publishing is disabled. Review the Reel, pass --confirm-publish, and set INSTAGRAM_PUBLISH_ENABLED=true.")
    if os.environ.get("INSTAGRAM_APP_LIVE_APPROVED") != "true":
        raise PipelineError("Meta app is not marked live/approved. Publishing remains disabled.")
    if not media_url.startswith("https://"):
        raise PipelineError("Meta must fetch the rendered MP4 from a public HTTPS URL; configure hosting first.")
    from .meta import (InstagramPublisher, MetaAmbiguousPublishError,
                       MetaConfig, MetaTerminalError, MetaTransientError)
    import time

    draft = load_draft(draft_path)
    ledger = ContentLedger(ledger_path)
    row = ledger.get(draft.id)
    if row["status"] != "READY":
        raise PipelineError("Draft must be explicitly marked READY in the ledger before publishing.")
    publisher = InstagramPublisher(MetaConfig.from_env(dry_run=False))
    container_id = publisher.create_reel(video_url=media_url, caption=draft.caption)
    if not container_id:
        raise PipelineError("Meta did not return a container ID.")
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        status = publisher.get_container_status(container_id)
        if status == "FINISHED":
            break
        if status in {"ERROR", "EXPIRED"}:
            raise PipelineError(f"Meta Reel processing stopped with status {status}.")
        time.sleep(10)
    else:
        raise PipelineError("Meta Reel processing timed out; check the container before retrying.")
    ledger.begin_publishing(draft.id)
    try:
        media_id = publisher.publish_reel(container_id)
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
