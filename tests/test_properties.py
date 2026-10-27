"""Property tests on the DPI and aspect rounding boundaries.

Thresholds are compared with exact rational arithmetic, so a pixel count
exactly at the boundary must pass and one pixel short must not, for any
decimal profile values.
"""

import math
from decimal import Decimal
from fractions import Fraction

from hypothesis import example, given
from hypothesis import strategies as st

from print_preflight.core import aspect_delta, aspect_reasons, effective_dpi, required_pixels, resolution_reasons
from print_preflight.profile import Profile

inches = st.decimals(min_value=Decimal("0.5"), max_value=Decimal("40"), places=3)
dpis = st.decimals(min_value=Decimal("1"), max_value=Decimal("1200"), places=2)
bleeds = st.decimals(min_value=Decimal("0"), max_value=Decimal("0.25"), places=3)


def make_profile(w, h, dpi_target, dpi_warn=None, bleed=0, tol=Decimal("0.01")):
    return Profile.from_dict(
        {
            "print_width_in": float(w),
            "print_height_in": float(h),
            "dpi_target": float(dpi_target),
            "dpi_warn": float(dpi_warn if dpi_warn is not None else dpi_target),
            "bleed_in": float(bleed),
            "safe_margin_in": 0,
            "aspect_tolerance": float(tol),
            "edge_coverage_min": 0,
        }
    )


@given(w=inches, h=inches, dpi=dpis, bleed=bleeds)
@example(w=Decimal("0.07"), h=Decimal("1"), dpi=Decimal("100"), bleed=Decimal("0"))  # 0.07*100 is 7.000000000000001 in floats
def test_dpi_exact_boundary(w, h, dpi, bleed):
    profile = make_profile(w, h, dpi, bleed=bleed)
    cw = Fraction(w) + 2 * Fraction(bleed)
    ch = Fraction(h) + 2 * Fraction(bleed)
    rw = math.ceil(cw * Fraction(dpi))
    rh = math.ceil(ch * Fraction(dpi))
    assert (required_pixels(profile.canvas_width_in, profile.dpi_target), required_pixels(profile.canvas_height_in, profile.dpi_target)) == (rw, rh)

    assert resolution_reasons(rw, rh, profile) == []
    assert effective_dpi(rw, rh, profile) >= Fraction(dpi)
    if rw > 1:
        assert resolution_reasons(rw - 1, rh, profile) == ["DPI_BELOW_TARGET"]
    if rh > 1:
        assert resolution_reasons(rw, rh - 1, profile) == ["DPI_BELOW_TARGET"]


@given(w=inches, h=inches, target=dpis, extra=st.decimals(min_value=Decimal("0"), max_value=Decimal("300"), places=2))
def test_dpi_warn_band(w, h, target, extra):
    warn = target + extra
    profile = make_profile(w, h, target, dpi_warn=warn)
    tw, th = (required_pixels(profile.canvas_width_in, profile.dpi_target), required_pixels(profile.canvas_height_in, profile.dpi_target))
    ww, wh = (required_pixels(profile.canvas_width_in, profile.dpi_warn), required_pixels(profile.canvas_height_in, profile.dpi_warn))
    assert resolution_reasons(ww, wh, profile) == []
    if (tw, th) != (ww, wh):
        assert resolution_reasons(tw, th, profile) == ["DPI_BELOW_WARN"]


@given(w=inches, h=inches, dpi=dpis, px_w=st.integers(1, 50000), px_h=st.integers(1, 50000))
def test_dpi_decision_matches_integer_oracle(w, h, dpi, px_w, px_h):
    profile = make_profile(w, h, dpi)
    # px / inches >= dpi  <=>  px * 1000 * 100 >= inches_milli * dpi_centi
    w_milli, h_milli, dpi_centi = int(w * 1000), int(h * 1000), int(dpi * 100)
    ok = px_w * 100_000 >= w_milli * dpi_centi and px_h * 100_000 >= h_milli * dpi_centi
    assert (resolution_reasons(px_w, px_h, profile) == []) == ok


@given(
    p=st.integers(1, 40),
    q=st.integers(1, 40),
    t=st.integers(0, 200),
    k=st.integers(1, 5),
)
@example(p=2, q=1, t=10, k=1)  # 2020x1000 vs 2:1 at 1%: 2.02/2 - 1 is 0.010000000000000009 in floats
def test_aspect_exact_boundary(p, q, t, k):
    tol = Decimal(t) / 1000
    profile = make_profile(Decimal(p), Decimal(q), 1, tol=tol)
    h = q * 1000 * k
    w = p * (1000 + t) * k  # aspect delta is exactly t/1000
    assert aspect_delta(w, h, profile) == Fraction(t, 1000)
    assert aspect_reasons(w, h, profile) == []
    assert aspect_reasons(w + 1, h, profile) == ["ASPECT_MISMATCH"]
    if t > 0:
        lo = p * (1000 - t) * k  # delta exactly t/1000 on the narrow side
        assert aspect_reasons(lo, h, profile) == []
        assert aspect_reasons(lo - 1, h, profile) == ["ASPECT_MISMATCH"]


@given(
    w=inches,
    h=inches,
    tol=st.decimals(min_value=Decimal("0"), max_value=Decimal("0.2"), places=4),
    px_w=st.integers(1, 20000),
    px_h=st.integers(1, 20000),
    scale=st.integers(1, 4),
)
def test_aspect_decision_matches_cross_multiplication_and_is_scale_invariant(w, h, tol, px_w, px_h, scale):
    profile = make_profile(w, h, 1, tol=tol)
    cw, ch, t = Fraction(w), Fraction(h), Fraction(tol)
    ok = abs(px_w * ch - px_h * cw) <= t * px_h * cw
    assert (aspect_reasons(px_w, px_h, profile) == []) == ok
    assert aspect_reasons(px_w * scale, px_h * scale, profile) == aspect_reasons(px_w, px_h, profile)
