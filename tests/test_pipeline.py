from datetime import date

import pytest
from PIL import Image
from io import BytesIO

from certipass_instagram import pipeline
from certipass_instagram.models import ContentDraft, Slide
from certipass_instagram.pipeline import PipelineError, publish_draft


def test_publish_fails_closed_before_reading_any_secret_or_draft(tmp_path, monkeypatch):
    monkeypatch.delenv("INSTAGRAM_PUBLISH_ENABLED", raising=False)
    with pytest.raises(PipelineError, match="Publishing is disabled"):
        publish_draft(draft_path=tmp_path / "missing.json", media_urls=["https://media.example/image.png"],
                      ledger_path=tmp_path / "ledger.json", confirm=False)


def test_publish_requires_app_live_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_PUBLISH_ENABLED", "true")
    monkeypatch.delenv("INSTAGRAM_APP_LIVE_APPROVED", raising=False)
    with pytest.raises(PipelineError, match="not marked live"):
        publish_draft(draft_path=tmp_path / "missing.json", media_urls=["https://media.example/image.png"],
                      ledger_path=tmp_path / "ledger.json", confirm=True)


def test_create_draft_requires_current_brand_and_technical_sources(tmp_path, monkeypatch):
    class FakeLedger:
        def __init__(self, path): pass
        def list_records(self): return []

    class Page:
        def __init__(self, url): self.url = url
        def evidence(self): return {"url": self.url, "title": "test", "accessed_at": "today", "text": "facts"}

    monkeypatch.setattr(pipeline, "ContentLedger", FakeLedger)
    monkeypatch.setattr(pipeline, "fetch_snapshot", lambda: [Page("https://www.certipass.md/")])
    with pytest.raises(PipelineError, match="technical reference"):
        pipeline.create_draft(day=date(2026, 9, 23), output_dir=tmp_path)


def test_create_draft_builds_static_png_carousel_without_any_video(tmp_path, monkeypatch):
    class Page:
        def __init__(self, url): self.url = url
        def evidence(self): return {"url": self.url, "title": "test", "accessed_at": "today", "text": "facts"}

    class CopyGenerator:
        def generate(self, **kwargs):
            return ContentDraft(
                id="post-2026-09-23", publish_date=date(2026, 9, 23), pillar="useful_it",
                language="ro", topic="Exemplu", hook="Un titlu clar", caption="Text pentru Instagram.",
                slides=tuple(Slide(f"Slide {i}", "Text exact", f"Artwork prompt {i}", f"Alt {i}")
                             for i in range(1, 5)),
            )

    class FakeImageGenerator:
        def generate(self, prompt):
            image = Image.new("RGB", (64, 80), "#6384aa")
            stream = BytesIO()
            image.save(stream, format="PNG")
            return stream.getvalue()

    monkeypatch.setattr(pipeline, "fetch_snapshot", lambda: [
        Page("https://www.certipass.md/"), Page("https://docs.python.org/3/tutorial/floatingpoint.html"),
    ])
    draft, images = pipeline.create_draft(
        day=date(2026, 9, 23), ledger_path=tmp_path / "ledger.json",
        output_dir=tmp_path / "artifacts", generator=CopyGenerator(),
        image_generator=FakeImageGenerator(),
    )
    assert draft.post_type == "CAROUSEL"
    assert len(images) == 4
    assert all(path.suffix == ".png" and path.exists() for path in images)
    assert not list((tmp_path / "artifacts").glob("*.mp4"))
    assert len(draft.asset_paths) == 4


def test_create_daily_post_renders_only_one_static_image(tmp_path, monkeypatch):
    class Page:
        def __init__(self, url): self.url = url
        def evidence(self): return {"url": self.url, "title": "test", "accessed_at": "today", "text": "facts"}

    class DailyGenerator:
        def generate_daily_post(self, **kwargs):
            day = kwargs["day"]
            kind = kwargs["content_type"]
            return ContentDraft(id=f"post-{day}-{kind}", publish_date=day, pillar="daily",
                                content_type=kind, language="ro", topic=f"Distinct topic for {kind}",
                                hook=f"A different hook about {kind}", caption=f"Caption specifically for {kind}.",
                                character=f"Character {kind}", visual_motif=f"Motif {kind}",
                                slides=(Slide(f"Titlu {kind}", "Text exact", f"Pastel art for {kind}", f"Alt {kind}"),))

    class FakeImageGenerator:
        def generate(self, prompt):
            image = Image.new("RGB", (64, 80), "#ded8f5")
            stream = BytesIO()
            image.save(stream, format="PNG")
            return stream.getvalue()

    monkeypatch.setattr(pipeline, "fetch_snapshot", lambda: [
        Page("https://www.certipass.md/"), Page("https://docs.python.org/3/tutorial/floatingpoint.html"),
    ])
    draft, images = pipeline.create_daily_post(
        day=date(2026, 9, 23), ledger_path=tmp_path / "ledger.json",
        output_dir=tmp_path / "artifacts", generator=DailyGenerator(), image_generator=FakeImageGenerator(),
    )
    assert draft.content_type == pipeline.next_content_type([], date(2026, 9, 23))
    assert len(images) == 1 and images[0].exists()
    assert len(pipeline.ContentLedger(tmp_path / "ledger.json").list_records()) == 1


def test_daily_content_type_rotates_to_next_category():
    assert pipeline.next_content_type([{"publish_date": "2026-09-23", "content_type": "meme"}],
                                      date(2026, 9, 24)) == "educational"
    assert pipeline.next_content_type([{"publish_date": "2026-09-23", "content_type": "educational"}],
                                      date(2026, 9, 24)) == "informative"
    assert pipeline.next_content_type([{"publish_date": "2026-09-23", "content_type": "informative"}],
                                      date(2026, 9, 24)) == "meme"


def test_daily_post_refuses_second_generation_for_same_day_before_spending(tmp_path):
    day = date(2026, 9, 23)
    ledger = pipeline.ContentLedger(tmp_path / "ledger.json")
    ledger.reserve(ContentDraft(id="already", publish_date=day, pillar="test", language="ro",
                               topic="Existing post topic", hook="Existing hook",
                               caption="Existing caption"))
    with pytest.raises(PipelineError, match="second one"):
        pipeline.create_daily_post(day=day, ledger_path=tmp_path / "ledger.json",
                                   output_dir=tmp_path / "artifacts")
