"""Preflight checks and report assembly."""

from __future__ import annotations

import math
from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from .content import EDGES, band_px, content_mask, measure
from .profile import PreflightError, Profile, exact, load_profile, profile_from_dict

SUPPORTED_FORMATS = ("PNG", "JPEG", "TIFF")

# Reason code -> severity. Order here is the order codes appear in reports.
REASONS: dict[str, str] = {
    "DPI_BELOW_TARGET": "fail",
    "DPI_BELOW_WARN": "warn",
    "ASPECT_MISMATCH": "fail",
    "CONTENT_EMPTY": "fail",
    "EDGE_COVERAGE_LOW": "fail",
    "CONTENT_OUTSIDE_SAFE": "warn",
    "OFF_CENTER": "warn",
}


def required_pixels(inches: Fraction, dpi: float) -> int:
    """Smallest pixel count that reaches ``dpi`` across ``inches``."""
    return math.ceil(inches * exact(dpi))


def floor_to(value: Fraction, places: int) -> float:
    """Truncate toward zero at ``places`` decimals (never overstates a value)."""
    scale = 10**places
    return float(Fraction(math.floor(value * scale), scale))


def round_to(value: Fraction, places: int) -> float:
    """Round half-to-even at ``places`` decimals, computed exactly."""
    return float(round(value, places))


def aspect_delta(width_px: int, height_px: int, profile: Profile) -> Fraction:
    """Relative difference between image and canvas aspect ratios (exact)."""
    target = profile.canvas_width_in / profile.canvas_height_in
    return abs(Fraction(width_px, height_px) / target - 1)


def open_image(path: str | Path) -> Image.Image:
    try:
        with Image.open(path) as img:
            if img.format not in SUPPORTED_FORMATS:
                raise PreflightError(
                    "UNSUPPORTED_FORMAT",
                    f"{img.format or 'unknown'} is not one of {', '.join(SUPPORTED_FORMATS)}",
                )
            img.seek(0)
            img.load()
            oriented = ImageOps.exif_transpose(img)
            return oriented.convert("RGBA")
    except PreflightError:
        raise
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise PreflightError("IMAGE_UNREADABLE", f"cannot read image: {exc}") from exc


def _coerce_profile(profile: Profile | dict[str, Any] | str | Path) -> Profile:
    if isinstance(profile, Profile):
        return profile
    if isinstance(profile, dict):
        return profile_from_dict(profile)
    return load_profile(profile)


def check(image: Image.Image | str | Path,
          profile: Profile | dict[str, Any] | str | Path) -> dict[str, Any]:
    """Run every preflight check and return the report dict.

    ``image`` may be a path or an already-open Pillow image; ``profile`` may
    be a :class:`Profile`, a profile dict, or a path to a profile JSON file.
    Raises :class:`PreflightError` for unreadable inputs.
    """
    prof = _coerce_profile(profile)
    img = open_image(image) if isinstance(image, (str, Path)) else image.convert("RGBA")
    w, h = img.size
    reasons: list[str] = []

    # Resolution: exact pixel counts against the full canvas (trim + bleed).
    cw, ch = prof.canvas_width_in, prof.canvas_height_in
    ppi_x, ppi_y = Fraction(w) / cw, Fraction(h) / ch
    effective = min(ppi_x, ppi_y)

    def short_at(dpi: float) -> bool:
        return w < required_pixels(cw, dpi) or h < required_pixels(ch, dpi)

    if short_at(prof.dpi_target):
        reasons.append("DPI_BELOW_TARGET")
    elif short_at(prof.dpi_warn):
        reasons.append("DPI_BELOW_WARN")

    # Aspect: the reported (rounded) value is the one compared, so the
    # report never contradicts its own verdict.
    delta = round_to(aspect_delta(w, h, prof), 6)
    if delta > prof.aspect_tolerance:
        reasons.append("ASPECT_MISMATCH")

    # Content box, edge coverage and centering.
    mask = content_mask(img, prof.background_rgb, prof.background_tolerance, prof.alpha_threshold)
    bleed = exact(prof.bleed_in)
    geo = measure(mask, band_px(bleed, ppi_x, w), band_px(bleed, ppi_y, h))

    if geo.bbox is None:
        reasons.append("CONTENT_EMPTY")
    else:
        if bleed > 0 and any(geo.edge_coverage[e] < exact(prof.edge_coverage_min) for e in EDGES):
            reasons.append("EDGE_COVERAGE_LOW")
        if not geo.full_bleed:
            inset = bleed + exact(prof.safe_margin_in)
            inset_x, inset_y = inset * ppi_x, inset * ppi_y
            left, top, right, bottom = geo.bbox
            if left < inset_x or top < inset_y or w - right < inset_x or h - bottom < inset_y:
                reasons.append("CONTENT_OUTSIDE_SAFE")
            tol = exact(prof.centering_tolerance_in)
            dx, dy = geo.centering_delta_px
            if abs(dx) > tol * ppi_x or abs(dy) > tol * ppi_y:
                reasons.append("OFF_CENTER")

    severities = {REASONS[r] for r in reasons}
    status = "fail" if "fail" in severities else "warn" if "warn" in severities else "pass"
    return {
        "status": status,
        "effective_dpi": floor_to(effective, 2),
        "aspect_delta": delta,
        "coverage_ratio": floor_to(geo.coverage_ratio, 4),
        "centering_delta_px": (
            None if geo.centering_delta_px is None
            else {"x": float(geo.centering_delta_px[0]), "y": float(geo.centering_delta_px[1])}
        ),
        "edge_coverage": {e: floor_to(geo.edge_coverage[e], 4) for e in EDGES},
        "reasons": reasons,
    }
