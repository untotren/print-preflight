"""Property tests on the DPI and aspect rounding boundaries.

``derandomize=True`` and no example database keep every run identical.
"""

import math
from decimal import Decimal
from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from print_preflight import Profile, measure_resolution

SETTINGS = settings(derandomize=True, database=None, max_examples=300, deadline=None)


def decimals(lo: str, hi: str, places: int):
    return st.decimals(min_value=Decimal(lo), max_value=Decimal(hi), places=places, allow_nan=False, allow_infinity=False)


def make_profile(width, height, bleed, dpi_target, dpi_warn=None, aspect_tolerance=1.0):
    return Profile.from_dict(
        {
            "print_width_in": float(width),
            "print_height_in": float(height),
            "dpi_target": float(dpi_target),
            "dpi_warn": float(dpi_warn if dpi_warn is not None else dpi_target),
            "bleed_in": float(bleed),
            "safe_margin_in": 0,
            "aspect_tolerance": float(aspect_tolerance),
            "edge_coverage_min": 0,
        }
    )


def needed(inches: Decimal, bleed: Decimal, dpi: Decimal) -> int:
    return math.ceil(Fraction((inches + 2 * bleed) * dpi))


@SETTINGS
@given(
    width=decimals("0.5", "6", 3),
    height=decimals("0.5", "6", 3),
    bleed=decimals("0", "0.25", 3),
    dpi=decimals("50", "400", 2),
)
def test_dpi_boundary_is_exact(width, height, bleed, dpi):
    profile = make_profile(width, height, bleed, dpi)
    w, h = needed(width, bleed, dpi), needed(height, bleed, dpi)

    at = measure_resolution(w, h, profile)
    assert "DPI_BELOW_TARGET" not in at["reasons"]
    assert at["required_px"]["target"] == [w, h]
    assert at["effective_dpi"] >= float(dpi)

    for short in ((w - 1, h), (w, h - 1)):
        below = measure_resolution(*short, profile)
        assert "DPI_BELOW_TARGET" in below["reasons"]
        assert below["effective_dpi"] < float(dpi)


@SETTINGS
@given(
    width=decimals("0.5", "6", 3),
    height=decimals("0.5", "6", 3),
    bleed=decimals("0", "0.25", 3),
    dpi_target=decimals("50", "300", 2),
    extra=decimals("0", "150", 2),
    w=st.integers(1, 3000),
    h=st.integers(1, 3000),
)
def test_reported_dpi_agrees_with_reasons(width, height, bleed, dpi_target, extra, w, h):
    dpi_warn = dpi_target + extra
    profile = make_profile(width, height, bleed, dpi_target, dpi_warn)
    report = measure_resolution(w, h, profile)
    eff = report["effective_dpi"]
    below_target = "DPI_BELOW_TARGET" in report["reasons"]
    below_warn = "DPI_BELOW_WARN" in report["reasons"]
    assert below_target == (eff < float(dpi_target))
    assert below_warn == (not below_target and eff < float(dpi_warn))


@SETTINGS
@given(
    width=decimals("0.5", "6", 3),
    height=decimals("0.5", "6", 3),
    bleed=decimals("0", "0.25", 3),
    tol=decimals("0", "0.2", 6),
    w=st.integers(1, 3000),
    h=st.integers(1, 3000),
)
def test_reported_aspect_agrees_with_reasons(width, height, bleed, tol, w, h):
    profile = make_profile(width, height, bleed, 1, aspect_tolerance=tol)
    report = measure_resolution(w, h, profile)
    assert ("ASPECT_MISMATCH" in report["reasons"]) == (report["aspect_delta"] > float(tol))
    target = Fraction(width + 2 * bleed) / Fraction(height + 2 * bleed)
    assert abs(report["aspect_delta"] - float(abs(Fraction(w, h) / target - 1))) <= 1e-6


@SETTINGS
@given(
    h=st.sampled_from([100, 125, 200, 250, 400, 500, 625, 800, 1000, 1250, 2000, 2500]),
    k=st.integers(0, 50),
    side=decimals("0.5", "6", 3),
)
def test_aspect_tolerance_boundary_is_inclusive(h, k, side):
    # Square canvas; an image k px wider than tall has delta exactly k / h,
    # which has at most 4 decimal places for these heights.
    delta = Fraction(k, h)
    at = make_profile(side, side, 0, 1, aspect_tolerance=float(delta))
    assert "ASPECT_MISMATCH" not in measure_resolution(h + k, h, at)["reasons"]
    if k:
        under = make_profile(side, side, 0, 1, aspect_tolerance=float(delta - Fraction(1, 10**6)))
        assert "ASPECT_MISMATCH" in measure_resolution(h + k, h, under)["reasons"]


@SETTINGS
@given(w=st.integers(1, 2000), h=st.integers(1, 2000), bleed=decimals("0", "0.25", 3))
def test_matching_canvas_has_zero_delta(w, h, bleed):
    # Canvas of exactly (w x h) hundredths of an inch including bleed.
    width = Decimal(w) / 100 - 2 * bleed
    height = Decimal(h) / 100 - 2 * bleed
    if width <= 0 or height <= 0:
        return
    report = measure_resolution(w, h, make_profile(width, height, bleed, 1, aspect_tolerance=0))
    assert report["aspect_delta"] == 0.0
    assert "ASPECT_MISMATCH" not in report["reasons"]


@SETTINGS
@given(h=st.integers(1000, 10**6), k=st.integers(0, 10**4), side=decimals("0.5", "6", 3))
def test_aspect_just_above_tolerance(h, k, side):
    # Tolerance = the exact delta truncated to 6 decimals, so the delta is at
    # most 1e-6 above it. Round-to-nearest reporting would often show a value
    # equal to the tolerance while ASPECT_MISMATCH is raised.
    delta = Fraction(k, h)
    tol = Fraction(math.floor(delta * 10**6), 10**6)
    report = measure_resolution(h + k, h, make_profile(side, side, 0, 1, aspect_tolerance=float(tol)))
    mismatch = "ASPECT_MISMATCH" in report["reasons"]
    assert mismatch == (delta > tol)
    assert mismatch == (report["aspect_delta"] > float(tol))
