import math
from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from print_preflight.dpi import (
    DPI_BELOW_TARGET,
    DPI_BELOW_WARN,
    check_dpi,
    effective_dpi,
    required_pixels,
)
from print_preflight.profile import Profile, exact

PROFILE = Profile.from_dict(
    {
        "print_width_in": 2,
        "print_height_in": 3,
        "dpi_target": 100,
        "dpi_warn": 150,
        "bleed_in": 0.125,
        "safe_margin_in": 0.125,
        "aspect_tolerance": 0.01,
        "edge_coverage_min": 0.98,
    }
)


def make_profile(width, height, target, warn, bleed=0):
    return Profile.from_dict(
        {
            "print_width_in": width,
            "print_height_in": height,
            "dpi_target": target,
            "dpi_warn": warn,
            "bleed_in": bleed,
            "safe_margin_in": 0,
            "aspect_tolerance": 0,
            "edge_coverage_min": 0,
        }
    )


def test_canvas_includes_bleed_on_both_sides():
    assert PROFILE.canvas_width_in == Fraction(9, 4)
    assert PROFILE.canvas_height_in == Fraction(13, 4)


def test_required_pixels_rounds_up():
    assert required_pixels(Fraction(9, 4), 100) == 225
    assert required_pixels(Fraction(9, 4), 150) == 338  # 337.5 -> 338
    assert required_pixels(Fraction(13, 4), 150) == 488  # 487.5 -> 488


def test_required_pixels_is_exact_for_decimal_inputs():
    # 8.5 * 300 in binary floats is not exactly 2550; must not round up to 2551.
    assert required_pixels(exact(8.5), 300) == 2550
    # 0.1 * 3 == 0.30000000000000004 in floats.
    assert required_pixels(exact(0.1) * 3, 10) == 3


@pytest.mark.parametrize(
    "size, status, reasons",
    [
        ((338, 488), "pass", ()),
        ((337, 488), "warn", (DPI_BELOW_WARN,)),
        ((338, 487), "warn", (DPI_BELOW_WARN,)),
        ((225, 325), "warn", (DPI_BELOW_WARN,)),
        ((224, 325), "fail", (DPI_BELOW_TARGET,)),
        ((225, 324), "fail", (DPI_BELOW_TARGET,)),
        ((1, 1), "fail", (DPI_BELOW_TARGET,)),
        ((5000, 5000), "pass", ()),
    ],
)
def test_check_dpi_boundaries(size, status, reasons):
    result = check_dpi(*size, PROFILE)
    assert result.status == status
    assert result.reasons == reasons


def test_effective_dpi_is_limiting_axis():
    # 450 / 2.25 = 200 horizontally, 488 / 3.25 = 150.15... vertically.
    assert effective_dpi(450, 488, PROFILE) == Fraction(488) / Fraction(13, 4)


def test_equal_target_and_warn_never_warns():
    profile = make_profile(1, 1, 300, 300)
    assert check_dpi(300, 300, profile).status == "pass"
    assert check_dpi(299, 300, profile).status == "fail"


# --- property tests on rounding boundaries -----------------------------------

inches = st.decimals(min_value="0.25", max_value="60", places=3).map(float)
dpis = st.integers(min_value=1, max_value=1200) | st.decimals(
    min_value="1", max_value="1200", places=2
).map(float)
bleeds = st.decimals(min_value="0", max_value="1", places=3).map(float)


@settings(max_examples=300, deadline=None)
@given(width=inches, height=inches, dpi=dpis, bleed=bleeds)
def test_exact_requirement_passes_one_less_fails(width, height, dpi, bleed):
    profile = make_profile(width, height, dpi, dpi, bleed)
    req_w = required_pixels(profile.canvas_width_in, dpi)
    req_h = required_pixels(profile.canvas_height_in, dpi)

    assert check_dpi(req_w, req_h, profile).status == "pass"
    assert effective_dpi(req_w, req_h, profile) >= exact(dpi)
    if req_w > 1:
        assert check_dpi(req_w - 1, req_h, profile).status == "fail"
        assert effective_dpi(req_w - 1, req_h, profile) < exact(dpi)
    if req_h > 1:
        assert check_dpi(req_w, req_h - 1, profile).status == "fail"


@settings(max_examples=300, deadline=None)
@given(width=inches, height=inches, dpi=dpis, bleed=bleeds)
def test_required_pixels_is_minimal_ceiling(width, height, dpi, bleed):
    canvas = exact(width) + 2 * exact(bleed)
    req = required_pixels(canvas, dpi)
    exact_px = canvas * exact(dpi)
    assert req >= exact_px > req - 1
    assert req == math.ceil(exact_px)


@settings(max_examples=300, deadline=None)
@given(
    width=inches,
    height=inches,
    target=st.integers(min_value=1, max_value=600),
    extra=st.integers(min_value=0, max_value=600),
    w_px=st.integers(min_value=1, max_value=50000),
    h_px=st.integers(min_value=1, max_value=50000),
)
def test_status_agrees_with_exact_effective_dpi(width, height, target, extra, w_px, h_px):
    warn = target + extra
    profile = make_profile(width, height, target, warn)
    eff = effective_dpi(w_px, h_px, profile)
    expected = "fail" if eff < target else "warn" if eff < warn else "pass"
    assert check_dpi(w_px, h_px, profile).status == expected


@settings(max_examples=100, deadline=None)
@given(w_px=st.integers(1, 20000), h_px=st.integers(1, 20000))
def test_check_dpi_is_deterministic(w_px, h_px):
    assert check_dpi(w_px, h_px, PROFILE) == check_dpi(w_px, h_px, PROFILE)
