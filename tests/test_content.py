"""T3: content bounding box, edge coverage, safe-margin coverage and centering."""

from __future__ import annotations

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import Image, ImageDraw

from print_preflight import check
from print_preflight.content import band_px, content_mask, measure

WHITE = (255, 255, 255)

# 1 x 1 in canvas, no bleed: 100 x 100 px is exactly dpi_target.
FLAT = {
    "print_width_in": 1, "print_height_in": 1, "dpi_target": 100, "dpi_warn": 100,
    "bleed_in": 0, "safe_margin_in": 0.1, "aspect_tolerance": 0, "edge_coverage_min": 1,
    "centering_tolerance_in": 0.05,
}
# 0.8 x 0.8 in trim + 0.1 in bleed = 1 x 1 in canvas; bleed band = 10 px.
BLEED = dict(FLAT, print_width_in=0.8, print_height_in=0.8, bleed_in=0.1,
             safe_margin_in=0, edge_coverage_min=0.9)


def canvas(box=None, size=(100, 100), fill=(0, 0, 0)):
    img = Image.new("RGB", size, WHITE)
    if box is not None:
        ImageDraw.Draw(img).rectangle((box[0], box[1], box[2] - 1, box[3] - 1), fill=fill)
    return img


def mask_of(img, tol=16, alpha=0):
    return content_mask(img, WHITE, tol, alpha)


# --- content mask -----------------------------------------------------------

def test_background_tolerance_is_exclusive():
    img = Image.new("RGB", (4, 1), WHITE)
    img.putpixel((0, 0), (239, 255, 255))  # diff 16 == tol -> background
    img.putpixel((1, 0), (238, 255, 255))  # diff 17 -> content
    img.putpixel((2, 0), (255, 255, 200))  # any channel counts
    m = mask_of(img)
    assert [m.getpixel((x, 0)) for x in range(4)] == [0, 255, 255, 0]


def test_alpha_threshold_and_transparent_ink():
    img = Image.new("RGBA", (4, 1), (0, 0, 0, 0))  # transparent black: not content
    img.putpixel((1, 0), (0, 0, 0, 10))
    img.putpixel((2, 0), (0, 0, 0, 11))
    img.putpixel((3, 0), (255, 255, 255, 255))  # opaque paper: not content
    m = mask_of(img, alpha=10)
    assert [m.getpixel((x, 0)) for x in range(4)] == [0, 0, 255, 0]


def test_custom_background_colour():
    img = Image.new("RGB", (10, 10), (0, 0, 0))
    img.putpixel((3, 4), WHITE)
    assert content_mask(img, (0, 0, 0), 0, 0).getbbox() == (3, 4, 4, 5)


def test_palette_image_with_transparency(tmp_path):
    img = Image.new("P", (10, 10), 0)
    img.putpalette([0, 0, 0, 255, 0, 0] + [0] * 762)
    img.info["transparency"] = 0
    ImageDraw.Draw(img).rectangle((2, 2, 7, 7), fill=1)
    path = tmp_path / "p.png"
    img.save(path, transparency=0)
    report = check(path, dict(FLAT, print_width_in=0.1, print_height_in=0.1, safe_margin_in=0))
    assert report["coverage_ratio"] == 0.36
    assert report["centering_delta_px"] == {"x": 0.0, "y": 0.0}


# --- geometry ---------------------------------------------------------------

def test_bbox_coverage_and_centering_exact():
    geo = measure(mask_of(canvas((10, 20, 41, 60))), 1, 1)
    assert geo.bbox == (10, 20, 41, 60)
    assert geo.coverage_ratio == Fraction(31 * 40, 100 * 100)
    assert geo.centering_delta_px == (Fraction(-49, 2), Fraction(-10))
    assert not geo.full_bleed


def test_bbox_spans_disjoint_marks():
    img = canvas((5, 5, 6, 6))
    ImageDraw.Draw(img).point((90, 70), fill=(0, 0, 0))
    geo = measure(mask_of(img), 1, 1)
    assert geo.bbox == (5, 5, 91, 71)


def test_empty_mask():
    geo = measure(mask_of(canvas()), 3, 3)
    assert geo.bbox is None and geo.centering_delta_px is None
    assert geo.coverage_ratio == 0
    assert set(geo.edge_coverage.values()) == {0}


def test_edge_bands_measured_independently():
    # Ink fills the left 10 px column and half of the top 10 px band.
    img = canvas((0, 0, 10, 100))
    ImageDraw.Draw(img).rectangle((0, 0, 49, 9), fill=(0, 0, 0))
    geo = measure(mask_of(img), 10, 10)
    assert geo.edge_coverage == {
        "top": Fraction(1, 2), "right": Fraction(0), "bottom": Fraction(1, 10), "left": Fraction(1),
    }


def test_band_px_rounds_up_and_clamps():
    assert band_px(Fraction(1, 10), Fraction(100), 50) == 10
    assert band_px(Fraction(1, 10), Fraction(101), 50) == 11
    assert band_px(Fraction(0), Fraction(100), 50) == 1
    assert band_px(Fraction(5), Fraction(100), 50) == 50


@settings(max_examples=60, deadline=None)
@given(st.integers(1, 40), st.integers(1, 30), st.integers(0, 39), st.integers(0, 29))
def test_rectangle_geometry_property(bw, bh, x0, y0):
    w, h = 40, 30
    x1, y1 = min(w, x0 + bw), min(h, y0 + bh)
    geo = measure(mask_of(canvas((x0, y0, x1, y1), size=(w, h))), 1, 1)
    assert geo.bbox == (x0, y0, x1, y1)
    assert geo.coverage_ratio == Fraction((x1 - x0) * (y1 - y0), w * h)
    assert geo.centering_delta_px == (Fraction(x0 + x1 - w, 2), Fraction(y0 + y1 - h, 2))
    assert geo.full_bleed == ((x0, y0, x1, y1) == (0, 0, w, h))


# --- checks wired into the report ------------------------------------------

def test_safe_margin_boundary_is_inclusive():
    # safe inset = 0.1 in * 100 ppi = 10 px.
    assert check(canvas((10, 10, 90, 90)), FLAT)["reasons"] == []
    assert check(canvas((9, 10, 90, 90)), FLAT)["reasons"] == ["CONTENT_OUTSIDE_SAFE"]
    assert check(canvas((10, 10, 90, 91)), FLAT)["reasons"] == ["CONTENT_OUTSIDE_SAFE"]


def test_safe_margin_skipped_for_full_bleed():
    report = check(canvas((0, 0, 100, 100)), FLAT)
    assert report["status"] == "pass" and report["coverage_ratio"] == 1.0


def test_safe_margin_counts_bleed_plus_margin():
    prof = dict(BLEED, safe_margin_in=0.05, edge_coverage_min=0)  # inset 15 px
    assert check(canvas((15, 15, 85, 85)), prof)["reasons"] == []
    assert check(canvas((14, 15, 85, 85)), prof)["reasons"] == ["CONTENT_OUTSIDE_SAFE"]


def test_centering_tolerance_boundary():
    # tolerance = 0.05 in * 100 ppi = 5 px; box 60 wide, shifted by 2*d px.
    assert check(canvas((25, 20, 85, 80)), FLAT)["centering_delta_px"] == {"x": 5.0, "y": 0.0}
    assert "OFF_CENTER" not in check(canvas((25, 20, 85, 80)), FLAT)["reasons"]
    shifted = check(canvas((26, 20, 85, 80)), FLAT)
    assert shifted["centering_delta_px"] == {"x": 5.5, "y": 0.0}
    assert shifted["reasons"] == ["OFF_CENTER"]
    up = check(canvas((20, 14, 80, 74)), FLAT)
    assert up["centering_delta_px"] == {"x": 0.0, "y": -6.0}
    assert up["reasons"] == ["OFF_CENTER"]


def test_edge_coverage_only_checked_when_bleeding():
    art = canvas((0, 0, 100, 95))  # bottom 5 px blank
    assert check(art, FLAT)["status"] != "fail"
    report = check(art, BLEED)
    assert report["edge_coverage"] == {"top": 1.0, "right": 0.95, "bottom": 0.5, "left": 0.95}
    assert report["reasons"] == ["EDGE_COVERAGE_LOW", "CONTENT_OUTSIDE_SAFE"]


def test_edge_coverage_min_boundary_is_inclusive():
    art = canvas((0, 0, 100, 100))
    ImageDraw.Draw(art).rectangle((0, 0, 9, 0), fill=WHITE)  # 10 of 1000 top-band px
    report = check(art, dict(BLEED, edge_coverage_min=0.99))
    assert report["edge_coverage"]["top"] == 0.99
    assert report["reasons"] == []
    assert check(art, dict(BLEED, edge_coverage_min=0.9901))["reasons"] == ["EDGE_COVERAGE_LOW"]


def test_reported_coverage_never_overstates():
    # 1/3 coverage must be reported as 0.3333, never 0.3334.
    report = check(canvas((0, 0, 100, 100), size=(300, 100)),
                   dict(FLAT, print_width_in=3, aspect_tolerance=0))
    assert report["coverage_ratio"] == 0.3333
