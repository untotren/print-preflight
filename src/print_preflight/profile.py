"""Target print profile: loading, validation and exact numeric access."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

from .errors import PreflightError

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

OPTIONAL_DEFAULTS: dict[str, Any] = {
    "background_rgb": [255, 255, 255],
    "background_tolerance": 8,
    "centering_tolerance": 0.01,
}


def exact(value: int | float) -> Fraction:
    """Convert a JSON number to an exact rational using its shortest decimal form.

    ``0.1`` becomes exactly 1/10 rather than the nearest binary double, so
    threshold comparisons behave the way the profile author wrote them.
    """
    if isinstance(value, int):
        return Fraction(value)
    return Fraction(Decimal(repr(value)))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


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
    background_rgb: tuple[int, int, int] = (255, 255, 255)
    background_tolerance: int = 8
    centering_tolerance: float = 0.01

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Profile":
        if not isinstance(data, Mapping):
            raise PreflightError("PROFILE_INVALID", "profile must be a JSON object")
        problems: list[str] = []
        unknown = sorted(set(data) - set(REQUIRED_FIELDS) - set(OPTIONAL_DEFAULTS))
        if unknown:
            problems.append(f"unknown field(s): {', '.join(unknown)}")
        missing = [k for k in REQUIRED_FIELDS if k not in data]
        if missing:
            problems.append(f"missing field(s): {', '.join(missing)}")
        for key in REQUIRED_FIELDS + ("background_tolerance", "centering_tolerance"):
            if key in data and not _is_number(data[key]):
                problems.append(f"{key} must be a finite number")
        if problems:
            raise PreflightError("PROFILE_INVALID", "; ".join(problems))

        merged = {**OPTIONAL_DEFAULTS, **data}
        rules = [
            ("print_width_in", merged["print_width_in"] > 0, "must be > 0"),
            ("print_height_in", merged["print_height_in"] > 0, "must be > 0"),
            ("dpi_target", merged["dpi_target"] > 0, "must be > 0"),
            ("dpi_warn", merged["dpi_warn"] >= merged["dpi_target"], "must be >= dpi_target"),
            ("bleed_in", merged["bleed_in"] >= 0, "must be >= 0"),
            ("safe_margin_in", merged["safe_margin_in"] >= 0, "must be >= 0"),
            ("aspect_tolerance", merged["aspect_tolerance"] >= 0, "must be >= 0"),
            ("edge_coverage_min", 0 <= merged["edge_coverage_min"] <= 1, "must be between 0 and 1"),
            ("centering_tolerance", merged["centering_tolerance"] >= 0, "must be >= 0"),
        ]
        tol = merged["background_tolerance"]
        rules.append(
            ("background_tolerance", isinstance(tol, int) and 0 <= tol <= 255, "must be an integer 0..255")
        )
        bg = merged["background_rgb"]
        bg_ok = (
            isinstance(bg, list)
            and len(bg) == 3
            and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in bg)
        )
        rules.append(("background_rgb", bg_ok, "must be a list of three integers 0..255"))
        problems = [f"{key} {msg}" for key, ok, msg in rules if not ok]
        if problems:
            raise PreflightError("PROFILE_INVALID", "; ".join(problems))

        numeric = REQUIRED_FIELDS + ("centering_tolerance",)
        return cls(
            **{k: merged[k] for k in numeric},
            background_rgb=tuple(bg),
            background_tolerance=tol,
        )

    def q(self, name: str) -> Fraction:
        """Exact rational value of a numeric profile field."""
        return exact(getattr(self, name))

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {k: getattr(self, k) for k in REQUIRED_FIELDS}
        out["background_rgb"] = list(self.background_rgb)
        out["background_tolerance"] = self.background_tolerance
        out["centering_tolerance"] = self.centering_tolerance
        return out


def load_profile(path: str | Path) -> Profile:
    """Read and validate a profile JSON file."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PreflightError("PROFILE_UNREADABLE", f"cannot read profile {path}: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PreflightError("PROFILE_UNREADABLE", f"profile {path} is not valid JSON: {exc}") from exc
    return Profile.from_dict(data)
