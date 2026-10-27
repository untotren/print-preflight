"""Target print profile: parsing and validation.

All numeric values are held as exact :class:`fractions.Fraction` so that
threshold comparisons never suffer from binary floating point drift. A float
``x`` is converted through ``repr(x)`` (its shortest round-trip decimal), and
JSON numbers are parsed straight from their decimal text, so ``8.333`` in a
profile file and ``8.333`` in a Python dict produce the same exact value.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from decimal import Decimal
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


def to_fraction(name: str, value: Any) -> Fraction:
    """Convert a profile number to an exact Fraction, rejecting non-numbers."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Fraction, Decimal)):
        raise PreflightError("PROFILE_INVALID", f"{name} must be a number, got {value!r}")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PreflightError("PROFILE_INVALID", f"{name} must be finite, got {value!r}")
        return Fraction(repr(value))
    if isinstance(value, Decimal) and not value.is_finite():
        raise PreflightError("PROFILE_INVALID", f"{name} must be finite, got {value!r}")
    return Fraction(value)


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

    @property
    def canvas_width_in(self) -> Fraction:
        """Width of the full artboard: trim plus bleed on both sides."""
        return self.print_width_in + 2 * self.bleed_in

    @property
    def canvas_height_in(self) -> Fraction:
        return self.print_height_in + 2 * self.bleed_in

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Profile":
        if not isinstance(data, Mapping):
            raise PreflightError("PROFILE_INVALID", "profile must be a JSON object")
        missing = [f for f in FIELDS if f not in data]
        if missing:
            raise PreflightError("PROFILE_INVALID", f"missing field(s): {', '.join(missing)}")
        unknown = sorted(set(data) - set(FIELDS))
        if unknown:
            raise PreflightError("PROFILE_INVALID", f"unknown field(s): {', '.join(unknown)}")
        p = cls(**{f: to_fraction(f, data[f]) for f in FIELDS})
        p._validate()
        return p

    def _validate(self) -> None:
        def bad(msg: str) -> None:
            raise PreflightError("PROFILE_INVALID", msg)

        for f in ("print_width_in", "print_height_in", "dpi_target", "dpi_warn"):
            if getattr(self, f) <= 0:
                bad(f"{f} must be > 0")
        for f in ("bleed_in", "safe_margin_in", "aspect_tolerance"):
            if getattr(self, f) < 0:
                bad(f"{f} must be >= 0")
        if not 0 <= self.edge_coverage_min <= 1:
            bad("edge_coverage_min must be between 0 and 1")
        if self.dpi_warn < self.dpi_target:
            bad("dpi_warn must be >= dpi_target (below dpi_target fails, below dpi_warn warns)")
        if 2 * self.safe_margin_in >= min(self.print_width_in, self.print_height_in):
            bad("safe_margin_in leaves no safe area inside the trim")


def _reject_constant(name: str) -> None:
    raise PreflightError("PROFILE_INVALID", f"non-finite number {name} is not allowed")


def parse_profile_json(text: str) -> Profile:
    try:
        data = json.loads(text, parse_float=Fraction, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise PreflightError("PROFILE_INVALID", f"profile is not valid JSON: {exc}") from None
    return Profile.from_dict(data)


def load_profile(path: str | Path) -> Profile:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise PreflightError("PROFILE_NOT_FOUND", f"profile not found: {path}") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise PreflightError("PROFILE_UNREADABLE", f"cannot read profile {path}: {exc}") from None
    return parse_profile_json(text)
