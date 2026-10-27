"""Pixel-dimension / effective-DPI check.

All arithmetic is exact (``fractions.Fraction``) so results do not depend on
float rounding: an image passes a DPI threshold iff both of its pixel
dimensions are >= ceil(canvas_inches * dpi).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from .profile import Profile, exact

FAIL = "fail"
WARN = "warn"
PASS = "pass"

DPI_BELOW_TARGET = "DPI_BELOW_TARGET"
DPI_BELOW_WARN = "DPI_BELOW_WARN"


def required_pixels(canvas_in: Fraction, dpi: float) -> int:
    """Smallest whole pixel count that reaches ``dpi`` across ``canvas_in`` inches."""
    return math.ceil(canvas_in * exact(dpi))


def effective_dpi(width_px: int, height_px: int, profile: Profile) -> Fraction:
    """Limiting DPI: the lower of the horizontal and vertical pixel densities."""
    return min(
        Fraction(width_px) / profile.canvas_width_in,
        Fraction(height_px) / profile.canvas_height_in,
    )


@dataclass(frozen=True)
class DpiResult:
    status: str
    effective_dpi: Fraction
    reasons: tuple[str, ...]


def check_dpi(width_px: int, height_px: int, profile: Profile) -> DpiResult:
    cw, ch = profile.canvas_width_in, profile.canvas_height_in

    def meets(dpi: float) -> bool:
        return width_px >= required_pixels(cw, dpi) and height_px >= required_pixels(ch, dpi)

    eff = effective_dpi(width_px, height_px, profile)
    if not meets(profile.dpi_target):
        return DpiResult(FAIL, eff, (DPI_BELOW_TARGET,))
    if not meets(profile.dpi_warn):
        return DpiResult(WARN, eff, (DPI_BELOW_WARN,))
    return DpiResult(PASS, eff, ())
