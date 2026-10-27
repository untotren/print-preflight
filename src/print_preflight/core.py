"""Preflight checks and report assembly.

Every threshold decision is made with exact rational arithmetic; values are
only rounded (half up) when written into the report.
"""

from __future__ import annotations

import math
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageChops, ImageOps, UnidentifiedImageError

from .errors import ImageError
from .profile import Profile
from .reasons import sort_codes, status_for

SCHEMA_VERSION = 1
SUPPORTED_FORMATS = ("PNG", "JPEG", "TIFF")
EDGES = ("top", "right", "bottom", "left")


def round_half_up(value: Fraction, places: int) -> float:
    scale = 10**places
    return float(Fraction(math.floor(value * scale + Fraction(1, 2)), scale))


def required_pixels(inches: Fraction, dpi: Fraction) -> int:
    """Smallest pixel count whose density over ``inches`` is >= ``dpi``."""
    return math.ceil(inches * dpi)


def effective_dpi(width_px: int, height_px: int, profile: Profile) -> Fraction:
    return min(
        Fraction(width_px) / profile.canvas_width_in,
        Fraction(height_px) / profile.canvas_height_in,
    )


def resolution_reasons(width_px: int, height_px: int, profile: Profile) -> list[str]:
    def meets(dpi: Fraction) -> bool:
        return width_px >= required_pixels(profile.canvas_width_in, dpi) and height_px >= required_pixels(
            profile.canvas_height_in, dpi
        )

    if not meets(profile.dpi_target):
        return ["DPI_BELOW_TARGET"]
    if not meets(profile.dpi_warn):
        return ["DPI_BELOW_WARN"]
    return []


def aspect_delta(width_px: int, height_px: int, profile: Profile) -> Fraction:
    """Relative difference ``|image_aspect / canvas_aspect - 1|``."""
    image_aspect = Fraction(width_px, height_px)
    canvas_aspect = profile.canvas_width_in / profile.canvas_height_in
    return abs(image_aspect / canvas_aspect - 1)


def aspect_reasons(width_px: int, height_px: int, profile: Profile) -> list[str]:
    return ["ASPECT_MISMATCH"] if aspect_delta(width_px, height_px, profile) > profile.aspect_tolerance else []


def _normalise(im: Image.Image) -> tuple[Image.Image, Image.Image | None]:
    """Return ``(rgb, alpha_or_None)`` for any Pillow mode we may meet."""
    if im.mode in ("I;16", "I;16B", "I;16L", "I;16N", "I"):
        im = im.convert("I").point(lambda v: v * (1 / 257)).convert("L")
    elif im.mode == "F":
        im = im.point(lambda v: v * 255).convert("L")
    alpha = None
    if "A" in im.getbands() or "transparency" in im.info:
        im = im.convert("RGBA")
        alpha = im.getchannel("A")
    return im.convert("RGB"), alpha


def content_mask(im: Image.Image, profile: Profile) -> Image.Image:
    """Mode-"L" mask: 255 where a pixel is content, 0 where it is background.

    A pixel is background if it is fully transparent, or if every channel is
    within ``background_tolerance`` of ``background_rgb``.
    """
    rgb, alpha = _normalise(im)
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, profile.background_rgb))
    r, g, b = diff.split()
    channel_max = ImageChops.lighter(ImageChops.lighter(r, g), b)
    tol = profile.background_tolerance
    mask = channel_max.point([255 if v > tol else 0 for v in range(256)])
    if alpha is not None:
        mask = ImageChops.multiply(mask, alpha.point([255 if v > 0 else 0 for v in range(256)]))
    return mask


def _count(mask: Image.Image, box: tuple[int, int, int, int]) -> int:
    return mask.crop(box).histogram()[255]


def analyze(im: Image.Image, profile: Profile, image_format: str | None = None) -> dict:
    """Run every check on an already-opened image and return the report."""
    width, height = im.size
    codes: list[str] = []
    codes += resolution_reasons(width, height, profile)
    codes += aspect_reasons(width, height, profile)

    sx = Fraction(width) / profile.canvas_width_in
    sy = Fraction(height) / profile.canvas_height_in

    mask = content_mask(im, profile)
    bbox = mask.getbbox()

    band_x = min(width, max(1, math.ceil(profile.bleed_in * sx)))
    band_y = min(height, max(1, math.ceil(profile.bleed_in * sy)))
    bands = {
        "top": (0, 0, width, band_y),
        "right": (width - band_x, 0, width, height),
        "bottom": (0, height - band_y, width, height),
        "left": (0, 0, band_x, height),
    }
    edge = {}
    for name in EDGES:
        l, t, r, b = bands[name]
        edge[name] = Fraction(_count(mask, bands[name]), (r - l) * (b - t))

    coverage = Fraction(0)
    centering = None
    if bbox is None:
        codes.append("NO_CONTENT")
    else:
        left, top, right, bottom = bbox
        trim = (profile.bleed_in * sx, profile.bleed_in * sy, width - profile.bleed_in * sx, height - profile.bleed_in * sy)
        ix = max(Fraction(0), min(Fraction(right), trim[2]) - max(Fraction(left), trim[0]))
        iy = max(Fraction(0), min(Fraction(bottom), trim[3]) - max(Fraction(top), trim[1]))
        coverage = ix * iy / ((trim[2] - trim[0]) * (trim[3] - trim[1]))

        if profile.must_bleed:
            if bbox != (0, 0, width, height):
                codes.append("BLEED_NOT_REACHED")
            if any(edge[n] < profile.edge_coverage_min for n in EDGES):
                codes.append("EDGE_COVERAGE_LOW")
        else:
            inset = profile.bleed_in + profile.safe_margin_in
            if left < inset * sx or top < inset * sy or right > width - inset * sx or bottom > height - inset * sy:
                codes.append("SAFE_MARGIN_VIOLATION")

        dx = Fraction(left + right - width, 2)
        dy = Fraction(top + bottom - height, 2)
        centering = {"x": float(dx), "y": float(dy)}
        tol = profile.centering_tolerance_in
        if abs(dx) > tol * sx or abs(dy) > tol * sy:
            codes.append("OFF_CENTER")

    reasons = sort_codes(codes)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status_for(reasons),
        "reasons": reasons,
        "effective_dpi": round_half_up(effective_dpi(width, height, profile), 2),
        "aspect_delta": round_half_up(aspect_delta(width, height, profile), 6),
        "coverage_ratio": round_half_up(coverage, 6),
        "centering_delta_px": centering,
        "edge_coverage": {n: round_half_up(edge[n], 6) for n in EDGES},
        "content_box": list(bbox) if bbox else None,
        "must_bleed": profile.must_bleed,
        "image": {"format": image_format, "mode": im.mode, "width_px": width, "height_px": height},
        "required_px": {
            key: {
                "width": required_pixels(profile.canvas_width_in, dpi),
                "height": required_pixels(profile.canvas_height_in, dpi),
            }
            for key, dpi in (("target", profile.dpi_target), ("warn", profile.dpi_warn))
        },
    }


def open_image(path: str | Path) -> tuple[Image.Image, str]:
    """Open ``path``, enforce PNG/JPEG/TIFF, apply EXIF orientation, load pixels."""
    try:
        im = Image.open(path)
    except FileNotFoundError as exc:
        raise ImageError(f"image not found: {path}") from exc
    except UnidentifiedImageError as exc:
        raise ImageError(f"not a recognised image: {path}") from exc
    except (OSError, Image.DecompressionBombError) as exc:
        raise ImageError(f"cannot open image {path}: {exc}") from exc
    fmt = im.format
    if fmt not in SUPPORTED_FORMATS:
        im.close()
        raise ImageError(f"unsupported image format {fmt} (expected PNG, JPEG or TIFF): {path}")
    try:
        with im:
            oriented = ImageOps.exif_transpose(im)
            oriented.load()
    except (OSError, ValueError, SyntaxError) as exc:
        raise ImageError(f"cannot decode image {path}: {exc}") from exc
    return oriented, fmt


def check_image(path: str | Path, profile: Profile) -> dict:
    """Preflight the image at ``path`` against ``profile`` and return the report."""
    im, fmt = open_image(path)
    return analyze(im, profile, fmt)
