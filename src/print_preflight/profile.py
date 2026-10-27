"""Target print profile: loading and validation."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

from .errors import PreflightError

FIELDS = (
    "print_width_in",
    "print_height_in",
    "dpi_target",
    "dpi_warn",
    "bleed_in",
    "safe_margin_in",
    "aspect_tolerance",
    "edge_coverage_min",
)


def exact(value: float) -> Fraction:
    """Exact decimal value of a profile number (8.5 * 300 must be 2550, not 2549.999...)."""
    return Fraction(repr(value)) if isinstance(value, float) else Fraction(value)


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

    @property
    def canvas_width_in(self) -> Fraction:
        """Full canvas width: trim width plus bleed on both sides."""
        return exact(self.print_width_in) + 2 * exact(self.bleed_in)

    @property
    def canvas_height_in(self) -> Fraction:
        return exact(self.print_height_in) + 2 * exact(self.bleed_in)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Profile":
        if not isinstance(data, Mapping):
            raise PreflightError("PROFILE_INVALID", "profile must be a JSON object")
        missing = [k for k in FIELDS if k not in data]
        unknown = sorted(k for k in data if k not in FIELDS)
        if missing:
            raise PreflightError("PROFILE_INVALID", f"missing keys: {', '.join(missing)}")
        if unknown:
            raise PreflightError("PROFILE_INVALID", f"unknown keys: {', '.join(unknown)}")
        values = {}
        for key in FIELDS:
            v = data[key]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise PreflightError("PROFILE_INVALID", f"{key} must be a finite number")
            values[key] = v
        for key in ("print_width_in", "print_height_in", "dpi_target", "dpi_warn"):
            if values[key] <= 0:
                raise PreflightError("PROFILE_INVALID", f"{key} must be > 0")
        for key in ("bleed_in", "safe_margin_in", "aspect_tolerance"):
            if values[key] < 0:
                raise PreflightError("PROFILE_INVALID", f"{key} must be >= 0")
        if not 0 <= values["edge_coverage_min"] <= 1:
            raise PreflightError("PROFILE_INVALID", "edge_coverage_min must be within [0, 1]")
        if values["dpi_warn"] < values["dpi_target"]:
            raise PreflightError(
                "PROFILE_INVALID",
                "dpi_warn must be >= dpi_target (below dpi_target fails, below dpi_warn warns)",
            )
        return cls(**values)

    @classmethod
    def load(cls, path: str | Path) -> "Profile":
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise PreflightError("PROFILE_INVALID", f"cannot read profile: {exc}") from exc
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PreflightError("PROFILE_INVALID", f"profile is not valid JSON: {exc}") from exc
        return cls.from_dict(data)
