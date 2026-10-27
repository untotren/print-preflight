import json
from fractions import Fraction

import pytest

from print_preflight import Profile, ProfileError, load_profile

BASE = {
    "print_width_in": 8.5,
    "print_height_in": 11,
    "dpi_target": 300,
    "dpi_warn": 300,
    "bleed_in": 0.125,
    "safe_margin_in": 0.25,
    "aspect_tolerance": 0.01,
    "edge_coverage_min": 0.95,
}


def test_decimal_values_are_exact():
    p = Profile.from_dict(BASE)
    assert p.print_width_in == Fraction(17, 2)
    assert p.canvas_width_in == Fraction(35, 4)
    assert p.aspect_tolerance == Fraction(1, 100)


def test_defaults():
    p = Profile.from_dict(BASE)
    assert p.must_bleed is True
    assert p.background_rgb == (255, 255, 255)
    assert p.background_tolerance == 8
    assert p.centering_tolerance_in == Fraction(1, 16)
    assert Profile.from_dict({**BASE, "bleed_in": 0}).must_bleed is False


def test_optional_overrides():
    p = Profile.from_dict({**BASE, "must_bleed": False, "background_rgb": [0, 0, 0], "background_tolerance": 0, "centering_tolerance_in": 0.5})
    assert (p.must_bleed, p.background_rgb, p.background_tolerance, p.centering_tolerance_in) == (False, (0, 0, 0), 0, Fraction(1, 2))


@pytest.mark.parametrize(
    "change,message",
    [
        ({"print_width_in": None}, "missing"),
        ({"extra": 1}, "unknown"),
        ({"dpi_target": "300"}, "must be a number"),
        ({"dpi_target": True}, "must be a number"),
        ({"dpi_target": float("nan")}, "finite"),
        ({"print_width_in": 0}, "> 0"),
        ({"bleed_in": -0.1}, ">= 0"),
        ({"dpi_warn": 299}, "dpi_warn"),
        ({"edge_coverage_min": 1.5}, "edge_coverage_min"),
        ({"safe_margin_in": 4.25}, "no safe area"),
        ({"must_bleed": 1}, "must_bleed"),
        ({"background_rgb": [255, 255]}, "background_rgb"),
        ({"background_rgb": [255, 255, 256]}, "background_rgb"),
        ({"background_tolerance": 300}, "background_tolerance"),
        ({"centering_tolerance_in": -1}, "centering_tolerance_in"),
    ],
)
def test_invalid_profiles(change, message):
    data = dict(BASE)
    for k, v in change.items():
        if v is None:
            del data[k]
        else:
            data[k] = v
    with pytest.raises(ProfileError, match=message):
        Profile.from_dict(data)


def test_non_object_profile():
    with pytest.raises(ProfileError):
        Profile.from_dict([1, 2])


def test_load_profile_roundtrip(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps(BASE))
    assert load_profile(path) == Profile.from_dict(BASE)
