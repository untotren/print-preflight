"""Target profile parsing and validation.

All numeric values are converted to exact ``Fraction``s via their decimal
string form so that every threshold comparison is free of float error.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from .errors import ProfileError

REQUIRED_KEYS = (
    "print_width_in",
    "print_height_in",
    "dpi_target",
    "dpi_warn",
    "bleed_in",
    "safe_margin_in",
    "aspect_tolerance",
    "edge_coverage_min",
)

OPTIONAL_DEFAULTS: dict[str, Any] = {
    "background": [255, 255, 255],
    "background_tolerance": 8,
    "centering_tolerance_in": 0.0625,
    "require_bleed": False,
}


def _exact(key: str, value: Any) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProfileError(f"{key} must be a number, got {value!r}")
    if isinstance(value, float) and not math.isfinite(value):
        raise ProfileError(f"{key} must be finite, got {value!r}")
    return Fraction(str(value))


def _parse_background(value: Any) -> tuple[int, int, int]:
    if isinstance(value, str):
        text = value.strip().lstrip("#")
        if len(text) != 6:
            raise ProfileError(f"background must be '#rrggbb' or [r, g, b], got {value!r}")
        try:
            return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
        except ValueError:
            raise ProfileError(f"background must be '#rrggbb' or [r, g, b], got {value!r}") from None
    if (
        isinstance(value, list)
        and len(value) == 3
        and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in value)
    ):
        return (value[0], value[1], value[2])
    raise ProfileError(f"background must be '#rrggbb' or [r, g, b], got {value!r}")


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
    background: tuple[int, int, int] = (255, 255, 255)
    background_tolerance: int = 8
    centering_tolerance_in: Fraction = Fraction(1, 16)
    require_bleed: bool = False

    @property
    def bleed_width_in(self) -> Fraction:
        return self.print_width_in + 2 * self.bleed_in

    @property
    def bleed_height_in(self) -> Fraction:
        return self.print_height_in + 2 * self.bleed_in

    @classmethod
    def from_dict(cls, data: Any) -> "Profile":
        if not isinstance(data, dict):
            raise ProfileError("profile must be a JSON object")
        missing = [k for k in REQUIRED_KEYS if k not in data]
        if missing:
            raise ProfileError(f"profile missing required keys: {', '.join(missing)}")
        unknown = sorted(set(data) - set(REQUIRED_KEYS) - set(OPTIONAL_DEFAULTS))
        if unknown:
            raise ProfileError(f"profile has unknown keys: {', '.join(unknown)}")

        values = {k: _exact(k, data[k]) for k in REQUIRED_KEYS}
        for key in ("print_width_in", "print_height_in", "dpi_target", "dpi_warn"):
            if values[key] <= 0:
                raise ProfileError(f"{key} must be > 0")
        for key in ("bleed_in", "safe_margin_in"):
            if values[key] < 0:
                raise ProfileError(f"{key} must be >= 0")
        if not 0 <= values["aspect_tolerance"] < 1:
            raise ProfileError("aspect_tolerance must be in [0, 1)")
        if not 0 <= values["edge_coverage_min"] <= 1:
            raise ProfileError("edge_coverage_min must be in [0, 1]")

        opts = {**OPTIONAL_DEFAULTS, **{k: data[k] for k in OPTIONAL_DEFAULTS if k in data}}
        tol = opts["background_tolerance"]
        if isinstance(tol, bool) or not isinstance(tol, int) or not 0 <= tol <= 255:
            raise ProfileError("background_tolerance must be an integer in [0, 255]")
        centering = _exact("centering_tolerance_in", opts["centering_tolerance_in"])
        if centering < 0:
            raise ProfileError("centering_tolerance_in must be >= 0")
        if not isinstance(opts["require_bleed"], bool):
            raise ProfileError("require_bleed must be true or false")

        return cls(
            **values,
            background=_parse_background(opts["background"]),
            background_tolerance=tol,
            centering_tolerance_in=centering,
            require_bleed=opts["require_bleed"],
        )


def load_profile(path: str | Path) -> Profile:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ProfileError(f"cannot read profile {path}: {exc.strerror or exc}") from None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProfileError(f"profile {path} is not valid JSON: {exc}") from None
    return Profile.from_dict(data)
