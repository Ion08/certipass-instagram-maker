from datetime import date

import pytest

from certipass_instagram import pipeline
from certipass_instagram.pipeline import PipelineError, publish_draft


def test_publish_fails_closed_before_reading_any_secret_or_draft(tmp_path, monkeypatch):
    monkeypatch.delenv("INSTAGRAM_PUBLISH_ENABLED", raising=False)
    with pytest.raises(PipelineError, match="Publishing is disabled"):
        publish_draft(draft_path=tmp_path / "missing.json", media_url="https://media.example/reel.mp4",
                      ledger_path=tmp_path / "ledger.json", confirm=False)


def test_publish_requires_app_live_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_PUBLISH_ENABLED", "true")
    monkeypatch.delenv("INSTAGRAM_APP_LIVE_APPROVED", raising=False)
    with pytest.raises(PipelineError, match="not marked live"):
        publish_draft(draft_path=tmp_path / "missing.json", media_url="https://media.example/reel.mp4",
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
