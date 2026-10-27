import json
from fractions import Fraction

import pytest

from print_preflight import PreflightError, Profile, load_profile, parse_profile_json


def test_json_and_dict_agree(standard_profile_path, standard_profile_dict):
    assert load_profile(standard_profile_path) == Profile.from_dict(standard_profile_dict)


def test_json_decimals_are_exact():
    text = json.dumps({"print_width_in": 8.333, "print_height_in": 0.1, "dpi_target": 300,
                       "dpi_warn": 300, "bleed_in": 0, "safe_margin_in": 0,
                       "aspect_tolerance": 0.01, "edge_coverage_min": 1})
    p = parse_profile_json(text)
    assert p.print_width_in == Fraction(8333, 1000)
    assert p.print_height_in == Fraction(1, 10)


@pytest.mark.parametrize("change", [
    {"print_width_in": 0},
    {"dpi_target": -1},
    {"bleed_in": -0.1},
    {"edge_coverage_min": 1.5},
    {"dpi_warn": 50},  # below dpi_target
    {"safe_margin_in": 1.5},  # no safe area left in a 3 in dimension
    {"extra": 1},
    {"dpi_target": None},
])
def test_invalid_profiles(standard_profile_dict, change):
    with pytest.raises(PreflightError) as exc:
        Profile.from_dict({**standard_profile_dict, **change})
    assert exc.value.code == "PROFILE_INVALID"


def test_missing_field(standard_profile_dict):
    del standard_profile_dict["bleed_in"]
    with pytest.raises(PreflightError, match="bleed_in"):
        Profile.from_dict(standard_profile_dict)


@pytest.mark.parametrize("text", ["not json", "[]", '{"print_width_in": NaN}'])
def test_bad_json(text):
    with pytest.raises(PreflightError) as exc:
        parse_profile_json(text)
    assert exc.value.code == "PROFILE_INVALID"


def test_missing_file(tmp_path):
    with pytest.raises(PreflightError) as exc:
        load_profile(tmp_path / "nope.json")
    assert exc.value.code == "PROFILE_NOT_FOUND"
