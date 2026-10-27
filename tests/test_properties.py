"""Property tests on DPI and aspect rounding boundaries."""

from __future__ import annotations

import math
from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import Image

from print_preflight import Profile, check_image
from print_preflight.analysis import aspect_delta_exact, floor_places, required_pixels

PROPS = settings(derandomize=True, deadline=None, max_examples=150)

# Decimal values with up to 3 places, as they would appear in a JSON profile.
inches = st.integers(min_value=50, max_value=2500).map(lambda n: Fraction(n, 1000))
small_inches = st.integers(min_value=100, max_value=1500).map(lambda n: Fraction(n, 1000))
dpis = st.integers(min_value=1000, max_value=60000).map(lambda n: Fraction(n, 100))
small_dpis = st.integers(min_value=1000, max_value=12000).map(lambda n: Fraction(n, 100))
tolerances = st.integers(min_value=0, max_value=200).map(lambda n: Fraction(n, 1000))


def make_profile(w_in, h_in, dpi_target, dpi_warn=None, bleed=Fraction(0), tol=Fraction(1, 100)) -> Profile:
    return Profile.from_dict(
        {
            "print_width_in": float(w_in),
            "print_height_in": float(h_in),
            "dpi_target": float(dpi_target),
            "dpi_warn": float(dpi_warn if dpi_warn is not None else dpi_target),
            "bleed_in": float(bleed),
            "safe_margin_in": 0,
            "aspect_tolerance": float(tol),
            "edge_coverage_min": 0,
        }
    )


@PROPS
@given(inches, dpis)
def test_required_pixels_is_tight_lower_bound(length, dpi):
    px = required_pixels(length, dpi)
    assert Fraction(px) / length >= dpi
    assert Fraction(px - 1) / length < dpi


@PROPS
@given(st.floats(min_value=0.05, max_value=40, allow_nan=False), st.floats(min_value=10, max_value=1200))
def test_profile_floats_parse_as_their_decimal_text(w_in, dpi):
    profile = make_profile(w_in, 1, dpi)
    assert profile.print_width_in == Fraction(repr(w_in))
    assert profile.dpi_target == Fraction(repr(dpi))


@PROPS
@given(small_inches, small_inches, small_dpis, st.integers(min_value=0, max_value=3).map(lambda n: Fraction(n, 40)))
def test_dpi_boundary_end_to_end(w_in, h_in, dpi, bleed):
    profile = make_profile(w_in, h_in, dpi, bleed=bleed, tol=Fraction(1, 2))
    req_w = required_pixels(profile.bleed_width_in, dpi)
    req_h = required_pixels(profile.bleed_height_in, dpi)

    at = check_image(Image.new("RGB", (req_w, req_h), (0, 0, 0)), profile)
    assert "DPI_BELOW_TARGET" not in at["reasons"]
    assert at["required_px"]["target"] == {"width": req_w, "height": req_h}
    # Reported DPI is floored, so it never overstates and a pass never shows < target.
    assert at["effective_dpi"] >= float(dpi)

    for size in ((req_w - 1, req_h), (req_w, req_h - 1)):
        if min(size) < 1:
            continue
        below = check_image(Image.new("RGB", size, (0, 0, 0)), profile)
        assert "DPI_BELOW_TARGET" in below["reasons"]
        assert below["status"] == "fail"
        assert below["effective_dpi"] < float(dpi)


@PROPS
@given(st.integers(min_value=1, max_value=20000), st.integers(min_value=1, max_value=20000), inches, inches)
def test_effective_dpi_floor_never_overstates(w_px, h_px, w_in, h_in):
    profile = make_profile(w_in, h_in, 1)
    exact = min(Fraction(w_px) / w_in, Fraction(h_px) / h_in)
    shown = floor_places(exact, 2)
    shown_exact = Fraction(repr(shown))
    assert shown_exact <= exact < shown_exact + Fraction(1, 100)
    # A target with two decimal places is met iff the displayed value meets it.
    k = math.floor(exact * 100)
    for target in (Fraction(k - 1, 100), Fraction(k, 100), Fraction(k + 1, 100)):
        assert (shown_exact >= target) == (exact >= target)


@PROPS
@given(st.integers(min_value=10, max_value=5000), inches, inches, tolerances)
def test_aspect_tolerance_boundary(width_px, w_in, h_in, tol):
    profile = make_profile(w_in, h_in, 1, tol=tol)
    target = profile.bleed_width_in / profile.bleed_height_in
    # delta <= tol  <=>  w / (A (1 + tol)) <= h <= w / (A (1 - tol))
    h_min = max(1, math.ceil(width_px / (target * (1 + tol))))
    h_max = math.floor(width_px / (target * (1 - tol)))
    if h_min <= h_max:
        assert aspect_delta_exact(width_px, h_min, profile) <= tol
        assert aspect_delta_exact(width_px, h_max, profile) <= tol
    assert aspect_delta_exact(width_px, h_max + 1, profile) > tol
    if h_min > 1:
        assert aspect_delta_exact(width_px, h_min - 1, profile) > tol


@PROPS
@given(st.integers(min_value=20, max_value=300), small_inches, small_inches, tolerances)
def test_aspect_boundary_end_to_end(width_px, w_in, h_in, tol):
    profile = make_profile(w_in, h_in, Fraction(1, 100), tol=tol)
    target = profile.bleed_width_in / profile.bleed_height_in
    h_max = math.floor(width_px / (target * (1 - tol)))
    if not 1 <= h_max <= 2000:
        return
    inside = check_image(Image.new("RGB", (width_px, h_max), (0, 0, 0)), profile)
    outside = check_image(Image.new("RGB", (width_px, h_max + 1), (0, 0, 0)), profile)
    in_delta = aspect_delta_exact(width_px, h_max, profile)
    assert ("ASPECT_MISMATCH" in inside["reasons"]) is (in_delta > tol)
    assert "ASPECT_MISMATCH" in outside["reasons"]
    assert outside["status"] == "fail"
    assert inside["aspect_delta"] == float(round(in_delta, 6))
