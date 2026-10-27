"""Behaviour of the image analysis beyond the golden fixtures."""

import io

from PIL import Image

from print_preflight import Profile, analyze, check_image
from print_preflight.core import round_half_up

from fractions import Fraction

FLAT = {
    "print_width_in": 2,
    "print_height_in": 2,
    "dpi_target": 10,
    "dpi_warn": 10,
    "bleed_in": 0,
    "safe_margin_in": 0.2,
    "aspect_tolerance": 0,
    "edge_coverage_min": 0,
}


def test_round_half_up():
    assert round_half_up(Fraction(1, 8), 2) == 0.13
    assert round_half_up(Fraction(5, 1000), 2) == 0.01
    assert round_half_up(Fraction(-1, 3), 2) == -0.33


def test_background_tolerance_and_colour():
    im = Image.new("RGB", (20, 20), (250, 250, 250))  # within 8 of white
    assert analyze(im, Profile.from_dict(FLAT))["reasons"] == ["NO_CONTENT"]
    assert analyze(im, Profile.from_dict({**FLAT, "background_tolerance": 4}))["content_box"] == [0, 0, 20, 20]
    dark = Image.new("RGB", (20, 20), (0, 0, 0))
    assert analyze(dark, Profile.from_dict({**FLAT, "background_rgb": [0, 0, 0]}))["reasons"] == ["NO_CONTENT"]


def test_sixteen_bit_greyscale():
    im = Image.new("I;16", (20, 20), 0)
    im.paste(65535, (0, 0, 20, 20))
    im.paste(0, (5, 5, 15, 15))
    report = analyze(im, Profile.from_dict(FLAT))
    assert report["content_box"] == [5, 5, 15, 15]
    assert report["status"] == "pass"


def test_exif_orientation_is_applied(tmp_path):
    im = Image.new("RGB", (20, 40), (255, 0, 0))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees when displayed
    path = tmp_path / "rot.jpg"
    im.save(path, exif=exif)
    report = check_image(path, Profile.from_dict({**FLAT, "print_width_in": 4, "aspect_tolerance": 0.01}))
    assert (report["image"]["width_px"], report["image"]["height_px"]) == (40, 20)
    assert "ASPECT_MISMATCH" not in report["reasons"]


def test_must_bleed_can_be_forced_without_bleed():
    im = Image.new("RGB", (20, 20), (255, 255, 255))
    im.paste((0, 0, 0), (1, 0, 20, 20))
    report = analyze(im, Profile.from_dict({**FLAT, "must_bleed": True, "edge_coverage_min": 1}))
    assert report["reasons"] == ["BLEED_NOT_REACHED", "EDGE_COVERAGE_LOW"]
    assert report["edge_coverage"]["left"] == 0.0


def test_centering_tolerance_boundary():
    # 20 px over 2 in = 10 px/in; tolerance 0.1 in = 1 px.
    prof = Profile.from_dict({**FLAT, "safe_margin_in": 0, "centering_tolerance_in": 0.1})
    im = Image.new("RGB", (20, 20), (255, 255, 255))
    im.paste((0, 0, 0), (6, 5, 16, 15))  # centre offset exactly +1 px in x
    assert analyze(im, prof)["reasons"] == []
    im.paste((0, 0, 0), (16, 5, 17, 15))  # box [6,5,17,15]: offset 1.5 px
    report = analyze(im, prof)
    assert report["reasons"] == ["OFF_CENTER"]
    assert report["centering_delta_px"] == {"x": 1.5, "y": 0.0}


def test_reports_are_deterministic(fixture_paths, profile_paths):
    from print_preflight import load_profile

    prof = load_profile(profile_paths["bleed"])
    first = [check_image(p, prof) for p in fixture_paths.values()]
    second = [check_image(p, prof) for p in fixture_paths.values()]
    assert first == second


def test_in_memory_image_has_no_format():
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), (0, 0, 0)).save(buf, "PNG")
    buf.seek(0)
    assert analyze(Image.open(buf), Profile.from_dict(FLAT))["image"]["format"] is None
