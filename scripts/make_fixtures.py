#!/usr/bin/env python3
"""Generate the procedural test fixtures.

Usage: python scripts/make_fixtures.py OUTDIR

All fixtures target tests/profiles/standard.json: a 4 x 3 in trim with 0.25 in
bleed (4.5 x 3.5 in canvas). At 120 DPI that canvas is 540 x 420 px, the bleed
line is 30 px in from each edge and the safe line is 60 px in.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw

W, H = 540, 420
WHITE = (255, 255, 255)
NAVY = (20, 30, 90)


def solid() -> Image.Image:
    return Image.new("RGB", (W, H), NAVY)


def checkerboard(cell: int = 30) -> Image.Image:
    im = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(im)
    for y in range(0, H, cell):
        for x in range(0, W, cell):
            if (x // cell + y // cell) % 2 == 0:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(0, 0, 0))
    return im


def _rect_on(bg: Image.Image, box: tuple[int, int, int, int], fill) -> Image.Image:
    """``box`` is (left, top, right, bottom) with right/bottom exclusive."""
    ImageDraw.Draw(bg).rectangle((box[0], box[1], box[2] - 1, box[3] - 1), fill=fill)
    return bg


def bordered() -> Image.Image:
    # Content box sits exactly on the safe line: the inclusive boundary passes.
    return _rect_on(Image.new("RGB", (W, H), WHITE), (60, 60, W - 60, H - 60), (200, 20, 20))


def transparent_margin() -> Image.Image:
    # Content between the trim line (30 px) and safe line (60 px).
    return _rect_on(Image.new("RGBA", (W, H), (0, 0, 0, 0)), (40, 40, W - 40, H - 40), (20, 160, 60, 255))


def off_centre() -> Image.Image:
    return _rect_on(Image.new("RGB", (W, H), WHITE), (100, 100, 300, 320), (240, 160, 0))


def bleed_short() -> Image.Image:
    # Crosses the trim line on the left but stops 10 px short of the edge.
    return _rect_on(Image.new("RGB", (W, H), WHITE), (10, 0, W, H), NAVY)


def blank() -> Image.Image:
    return Image.new("RGB", (W, H), WHITE)


def low_res() -> Image.Image:
    # ~102 DPI: above dpi_target (100), below dpi_warn (120); aspect within 1%.
    return Image.new("RGB", (460, 358), NAVY)


def tiny() -> Image.Image:
    # 400 x 300: below dpi_target and 4:3 instead of 9:7.
    return Image.new("RGB", (400, 300), NAVY)


def rotated() -> Image.Image:
    return Image.new("RGB", (H, W), NAVY)


FIXTURES: dict[str, Callable[[], Image.Image]] = {
    "solid": solid,
    "checkerboard": checkerboard,
    "bordered": bordered,
    "transparent-margin": transparent_margin,
    "off-centre": off_centre,
    "bleed-short": bleed_short,
    "blank": blank,
    "low-res": low_res,
    "tiny": tiny,
    "rotated": rotated,
}


def generate(outdir: str | Path) -> dict[str, Path]:
    """Write every fixture as PNG (plus solid as JPEG and TIFF); return paths."""
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, make in FIXTURES.items():
        path = out / f"{name}.png"
        make().save(path, format="PNG")
        paths[name] = path
    paths["solid-jpeg"] = out / "solid.jpg"
    solid().save(paths["solid-jpeg"], format="JPEG", quality=95)
    paths["solid-tiff"] = out / "solid.tif"
    solid().save(paths["solid-tiff"], format="TIFF")
    return paths


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__.strip().splitlines()[2])
    for name, path in generate(sys.argv[1]).items():
        print(f"{name}: {path}")
