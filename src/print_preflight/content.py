"""Content detection: bounding box, edge-band coverage and centering.

A pixel is *content* when it is both visible (alpha above the profile's
``alpha_threshold``) and differs from the paper colour (``background_rgb``)
by more than ``background_tolerance`` in at least one RGB channel.
Everything here works on Pillow masks only, so results are bit-exact.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from PIL import Image, ImageChops

EDGES = ("top", "right", "bottom", "left")


def content_mask(image: Image.Image, background_rgb: tuple[int, int, int],
                 background_tolerance: int, alpha_threshold: int) -> Image.Image:
    """Return an ``L`` mask that is 255 where the pixel is content, else 0."""
    rgba = image if image.mode == "RGBA" else image.convert("RGBA")
    r, g, b, a = rgba.split()
    rgb = Image.merge("RGB", (r, g, b))
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, background_rgb))
    dr, dg, db = diff.split()
    channel_max = ImageChops.lighter(ImageChops.lighter(dr, dg), db)
    ink = channel_max.point([255 if v > background_tolerance else 0 for v in range(256)])
    visible = a.point([255 if v > alpha_threshold else 0 for v in range(256)])
    return ImageChops.darker(ink, visible)


def _fraction_set(mask: Image.Image) -> Fraction:
    """Exact fraction of mask pixels that are set (255)."""
    total = mask.width * mask.height
    if total == 0:
        return Fraction(0)
    return Fraction(mask.histogram()[255], total)


def band_px(inches: Fraction, ppi: Fraction, limit: int) -> int:
    """Width in pixels of an edge band, at least 1 and at most ``limit``."""
    return max(1, min(limit, math.ceil(inches * ppi)))


@dataclass(frozen=True)
class ContentGeometry:
    size: tuple[int, int]
    bbox: tuple[int, int, int, int] | None  # left, top, right, bottom (exclusive)
    edge_coverage: dict[str, Fraction]
    coverage_ratio: Fraction
    centering_delta_px: tuple[Fraction, Fraction] | None

    @property
    def full_bleed(self) -> bool:
        """True when the content box touches all four image edges."""
        return self.bbox == (0, 0, *self.size)


def measure(mask: Image.Image, band_x: int, band_y: int) -> ContentGeometry:
    """Measure content box, coverage and centering of a content mask.

    ``band_x`` is the width of the left/right edge bands and ``band_y`` the
    height of the top/bottom bands, in pixels.
    """
    w, h = mask.size
    bbox = mask.getbbox()
    bands = {
        "top": (0, 0, w, band_y),
        "right": (w - band_x, 0, w, h),
        "bottom": (0, h - band_y, w, h),
        "left": (0, 0, band_x, h),
    }
    edge_coverage = {name: _fraction_set(mask.crop(box)) for name, box in bands.items()}
    if bbox is None:
        return ContentGeometry((w, h), None, edge_coverage, Fraction(0), None)
    left, top, right, bottom = bbox
    coverage = Fraction((right - left) * (bottom - top), w * h)
    # Positive x = content sits right of centre, positive y = below centre.
    dx = Fraction(left + right, 2) - Fraction(w, 2)
    dy = Fraction(top + bottom, 2) - Fraction(h, 2)
    return ContentGeometry((w, h), bbox, edge_coverage, coverage, (dx, dy))
