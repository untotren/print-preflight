"""Target print profile loading and validation.

All numeric fields are converted to :class:`fractions.Fraction` from their
decimal text so threshold comparisons are exact (``8.5`` means exactly 17/2,
not the nearest binary float).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from .errors import ProfileError

REQUIRED_FIELDS = (
    "print_width_in",
    "print_height_in",
    "dpi_target",
    "dpi_warn",
    "bleed_in",
    "safe_margin_in",
    "aspect_tolerance",
    "edge_coverage_min",
)
OPTIONAL_FIELDS = (
    "must_bleed",
    "background_rgb",
    "background_tolerance",
    "centering_tolerance_in",
)

DEFAULT_BACKGROUND_RGB = (255, 255, 255)
DEFAULT_BACKGROUND_TOLERANCE = 8
DEFAULT_CENTERING_TOLERANCE_IN = Fraction(1, 16)


def to_fraction(value: Any, name: str) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProfileError(f"{name} must be a number, got {value!r}")
    if isinstance(value, float) and not math.isfinite(value):
        raise ProfileError(f"{name} must be finite, got {value!r}")
    # str() of a float is its shortest round-tripping decimal, i.e. what the
    # author wrote in the JSON.
    return Fraction(str(value)) if isinstance(value, float) else Fraction(value)


@dataclass(frozen=True)
class Profile:
    print_width_in: Fraction
    print_height_in: Fraction
    dpi_target: Fraction
    dpi_warn: Fraction
    bleed_in: Fraction
    safe_margin_in: Fraction
    aspect_tolerance: Fraction
    edge_coverage_min: Fraction
    must_bleed: bool
    background_rgb: tuple[int, int, int] = DEFAULT_BACKGROUND_RGB
    background_tolerance: int = DEFAULT_BACKGROUND_TOLERANCE
    centering_tolerance_in: Fraction = DEFAULT_CENTERING_TOLERANCE_IN

    @property
    def canvas_width_in(self) -> Fraction:
        return self.print_width_in + 2 * self.bleed_in

    @property
    def canvas_height_in(self) -> Fraction:
        return self.print_height_in + 2 * self.bleed_in

    @classmethod
    def from_dict(cls, data: Any) -> "Profile":
        if not isinstance(data, dict):
            raise ProfileError("profile must be a JSON object")
        missing = [k for k in REQUIRED_FIELDS if k not in data]
        if missing:
            raise ProfileError(f"profile is missing required field(s): {', '.join(missing)}")
        unknown = sorted(set(data) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS))
        if unknown:
            raise ProfileError(f"profile has unknown field(s): {', '.join(unknown)}")

        f = {k: to_fraction(data[k], k) for k in REQUIRED_FIELDS}
        for k in ("print_width_in", "print_height_in", "dpi_target"):
            if f[k] <= 0:
                raise ProfileError(f"{k} must be > 0")
        for k in ("bleed_in", "safe_margin_in", "aspect_tolerance"):
            if f[k] < 0:
                raise ProfileError(f"{k} must be >= 0")
        if f["dpi_warn"] < f["dpi_target"]:
            raise ProfileError("dpi_warn must be >= dpi_target")
        if not 0 <= f["edge_coverage_min"] <= 1:
            raise ProfileError("edge_coverage_min must be between 0 and 1")
        if 2 * f["safe_margin_in"] >= min(f["print_width_in"], f["print_height_in"]):
            raise ProfileError("safe_margin_in leaves no safe area")

        must_bleed = data.get("must_bleed", f["bleed_in"] > 0)
        if not isinstance(must_bleed, bool):
            raise ProfileError("must_bleed must be true or false")

        bg = data.get("background_rgb", list(DEFAULT_BACKGROUND_RGB))
        if (
            not isinstance(bg, list)
            or len(bg) != 3
            or not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in bg)
        ):
            raise ProfileError("background_rgb must be a list of three integers 0-255")

        tol = data.get("background_tolerance", DEFAULT_BACKGROUND_TOLERANCE)
        if isinstance(tol, bool) or not isinstance(tol, int) or not 0 <= tol <= 255:
            raise ProfileError("background_tolerance must be an integer 0-255")

        if "centering_tolerance_in" in data:
            ctol = to_fraction(data["centering_tolerance_in"], "centering_tolerance_in")
            if ctol < 0:
                raise ProfileError("centering_tolerance_in must be >= 0")
        else:
            ctol = DEFAULT_CENTERING_TOLERANCE_IN

        return cls(
            **f,
            must_bleed=must_bleed,
            background_rgb=(bg[0], bg[1], bg[2]),
            background_tolerance=tol,
            centering_tolerance_in=ctol,
        )


def load_profile(path: str | Path) -> Profile:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ProfileError(f"cannot read profile {path}: {exc.strerror or exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProfileError(f"profile {path} is not valid JSON: {exc}") from exc
    return Profile.from_dict(data)
