"""Procedurally generate the test fixture images.

Usage: python tests/fixtures/make_fixtures.py OUTDIR

Fixtures are generated (never committed) so they are reproducible from this
script alone. Sizes are chosen against ``tests/fixtures/profile.json``
(2 x 3 in trim + 0.125 in bleed = 2.25 x 3.25 in canvas):

    dpi_target 100 -> 225 x 325 px required   (below: fail)
    dpi_warn   150 -> 338 x 488 px required   (below: warn)
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

INK = (30, 60, 120)
PAPER = (255, 255, 255)


def solid(size):
    return Image.new("RGB", size, INK)


def checkerboard(size, cell=16):
    img = Image.new("RGB", size, PAPER)
    draw = ImageDraw.Draw(img)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2 == 0:
                draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=INK)
    return img


def bordered(size, border=20):
    img = Image.new("RGB", size, PAPER)
    ImageDraw.Draw(img).rectangle(
        [border, border, size[0] - 1 - border, size[1] - 1 - border], fill=INK
    )
    return img


def transparent_margin(size, margin=24):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle(
        [margin, margin, size[0] - 1 - margin, size[1] - 1 - margin], fill=INK + (255,)
    )
    return img


def off_centre(size, box=(40, 30, 200, 250)):
    img = Image.new("RGB", size, PAPER)
    ImageDraw.Draw(img).rectangle(box, fill=INK)
    return img


# name -> (filename, builder, pixel size)
FIXTURES = {
    "solid": ("solid.png", solid, (338, 488)),  # exactly at dpi_warn -> pass
    "checkerboard": ("checkerboard.jpg", checkerboard, (300, 434)),  # between -> warn
    "bordered": ("bordered.png", bordered, (225, 325)),  # exactly at dpi_target -> warn
    "transparent_margin": ("transparent_margin.png", transparent_margin, (224, 325)),  # 1px short -> fail
    "off_centre": ("off_centre.tiff", off_centre, (400, 600)),  # comfortably above -> pass
}


def generate(outdir: str | Path) -> dict[str, Path]:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, (filename, build, size) in FIXTURES.items():
        path = outdir / filename
        build(size).save(path)
        paths[name] = path
    return paths


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    for name, path in generate(sys.argv[1]).items():
        print(f"{name}: {path}")
