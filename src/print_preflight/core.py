"""Report assembly: runs every check and produces the report dict."""

from __future__ import annotations

import math
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

from PIL import Image

from . import checks
from .profile import Profile, load_profile
from .raster import content_mask, count_content, load_image, to_rgba
from .reasons import REASONS, status_for

SIDES = ("top", "right", "bottom", "left")

# Non-bleeding content may sit this fraction of the image dimension away from
# centre (or 1 px, whichever is larger) before OFF_CENTER is raised.
CENTER_TOLERANCE = Fraction(1, 100)


def _as_profile(profile: Profile | Mapping[str, Any] | str | Path) -> Profile:
    if isinstance(profile, Profile):
        return profile
    if isinstance(profile, Mapping):
        return Profile.from_dict(profile)
    return load_profile(profile)


def analyze(image: Image.Image, profile: Profile | Mapping[str, Any]) -> dict[str, Any]:
    """Run all checks on an in-memory Pillow image and return the report."""
    profile = _as_profile(profile)
    rgba = image if image.mode == "RGBA" else to_rgba(image)
    w, h = rgba.size

    reasons: list[str] = []
    reasons += checks.dpi_reasons(w, h, profile)
    reasons += checks.aspect_reasons(w, h, profile)

    # Pixel geometry of the bleed, trim and safe lines on each side.
    sx = Fraction(w) / profile.canvas_width_in
    sy = Fraction(h) / profile.canvas_height_in
    bleed_px = {"top": profile.bleed_in * sy, "bottom": profile.bleed_in * sy,
                "left": profile.bleed_in * sx, "right": profile.bleed_in * sx}
    safe_px = {"top": (profile.bleed_in + profile.safe_margin_in) * sy,
               "bottom": (profile.bleed_in + profile.safe_margin_in) * sy,
               "left": (profile.bleed_in + profile.safe_margin_in) * sx,
               "right": (profile.bleed_in + profile.safe_margin_in) * sx}

    mask = content_mask(rgba)

    # Edge bands: the bleed strip along each side, at least one pixel thick.
    bx = min(w, max(1, math.ceil(bleed_px["left"])))
    by = min(h, max(1, math.ceil(bleed_px["top"])))
    bands = {"top": (0, 0, w, by), "bottom": (0, h - by, w, h),
             "left": (0, 0, bx, h), "right": (w - bx, 0, w, h)}
    edge_cov: dict[str, Fraction] = {}
    for side, box in bands.items():
        area = (box[2] - box[0]) * (box[3] - box[1])
        edge_cov[side] = Fraction(count_content(mask, box), area)

    bbox = mask.getbbox()
    if bbox is None:
        reasons.append("NO_CONTENT")
        coverage = Fraction(0)
        dx = dy = Fraction(0)
    else:
        left, top, right, bottom = bbox  # right/bottom exclusive
        dist = {"top": top, "right": w - right, "bottom": h - bottom, "left": left}
        bleeds = {s: dist[s] == 0 or dist[s] < bleed_px[s] for s in SIDES}

        for side in SIDES:
            if bleeds[side] and dist[side] > 0:
                reasons.append("BLEED_INCOMPLETE")
        for side in SIDES:
            if not bleeds[side] and dist[side] < safe_px[side]:
                reasons.append("SAFE_MARGIN_VIOLATION")
        for side in SIDES:
            if bleeds[side] and dist[side] == 0 and edge_cov[side] < profile.edge_coverage_min:
                reasons.append("EDGE_COVERAGE_LOW")

        dx = Fraction(left + right - w, 2)
        dy = Fraction(top + bottom - h, 2)
        if not (bleeds["left"] or bleeds["right"]) and abs(dx) > max(1, w * CENTER_TOLERANCE):
            reasons.append("OFF_CENTER")
        if not (bleeds["top"] or bleeds["bottom"]) and abs(dy) > max(1, h * CENTER_TOLERANCE):
            reasons.append("OFF_CENTER")

        # Fraction of the trim (finished page) area spanned by the content box.
        tl, tt = bleed_px["left"], bleed_px["top"]
        tr, tb = w - bleed_px["right"], h - bleed_px["bottom"]
        iw = max(Fraction(0), min(Fraction(right), tr) - max(Fraction(left), tl))
        ih = max(Fraction(0), min(Fraction(bottom), tb) - max(Fraction(top), tt))
        coverage = (iw * ih) / ((tr - tl) * (tb - tt))

    order = list(REASONS)
    codes = sorted(set(reasons), key=order.index)
    return {
        "status": status_for(codes),
        "effective_dpi": checks.floor_dp(checks.effective_dpi(w, h, profile), 2),
        "aspect_delta": checks.ceil_dp(checks.aspect_delta(w, h, profile), 6),
        "coverage_ratio": checks.floor_dp(coverage, 6),
        "centering_delta_px": {"x": float(dx), "y": float(dy)},
        "edge_coverage": {s: checks.floor_dp(edge_cov[s], 6) for s in SIDES},
        "reasons": codes,
    }


def check(image_path: str | Path, profile: Profile | Mapping[str, Any] | str | Path) -> dict[str, Any]:
    """Load ``image_path`` and run all checks against ``profile``.

    ``profile`` may be a :class:`Profile`, a dict, or a path to a JSON file.
    Raises :class:`PreflightError` if the image or profile cannot be used.
    """
    profile = _as_profile(profile)
    return analyze(load_image(image_path), profile)
