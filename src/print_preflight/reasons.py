"""Reason codes emitted in reports. Every code here is documented in README.md."""

from __future__ import annotations

FAIL = "fail"
WARN = "warn"

# Ordered catalogue: reports list reasons in this order.
REASONS: dict[str, tuple[str, str]] = {
    "DPI_BELOW_TARGET": (FAIL, "Pixel dimensions are below those required at dpi_target."),
    "DPI_BELOW_WARN": (WARN, "Pixel dimensions meet dpi_target but are below those required at dpi_warn."),
    "ASPECT_MISMATCH": (FAIL, "Image aspect ratio differs from the bleed-box aspect by more than aspect_tolerance."),
    "CONTENT_EMPTY": (FAIL, "No non-transparent, non-background pixels were found."),
    "BLEED_MISSING": (FAIL, "require_bleed is set but content does not reach the bleed edge on at least one side."),
    "BLEED_SHORT": (WARN, "Content crosses the trim line but stops short of the bleed edge on at least one side."),
    "EDGE_COVERAGE_LOW": (WARN, "A side that must bleed has an edge band coverage below edge_coverage_min."),
    "SAFE_MARGIN_VIOLATION": (WARN, "Content stops inside the safe margin (between the trim line and the safe line)."),
    "OFF_CENTRE": (WARN, "The content box centre is offset from the image centre by more than centering_tolerance_in."),
}


def severity(code: str) -> str:
    return REASONS[code][0]


def ordered(codes: set[str]) -> list[str]:
    return [code for code in REASONS if code in codes]


def status_for(codes: set[str]) -> str:
    severities = {severity(code) for code in codes}
    if FAIL in severities:
        return "fail"
    if WARN in severities:
        return "warn"
    return "pass"
