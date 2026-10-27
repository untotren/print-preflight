"""Hypothesis property tests on DPI and aspect rounding boundaries."""

from __future__ import annotations

import math
from fractions import Fraction

from hypothesis import assume, given, settings
from hypothesis import strategies as st
from PIL import Image

from print_preflight import check, profile_from_dict
from print_preflight.checks import aspect_delta, floor_to, required_pixels
from print_preflight.profile import exact

# Decimal inches with two places (e.g. 8.27) and dpi with up to one place.
inches = st.integers(50, 1200).map(lambda n: n / 100)
dpis = st.integers(500, 6000).map(lambda n: n / 10)


def profile(w_in, h_in, *, dpi_target=100, dpi_warn=100, bleed=0, tol=1.0):
    return profile_from_dict({
        "print_width_in": w_in, "print_height_in": h_in, "dpi_target": dpi_target,
        "dpi_warn": dpi_warn, "bleed_in": bleed, "safe_margin_in": 0,
        "aspect_tolerance": tol, "edge_coverage_min": 0,
    })


@given(inches, dpis)
def test_required_pixels_is_exact_ceiling(w_in, dpi):
    px = required_pixels(exact(w_in), dpi)
    exact_px = exact(w_in) * exact(dpi)
    assert px - 1 < exact_px <= px
    # Boundary: px reaches the dpi, px - 1 does not.
    assert Fraction(px) / exact(w_in) >= exact(dpi)
    assert Fraction(px - 1) / exact(w_in) < exact(dpi)


@given(inches, dpis)
def test_decimal_profile_values_are_not_binary_floats(w_in, dpi):
    # e.g. 0.29 * 100 = 28.999999999999996 in floats; we must say 29.
    if (exact(w_in) * exact(dpi)).denominator == 1:
        assert required_pixels(exact(w_in), dpi) == exact(w_in) * exact(dpi)


@settings(max_examples=40, deadline=None)
@given(st.integers(20, 120), st.integers(20, 120), st.integers(50, 400))
def test_dpi_target_boundary_in_report(w_hund, h_hund, dpi):
    w_in, h_in = w_hund / 100, h_hund / 100
    prof = profile(w_in, h_in, dpi_target=dpi, dpi_warn=dpi)
    w_px, h_px = required_pixels(prof.canvas_width_in, dpi), required_pixels(prof.canvas_height_in, dpi)
    assume(w_px <= 600 and h_px <= 600)

    ok = check(Image.new("RGB", (w_px, h_px), (0, 0, 0)), prof)
    assert "DPI_BELOW_TARGET" not in ok["reasons"]
    assert ok["effective_dpi"] >= dpi

    for short in ((w_px - 1, h_px), (w_px, h_px - 1)):
        bad = check(Image.new("RGB", short, (0, 0, 0)), prof)
        assert "DPI_BELOW_TARGET" in bad["reasons"]
        # Truncated reporting never shows a failing image as reaching target.
        assert bad["effective_dpi"] < dpi


@settings(max_examples=40, deadline=None)
@given(st.integers(20, 120), st.integers(20, 120), st.integers(100, 300), st.integers(1, 100))
def test_dpi_warn_band(w_hund, h_hund, target, extra):
    w_in, h_in = w_hund / 100, h_hund / 100
    warn = target + extra
    prof = profile(w_in, h_in, dpi_target=target, dpi_warn=warn)
    w_px, h_px = required_pixels(prof.canvas_width_in, warn), required_pixels(prof.canvas_height_in, warn)
    assume(w_px <= 600 and h_px <= 600)
    assert check(Image.new("RGB", (w_px, h_px), (0, 0, 0)), prof)["reasons"] == []
    tw, th = required_pixels(prof.canvas_width_in, target), required_pixels(prof.canvas_height_in, target)
    if (tw, th) != (w_px, h_px):
        mid = check(Image.new("RGB", (max(tw, w_px - 1), h_px), (0, 0, 0)), prof)
        if max(tw, w_px - 1) < w_px:
            assert mid["reasons"][:1] == ["DPI_BELOW_WARN"]


@given(st.fractions(min_value=0, max_value=10_000))
def test_floor_to_never_overstates(value):
    shown = floor_to(value, 2)
    assert Fraction(str(shown)) <= value < Fraction(str(shown)) + Fraction(1, 100)


@given(st.integers(1, 50), st.integers(1, 50), st.integers(1, 20))
def test_exact_aspect_is_zero_delta(a, b, k):
    prof = profile(a / 10, b / 10)
    # Image k*a x k*b has exactly the canvas aspect a:b.
    assert aspect_delta(k * a, k * b, prof) == 0


@settings(max_examples=60, deadline=None)
@given(st.integers(10, 400), st.integers(10, 400), st.integers(10, 400), st.integers(10, 400))
def test_aspect_tolerance_boundary_is_inclusive(w_px, h_px, w_hund, h_hund):
    prof = profile(w_hund / 100, h_hund / 100)
    delta = check(Image.new("RGB", (w_px, h_px), (0, 0, 0)), prof)["aspect_delta"]
    assert delta == float(round(aspect_delta(w_px, h_px, prof), 6))

    at = profile(w_hund / 100, h_hund / 100, tol=delta)
    assert "ASPECT_MISMATCH" not in check(Image.new("RGB", (w_px, h_px), (0, 0, 0)), at)["reasons"]
    if delta >= 1e-6:
        below = profile(w_hund / 100, h_hund / 100, tol=round(delta - 1e-6, 6))
        assert "ASPECT_MISMATCH" in check(Image.new("RGB", (w_px, h_px), (0, 0, 0)), below)["reasons"]


@given(st.integers(10, 400), st.integers(10, 400))
def test_aspect_delta_includes_bleed(w_px, h_px):
    # 2 x 1 trim with 0.5 bleed is a 3 x 2 canvas, not 2 x 1.
    prof = profile(2, 1, bleed=0.5)
    assert aspect_delta(w_px, h_px, prof) == abs(Fraction(w_px, h_px) / Fraction(3, 2) - 1)
    assert math.isclose(float(prof.canvas_width_in / prof.canvas_height_in), 1.5)
