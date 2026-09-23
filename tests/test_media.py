from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from certipass_instagram.models import ContentDraft, Scene
from certipass_instagram.render import RenderConfig, RenderError, _scene_image, render_reel


def draft(*scenes: Scene) -> ContentDraft:
    return ContentDraft(
        id="media-test-001",
        publish_date=date(2026, 9, 23),
        pillar="digital_skills",
        language="ro",
        topic="Educație digitală",
        hook="Învață digital, pas cu pas.",
        caption="Resurse practice pentru competențe digitale.",
        scenes=tuple(scenes),
    )


@pytest.fixture
def small_config() -> RenderConfig:
    return RenderConfig(width=360, height=640, fps=5)


def test_renders_valid_vertical_mp4_with_scene_duration(tmp_path: Path, small_config: RenderConfig) -> None:
    scenes = (
        Scene("Bun venit", "Învață digital", "Competențe pentru fiecare zi", 0.8),
        Scene("Verifică sursa", "Gândește critic", "Un pas mic, un obicei bun", 1.2),
    )
    output = render_reel(draft(*scenes), tmp_path / "sample.mp4", small_config)
    assert output.is_file() and output.stat().st_size > 1000
    probe = subprocess.run(
        [small_config.ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", str(output)],
        check=True, capture_output=True, text=True,
    )
    assert probe.stdout.strip() == "360x640"
    duration = float(subprocess.run(
        [small_config.ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(output)],
        check=True, capture_output=True, text=True,
    ).stdout.strip())
    assert duration == pytest.approx(2.0, abs=0.05)


def test_scene_layout_has_romanian_text_and_safe_area(tmp_path: Path, small_config: RenderConfig) -> None:
    scene = Scene("Învățarea", "Știință, educație și încredere", "Exersează în fiecare zi", 1.0)
    image = _scene_image(draft(scene), scene, 0, 1, small_config)
    assert image.size == (360, 640)
    # Meaningful contrast in the reserved central text band proves that the
    # overlay was laid out there rather than clipped into Instagram UI areas.
    crop = image.crop((20, 190, 340, 500)).convert("RGB")
    assert crop.getbbox() is not None
    changed = ImageChops.difference(crop, Image.new("RGB", crop.size, small_config.background))
    assert changed.getbbox() is not None
    assert render_reel(draft(scene), tmp_path / "diacritics.mp4", small_config).exists()


def test_frame_counter_stays_inside_canvas_right_safe_margin(small_config: RenderConfig) -> None:
    config = RenderConfig(width=360, height=640, fps=5)
    scene = Scene("Final", "Distribuie cu grijă", "", 0.5)
    image = _scene_image(draft(scene), scene, 99, 100, config)
    # Find exact white glyph pixels in the header's right half (the counter).
    # The counter must retain a visible inset from the right canvas edge.
    header_bottom = int(config.height * 0.105)
    white_x = [
        x
        for y in range(int(config.height * 0.045), header_bottom)
        for x in range(config.width // 2, config.width)
        if image.getpixel((x, y)) == (255, 255, 255)
    ]
    assert white_x, "frame counter should render in the header's right half"
    assert max(white_x) < config.width - int(config.width * 0.09) - 10


def test_render_defaults_use_requested_brand_palette() -> None:
    config = RenderConfig()
    assert config.background == "#F3EFE7"
    assert config.ink == "#0F172A"
    assert config.accent == "#D94A3A"


def test_render_is_deterministic_and_uses_no_credentials(tmp_path: Path, small_config: RenderConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    # The public renderer has no credential parameters or network calls. Empty
    # environments still render from the local draft and geometric template.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("META_ACCESS_TOKEN", raising=False)
    scene = Scene("Idei clare", "Competențele cresc prin practică", "", 0.6)
    content = draft(scene)
    first = render_reel(content, tmp_path / "one.mp4", small_config)
    second = render_reel(content, tmp_path / "two.mp4", small_config)
    assert first.read_bytes() == second.read_bytes()


def test_rejects_missing_scenes_invalid_duration_and_bad_aspect(tmp_path: Path, small_config: RenderConfig) -> None:
    with pytest.raises(RenderError, match="at least one scene"):
        render_reel(draft(), tmp_path / "empty.mp4", small_config)
    with pytest.raises(RenderError, match="greater than zero"):
        render_reel(draft(Scene("", "", "", 0)), tmp_path / "bad-duration.mp4", small_config)
    with pytest.raises(RenderError, match="9:16"):
        render_reel(draft(Scene("ok", "ok", "", 1)), tmp_path / "bad-size.mp4", RenderConfig(width=360, height=600, fps=5, ffmpeg=small_config.ffmpeg, ffprobe=small_config.ffprobe, background=small_config.background))


def test_reports_unavailable_ffmpeg_clearly(tmp_path: Path, small_config: RenderConfig) -> None:
    scene = Scene("Text", "Mesaj", "", 0.5)
    config = RenderConfig(width=360, height=640, fps=5, ffmpeg="definitely-not-an-ffmpeg-binary", ffprobe=small_config.ffprobe)
    with pytest.raises(RenderError, match="ffmpeg executable not found"):
        render_reel(draft(scene), tmp_path / "no-ffmpeg.mp4", config)
