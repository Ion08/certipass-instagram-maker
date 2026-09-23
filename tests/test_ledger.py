from concurrent.futures import ProcessPoolExecutor
from datetime import date

import pytest

from certipass_instagram.ledger import (
    AmbiguousPublishError,
    ContentLedger,
    DuplicateContentError,
    DuplicateDayError,
    InvalidTransitionError,
)
from certipass_instagram.models import ContentDraft


def draft(
    day: date,
    *,
    topic: str = "Study habits",
    hook: str = "Build a daily learning routine",
    caption: str = "Small daily practice leads to lasting progress.",
) -> ContentDraft:
    return ContentDraft(
        id=f"post-{day.isoformat()}",
        publish_date=day,
        pillar="learning",
        language="en",
        topic=topic,
        hook=hook,
        caption=caption,
        facts=("Practice regularly",),
    )


def _reserve(path: str, day: str, post_id: str) -> str:
    item = ContentDraft(
        id=post_id,
        publish_date=date.fromisoformat(day),
        pillar="learning",
        language="en",
        topic=post_id,
        hook="A unique educational opening",
        caption="An entirely distinct caption for this reservation.",
    )
    try:
        ContentLedger(path).reserve(item)
        return "reserved"
    except DuplicateDayError:
        return "duplicate"


def test_status_transitions_are_audited_and_persisted(tmp_path):
    ledger = ContentLedger(tmp_path / "ledger.json")
    day = date(2026, 9, 24)
    ledger.reserve(draft(day))
    ledger.update_status("post-2026-09-24", "APPROVED")
    ledger.update_status("post-2026-09-24", "READY")
    ledger.begin_publishing("post-2026-09-24")
    saved = ledger.update_status("post-2026-09-24", "PUBLISHED", instagram_media_id="ig-123")
    assert saved["instagram_media_id"] == "ig-123"
    loaded = ContentLedger(tmp_path / "ledger.json").get("post-2026-09-24")
    assert loaded["status"] == "PUBLISHED"
    assert [event["status"] for event in loaded["history"]] == ["IDEA", "APPROVED", "READY", "PUBLISHING", "PUBLISHED"]


def test_invalid_transition_and_published_without_media_id_are_rejected(tmp_path):
    ledger = ContentLedger(tmp_path / "ledger.json")
    ledger.reserve(draft(date(2026, 9, 24)))
    with pytest.raises(InvalidTransitionError):
        ledger.update_status("post-2026-09-24", "PUBLISHED")
    with pytest.raises(InvalidTransitionError):
        ledger.update_status("post-2026-09-24", "PUBLISHING")


def test_same_day_reservation_rejected_after_reload(tmp_path):
    path = tmp_path / "ledger.json"
    ContentLedger(path).reserve(draft(date(2026, 9, 24)))
    with pytest.raises(DuplicateDayError):
        ContentLedger(path).reserve(draft(date(2026, 9, 24), topic="A different idea", hook="Completely new hook"))


def test_same_day_reservation_is_atomic_across_processes(tmp_path):
    path = str(tmp_path / "ledger.json")
    day = date(2026, 9, 24).isoformat()
    with ProcessPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(_reserve, [path, path], [day, day], ["one", "two"]))
    assert sorted(outcomes) == ["duplicate", "reserved"]
    assert len(ContentLedger(path).list_records()) == 1


def test_exact_and_near_duplicate_content_rejected_even_on_different_day(tmp_path):
    ledger = ContentLedger(tmp_path / "ledger.json", similarity_threshold=0.7)
    ledger.reserve(draft(date(2026, 9, 24)))
    with pytest.raises(DuplicateContentError):
        ledger.reserve(draft(date(2026, 9, 25)))
    with pytest.raises(DuplicateContentError):
        ledger.reserve(
            draft(
                date(2026, 9, 25),
                topic="Study habits",
                hook="Build a daily learning routine",
                caption="Small daily practice leads to lasting progress today.",
            )
        )


def test_ambiguous_publish_cannot_be_retried_without_explicit_reconciliation(tmp_path):
    ledger = ContentLedger(tmp_path / "ledger.json")
    post_id = "post-2026-09-24"
    ledger.reserve(draft(date(2026, 9, 24)))
    ledger.update_status(post_id, "APPROVED")
    ledger.update_status(post_id, "READY")
    ledger.begin_publishing(post_id)
    ledger.mark_ambiguous(post_id)
    with pytest.raises(AmbiguousPublishError):
        ledger.begin_publishing(post_id)
    with pytest.raises(AmbiguousPublishError):
        ledger.update_status(post_id, "PUBLISHING")
    # Only explicit confirmation that no post was created unlocks another attempt.
    ledger.resolve_ambiguous(post_id, published=False)
    assert ledger.get(post_id)["status"] == "READY"
    assert ledger.begin_publishing(post_id)["status"] == "PUBLISHING"


def test_ambiguous_success_requires_media_id(tmp_path):
    ledger = ContentLedger(tmp_path / "ledger.json")
    post_id = "post-2026-09-24"
    ledger.reserve(draft(date(2026, 9, 24)))
    ledger.update_status(post_id, "APPROVED")
    ledger.update_status(post_id, "READY")
    ledger.begin_publishing(post_id)
    ledger.mark_ambiguous(post_id)
    with pytest.raises(InvalidTransitionError):
        ledger.resolve_ambiguous(post_id, published=True)
    assert ledger.resolve_ambiguous(post_id, published=True, instagram_media_id="ig-456")["status"] == "PUBLISHED"
