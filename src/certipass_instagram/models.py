"""Shared content contracts for the automation pipeline."""

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
class Scene:
    narration: str
    overlay_text: str
    visual_description: str
    duration_seconds: float


@dataclass(frozen=True)
class ContentDraft:
    id: str
    publish_date: date
    pillar: str
    language: str
    topic: str
    hook: str
    caption: str
    scenes: tuple[Scene, ...] = ()
    sources: tuple[Source, ...] = ()
    visual_family: str = "editorial"
    facts: tuple[str, ...] = ()
    asset_path: str | None = None
    media_url: str | None = None
    status: str = "IDEA"
    instagram_media_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible record."""
        result = asdict(self)
        result["publish_date"] = self.publish_date.isoformat()
        result["scenes"] = [asdict(scene) for scene in self.scenes]
        result["sources"] = [asdict(source) for source in self.sources]
        return result

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ContentDraft:
        values = dict(raw)
        values["publish_date"] = date.fromisoformat(values["publish_date"])
        values["scenes"] = tuple(Scene(**scene) for scene in values.get("scenes", []))
        values["sources"] = tuple(Source(**source) for source in values.get("sources", []))
        values["facts"] = tuple(values.get("facts", ()))
        return cls(**values)
