"""Bleed, safe-margin, edge-coverage and centering behaviour on synthetic images."""

from PIL import Image, ImageDraw

from print_preflight import analyze

PROFILE = {
    "print_width_in": 4, "print_height_in": 3, "dpi_target": 100, "dpi_warn": 120,
    "bleed_in": 0.25, "safe_margin_in": 0.25, "aspect_tolerance": 0.01, "edge_coverage_min": 0.9,
}
W, H = 540, 420  # 120 DPI: bleed line 30 px, safe line 60 px


def with_rect(box, mode="RGB", bg="white"):
    im = Image.new(mode, (W, H), bg)
    ImageDraw.Draw(im).rectangle((box[0], box[1], box[2] - 1, box[3] - 1), fill="navy")
    return im


def test_safe_line_boundary():
    assert analyze(with_rect((60, 60, W - 60, H - 60)), PROFILE)["reasons"] == []
    assert analyze(with_rect((59, 60, W - 59, H - 60)), PROFILE)["reasons"] == ["SAFE_MARGIN_VIOLATION"]


def test_bleed_line_boundary():
    # 30 px from the edge is exactly the trim line: not bleeding, but outside safe.
    assert analyze(with_rect((30, 60, W - 30, H - 60)), PROFILE)["reasons"] == ["SAFE_MARGIN_VIOLATION"]
    # 29 px: crosses the trim line, so must reach the edge.
    assert "BLEED_INCOMPLETE" in analyze(with_rect((29, 60, W - 29, H - 60)), PROFILE)["reasons"]


def test_partial_bleed_on_one_side_is_fine():
    report = analyze(with_rect((0, 60, W - 60, H - 60)), PROFILE)
    assert report["reasons"] == ["EDGE_COVERAGE_LOW"]  # left band only 300/420 covered
    # Bleeding left, top and bottom; the top/bottom bands are 480/540 covered.
    report = analyze(with_rect((0, 0, W - 60, H)), PROFILE)
    assert report["reasons"] == ["EDGE_COVERAGE_LOW"]
    assert report["edge_coverage"]["left"] == 1.0
    assert report["edge_coverage"]["top"] == 0.888888
    assert analyze(with_rect((0, 0, W - 60, H)), {**PROFILE, "edge_coverage_min": 0.8})["reasons"] == []


def test_transparency_is_background():
    report = analyze(with_rect((60, 60, W - 60, H - 60), mode="RGBA", bg=(0, 0, 0, 0)), PROFILE)
    assert report["reasons"] == []
    assert report["edge_coverage"] == {"top": 0.0, "right": 0.0, "bottom": 0.0, "left": 0.0}


def test_near_white_is_background():
    im = Image.new("RGB", (W, H), (251, 252, 250))
    assert analyze(im, PROFILE)["reasons"] == ["NO_CONTENT"]
    im = Image.new("RGB", (W, H), (249, 255, 255))
    assert analyze(im, PROFILE)["reasons"] == []


def test_centering_tolerance():
    # 1% of 540 = 5.4 px; shifting the box by 10 px moves its centre 5 px.
    off = analyze(with_rect((80, 70, W - 60, H - 70)), PROFILE)
    assert off["centering_delta_px"] == {"x": 10.0, "y": 0.0}
    assert off["reasons"] == ["OFF_CENTER"]
    ok = analyze(with_rect((75, 70, W - 65, H - 70)), PROFILE)
    assert ok["centering_delta_px"] == {"x": 5.0, "y": 0.0}
    assert ok["reasons"] == []


def test_zero_bleed_profile():
    p = {**PROFILE, "bleed_in": 0}
    im = Image.new("RGB", (480, 360), "navy")
    report = analyze(im, p)
    assert report["reasons"] == []
    assert report["effective_dpi"] == 120.0
    assert report["coverage_ratio"] == 1.0
