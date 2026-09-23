"""Shared content contracts for static Instagram image posts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class Source:
    title: str
    url: str
    accessed_at: str
    supports: str


@dataclass(frozen=True)
class Slide:
    headline: str
    body: str
    image_prompt: str
    alt_text: str


@dataclass(frozen=True)
class ContentDraft:
    id: str
    publish_date: date
    pillar: str
    language: str
    topic: str
    hook: str
    caption: str
    slides: tuple[Slide, ...] = ()
    sources: tuple[Source, ...] = ()
    visual_family: str = "editorial"
    facts: tuple[str, ...] = ()
    asset_paths: tuple[str, ...] = ()
    media_urls: tuple[str, ...] = ()
    status: str = "IDEA"
    instagram_media_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def post_type(self) -> str:
        return "IMAGE" if len(self.slides) == 1 else "CAROUSEL"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["publish_date"] = self.publish_date.isoformat()
        result["slides"] = [asdict(slide) for slide in self.slides]
        result["sources"] = [asdict(source) for source in self.sources]
        return result

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ContentDraft:
        values = dict(raw)
        values["publish_date"] = date.fromisoformat(values["publish_date"])
        values["slides"] = tuple(Slide(**slide) for slide in values.get("slides", []))
        values["sources"] = tuple(Source(**source) for source in values.get("sources", []))
        values["facts"] = tuple(values.get("facts", ()))
        values["asset_paths"] = tuple(values.get("asset_paths", ()))
        values["media_urls"] = tuple(values.get("media_urls", ()))
        # Old Reel drafts are intentionally rejected: they are a different product.
        if "scenes" in values:
            raise ValueError("Reel drafts are no longer supported; create an image post or carousel.")
        return cls(**values)
