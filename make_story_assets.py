"""Fit existing carousel slides inside 9:16 Story canvases without cropping."""

from argparse import ArgumentParser
from pathlib import Path

from PIL import Image


SIZE = (1080, 1920)
BACKGROUND = (247, 244, 236)
MAX_CONTENT = (1020, 1500)


def make_story(source: Path, destination: Path) -> None:
    with Image.open(source) as original:
        slide = original.convert("RGB")
        slide.thumbnail(MAX_CONTENT, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", SIZE, BACKGROUND)
        x = (SIZE[0] - slide.width) // 2
        y = (SIZE[1] - slide.height) // 2
        canvas.paste(slide, (x, y))
        destination.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(destination, format="JPEG", quality=90, optimize=True, progressive=True)


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    for day in range(1, 91):
        for number in (1, 2):
            name = f"day-{day:03}-{number:02}.jpg"
            source = args.source_dir / name
            destination = args.output_dir / f"day-{day:03}-{number:02}-story.jpg"
            make_story(source, destination)


if __name__ == "__main__":
    main()
