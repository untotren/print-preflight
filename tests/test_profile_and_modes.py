from __future__ import annotations

from fractions import Fraction

import pytest
from PIL import Image

from conftest import PROFILE_PATH
from print_preflight import Profile, ProfileError, check_image, load_profile, preflight

BASE = {
    "print_width_in": 4,
    "print_height_in": 6,
    "dpi_target": 70,
    "dpi_warn": 80,
    "bleed_in": 0.125,
    "safe_margin_in": 0.125,
    "aspect_tolerance": 0.01,
    "edge_coverage_min": 0.9,
}


def test_load_profile_exact_values():
    p = load_profile(PROFILE_PATH)
    assert p.bleed_width_in == Fraction("4.25")
    assert p.bleed_height_in == Fraction("6.25")
    assert p.centering_tolerance_in == Fraction(1, 16)
    assert p.background == (255, 255, 255)


@pytest.mark.parametrize(
    "override",
    [
        {"print_width_in": -1},
        {"dpi_warn": True},
        {"aspect_tolerance": 1},
        {"safe_margin_in": -0.1},
        {"background": "#12345"},
        {"background": [1, 2]},
        {"background_tolerance": 300},
        {"require_bleed": "yes"},
        {"centering_tolerance_in": -1},
    ],
)
def test_invalid_profiles(override):
    with pytest.raises(ProfileError):
        Profile.from_dict({**BASE, **override})


def test_background_option():
    black_paper = Profile.from_dict({**BASE, "background": "#000000"})
    img = Image.new("RGB", (340, 500), (0, 0, 0))
    assert check_image(img, black_paper)["reasons"] == ["CONTENT_EMPTY"]
    assert check_image(img, Profile.from_dict(BASE))["status"] == "pass"


def test_warn_not_above_target_never_warns():
    # With dpi_warn <= dpi_target the warn band is empty.
    p = Profile.from_dict({**BASE, "dpi_warn": 60})
    assert check_image(Image.new("RGB", (298, 438), (9, 9, 9)), p)["reasons"] == []
    assert check_image(Image.new("RGB", (297, 438), (9, 9, 9)), p)["reasons"] == ["DPI_BELOW_TARGET"]


@pytest.mark.parametrize("mode", ["L", "LA", "P", "CMYK", "RGBA", "I;16", "1"])
def test_image_modes(mode):
    img = Image.new("RGB", (340, 500), (20, 20, 20)).convert(mode)
    assert check_image(img, Profile.from_dict(BASE))["status"] == "pass"


def test_sixteen_bit_png_roundtrip(tmp_path):
    path = tmp_path / "g16.png"
    Image.new("I;16", (340, 500), 1000).save(path)
    assert preflight(path, Profile.from_dict(BASE))["status"] == "pass"


def test_exif_orientation_applied(tmp_path):
    path = tmp_path / "rot.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 CW on display
    Image.new("RGB", (500, 340), (200, 30, 30)).save(path, "JPEG", exif=exif.tobytes())
    report = preflight(path, Profile.from_dict(BASE))
    assert report["image"] == {"width_px": 340, "height_px": 500}
    assert report["status"] == "pass"


def test_input_image_not_mutated():
    img = Image.new("RGBA", (340, 500), (1, 2, 3, 255))
    before = img.tobytes()
    check_image(img, Profile.from_dict(BASE))
    assert img.tobytes() == before
