"""Procedurally generate the preflight test fixtures.

Usage: python tests/fixtures/make_fixtures.py OUT_DIR

Every image is drawn from integer rectangles only, so the pixel content is
identical on every run and platform. The images are sized for
``tests/fixtures/profile.json``: a 4 x 6 in print with 0.125 in bleed is a
4.25 x 6.25 in bleed box, i.e. 340 x 500 px at 80 dpi (10 px bleed band,
20 px from the edge to the safe line).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 340, 500
WHITE = (255, 255, 255)
RED = (200, 30, 30)
BLUE = (30, 60, 200)
GREEN = (20, 150, 60)
BLACK = (0, 0, 0)


def solid(size=(W, H), colour=RED) -> Image.Image:
    return Image.new("RGB", size, colour)


def checkerboard(cell: int = 20) -> Image.Image:
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)
    for y in range(0, H, cell):
        for x in range(0, W, cell):
            if (x // cell + y // cell) % 2 == 0:
                draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=BLACK)
    return img


def boxed(left: int, top: int, right: int, bottom: int, colour=BLUE) -> Image.Image:
    """White page with a solid rectangle covering [left, right) x [top, bottom)."""
    img = Image.new("RGB", (W, H), WHITE)
    ImageDraw.Draw(img).rectangle([left, top, right - 1, bottom - 1], fill=colour)
    return img


def transparent_margin(margin: int) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle([margin, margin, W - margin - 1, H - margin - 1], fill=GREEN + (255,))
    return img


def notched_edge() -> Image.Image:
    """Full-bleed art whose right bleed band is white for the top half."""
    img = solid()
    ImageDraw.Draw(img).rectangle([W - 6, 0, W - 1, H // 2 - 1], fill=WHITE)
    return img


FIXTURES = {
    "solid.png": lambda: solid(),
    "checkerboard.png": checkerboard,
    "bordered.png": lambda: boxed(40, 40, W - 40, H - 40),
    "transparent_margin.png": lambda: transparent_margin(5),
    "transparent_safe.png": lambda: transparent_margin(15),
    "off_centre.png": lambda: boxed(60, 50, 320, 470),
    "notched_edge.png": notched_edge,
    "low_res.png": lambda: solid((260, 382)),
    "below_warn.png": lambda: solid((320, 470)),
    "wrong_aspect.png": lambda: solid((500, 500)),
    "blank.png": lambda: solid(colour=WHITE),
    "solid.jpg": lambda: solid(),
    "bordered.tif": lambda: boxed(40, 40, W - 40, H - 40),
}


def generate(out_dir: str | Path) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, make in FIXTURES.items():
        path = out / name
        img = make()
        if name.endswith(".jpg"):
            img.save(path, "JPEG", quality=95, subsampling=0)
        elif name.endswith(".tif"):
            img.save(path, "TIFF")
        else:
            img.save(path, "PNG")
        paths[name] = path
    return paths


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: make_fixtures.py OUT_DIR")
    for p in generate(sys.argv[1]).values():
        print(p)
