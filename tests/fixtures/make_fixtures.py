#!/usr/bin/env python3
"""Procedurally generate the preflight test fixtures.

Usage: python tests/fixtures/make_fixtures.py OUTDIR

Every fixture is drawn from code (no randomness, no downloads), so the test
suite regenerates them into a temporary directory on each run instead of
committing binary images. Sizes are chosen against the profiles in
``tests/fixtures/profiles``: both describe a 4.5 x 6.5 in canvas, which is
225 x 325 px at the 50 dpi warn threshold and 180 x 260 px at the 40 dpi
target threshold.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 225, 325
RED = (200, 30, 40)
BLUE = (20, 60, 180)
GREEN = (30, 150, 60)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


def solid(size=(W, H), color=RED, mode="RGB") -> Image.Image:
    return Image.new(mode, size, color)


def checkerboard(cell: int = 15) -> Image.Image:
    """Black/white cells with black in the top-left; white is background."""
    im = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(im)
    for y in range(0, H, cell):
        for x in range(0, W, cell):
            if (x // cell + y // cell) % 2 == 0:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=BLACK)
    return im


def bordered(border: int = 25) -> Image.Image:
    """Blue art inset by a white border exactly as wide as the flat profile's safe margin."""
    im = Image.new("RGB", (W, H), WHITE)
    ImageDraw.Draw(im).rectangle((border, border, W - border - 1, H - border - 1), fill=BLUE)
    return im


def transparent_margin(margin: int = 10) -> Image.Image:
    """Opaque green art inside a fully transparent margin.

    Transparent pixels are black in RGB so only alpha can classify them as
    background.
    """
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle((margin, margin, W - margin - 1, H - margin - 1), fill=GREEN + (255,))
    return im


def off_centre() -> Image.Image:
    """A 100 x 100 black box at (30, 40) on white: inside the safe area but off centre."""
    im = Image.new("RGB", (W, H), WHITE)
    ImageDraw.Draw(im).rectangle((30, 40, 129, 139), fill=BLACK)
    return im


def palette_transparent() -> Image.Image:
    """Palette image whose index 0 is transparent; art fills the centre."""
    im = Image.new("P", (W, H), 0)
    im.putpalette([255, 0, 255] + list(BLUE) + [0] * (256 * 3 - 6))
    ImageDraw.Draw(im).rectangle((25, 25, W - 26, H - 26), fill=1)
    im.info["transparency"] = 0
    return im


# name -> (builder, save kwargs). File format follows the extension.
FIXTURES: dict[str, tuple[Callable[[], Image.Image], dict]] = {
    "solid.png": (solid, {}),
    "solid.jpg": (solid, {"quality": 95, "subsampling": 0}),
    "solid_cmyk.tif": (lambda: solid(color=(0, 85, 80, 20), mode="CMYK"), {}),
    "solid_lowres.png": (lambda: solid(size=(180, 260)), {}),
    "solid_tiny.png": (lambda: solid(size=(100, 144)), {}),
    "solid_square.png": (lambda: solid(size=(325, 325)), {}),
    "blank.png": (lambda: solid(color=WHITE), {}),
    "checkerboard.png": (checkerboard, {}),
    "checkerboard.tif": (checkerboard, {"compression": "tiff_lzw"}),
    "bordered.png": (bordered, {}),
    "transparent_margin.png": (transparent_margin, {}),
    "off_centre.png": (off_centre, {}),
    "palette_transparent.png": (palette_transparent, {"transparency": 0}),
}

LOSSLESS = tuple(name for name in FIXTURES if not name.endswith(".jpg"))


def build(name: str) -> Image.Image:
    return FIXTURES[name][0]()


def write_all(outdir: str | Path) -> dict[str, Path]:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, (builder, kwargs) in FIXTURES.items():
        path = outdir / name
        builder().save(path, **kwargs)
        paths[name] = path
    return paths


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    for path in write_all(argv[0]).values():
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
