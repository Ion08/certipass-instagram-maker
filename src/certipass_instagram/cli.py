"""Command-line interface for creating and explicitly publishing static image posts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .ledger import ContentLedger
from .pipeline import PipelineError, create_daily_set, load_draft, publish_draft


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="certipass-instagram", description="Create a daily certiPass image-post set.")
    subs = parser.add_subparsers(dest="command", required=True)
    draft = subs.add_parser("draft", help="Create one meme, one educational and one informative static post (never publishes).")
    draft.add_argument("--date", type=date.fromisoformat, help="ISO date; defaults to Europe/Chisinau today.")
    draft.add_argument("--ledger", default="data/ledger.json")
    draft.add_argument("--output-dir", default="artifacts")
    approve = subs.add_parser("approve", help="Mark a reviewed draft READY for a later explicit publish command.")
    approve.add_argument("post_id")
    approve.add_argument("--ledger", default="data/ledger.json")
    publish = subs.add_parser("publish", help="Publish reviewed static images through Meta's official API.")
    publish.add_argument("post_id")
    publish.add_argument("--draft", required=True)
    publish.add_argument("--media-urls", required=True, nargs="+", help="Public HTTPS PNG URLs, one per slide.")
    publish.add_argument("--ledger", default="data/ledger.json")
    publish.add_argument("--confirm-publish", action="store_true", help="Confirm that the image post should be posted now.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "draft":
            posts = create_daily_set(day=args.date, ledger_path=args.ledger, output_dir=args.output_dir)
            print(json.dumps({"posts": [
                {"id": draft.id, "content_type": draft.content_type, "topic": draft.topic,
                 "caption": draft.caption,
                 "draft": str(Path(args.output_dir) / f"{draft.id}.json"),
                 "post_type": draft.post_type, "images": [str(image) for image in images],
                 "status": "IDEA", "published": False}
                for draft, images in posts
            ]}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "approve":
            ledger = ContentLedger(args.ledger)
            ledger.update_status(args.post_id, "APPROVED")
            ledger.update_status(args.post_id, "READY")
            print(f"{args.post_id} is READY. Review every exact PNG image before publishing.")
            return 0
        if args.command == "publish":
            if load_draft(args.draft).id != args.post_id:
                raise PipelineError("The post ID does not match the selected draft file.")
            media_id = publish_draft(draft_path=args.draft, media_urls=args.media_urls,
                                     ledger_path=args.ledger, confirm=args.confirm_publish)
            print(f"Published Instagram media ID: {media_id}")
            return 0
    except (PipelineError, RuntimeError, ValueError) as exc:
        print(f"Stopped safely: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
