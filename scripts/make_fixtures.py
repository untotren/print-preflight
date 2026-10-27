"""Procedurally generate the raster fixtures used by the test suite.

Usage: python scripts/make_fixtures.py OUTDIR

Every fixture is drawn from integer geometry with Pillow, so the output is
identical on every run. Sizes are chosen against tests/profiles/bleed.json:
2.0 x 1.5 in trim + 0.1 in bleed = 2.2 x 1.7 in canvas, i.e. 330 x 255 px at
150 dpi (dpi_warn) and 220 x 170 px at 100 dpi (dpi_target).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 330, 255
WHITE = (255, 255, 255)
RED = (200, 30, 40)
BLUE = (20, 60, 180)
GREEN = (30, 150, 60)


def solid(size=(W, H), color=RED) -> Image.Image:
    return Image.new("RGB", size, color)


def checkerboard(cell: int = 15) -> Image.Image:
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)
    for y in range(0, H, cell):
        for x in range(0, W, cell):
            if (x // cell + y // cell) % 2 == 0:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(0, 0, 0))
    return img


def bordered(border: int = 40) -> Image.Image:
    img = Image.new("RGB", (W, H), WHITE)
    ImageDraw.Draw(img).rectangle((border, border, W - border - 1, H - border - 1), fill=BLUE)
    return img


def transparent_margin(margin: int = 20) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle((margin, margin, W - margin - 1, H - margin - 1), fill=GREEN + (255,))
    return img


def off_centre() -> Image.Image:
    # 160 x 135 box: 130 px left margin, 40 px right; vertically centred.
    img = Image.new("RGB", (W, H), WHITE)
    ImageDraw.Draw(img).rectangle((130, 60, 289, 194), fill=RED)
    return img


FIXTURES = {
    "solid.png": lambda: solid(),
    "solid.jpg": lambda: solid(),
    "checkerboard.png": checkerboard,
    "bordered.png": bordered,
    "bordered.tif": bordered,
    "transparent_margin.png": transparent_margin,
    "off_centre.png": off_centre,
    "blank.png": lambda: solid(color=WHITE),
    "low_res.png": lambda: solid((220, 170)),
    "too_small.png": lambda: solid((219, 170)),
    "wrong_aspect.png": lambda: solid((330, 330)),
}


def build(outdir: str | Path) -> dict[str, Path]:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, make in FIXTURES.items():
        path = out / name
        img = make()
        if name.endswith(".jpg"):
            img.save(path, quality=95, subsampling=0)
        else:
            img.save(path)
        paths[name] = path
    return paths


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: make_fixtures.py OUTDIR")
    for p in build(sys.argv[1]).values():
        print(p)
