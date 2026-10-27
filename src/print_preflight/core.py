"""Library entry point: ``preflight(image_path, profile) -> report dict``."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from PIL import Image, UnidentifiedImageError

from .dpi import FAIL, PASS, WARN, check_dpi
from .errors import PreflightError
from .profile import Profile

SUPPORTED_FORMATS = frozenset({"PNG", "JPEG", "TIFF"})
_SEVERITY = {PASS: 0, WARN: 1, FAIL: 2}


def read_dimensions(image_path: str | Path) -> tuple[int, int]:
    """Return (width, height) in pixels of a local PNG/JPEG/TIFF file."""
    try:
        with Image.open(image_path) as img:
            if img.format not in SUPPORTED_FORMATS:
                raise PreflightError(
                    "IMAGE_UNSUPPORTED", f"unsupported image format: {img.format}"
                )
            return img.size
    except PreflightError:
        raise
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise PreflightError("IMAGE_UNREADABLE", f"cannot read image: {exc}") from exc


def preflight(image_path: str | Path, profile: Profile | Mapping[str, Any]) -> dict[str, Any]:
    """Run all implemented checks and return the report dict.

    Raises ``PreflightError`` if the profile or image cannot be used.
    Fields for checks that are not implemented yet are ``None``.
    """
    if not isinstance(profile, Profile):
        profile = Profile.from_dict(profile)
    width, height = read_dimensions(image_path)

    dpi = check_dpi(width, height, profile)
    results = [dpi]

    status = max((r.status for r in results), key=_SEVERITY.__getitem__)
    return {
        "status": status,
        "effective_dpi": round(float(dpi.effective_dpi), 3),
        "aspect_delta": None,
        "coverage_ratio": None,
        "centering_delta_px": None,
        "edge_coverage": None,
        "reasons": [code for r in results for code in r.reasons],
    }
