"""Durable, process-safe content ledger.

The JSON file is updated atomically under an OS file lock. Each post is stored
once; status changes are appended to its ``history`` so the audit trail is
preserved. Lock files contain no credentials or user-supplied content.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator

from .models import ContentDraft


class LedgerError(Exception):
    """Base class for ledger errors."""


class DuplicateDayError(LedgerError):
    """A post has already reserved the requested publish date."""


class DuplicateContentError(LedgerError):
    """A draft is an exact or near duplicate of existing content."""


class InvalidTransitionError(LedgerError):
    """A requested status transition is not allowed."""


class AmbiguousPublishError(LedgerError):
    """Publishing outcome is uncertain and must be reconciled first."""


class RecordNotFoundError(LedgerError):
    """No ledger record has the requested ID."""


class LedgerCorruptionError(LedgerError):
    """The persisted ledger is invalid or cannot be decoded."""


VALID_STATUSES = frozenset(
    {"IDEA", "APPROVED", "READY", "PUBLISHING", "AMBIGUOUS", "PUBLISHED", "FAILED", "REJECTED"}
)
TRANSITIONS: dict[str, frozenset[str]] = {
    "IDEA": frozenset({"APPROVED", "REJECTED"}),
    "APPROVED": frozenset({"READY", "REJECTED"}),
    "READY": frozenset({"PUBLISHING", "REJECTED"}),
    "PUBLISHING": frozenset({"PUBLISHED", "FAILED", "AMBIGUOUS"}),
    # Returning to READY requires explicit confirmation that Meta did not publish.
    "AMBIGUOUS": frozenset({"PUBLISHED", "READY"}),
    "FAILED": frozenset(),
    "PUBLISHED": frozenset(),
    "REJECTED": frozenset(),
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.findall(r"[\w]+", text, flags=re.UNICODE))


def _fingerprint(draft: ContentDraft) -> str:
    material = "\n".join(_normalize(part) for part in (draft.topic, draft.hook, draft.caption))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _similarity(left: str, right: str) -> float:
    a, b = set(_normalize(left).split()), set(_normalize(right).split())
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class ContentLedger:
    """JSON-backed ledger with atomic daily reservation and audited updates."""

    def __init__(self, path: str | Path, *, similarity_threshold: float = 0.82):
        if not 0 < similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be within (0, 1]")
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.similarity_threshold = similarity_threshold

    @contextmanager
    def _locked(self) -> Iterator[None]:
        """Serialize readers/writers across processes using an advisory lock."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # GitHub Actions uses Linux; flock also works on macOS for local use.
        import fcntl

        with self.lock_path.open("a+b") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _read_records(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("records"), list):
                raise ValueError("unexpected ledger schema")
            records = data["records"]
            if any(not isinstance(row, dict) or not row.get("id") for row in records):
                raise ValueError("invalid record")
            return records
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise LedgerCorruptionError("ledger could not be read") from exc

    def _write_records(self, records: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"version": 1, "records": records}, ensure_ascii=False, indent=2) + "\n"
        fd, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, self.path)
            # Persist the rename where supported.
            dir_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def list_records(self) -> list[dict]:
        with self._locked():
            return self._read_records()

    def get(self, post_id: str) -> dict:
        with self._locked():
            for row in self._read_records():
                if row["id"] == post_id:
                    return row
        raise RecordNotFoundError("content record was not found")

    def reserve(self, draft: ContentDraft) -> dict:
        """Atomically reserve at most one post for a date."""
        row = draft.to_dict()
        if row["status"] not in VALID_STATUSES or row["status"] != "IDEA":
            raise InvalidTransitionError("new records must start in IDEA")
        row["fingerprint"] = _fingerprint(draft)
        now = datetime.now(timezone.utc).isoformat()
        row["history"] = [{"status": "IDEA", "at": now}]
        with self._locked():
            records = self._read_records()
            day = draft.publish_date.isoformat()
            if any(item.get("publish_date") == day for item in records):
                raise DuplicateDayError("publish date is already reserved")
            for item in records:
                if row["fingerprint"] == item.get("fingerprint") or (
                    _similarity(draft.topic + " " + draft.hook + " " + draft.caption,
                                " ".join((item.get("topic", ""), item.get("hook", ""), item.get("caption", ""))))
                    >= self.similarity_threshold
                ):
                    raise DuplicateContentError("draft resembles existing content")
            records.append(row)
            self._write_records(records)
        return row

    def update_status(self, post_id: str, status: str, *, instagram_media_id: str | None = None) -> dict:
        """Append a status event and atomically persist the updated record."""
        status = status.upper()
        if status not in VALID_STATUSES:
            raise InvalidTransitionError("unknown status")
        with self._locked():
            records = self._read_records()
            row = next((item for item in records if item["id"] == post_id), None)
            if row is None:
                raise RecordNotFoundError("content record was not found")
            previous = row["status"]
            if status not in TRANSITIONS.get(previous, frozenset()):
                if previous in {"PUBLISHING", "AMBIGUOUS"} and status == "PUBLISHING":
                    raise AmbiguousPublishError("publishing may already have reached Instagram; reconcile before retry")
                raise InvalidTransitionError("status transition is not allowed")
            if status == "PUBLISHED" and not instagram_media_id:
                raise InvalidTransitionError("PUBLISHED requires an Instagram media ID")
            if instagram_media_id is not None:
                row["instagram_media_id"] = instagram_media_id
            row["status"] = status
            row.setdefault("history", []).append({"status": status, "at": datetime.now(timezone.utc).isoformat()})
            self._write_records(records)
            return row

    def begin_publishing(self, post_id: str) -> dict:
        """Move READY to PUBLISHING. A PUBLISHING/AMBIGUOUS post is never retried."""
        row = self.get(post_id)
        if row["status"] in {"PUBLISHING", "AMBIGUOUS"}:
            raise AmbiguousPublishError("publishing may already have reached Instagram; reconcile before retry")
        return self.update_status(post_id, "PUBLISHING")

    def mark_ambiguous(self, post_id: str) -> dict:
        """Record an uncertain publish outcome; an operator must reconcile it."""
        return self.update_status(post_id, "AMBIGUOUS")

    def resolve_ambiguous(self, post_id: str, *, published: bool, instagram_media_id: str | None = None) -> dict:
        """Explicitly reconcile an ambiguous outcome before another publish attempt."""
        if published:
            if not instagram_media_id:
                raise InvalidTransitionError("confirmed publication requires an Instagram media ID")
            return self.update_status(post_id, "PUBLISHED", instagram_media_id=instagram_media_id)
        return self.update_status(post_id, "READY")
