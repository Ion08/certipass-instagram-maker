"""Compose AI-generated artwork and exact copy into static Instagram PNGs.

This module writes ordinary raster image files directly. It never creates HTML,
captures a browser, or encodes video.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import ContentDraft


class RenderError(RuntimeError):
    """A validation or image-composition error."""


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        ("/System/Library/Fonts/Supplemental/Verdana Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        if bold else
        ("/System/Library/Fonts/Supplemental/Verdana.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    )
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    line = ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if line and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def compose_slide(artwork: Image.Image, *, brand: str, headline: str, body: str = "",
                  index: int = 1, count: int = 1, size: int = 1080) -> Image.Image:
    """Return one full-frame PNG image from generated art and precisely rendered text."""
    if not headline.strip() or not 1 <= index <= count <= 7:
        raise RenderError("A slide needs a headline and carousel size from 1 to 7.")
    if size < 320:
        raise RenderError("Image size must be at least 320 pixels.")
    height = round(size * 1.25)
    image = artwork.convert("RGB")
    # Center-crop/scale generated artwork to the 4:5 Instagram feed aspect.
    scale = max(size / image.width, height / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left = (image.width - size) // 2
    top = (image.height - height) // 2
    image = image.crop((left, top, left + size, top + height)).convert("RGBA")

    overlay = Image.new("RGBA", (size, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    pad = int(size * 0.075)
    panel_top = int(height * 0.53)
    draw.rounded_rectangle((pad // 2, panel_top, size - pad // 2, height - pad // 2),
                           radius=int(size * 0.045), fill=(12, 26, 48, 218))
    brand_font = _font(int(size * 0.035), True)
    draw.text((pad, int(height * 0.045)), brand, font=brand_font, fill="white",
              stroke_width=1, stroke_fill=(0, 0, 0, 64))
    if count > 1:
        count_text = f"{index}/{count}"
        box = draw.textbbox((0, 0), count_text, font=brand_font)
        draw.text((size - pad - (box[2] - box[0]), int(height * 0.045)), count_text, font=brand_font,
                  fill="white", stroke_width=1, stroke_fill=(0, 0, 0, 64))

    text_width = size - 2 * pad
    title_size = int(size * 0.077)
    while title_size >= int(size * 0.043):
        title_font = _font(title_size, True)
        title_lines = _wrap(draw, headline.strip(), title_font, text_width)
        if len(title_lines) <= 4:
            break
        title_size -= 2
    else:
        raise RenderError("Headline is too long for an Instagram slide.")
    line_height = int(title_size * 1.15)
    y = panel_top + int(height * 0.07)
    for line in title_lines:
        draw.text((pad, y), line, font=title_font, fill="#FFFFFF")
        y += line_height

    if body.strip():
        body_font = _font(int(size * 0.034))
        body_lines = _wrap(draw, body.strip(), body_font, text_width)
        if len(body_lines) > 5:
            raise RenderError("Slide body is too long for an Instagram slide.")
        y += int(height * 0.025)
        for line in body_lines:
            draw.text((pad, y), line, font=body_font, fill="#E6EDF5")
            y += int(height * 0.048)
    return Image.alpha_composite(image, overlay).convert("RGB")


def render_carousel(draft: ContentDraft, artwork_paths: list[str | Path],
                    output_dir: str | Path, *, size: int = 1080) -> list[Path]:
    """Create ordered, static PNG slides from image-generated artwork."""
    if not draft.slides or len(draft.slides) != len(artwork_paths):
        raise RenderError("Each carousel slide must have one generated artwork image.")
    if len(draft.slides) > 7:
        raise RenderError("Instagram carousels are limited to seven slides in this workflow.")
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for i, (slide, source) in enumerate(zip(draft.slides, artwork_paths), 1):
        try:
            with Image.open(source) as opened:
                artwork = opened.copy()
        except (OSError, ValueError) as exc:
            raise RenderError(f"Could not open generated artwork for slide {i}.") from exc
        composed = compose_slide(artwork, brand="certiPass.md", headline=slide.headline,
                                 body=slide.body, index=i, count=len(draft.slides), size=size)
        path = folder / f"{draft.id}-{i:02d}.png"
        composed.save(path, format="PNG", optimize=True)
        outputs.append(path)
    return outputs
