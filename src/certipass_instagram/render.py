"""Deterministic, local-only Instagram Reel rendering.

This renderer deliberately uses Pillow and the ffmpeg executable only. It does
not call a remote image, video, or language model service.
"""

from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import ContentDraft, Scene


class RenderError(RuntimeError):
    """A validation or encoding error while producing a Reel."""


@dataclass(frozen=True)
class RenderConfig:
    width: int = 1080
    height: int = 1920
    fps: int = 24
    background: str = "#F3EFE7"
    ink: str = "#0F172A"
    accent: str = "#D94A3A"
    muted: str = "#65727A"
    safe_top_ratio: float = 0.14
    safe_bottom_ratio: float = 0.18
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        ("/System/Library/Fonts/Supplemental/Verdana Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        if bold
        else ("/System/Library/Fonts/Supplemental/Verdana.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    )
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
    # Pillow's built-in bitmap font is a usable final fallback, though systems
    # without a Unicode font may not render Romanian diacritics correctly.
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _scene_image(draft: ContentDraft, scene: Scene, index: int, count: int, config: RenderConfig) -> Image.Image:
    image = Image.new("RGB", (config.width, config.height), config.background)
    draw = ImageDraw.Draw(image)
    w, h = config.width, config.height
    pad = int(w * 0.09)

    # Original geometric identity: deep-blue corner panel, mint orb and ruled
    # editorial card. Positions remain inside Instagram's UI caption-safe band.
    draw.rounded_rectangle((pad, int(h * 0.045), w - pad, int(h * 0.105)), radius=24, fill=config.ink)
    brand_font = _font(max(16, int(w * 0.032)), True)
    draw.text((pad + 20, int(h * 0.059)), "certiPass.md", fill="#FFFFFF", font=brand_font)
    counter = f"{index + 1:02d}/{count:02d}"
    counter_box = draw.textbbox((0, 0), counter, font=brand_font)
    counter_x = w - pad - 20 - counter_box[2]
    draw.text((counter_x, int(h * 0.059)), counter, fill="#FFFFFF", font=brand_font)

    cx, cy = int(w * 0.82), int(h * 0.22)
    radius = int(w * 0.17)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill="#D7F3E9")
    draw.ellipse((cx - radius // 2, cy - radius // 2, cx + radius // 2, cy + radius // 2), fill=config.accent)
    draw.rounded_rectangle((pad, int(h * 0.19), pad + int(w * 0.18), int(h * 0.202)), radius=6, fill=config.accent)

    top = max(int(h * config.safe_top_ratio), int(h * 0.31))
    bottom = min(int(h * (1 - config.safe_bottom_ratio)), int(h * 0.78))
    title = scene.overlay_text.strip() or scene.narration.strip()
    if not title:
        raise RenderError(f"Scene {index + 1} has no text to render")
    # Scale text to the scene and line-wrap. Fail instead of silently clipping.
    max_text_width = w - 2 * pad
    size = int(w * 0.092)
    while size >= max(18, int(w * 0.045)):
        title_font = _font(size, True)
        lines = _wrap(draw, title, title_font, max_text_width)
        line_h = int(size * 1.23)
        if len(lines) * line_h <= bottom - top:
            break
        size -= 2
    else:
        raise RenderError(f"Scene {index + 1} text is too long to fit the Reel safe area")

    y = top + (bottom - top - len(lines) * line_h) // 2
    for line in lines:
        draw.text((pad, y), line, fill=config.ink, font=title_font)
        y += line_h

    # Narration is visual context only; it is not synthesized into audio.
    visual = scene.visual_description.strip()
    if visual:
        small = _font(max(14, int(w * 0.034)))
        vlines = _wrap(draw, visual, small, max_text_width)
        vlines = vlines[:2]
        vy = int(h * 0.81)
        for line in vlines:
            draw.text((pad, vy), line, fill=config.muted, font=small)
            vy += int(w * 0.05)
    draw.rounded_rectangle((pad, int(h * 0.92), w - pad, int(h * 0.928)), radius=4, fill="#D7DDD9")
    draw.rounded_rectangle((pad, int(h * 0.92), pad + int((w - 2 * pad) * (index + 1) / count), int(h * 0.928)), radius=4, fill=config.accent)
    return image


def _probe(path: Path, executable: str) -> tuple[int, int, float]:
    try:
        result = subprocess.run(
            [executable, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,duration", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            check=True, capture_output=True, text=True,
        )
    except FileNotFoundError as exc:
        raise RenderError(f"ffprobe executable not found: {executable}") from exc
    except subprocess.CalledProcessError as exc:
        raise RenderError(f"Could not inspect rendered MP4: {exc.stderr.strip()}") from exc
    values = [v.strip() for v in result.stdout.splitlines() if v.strip()]
    # ffprobe emits width, height, then stream duration (sometimes N/A), then format duration.
    try:
        width, height = int(values[0]), int(values[1])
        duration_candidates = [float(v) for v in values[2:] if v.lower() != "n/a"]
        duration = duration_candidates[-1]
        return width, height, duration
    except (ValueError, IndexError) as exc:
        raise RenderError("ffprobe returned incomplete video metadata") from exc


def render_reel(draft: ContentDraft, output_path: str | Path, config: RenderConfig = RenderConfig()) -> Path:
    """Render scenes in *draft* to a silent, vertical H.264 MP4 and verify it.

    Requires Pillow (Python package) and ffmpeg + ffprobe executables. All visual
    assets are generated locally from the supplied text and geometric shapes.
    """
    if not isinstance(draft, ContentDraft):
        raise TypeError("draft must be a ContentDraft")
    if not draft.scenes:
        raise RenderError("ContentDraft must contain at least one scene")
    if config.width < 180 or config.height < 320 or config.fps < 1:
        raise RenderError("Render dimensions must be at least 180x320 and fps must be positive")
    if config.width * 16 != config.height * 9:
        raise RenderError("Reel dimensions must use a 9:16 aspect ratio")
    for i, scene in enumerate(draft.scenes, 1):
        if not math.isfinite(scene.duration_seconds) or scene.duration_seconds <= 0:
            raise RenderError(f"Scene {i} duration_seconds must be finite and greater than zero")
    ffmpeg_path = shutil.which(config.ffmpeg)
    if not ffmpeg_path:
        raise RenderError(f"ffmpeg executable not found: {config.ffmpeg}")
    if not shutil.which(config.ffprobe):
        raise RenderError(f"ffprobe executable not found: {config.ffprobe}")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg_path, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
               "-pix_fmt", "rgb24", "-s", f"{config.width}x{config.height}", "-r", str(config.fps),
               "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)]
    expected_duration = 0.0
    try:
        encoder = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        assert encoder.stdin is not None
        for index, scene in enumerate(draft.scenes):
            frames = max(1, round(scene.duration_seconds * config.fps))
            expected_duration += frames / config.fps
            raw_frame = _scene_image(draft, scene, index, len(draft.scenes), config).tobytes()
            for _ in range(frames):
                encoder.stdin.write(raw_frame)
        encoder.stdin.close()
        stderr = encoder.stderr.read().decode("utf-8", errors="replace") if encoder.stderr else ""
        status = encoder.wait()
        if status:
            raise RenderError(f"ffmpeg failed to encode Reel: {stderr.strip()}")
    except FileNotFoundError as exc:
        raise RenderError(f"ffmpeg executable not found: {config.ffmpeg}") from exc
    except BrokenPipeError as exc:
        stderr = encoder.stderr.read().decode("utf-8", errors="replace") if encoder.stderr else ""
        encoder.wait()
        raise RenderError(f"ffmpeg stopped while receiving video frames: {stderr.strip()}") from exc
    if not output.is_file() or output.stat().st_size == 0:
        raise RenderError("ffmpeg did not create a non-empty output file")
    width, height, duration = _probe(output, config.ffprobe)
    if (width, height) != (config.width, config.height):
        raise RenderError(f"Rendered dimensions are {width}x{height}; expected {config.width}x{config.height}")
    if abs(duration - expected_duration) > max(1 / config.fps, 0.05):
        raise RenderError(f"Rendered duration {duration:.3f}s differs from expected {expected_duration:.3f}s")
    return output
