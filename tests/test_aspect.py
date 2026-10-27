"""T2: aspect ratio, tolerance boundaries and property tests."""

from fractions import Fraction

import pytest
from hypothesis import assume, example, given, settings
from hypothesis import strategies as st
from PIL import Image

from print_preflight import Profile, analyze
from print_preflight.checks import aspect_delta, aspect_reasons, ceil_dp, target_aspect

BASE = {
    "print_width_in": 4, "print_height_in": 3, "dpi_target": 1, "dpi_warn": 1,
    "bleed_in": 0.25, "safe_margin_in": 0, "aspect_tolerance": 0.01, "edge_coverage_min": 0,
}


def profile(**overrides) -> Profile:
    return Profile.from_dict({**BASE, **overrides})


# Decimal inches with up to 3 places, like real-world profile files.
inches = st.integers(min_value=500, max_value=40000).map(lambda n: Fraction(n, 1000))
bleeds = st.integers(min_value=0, max_value=250).map(lambda n: Fraction(n, 1000))
# Tolerances on a 6-decimal grid, the precision aspect_delta is reported at.
tolerances = st.integers(min_value=0, max_value=200_000).map(lambda n: Fraction(n, 1_000_000))
pixels = st.integers(min_value=1, max_value=20000)


def make_profile(w, h, b, tol) -> Profile:
    return Profile.from_dict({**BASE, "print_width_in": w, "print_height_in": h,
                              "bleed_in": b, "safe_margin_in": 0, "aspect_tolerance": tol})


# --- unit cases ----------------------------------------------------------------

def test_target_aspect_includes_bleed():
    assert target_aspect(profile()) == Fraction(9, 7)  # 4.5 x 3.5 canvas


def test_exact_match_has_zero_delta():
    assert aspect_delta(540, 420, profile()) == 0
    assert aspect_reasons(540, 420, profile()) == []


def test_mismatch_and_rotated_codes():
    p = profile()
    assert aspect_reasons(400, 300, p) == ["ASPECT_MISMATCH"]
    assert aspect_reasons(420, 540, p) == ["ASPECT_ROTATED"]


def test_square_target_never_reports_rotated():
    p = profile(print_width_in=3, print_height_in=3)
    assert aspect_reasons(100, 100, p) == []
    assert aspect_reasons(100, 120, p) == ["ASPECT_MISMATCH"]


def test_tolerance_boundary_is_inclusive():
    # 909 x 700 vs 9:7 is exactly 1% wide.
    p = profile()
    d = aspect_delta(909, 700, p)
    assert d == Fraction(909, 700) / Fraction(9, 7) - 1 == Fraction(1, 100)
    assert aspect_reasons(909, 700, profile(aspect_tolerance=0.01)) == []
    assert aspect_reasons(909, 700, profile(aspect_tolerance=0.009999)) == ["ASPECT_MISMATCH"]


def test_float_tolerance_is_decimal_exact():
    # 0.01 as a binary float is slightly above 1/100; the profile must treat it
    # as exactly 1/100 whether it came from JSON text or a Python float.
    assert profile(aspect_tolerance=0.01).aspect_tolerance == Fraction(1, 100)


def test_zero_tolerance_requires_exact_ratio():
    p = profile(aspect_tolerance=0)
    assert aspect_reasons(1080, 840, p) == []
    assert aspect_reasons(1081, 840, p) == ["ASPECT_MISMATCH"]


def test_report_aspect_delta_rounds_up():
    report = analyze(Image.new("RGB", (460, 358), "navy"), profile(dpi_target=1, dpi_warn=1))
    exact = aspect_delta(460, 358, profile())
    assert report["aspect_delta"] == ceil_dp(exact, 6) == 0.000621
    assert report["aspect_delta"] >= float(exact)


# --- properties ----------------------------------------------------------------

@given(inches, inches, bleeds, pixels, pixels, st.integers(min_value=1, max_value=50))
def test_delta_is_scale_invariant(w, h, b, pw, ph, k):
    p = make_profile(w, h, b, 0)
    assert aspect_delta(pw, ph, p) == aspect_delta(pw * k, ph * k, p)


@given(inches, inches, bleeds, pixels, pixels, tolerances)
def test_reason_matches_exact_comparison(w, h, b, pw, ph, tol):
    p = make_profile(w, h, b, tol)
    exact = abs(Fraction(pw, ph) / ((w + 2 * b) / (h + 2 * b)) - 1)
    assert aspect_delta(pw, ph, p) == exact
    assert (aspect_reasons(pw, ph, p) == []) == (exact <= tol)


@given(inches, inches, bleeds, pixels, pixels)
def test_tolerance_equal_to_delta_passes_and_just_below_fails(w, h, b, pw, ph):
    d = aspect_delta(pw, ph, make_profile(w, h, b, 0))
    assume(d > 0)
    assert aspect_reasons(pw, ph, make_profile(w, h, b, d)) == []
    below = aspect_reasons(pw, ph, make_profile(w, h, b, d - Fraction(1, 10**12)))
    assert below in (["ASPECT_MISMATCH"], ["ASPECT_ROTATED"])


@given(inches, inches, bleeds, pixels, pixels, tolerances)
def test_reported_delta_agrees_with_verdict(w, h, b, pw, ph, tol):
    # Rounding up to 6 dp means the displayed delta is <= tolerance exactly
    # when the check passes (tolerances are on the 6 dp grid).
    p = make_profile(w, h, b, tol)
    shown = Fraction(repr(ceil_dp(aspect_delta(pw, ph, p), 6)))
    assert (shown <= tol) == (aspect_reasons(pw, ph, p) == [])


@given(inches, inches, bleeds, st.integers(min_value=50, max_value=600))
@example(Fraction(4), Fraction(3), Fraction(1, 4), 120)
def test_image_rendered_at_any_dpi_matches(w, h, b, dpi):
    # Rounding the ideal pixel size to whole pixels stays within half a pixel
    # per axis, so an image this large is always within a 1% tolerance.
    p = make_profile(w, h, b, 0)
    pw = round(p.canvas_width_in * dpi)
    ph = round(p.canvas_height_in * dpi)
    assume(min(pw, ph) >= 200)
    assert aspect_delta(pw, ph, p) <= Fraction(1, 100)


@given(inches, inches, bleeds, st.integers(min_value=50, max_value=600), tolerances)
def test_rotated_is_symmetric(w, h, b, dpi, tol):
    # An image that passes, once rotated, is either still passing (near-square)
    # or reported as ASPECT_ROTATED - never as a plain mismatch.
    p = make_profile(w, h, b, tol)
    pw = max(1, round(p.canvas_width_in * dpi))
    ph = max(1, round(p.canvas_height_in * dpi))
    assume(aspect_reasons(pw, ph, p) == [])
    assert aspect_reasons(ph, pw, p) in ([], ["ASPECT_ROTATED"])


@settings(max_examples=30, deadline=None)
@given(st.integers(min_value=20, max_value=120), st.integers(min_value=20, max_value=120), tolerances)
def test_report_reasons_match_pure_check(pw, ph, tol):
    p = profile(aspect_tolerance=tol)
    report = analyze(Image.new("RGB", (pw, ph), "navy"), p)
    aspect_codes = [r for r in report["reasons"] if r.startswith("ASPECT_")]
    assert aspect_codes == aspect_reasons(pw, ph, p)


@pytest.mark.parametrize("tol", [-0.1, float("nan"), "0.01", True])
def test_invalid_tolerance_rejected(tol):
    from print_preflight import PreflightError
    with pytest.raises(PreflightError) as exc:
        profile(aspect_tolerance=tol)
    assert exc.value.code == "PROFILE_INVALID"
