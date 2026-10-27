import io

import pytest
from PIL import Image

from print_preflight import PreflightError, Profile, analyze, check_image, open_image
from print_preflight.checks import REASON_CODES

EXPECTED = {
    "solid.png": ("pass", []),
    "solid.jpg": ("pass", []),
    "solid.tif": ("pass", []),
    "solid_lowres.png": ("warn", ["DPI_BELOW_WARN"]),
    "solid_tiny.png": ("fail", ["DPI_BELOW_TARGET"]),
    "solid_square.png": ("fail", ["ASPECT_MISMATCH"]),
    "checkerboard.png": ("warn", ["EDGE_COVERAGE_LOW"]),
    "bordered.png": ("pass", []),
    "bordered_safe.png": ("warn", ["SAFE_MARGIN_INTRUSION"]),
    "bordered_bleed_short.png": ("fail", ["BLEED_SHORT"]),
    "transparent_margin.png": ("pass", []),
    "off_centre.png": ("warn", ["OFF_CENTER"]),
    "blank.png": ("fail", ["CONTENT_EMPTY"]),
}


def test_every_fixture_has_an_expectation(fixtures):
    assert set(fixtures) == set(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_fixture_verdicts(fixtures, standard_profile, name):
    report = check_image(fixtures[name], standard_profile)
    assert (report["status"], report["reasons"]) == EXPECTED[name]


def test_every_reason_code_is_exercised():
    seen = {code for _, codes in EXPECTED.values() for code in codes}
    assert seen == set(REASON_CODES)


def test_report_keys(fixtures, standard_profile):
    report = check_image(fixtures["solid.png"], standard_profile)
    for key in ("status", "effective_dpi", "aspect_delta", "coverage_ratio", "centering_delta_px", "edge_coverage", "reasons"):
        assert key in report
    assert set(report["edge_coverage"]) == {"top", "right", "bottom", "left"}


def test_solid_metrics(fixtures, standard_profile):
    report = check_image(fixtures["solid.png"], standard_profile)
    assert report["effective_dpi"] == 150.22  # min(338 / 2.25, 263 / 1.75), floored
    assert report["required_px"] == {"target": [225, 175], "warn": [338, 263]}
    assert report["coverage_ratio"] == 1.0
    assert report["centering_delta_px"] == {"x": 0, "y": 0}
    assert report["edge_coverage"] == {"top": 1.0, "right": 1.0, "bottom": 1.0, "left": 1.0}
    assert report["background_mode"] == "color"


def test_bordered_geometry(fixtures, standard_profile):
    report = check_image(fixtures["bordered.png"], standard_profile)
    assert report["content_box_px"] == [40, 40, 298, 223]
    assert report["margins_px"] == {"top": 40, "right": 40, "bottom": 40, "left": 40}


def test_transparent_margin_uses_alpha(fixtures, standard_profile):
    # The art is opaque white, which would be background in colour mode.
    report = check_image(fixtures["transparent_margin.png"], standard_profile)
    assert report["background_mode"] == "alpha"
    assert report["content_box_px"] == [40, 40, 298, 223]


def test_off_centre_delta(fixtures, standard_profile):
    report = check_image(fixtures["off_centre.png"], standard_profile)
    assert report["centering_delta_px"] == {"x": -49, "y": 0}


def test_empty_content_report(fixtures, standard_profile):
    report = check_image(fixtures["blank.png"], standard_profile)
    assert report["coverage_ratio"] == 0.0
    assert report["centering_delta_px"] is None
    assert report["content_box_px"] is None


def test_half_pixel_centering(standard_profile):
    img = Image.new("RGB", (338, 263), "white")
    img.paste((0, 0, 0), (100, 100, 201, 150))
    report = analyze(img, standard_profile)
    assert report["centering_delta_px"] == {"x": -18.5, "y": -6.5}


def test_background_override(standard_profile):
    data = {**standard_profile.to_dict(), "background_rgb": [200, 30, 40]}
    img = Image.new("RGB", (338, 263), (200, 30, 40))
    assert analyze(img, Profile.from_dict(data))["reasons"] == ["CONTENT_EMPTY"]


def test_background_tolerance(standard_profile):
    img = Image.new("RGB", (338, 263), (250, 250, 250))
    assert analyze(img, standard_profile)["reasons"] == ["CONTENT_EMPTY"]
    strict = Profile.from_dict({**standard_profile.to_dict(), "background_tolerance": 0})
    assert analyze(img, strict)["reasons"] == []


def test_zero_bleed_uses_one_pixel_band(standard_profile):
    data = {**standard_profile.to_dict(), "bleed_in": 0, "print_width_in": 2.25, "print_height_in": 1.75}
    img = Image.new("RGB", (338, 263), "red")
    img.paste((255, 255, 255), (0, 0, 338, 1))  # white top row
    img.paste((0, 0, 255), (0, 0, 1, 1))  # one content pixel keeps the box at the edge
    report = analyze(img, Profile.from_dict(data))
    assert report["edge_coverage"]["top"] == 0.0029  # 1/338, floored
    assert report["reasons"] == ["EDGE_COVERAGE_LOW"]


@pytest.mark.parametrize(
    "mode, fill",
    [("L", 0), ("1", 0), ("LA", (0, 255)), ("P", 1), ("CMYK", (0, 255, 255, 0)), ("I;16", 0), ("I", 0), ("F", 0.0)],
)
def test_pixel_modes(standard_profile, mode, fill):
    img = Image.new(mode, (338, 263), fill)
    report = analyze(img, standard_profile)
    assert report["status"] == "pass", report


def test_palette_transparency(tmp_path, standard_profile):
    img = Image.new("P", (338, 263), 0)
    img.putpalette([0, 0, 0, 255, 0, 0] + [0] * 762)
    img.paste(1, (40, 40, 298, 223))
    path = tmp_path / "pal.png"
    img.save(path, transparency=0)
    report = check_image(path, standard_profile)
    assert report["background_mode"] == "alpha"
    assert report["content_box_px"] == [40, 40, 298, 223]


def test_opaque_rgba_uses_colour_background(standard_profile):
    img = Image.new("RGBA", (338, 263), (255, 255, 255, 255))
    assert analyze(img, standard_profile)["background_mode"] == "color"


def test_missing_image(tmp_path, standard_profile):
    with pytest.raises(PreflightError) as info:
        check_image(tmp_path / "nope.png", standard_profile)
    assert info.value.code == "IMAGE_NOT_FOUND"


def test_unsupported_format(tmp_path):
    path = tmp_path / "a.gif"
    Image.new("RGB", (10, 10)).save(path)
    with pytest.raises(PreflightError) as info:
        open_image(path)
    assert info.value.code == "IMAGE_FORMAT_UNSUPPORTED"


def test_corrupt_images(tmp_path):
    junk = tmp_path / "junk.png"
    junk.write_bytes(b"not an image at all")
    with pytest.raises(PreflightError) as info:
        open_image(junk)
    assert info.value.code == "IMAGE_UNREADABLE"

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), "red").save(buf, "PNG")
    truncated = tmp_path / "trunc.png"
    truncated.write_bytes(buf.getvalue()[:60])
    with pytest.raises(PreflightError) as info:
        open_image(truncated)
    assert info.value.code == "IMAGE_UNREADABLE"


def test_deterministic(fixtures, standard_profile):
    for path in fixtures.values():
        assert check_image(path, standard_profile) == check_image(path, standard_profile)
