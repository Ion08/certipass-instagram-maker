from datetime import date
from pathlib import Path

import pytest
from PIL import Image

from certipass_instagram.models import ContentDraft, Slide
from certipass_instagram.render import RenderError, compose_slide, render_carousel


def draft(slides: tuple[Slide, ...]) -> ContentDraft:
    return ContentDraft(
        id="post-test-001", publish_date=date(2026, 9, 23), pillar="useful_it",
        language="ro", topic="Educație digitală", hook="Învață pas cu pas",
        caption="Învață pas cu pas.", slides=slides,
    )


def test_composes_full_frame_png_from_generated_art_and_exact_copy(tmp_path: Path):
    artwork = Image.new("RGB", (1024, 1024), "#64a6df")
    result = compose_slide(artwork, brand="certiPass.md",
                           headline="Învață digital, pas cu pas", body="Explicații clare.",
                           index=1, count=1, size=512)
    output = tmp_path / "post.png"
    result.save(output)
    with Image.open(output) as saved:
        assert saved.format == "PNG"
        assert saved.size == (512, 640)
        assert saved.getpixel((15, 15)) == (100, 166, 223)


def test_renders_ordered_carousel_pngs_and_alt_slides(tmp_path: Path):
    slides = tuple(Slide(f"Titlu {i}", "Text scurt", f"Educational illustration {i}", f"Imagine {i}")
                   for i in range(1, 5))
    assets = []
    for i in range(4):
        path = tmp_path / f"art-{i}.jpg"
        Image.new("RGB", (320, 320), (i * 30, 100, 180)).save(path)
        assets.append(path)
    paths = render_carousel(draft(slides), assets, tmp_path / "out", size=360)
    assert len(paths) == 4
    assert [p.name for p in paths] == [f"post-test-001-{i:02d}.png" for i in range(1, 5)]
    for path in paths:
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert image.size == (360, 450)


def test_rejects_missing_artwork_or_invalid_copy(tmp_path: Path):
    one = draft((Slide("Titlu", "", "A visual", "Alt text"),))
    with pytest.raises(RenderError, match="one generated artwork"):
        render_carousel(one, [], tmp_path)
    with pytest.raises(RenderError, match="headline"):
        compose_slide(Image.new("RGB", (64, 64)), brand="certiPass.md", headline=" ",
                     index=1, count=1)
