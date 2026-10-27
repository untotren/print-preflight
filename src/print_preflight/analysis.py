"""Core preflight analysis.

Decisions are made on exact rational values (``Fraction``); reported numbers
are rounded only for display, using fixed rules documented in README.md.
"""

from __future__ import annotations

import math
from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageOps, UnidentifiedImageError

from . import reasons as R
from .errors import ImageLoadError
from .profile import Profile

SUPPORTED_FORMATS = {"PNG", "JPEG", "MPO", "TIFF"}
SIDES = ("top", "right", "bottom", "left")


# --------------------------------------------------------------------------
# Exact numeric helpers (pure, used directly by the property tests)
# --------------------------------------------------------------------------

def required_pixels(inches: Fraction, dpi: Fraction) -> int:
    """Smallest pixel count whose density over ``inches`` is at least ``dpi``."""
    return math.ceil(Fraction(inches) * Fraction(dpi))


def effective_dpi_exact(width_px: int, height_px: int, profile: Profile) -> Fraction:
    return min(
        Fraction(width_px) / profile.bleed_width_in,
        Fraction(height_px) / profile.bleed_height_in,
    )


def aspect_delta_exact(width_px: int, height_px: int, profile: Profile) -> Fraction:
    """Relative deviation of the image aspect from the bleed-box aspect."""
    target = profile.bleed_width_in / profile.bleed_height_in
    return abs(Fraction(width_px, height_px) / target - 1)


def round_px(value: Fraction) -> int:
    """Round half up to a whole pixel."""
    return math.floor(Fraction(value) + Fraction(1, 2))


def floor_places(value: Fraction, places: int) -> float:
    scale = 10**places
    return float(Fraction(math.floor(Fraction(value) * scale), scale))


def round_places(value: Fraction, places: int) -> float:
    # round() on a Fraction is exact and uses round-half-even.
    return float(round(Fraction(value), places))


# --------------------------------------------------------------------------
# Image handling
# --------------------------------------------------------------------------

def to_rgba(img: Image.Image) -> Image.Image:
    """Normalise any Pillow mode to 8-bit RGBA without touching the source."""
    if img.mode in ("I", "I;16", "I;16L", "I;16B", "I;16N"):
        img = img.convert("I").point(lambda v: v * (1 / 256)).convert("L")
    elif img.mode == "F":
        img = img.convert("L")
    if img.mode == "RGBA":
        return img.copy()
    return img.convert("RGBA")


def load_image(path: str | Path) -> Image.Image:
    """Open a PNG/JPEG/TIFF from disk as RGBA (first frame, EXIF-oriented)."""
    try:
        with Image.open(path) as im:
            fmt = im.format
            if fmt not in SUPPORTED_FORMATS:
                raise ImageLoadError(f"unsupported image format {fmt!r} (expected PNG, JPEG or TIFF)")
            im.seek(0)
            im.load()
            return to_rgba(ImageOps.exif_transpose(im))
    except ImageLoadError:
        raise
    except FileNotFoundError:
        raise ImageLoadError(f"image not found: {path}") from None
    except UnidentifiedImageError:
        raise ImageLoadError(f"not a recognised image: {path}") from None
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageLoadError(f"cannot read image {path}: {exc}") from None


def content_mask(rgba: Image.Image, background: tuple[int, int, int], tolerance: int) -> Image.Image:
    """'L' mask: 255 where a pixel is non-transparent and differs from the
    background by more than ``tolerance`` in any channel, else 0."""
    rgb = rgba.convert("RGB")
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, background))
    r, g, b = diff.split()
    channel_max = ImageChops.lighter(ImageChops.lighter(r, g), b)
    ink = channel_max.point([255 if v > tolerance else 0 for v in range(256)])
    opaque = rgba.getchannel("A").point([255 if v > 0 else 0 for v in range(256)])
    return ImageChops.multiply(ink, opaque)


def edge_bands(width: int, height: int, band_x: int, band_y: int) -> dict[str, tuple[int, int, int, int]]:
    """Crop boxes (left, upper, right, lower) for each edge band.

    Top/bottom bands are ``band_y`` rows tall and span the full width;
    left/right bands are ``band_x`` columns wide and span the full height.
    Bands are clamped to at least one pixel and at most the image size, so
    corner pixels belong to two bands.
    """
    bx = min(max(band_x, 1), width)
    by = min(max(band_y, 1), height)
    return {
        "top": (0, 0, width, by),
        "right": (width - bx, 0, width, height),
        "bottom": (0, height - by, width, height),
        "left": (0, 0, bx, height),
    }


def edge_coverage_exact(mask: Image.Image, bands: dict[str, tuple[int, int, int, int]]) -> dict[str, Fraction]:
    """Fraction of each band's pixels that are content (non-background)."""
    result = {}
    for side in SIDES:
        box = bands[side]
        total = (box[2] - box[0]) * (box[3] - box[1])
        hits = mask.crop(box).histogram()[255]
        result[side] = Fraction(hits, total)
    return result


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_image(img: Image.Image, profile: Profile) -> dict[str, Any]:
    """Run every check on an in-memory image and return the report dict."""
    rgba = to_rgba(img)
    width, height = rgba.size
    if width == 0 or height == 0:
        raise ImageLoadError("image has zero width or height")
    codes: set[str] = set()

    # Resolution
    bw, bh = profile.bleed_width_in, profile.bleed_height_in
    req_target = (required_pixels(bw, profile.dpi_target), required_pixels(bh, profile.dpi_target))
    req_warn = (required_pixels(bw, profile.dpi_warn), required_pixels(bh, profile.dpi_warn))
    if width < req_target[0] or height < req_target[1]:
        codes.add("DPI_BELOW_TARGET")
    elif width < req_warn[0] or height < req_warn[1]:
        codes.add("DPI_BELOW_WARN")
    eff_dpi = effective_dpi_exact(width, height, profile)

    # Aspect
    aspect_delta = aspect_delta_exact(width, height, profile)
    if aspect_delta > profile.aspect_tolerance:
        codes.add("ASPECT_MISMATCH")

    # Geometry: the image is mapped onto the bleed box, independently per axis.
    sx, sy = Fraction(width) / bw, Fraction(height) / bh
    trim = {"x": round_px(profile.bleed_in * sx), "y": round_px(profile.bleed_in * sy)}
    safe = {
        "x": round_px((profile.bleed_in + profile.safe_margin_in) * sx),
        "y": round_px((profile.bleed_in + profile.safe_margin_in) * sy),
    }
    axis = {"top": "y", "bottom": "y", "left": "x", "right": "x"}

    mask = content_mask(rgba, profile.background, profile.background_tolerance)
    bands = edge_bands(width, height, trim["x"], trim["y"])
    coverage = edge_coverage_exact(mask, bands)
    bbox = mask.getbbox()

    must_bleed: list[str] = []
    centering = None
    coverage_ratio = Fraction(0)
    if bbox is None:
        codes.add("CONTENT_EMPTY")
    else:
        left, top, right, bottom = bbox
        distance = {"top": top, "right": width - right, "bottom": height - bottom, "left": left}
        for side in SIDES:
            d = distance[side]
            trim_px = trim[axis[side]]
            crossed_trim = d < max(trim_px, 1)
            if profile.require_bleed and d > 0:
                codes.add("BLEED_MISSING")
            if crossed_trim and d > 0:
                codes.add("BLEED_SHORT")
            if not crossed_trim and d < safe[axis[side]]:
                codes.add("SAFE_MARGIN_VIOLATION")
            if crossed_trim or profile.require_bleed:
                must_bleed.append(side)
                if coverage[side] < profile.edge_coverage_min:
                    codes.add("EDGE_COVERAGE_LOW")

        dx = Fraction(left + right - width, 2)
        dy = Fraction(top + bottom - height, 2)
        if abs(dx) > profile.centering_tolerance_in * sx or abs(dy) > profile.centering_tolerance_in * sy:
            codes.add("OFF_CENTRE")
        centering = {"x": float(dx), "y": float(dy)}

        tl, tt, tr, tb = trim["x"], trim["y"], width - trim["x"], height - trim["y"]
        trim_area = max(tr - tl, 0) * max(tb - tt, 0)
        if trim_area:
            iw = max(min(right, tr) - max(left, tl), 0)
            ih = max(min(bottom, tb) - max(top, tt), 0)
            coverage_ratio = Fraction(iw * ih, trim_area)

    return {
        "status": R.status_for(codes),
        "effective_dpi": floor_places(eff_dpi, 2),
        "aspect_delta": round_places(aspect_delta, 6),
        "coverage_ratio": round_places(coverage_ratio, 4),
        "centering_delta_px": centering,
        "edge_coverage": {side: round_places(coverage[side], 4) for side in SIDES},
        "reasons": R.ordered(codes),
        "image": {"width_px": width, "height_px": height},
        "required_px": {
            "target": {"width": req_target[0], "height": req_target[1]},
            "warn": {"width": req_warn[0], "height": req_warn[1]},
        },
        "content_box_px": list(bbox) if bbox else None,
        "edge_band_px": {"x": bands["left"][2], "y": bands["top"][3]},
        "must_bleed": must_bleed,
    }


def preflight(image_path: str | Path, profile: Profile) -> dict[str, Any]:
    """Load ``image_path`` and return its preflight report."""
    return check_image(load_image(image_path), profile)
