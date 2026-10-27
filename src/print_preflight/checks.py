"""Preflight checks. All decisions use exact rational arithmetic; reported
numbers are rounded *in the direction that preserves the decision* so a
reported value can be compared with the profile threshold and agree with the
reason codes (see README, "Rounding")."""

from __future__ import annotations

import math
from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, UnidentifiedImageError

from .errors import PreflightError
from .profile import Profile

SUPPORTED_FORMATS = ("PNG", "JPEG", "TIFF")
SIDES = ("top", "right", "bottom", "left")

# Canonical order of reason codes in a report, with their severity.
REASON_CODES: dict[str, str] = {
    "DPI_BELOW_TARGET": "fail",
    "DPI_BELOW_WARN": "warn",
    "ASPECT_MISMATCH": "fail",
    "CONTENT_EMPTY": "fail",
    "BLEED_SHORT": "fail",
    "SAFE_MARGIN_INTRUSION": "warn",
    "EDGE_COVERAGE_LOW": "warn",
    "OFF_CENTER": "warn",
}


def floor_to(value: Fraction, places: int) -> float:
    scale = 10**places
    return math.floor(value * scale) / scale


def ceil_to(value: Fraction, places: int) -> float:
    scale = 10**places
    return math.ceil(value * scale) / scale


def _half(value: Fraction) -> float | int:
    # Centre offsets are multiples of 0.5 px; keep whole values as ints.
    return int(value) if value.denominator == 1 else float(value)


def canvas_inches(profile: Profile) -> tuple[Fraction, Fraction]:
    """Full canvas size (trim plus bleed on both sides) in exact inches."""
    bleed2 = 2 * profile.q("bleed_in")
    return profile.q("print_width_in") + bleed2, profile.q("print_height_in") + bleed2


def required_pixels(profile: Profile, dpi: Fraction) -> tuple[int, int]:
    cw, ch = canvas_inches(profile)
    return math.ceil(cw * dpi), math.ceil(ch * dpi)


def measure_resolution(width: int, height: int, profile: Profile) -> dict[str, Any]:
    """Pixel-dimension and aspect checks; needs no pixel data."""
    cw, ch = canvas_inches(profile)
    effective = min(Fraction(width) / cw, Fraction(height) / ch)
    req_target = required_pixels(profile, profile.q("dpi_target"))
    req_warn = required_pixels(profile, profile.q("dpi_warn"))
    aspect_delta = abs(Fraction(width, height) / (cw / ch) - 1)

    reasons = []
    if width < req_target[0] or height < req_target[1]:
        reasons.append("DPI_BELOW_TARGET")
    elif width < req_warn[0] or height < req_warn[1]:
        reasons.append("DPI_BELOW_WARN")
    if aspect_delta > profile.q("aspect_tolerance"):
        reasons.append("ASPECT_MISMATCH")
    return {
        "effective_dpi": floor_to(effective, 2),
        "aspect_delta": ceil_to(aspect_delta, 6),
        "required_px": {"target": list(req_target), "warn": list(req_warn)},
        "reasons": reasons,
    }


def _to_rgba(img: Image.Image) -> Image.Image:
    if img.mode in ("I;16", "I;16B", "I;16L", "I;16N", "I"):
        img = img.convert("I").point(lambda v: v * (1 / 256)).convert("L")
    elif img.mode == "F":
        img = img.convert("L")
    try:
        return img.convert("RGBA")
    except (ValueError, OSError) as exc:
        raise PreflightError("IMAGE_FORMAT_UNSUPPORTED", f"cannot convert mode {img.mode}: {exc}") from exc


def content_mask(img: Image.Image, profile: Profile) -> tuple[Image.Image, str]:
    """Return an "L" mask (255 = content, 0 = background) and the background mode.

    Images with real transparency use alpha: only fully transparent pixels are
    background. Opaque images use ``background_rgb``: pixels whose every
    channel is within ``background_tolerance`` of it are background.
    """
    has_alpha = "A" in img.getbands() or "transparency" in img.info
    rgba = _to_rgba(img)
    alpha = rgba.getchannel("A")
    if has_alpha and alpha.getextrema()[0] < 255:
        return alpha.point(lambda v: 255 if v > 0 else 0), "alpha"
    rgb = rgba.convert("RGB")
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, profile.background_rgb))
    r, g, b = diff.split()
    peak = ImageChops.lighter(ImageChops.lighter(r, g), b)
    tol = profile.background_tolerance
    return peak.point(lambda v: 255 if v > tol else 0), "color"


def _count(mask: Image.Image, box: tuple[int, int, int, int]) -> int:
    return mask.crop(box).histogram()[255]


def analyze(img: Image.Image, profile: Profile) -> dict[str, Any]:
    """Run every check on an in-memory image and return the report dict."""
    width, height = img.size
    if width == 0 or height == 0:
        raise PreflightError("IMAGE_UNREADABLE", "image has zero size")
    res = measure_resolution(width, height, profile)
    reasons = set(res.pop("reasons"))

    mask, background_mode = content_mask(img, profile)
    cw, ch = canvas_inches(profile)
    sx, sy = Fraction(width) / cw, Fraction(height) / ch
    bleed = {"x": profile.q("bleed_in") * sx, "y": profile.q("bleed_in") * sy}
    safe = {"x": profile.q("safe_margin_in") * sx, "y": profile.q("safe_margin_in") * sy}

    band_x = min(width, max(1, math.ceil(bleed["x"])))
    band_y = min(height, max(1, math.ceil(bleed["y"])))
    bands = {
        "top": (0, 0, width, band_y),
        "right": (width - band_x, 0, width, height),
        "bottom": (0, height - band_y, width, height),
        "left": (0, 0, band_x, height),
    }
    edge_exact = {}
    for side, box in bands.items():
        area = (box[2] - box[0]) * (box[3] - box[1])
        edge_exact[side] = Fraction(_count(mask, box), area)

    bbox = mask.getbbox()
    if bbox is None:
        reasons.add("CONTENT_EMPTY")
        coverage = Fraction(0)
        centering = None
        margins = None
    else:
        left, top, right, bottom = bbox
        coverage = Fraction((right - left) * (bottom - top), width * height)
        margins = {"top": top, "right": width - right, "bottom": height - bottom, "left": left}
        edge_min = profile.q("edge_coverage_min")
        for side, dist in margins.items():
            axis = "x" if side in ("left", "right") else "y"
            if dist == 0:
                # Art reaches the canvas edge on this side, so it must bleed.
                if edge_exact[side] < edge_min:
                    reasons.add("EDGE_COVERAGE_LOW")
            elif dist <= bleed[axis]:
                reasons.add("BLEED_SHORT")
            elif dist < bleed[axis] + safe[axis]:
                reasons.add("SAFE_MARGIN_INTRUSION")
        dx = Fraction(left + right, 2) - Fraction(width, 2)
        dy = Fraction(top + bottom, 2) - Fraction(height, 2)
        ctol = profile.q("centering_tolerance")
        if abs(dx) > ctol * width or abs(dy) > ctol * height:
            reasons.add("OFF_CENTER")
        centering = {"x": _half(dx), "y": _half(dy)}

    ordered = [code for code in REASON_CODES if code in reasons]
    severities = {REASON_CODES[c] for c in ordered}
    status = "fail" if "fail" in severities else "warn" if "warn" in severities else "pass"
    return {
        "status": status,
        "effective_dpi": res["effective_dpi"],
        "aspect_delta": res["aspect_delta"],
        "coverage_ratio": floor_to(coverage, 4),
        "centering_delta_px": centering,
        "edge_coverage": {side: floor_to(edge_exact[side], 4) for side in SIDES},
        "reasons": ordered,
        "image_px": {"width": width, "height": height},
        "required_px": res["required_px"],
        "content_box_px": list(bbox) if bbox else None,
        "margins_px": margins,
        "background_mode": background_mode,
    }


def open_image(path: str | Path) -> Image.Image:
    """Open and fully decode a PNG/JPEG/TIFF file (first frame only)."""
    path = Path(path)
    if not path.is_file():
        raise PreflightError("IMAGE_NOT_FOUND", f"no such image file: {path}")
    try:
        with Image.open(path) as img:
            fmt = img.format
            if fmt not in SUPPORTED_FORMATS:
                raise PreflightError(
                    "IMAGE_FORMAT_UNSUPPORTED", f"{path.name}: format {fmt} is not one of PNG, JPEG, TIFF"
                )
            img.load()
            loaded = img.copy()
            loaded.info = dict(img.info)
            return loaded
    except PreflightError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise PreflightError("IMAGE_UNREADABLE", f"{path.name}: {exc}") from exc


def check_image(path: str | Path, profile: Profile) -> dict[str, Any]:
    """Preflight an image file against a profile and return the report dict."""
    return analyze(open_image(path), profile)
