"""Reason codes emitted in preflight reports.

This module is the single source of truth for reason codes. The README
reason-code table is generated from :data:`REASONS` (see
:func:`markdown_table`) and a test keeps the two in sync.
"""

from __future__ import annotations

from dataclasses import dataclass

FAIL = "fail"
WARN = "warn"


@dataclass(frozen=True)
class Reason:
    code: str
    severity: str
    summary: str


# Listed in evaluation order; reports list reasons in this order.
REASONS: tuple[Reason, ...] = (
    Reason(
        "DPI_BELOW_TARGET",
        FAIL,
        "Pixel width or height is below the count `dpi_target` requires for the "
        "full canvas (trim + 2 x `bleed_in`).",
    ),
    Reason(
        "DPI_BELOW_WARN",
        WARN,
        "Pixel dimensions meet `dpi_target` but the width or height is below the "
        "count `dpi_warn` requires.",
    ),
    Reason(
        "ASPECT_MISMATCH",
        FAIL,
        "Image aspect ratio differs from the canvas aspect ratio by more than "
        "`aspect_tolerance` (relative; a delta equal to the tolerance passes).",
    ),
    Reason(
        "NO_CONTENT",
        FAIL,
        "Every pixel is background (transparent, or within `background_tolerance` "
        "of `background_rgb`); coverage, bleed, margin and centering checks are "
        "skipped.",
    ),
    Reason(
        "BLEED_NOT_REACHED",
        FAIL,
        "Art must bleed but the content box does not reach every image edge, so "
        "unprinted paper can show after trimming.",
    ),
    Reason(
        "EDGE_COVERAGE_LOW",
        WARN,
        "Art must bleed but at least one edge band has a non-background fraction "
        "below `edge_coverage_min`.",
    ),
    Reason(
        "SAFE_MARGIN_VIOLATION",
        WARN,
        "Art does not bleed and the content box extends outside the safe area "
        "(inset `bleed_in + safe_margin_in` from each image edge).",
    ),
    Reason(
        "OFF_CENTER",
        WARN,
        "The content box centre is offset from the image centre by more than "
        "`centering_tolerance_in` on at least one axis.",
    ),
)

BY_CODE: dict[str, Reason] = {r.code: r for r in REASONS}
_ORDER: dict[str, int] = {r.code: i for i, r in enumerate(REASONS)}


def sort_codes(codes: set[str] | list[str]) -> list[str]:
    """Return ``codes`` in canonical evaluation order."""
    return sorted(set(codes), key=_ORDER.__getitem__)


def status_for(codes: list[str]) -> str:
    severities = {BY_CODE[c].severity for c in codes}
    if FAIL in severities:
        return "fail"
    if WARN in severities:
        return "warn"
    return "pass"


def markdown_table() -> str:
    """Render the README reason-code table."""
    lines = [
        "| Code | Severity | Meaning |",
        "| --- | --- | --- |",
    ]
    for r in REASONS:
        lines.append(f"| `{r.code}` | {r.severity} | {r.summary} |")
    return "\n".join(lines) + "\n"
