import json
from fractions import Fraction

import pytest

from print_preflight import PreflightError, Profile, load_profile
from print_preflight.profile import exact

BASE = {
    "print_width_in": 2,
    "print_height_in": 1.5,
    "dpi_target": 100,
    "dpi_warn": 150,
    "bleed_in": 0.125,
    "safe_margin_in": 0.125,
    "aspect_tolerance": 0.01,
    "edge_coverage_min": 0.95,
}


def test_defaults_applied():
    p = Profile.from_dict(BASE)
    assert p.background_rgb == (255, 255, 255)
    assert p.background_tolerance == 8
    assert p.centering_tolerance == 0.01
    assert p.to_dict()["background_rgb"] == [255, 255, 255]


def test_exact_uses_decimal_form():
    assert exact(0.1) == Fraction(1, 10)
    assert exact(3) == 3
    assert Profile.from_dict(BASE).q("aspect_tolerance") == Fraction(1, 100)


@pytest.mark.parametrize(
    "change, fragment",
    [
        ({"print_width_in": 0}, "print_width_in must be > 0"),
        ({"dpi_warn": 50}, "dpi_warn must be >= dpi_target"),
        ({"bleed_in": -0.1}, "bleed_in must be >= 0"),
        ({"edge_coverage_min": 1.5}, "edge_coverage_min must be between 0 and 1"),
        ({"dpi_target": "300"}, "dpi_target must be a finite number"),
        ({"dpi_target": True}, "dpi_target must be a finite number"),
        ({"dpi_target": float("nan")}, "dpi_target must be a finite number"),
        ({"background_rgb": [0, 0]}, "background_rgb"),
        ({"background_tolerance": 2.5}, "background_tolerance"),
        ({"colour": "red"}, "unknown field(s): colour"),
    ],
)
def test_invalid_profiles(change, fragment):
    with pytest.raises(PreflightError) as info:
        Profile.from_dict({**BASE, **change})
    assert info.value.code == "PROFILE_INVALID"
    assert fragment in info.value.message


def test_missing_field():
    data = dict(BASE)
    del data["bleed_in"]
    with pytest.raises(PreflightError, match="missing field"):
        Profile.from_dict(data)


def test_not_an_object():
    with pytest.raises(PreflightError) as info:
        Profile.from_dict([1, 2])
    assert info.value.code == "PROFILE_INVALID"


def test_load_profile_errors(tmp_path):
    with pytest.raises(PreflightError) as info:
        load_profile(tmp_path / "missing.json")
    assert info.value.code == "PROFILE_UNREADABLE"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(PreflightError) as info:
        load_profile(bad)
    assert info.value.code == "PROFILE_UNREADABLE"
    good = tmp_path / "good.json"
    good.write_text(json.dumps(BASE))
    assert load_profile(good).dpi_warn == 150
