#!/usr/bin/env python3
"""Generate the procedural test fixtures.

The images are pure functions of the code below, so tests build them into a
temporary directory instead of committing binaries. Run this script by hand
to inspect them:

    python scripts/make_fixtures.py OUT_DIR

All fixtures target ``tests/profiles/standard.json``: a 2 x 1.5 in trim with
0.125 in bleed, i.e. a 2.25 x 1.75 in canvas. 338 x 263 px is the smallest
size that meets its 150 dpi warn threshold.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 338, 263
ART = (200, 30, 40)
WHITE = (255, 255, 255)


def solid(size=(W, H), color=ART) -> Image.Image:
    return Image.new("RGB", size, color)


def checkerboard(cell: int = 16) -> Image.Image:
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)
    for cy in range(0, H, cell):
        for cx in range(0, W, cell):
            if (cx // cell + cy // cell) % 2 == 0:
                draw.rectangle((cx, cy, cx + cell - 1, cy + cell - 1), fill=(0, 0, 0))
    return img


def bordered(inset: int) -> Image.Image:
    img = Image.new("RGB", (W, H), WHITE)
    ImageDraw.Draw(img).rectangle((inset, inset, W - 1 - inset, H - 1 - inset), fill=ART)
    return img


def transparent_margin(inset: int = 40) -> Image.Image:
    # White art on a transparent canvas: only alpha separates art from background.
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle((inset, inset, W - 1 - inset, H - 1 - inset), fill=(255, 255, 255, 255))
    return img


def off_centre() -> Image.Image:
    img = Image.new("RGB", (W, H), WHITE)
    ImageDraw.Draw(img).rectangle((40, 40, 199, H - 41), fill=ART)
    return img


# name -> (builder, file format)
FIXTURES = {
    "solid.png": (solid, "PNG"),
    "solid.jpg": (solid, "JPEG"),
    "solid.tif": (solid, "TIFF"),
    "solid_lowres.png": (lambda: solid((240, 187)), "PNG"),
    "solid_tiny.png": (lambda: solid((200, 156)), "PNG"),
    "solid_square.png": (lambda: solid((W, W)), "PNG"),
    "checkerboard.png": (checkerboard, "PNG"),
    "bordered.png": (lambda: bordered(40), "PNG"),
    "bordered_safe.png": (lambda: bordered(28), "PNG"),
    "bordered_bleed_short.png": (lambda: bordered(10), "PNG"),
    "transparent_margin.png": (transparent_margin, "PNG"),
    "off_centre.png": (off_centre, "PNG"),
    "blank.png": (lambda: solid(color=WHITE), "PNG"),
}


def generate(out_dir: str | Path) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, (build, fmt) in FIXTURES.items():
        path = out / name
        options = {"quality": 95, "subsampling": 0} if fmt == "JPEG" else {}
        build().save(path, format=fmt, **options)
        paths[name] = path
    return paths


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: make_fixtures.py OUT_DIR")
    for path in generate(sys.argv[1]).values():
        print(path)
