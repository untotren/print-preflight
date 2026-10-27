"""Pure, exact arithmetic for the resolution and aspect checks.

Everything here works on integers and Fractions so that results at threshold
boundaries are exact. Reported floats are rounded *conservatively* (see
``floor_dp`` / ``ceil_dp``) so that a displayed value never appears to pass a
threshold that the exact value fails.
"""

from __future__ import annotations

import math
from fractions import Fraction

from .profile import Profile


def floor_dp(x: Fraction, places: int) -> float:
    scale = 10**places
    return float(Fraction(math.floor(x * scale), scale))


def ceil_dp(x: Fraction, places: int) -> float:
    scale = 10**places
    return float(Fraction(math.ceil(x * scale), scale))


# --- resolution -------------------------------------------------------------

def required_pixels(inches: Fraction, dpi: Fraction) -> int:
    """Smallest whole pixel count that covers ``inches`` at ``dpi``."""
    return math.ceil(inches * dpi)


def effective_dpi(width_px: int, height_px: int, profile: Profile) -> Fraction:
    """DPI achieved when the image is scaled to cover the full bleed canvas.

    The limiting (lower) axis determines the printed resolution.
    """
    return min(
        Fraction(width_px) / profile.canvas_width_in,
        Fraction(height_px) / profile.canvas_height_in,
    )


def dpi_reasons(width_px: int, height_px: int, profile: Profile) -> list[str]:
    dpi = effective_dpi(width_px, height_px, profile)
    if dpi < profile.dpi_target:
        return ["DPI_BELOW_TARGET"]
    if dpi < profile.dpi_warn:
        return ["DPI_BELOW_WARN"]
    return []


# --- aspect -----------------------------------------------------------------

def target_aspect(profile: Profile) -> Fraction:
    """Width / height of the bleed canvas the image is mapped onto."""
    return profile.canvas_width_in / profile.canvas_height_in


def aspect_delta(width_px: int, height_px: int, profile: Profile) -> Fraction:
    """Relative aspect error: ``|image_aspect / target_aspect - 1|``.

    Scale invariant: multiplying both pixel dimensions by k leaves it unchanged.
    """
    if width_px <= 0 or height_px <= 0:
        raise ValueError("image dimensions must be positive")
    return abs(Fraction(width_px, height_px) / target_aspect(profile) - 1)


def aspect_reasons(width_px: int, height_px: int, profile: Profile) -> list[str]:
    """Empty when within tolerance (inclusive); otherwise one aspect code.

    ``ASPECT_ROTATED`` is used instead of ``ASPECT_MISMATCH`` when the image
    would be within tolerance if rotated by 90 degrees.
    """
    if aspect_delta(width_px, height_px, profile) <= profile.aspect_tolerance:
        return []
    if aspect_delta(height_px, width_px, profile) <= profile.aspect_tolerance:
        return ["ASPECT_ROTATED"]
    return ["ASPECT_MISMATCH"]
