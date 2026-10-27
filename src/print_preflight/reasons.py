"""Reason codes that can appear in a report's ``reasons`` list.

Every code here is documented in README.md; a test enforces that.
"""

FAIL = "fail"
WARN = "warn"

# code -> (severity, one-line description). Insertion order is the order in
# which codes appear in reports.
REASONS: dict[str, tuple[str, str]] = {
    "DPI_BELOW_TARGET": (FAIL, "effective DPI is below dpi_target"),
    "DPI_BELOW_WARN": (WARN, "effective DPI is at or above dpi_target but below dpi_warn"),
    "ASPECT_MISMATCH": (FAIL, "image aspect ratio differs from the bleed canvas by more than aspect_tolerance"),
    "ASPECT_ROTATED": (FAIL, "image aspect ratio matches the bleed canvas only when rotated 90 degrees"),
    "NO_CONTENT": (FAIL, "image contains no non-background pixels"),
    "BLEED_INCOMPLETE": (FAIL, "content crosses the trim line on a side but stops short of the bleed edge"),
    "SAFE_MARGIN_VIOLATION": (WARN, "non-bleeding content lies between the trim line and the safe margin"),
    "EDGE_COVERAGE_LOW": (WARN, "a bleeding edge band is less than edge_coverage_min non-background"),
    "OFF_CENTER": (WARN, "non-bleeding content box is off-centre by more than 1% of the image dimension"),
}


def severity(code: str) -> str:
    return REASONS[code][0]


def status_for(codes: list[str]) -> str:
    severities = {severity(c) for c in codes}
    if FAIL in severities:
        return "fail"
    if WARN in severities:
        return "warn"
    return "pass"
