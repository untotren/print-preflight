"""Resolution checks and rounding-boundary properties."""

import math
from fractions import Fraction

from hypothesis import given
from hypothesis import strategies as st

from print_preflight import Profile
from print_preflight.checks import dpi_reasons, effective_dpi, floor_dp, required_pixels

inches = st.integers(min_value=100, max_value=40000).map(lambda n: Fraction(n, 1000))
bleeds = st.integers(min_value=0, max_value=250).map(lambda n: Fraction(n, 1000))
# DPI thresholds with up to 2 decimals (the precision effective_dpi is shown at).
dpis = st.integers(min_value=7200, max_value=60000).map(lambda n: Fraction(n, 100))


def make_profile(w, h, b, target, warn) -> Profile:
    return Profile.from_dict({
        "print_width_in": w, "print_height_in": h, "dpi_target": target, "dpi_warn": warn,
        "bleed_in": b, "safe_margin_in": 0, "aspect_tolerance": 1, "edge_coverage_min": 0,
    })


def test_required_pixels_examples():
    assert required_pixels(Fraction("8.5"), Fraction(300)) == 2550
    assert required_pixels(Fraction("8.333"), Fraction(300)) == 2500  # 2499.9 -> 2500
    assert required_pixels(Fraction("0.1"), Fraction(30)) == 3  # no float drift


def test_effective_dpi_uses_limiting_axis():
    p = make_profile(4, 3, Fraction(1, 4), 100, 120)
    assert effective_dpi(540, 420, p) == 120
    assert effective_dpi(900, 420, p) == 120
    assert effective_dpi(540, 700, p) == 120


@given(inches, inches, bleeds, dpis, dpis)
def test_required_pixels_are_the_exact_boundary(w, h, b, d1, d2):
    target, warn = sorted((d1, d2))
    p = make_profile(w, h, b, target, warn)
    rw = required_pixels(p.canvas_width_in, target)
    rh = required_pixels(p.canvas_height_in, target)
    assert "DPI_BELOW_TARGET" not in dpi_reasons(rw, rh, p)
    assert dpi_reasons(rw - 1, rh, p) == ["DPI_BELOW_TARGET"] or rw == 1
    assert dpi_reasons(rw, rh - 1, p) == ["DPI_BELOW_TARGET"] or rh == 1

    ww = required_pixels(p.canvas_width_in, warn)
    wh = required_pixels(p.canvas_height_in, warn)
    assert dpi_reasons(ww, wh, p) == []
    if ww - 1 >= rw:
        assert dpi_reasons(ww - 1, wh, p) == ["DPI_BELOW_WARN"]


@given(inches, inches, bleeds, dpis, st.integers(min_value=1, max_value=30000),
       st.integers(min_value=1, max_value=30000))
def test_displayed_dpi_agrees_with_verdict(w, h, b, target, pw, ph):
    p = make_profile(w, h, b, target, target)
    shown = Fraction(repr(floor_dp(effective_dpi(pw, ph, p), 2)))
    failed = dpi_reasons(pw, ph, p) == ["DPI_BELOW_TARGET"]
    assert failed == (shown < target)


@given(inches, inches, bleeds, dpis)
def test_pixels_rendered_at_target_always_pass(w, h, b, target):
    p = make_profile(w, h, b, target, target)
    pw = math.ceil(p.canvas_width_in * target)
    ph = math.ceil(p.canvas_height_in * target)
    assert effective_dpi(pw, ph, p) >= target
    assert dpi_reasons(pw, ph, p) == []
