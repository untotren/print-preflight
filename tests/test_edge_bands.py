"""T4: edge-coverage bands."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest
from PIL import Image, ImageDraw

from print_preflight import check_image
from print_preflight.analysis import content_mask, edge_bands, edge_coverage_exact

RED = (200, 30, 30)


def test_band_geometry():
    bands = edge_bands(340, 500, 10, 12)
    assert bands == {
        "top": (0, 0, 340, 12),
        "right": (330, 0, 340, 500),
        "bottom": (0, 488, 340, 500),
        "left": (0, 0, 10, 500),
    }


def test_zero_bleed_uses_one_pixel_band():
    bands = edge_bands(50, 40, 0, 0)
    assert bands["top"] == (0, 0, 50, 1)
    assert bands["left"] == (0, 0, 1, 40)


def test_band_clamped_to_image():
    bands = edge_bands(4, 3, 10, 10)
    assert all(box == (0, 0, 4, 3) for box in bands.values())


def test_coverage_counts_exactly():
    img = Image.new("RGB", (100, 50), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 24, 4], fill=RED)  # 25 of 100 columns in the 5-row top band
    draw.rectangle([95, 0, 99, 9], fill=RED)  # 10 of 50 rows in the 5-col right band
    mask = content_mask(img.convert("RGBA"), (255, 255, 255), 8)
    cov = edge_coverage_exact(mask, edge_bands(100, 50, 5, 5))
    # top band: 25*5 from first rect + 5*5 overlap of the second rect
    assert cov["top"] == Fraction(25 * 5 + 5 * 5, 100 * 5)
    assert cov["right"] == Fraction(5 * 10, 5 * 50)
    assert cov["bottom"] == 0
    assert cov["left"] == Fraction(5 * 5, 5 * 50)


def test_transparent_pixels_are_not_coverage():
    img = Image.new("RGBA", (20, 20), RED + (0,))
    mask = content_mask(img, (255, 255, 255), 8)
    assert set(edge_coverage_exact(mask, edge_bands(20, 20, 2, 2)).values()) == {0}


def test_background_tolerance_applies_to_bands():
    img = Image.new("RGB", (20, 20), (250, 250, 250))  # near-white paper tone
    assert edge_coverage_exact(content_mask(img.convert("RGBA"), (255, 255, 255), 8), edge_bands(20, 20, 2, 2))[
        "top"
    ] == 0
    assert edge_coverage_exact(content_mask(img.convert("RGBA"), (255, 255, 255), 4), edge_bands(20, 20, 2, 2))[
        "top"
    ] == 1


def notched(width_white: int, rows_white: int) -> Image.Image:
    img = Image.new("RGB", (340, 500), RED)
    if rows_white:
        ImageDraw.Draw(img).rectangle([340 - width_white, 0, 339, rows_white - 1], fill=(255, 255, 255))
    return img


@pytest.mark.parametrize(
    "rows_white, expected_right, low",
    [
        (0, 1.0, False),
        (50, 0.94, False),  # 1 - 50*6/5000
        (84, 0.8992, True),  # just under 0.9 -> warn
        (83, 0.9004, False),  # just over 0.9 -> no warn
        (250, 0.7, True),
    ],
)
def test_edge_coverage_threshold(profile, rows_white, expected_right, low):
    report = check_image(notched(6, rows_white), profile)
    assert report["edge_coverage"]["right"] == expected_right
    assert ("EDGE_COVERAGE_LOW" in report["reasons"]) is low
    assert report["must_bleed"] == ["top", "right", "bottom", "left"]


def test_coverage_equal_to_minimum_passes(profile):
    # 6-col notch over 500/6 rows can't hit 0.9 exactly; use a 5-col notch: 1 - 100*5/5000 = 0.9
    report = check_image(notched(5, 100), profile)
    assert report["edge_coverage"]["right"] == 0.9
    assert report["status"] == "pass"


def test_only_bleeding_sides_are_checked(profile):
    # Art bleeds off the left edge only; the other edges are inside the safe area.
    img = Image.new("RGB", (340, 500), (255, 255, 255))
    ImageDraw.Draw(img).rectangle([0, 40, 299, 459], fill=RED)
    report = check_image(img, replace(profile, centering_tolerance_in=Fraction(10)))
    assert report["must_bleed"] == ["left"]
    assert report["edge_coverage"]["left"] == 0.84  # 420 of 500 rows
    assert report["reasons"] == ["EDGE_COVERAGE_LOW"]
    relaxed = check_image(img, replace(profile, centering_tolerance_in=Fraction(10), edge_coverage_min=Fraction("0.84")))
    assert relaxed["status"] == "pass"


def test_require_bleed_checks_every_side(profile):
    img = Image.new("RGB", (340, 500), (255, 255, 255))
    ImageDraw.Draw(img).rectangle([40, 40, 299, 459], fill=RED)
    report = check_image(img, replace(profile, require_bleed=True))
    assert report["must_bleed"] == ["top", "right", "bottom", "left"]
    assert report["reasons"] == ["BLEED_MISSING", "EDGE_COVERAGE_LOW"]
    assert report["status"] == "fail"


def test_band_width_follows_bleed_scale(profile):
    # 680 x 1000 px is 160 dpi: the 0.125 in bleed band is 20 px.
    report = check_image(Image.new("RGB", (680, 1000), RED), profile)
    assert report["edge_band_px"] == {"x": 20, "y": 20}
    no_bleed = check_image(Image.new("RGB", (320, 480), RED), replace(profile, bleed_in=Fraction(0)))
    assert no_bleed["edge_band_px"] == {"x": 1, "y": 1}
    assert no_bleed["status"] == "pass"
