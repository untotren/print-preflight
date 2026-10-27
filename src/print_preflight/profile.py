"""Target print profile loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any


class PreflightError(Exception):
    """An input problem that prevents a report from being produced (exit 3)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def exact(value: float | int) -> Fraction:
    """Exact rational for a profile number, using its shortest decimal form.

    ``8.1`` becomes ``81/10`` rather than the binary float approximation, so
    boundary comparisons behave the way a human reading the profile expects.
    """
    return Fraction(str(value))


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


@dataclass(frozen=True)
class Profile:
    print_width_in: float
    print_height_in: float
    dpi_target: float
    dpi_warn: float
    bleed_in: float
    safe_margin_in: float
    aspect_tolerance: float
    edge_coverage_min: float
    # Optional tuning knobs (see README "Profile").
    background_rgb: tuple[int, int, int] = (255, 255, 255)
    background_tolerance: int = 16
    alpha_threshold: int = 0
    centering_tolerance_in: float = 0.0625

    @property
    def canvas_width_in(self) -> Fraction:
        """Full art width: trim width plus bleed on both sides."""
        return exact(self.print_width_in) + 2 * exact(self.bleed_in)

    @property
    def canvas_height_in(self) -> Fraction:
        return exact(self.print_height_in) + 2 * exact(self.bleed_in)


def _number(data: dict[str, Any], key: str, *, positive: bool) -> float:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PreflightError("PROFILE_INVALID", f"{key} must be a number")
    if value != value or value in (float("inf"), float("-inf")):
        raise PreflightError("PROFILE_INVALID", f"{key} must be finite")
    if positive and value <= 0:
        raise PreflightError("PROFILE_INVALID", f"{key} must be > 0")
    if not positive and value < 0:
        raise PreflightError("PROFILE_INVALID", f"{key} must be >= 0")
    return value


def profile_from_dict(data: Any) -> Profile:
    if not isinstance(data, dict):
        raise PreflightError("PROFILE_INVALID", "profile must be a JSON object")
    missing = [k for k in REQUIRED_FIELDS if k not in data]
    if missing:
        raise PreflightError("PROFILE_INVALID", f"missing fields: {', '.join(missing)}")

    kwargs: dict[str, Any] = {}
    for key in ("print_width_in", "print_height_in", "dpi_target", "dpi_warn"):
        kwargs[key] = _number(data, key, positive=True)
    for key in ("bleed_in", "safe_margin_in", "aspect_tolerance", "edge_coverage_min"):
        kwargs[key] = _number(data, key, positive=False)
    if kwargs["edge_coverage_min"] > 1:
        raise PreflightError("PROFILE_INVALID", "edge_coverage_min must be <= 1")

    if "background_rgb" in data:
        rgb = data["background_rgb"]
        if (
            not isinstance(rgb, list)
            or len(rgb) != 3
            or not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in rgb)
        ):
            raise PreflightError("PROFILE_INVALID", "background_rgb must be [r, g, b] with 0-255 ints")
        kwargs["background_rgb"] = tuple(rgb)
    for key in ("background_tolerance", "alpha_threshold"):
        if key in data:
            v = data[key]
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 255:
                raise PreflightError("PROFILE_INVALID", f"{key} must be an int in 0-255")
            kwargs[key] = v
    if "centering_tolerance_in" in data:
        kwargs["centering_tolerance_in"] = _number(data, "centering_tolerance_in", positive=False)

    unknown = sorted(set(data) - set(REQUIRED_FIELDS) - set(Profile.__dataclass_fields__))
    if unknown:
        raise PreflightError("PROFILE_INVALID", f"unknown fields: {', '.join(unknown)}")
    return Profile(**kwargs)


def load_profile(path: str | Path) -> Profile:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise PreflightError("PROFILE_INVALID", f"cannot read profile: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PreflightError("PROFILE_INVALID", f"profile is not valid JSON: {exc}") from exc
    return profile_from_dict(data)
