import json

import pytest

from print_preflight import PreflightError, Profile


def test_load(profile_path, profile_dict):
    assert Profile.load(profile_path) == Profile.from_dict(profile_dict)


@pytest.mark.parametrize(
    "patch, fragment",
    [
        ({"dpi_target": None}, "dpi_target must be a finite number"),
        ({"dpi_target": True}, "dpi_target must be a finite number"),
        ({"dpi_target": "300"}, "dpi_target must be a finite number"),
        ({"print_width_in": 0}, "print_width_in must be > 0"),
        ({"bleed_in": -0.1}, "bleed_in must be >= 0"),
        ({"edge_coverage_min": 1.5}, "edge_coverage_min must be within [0, 1]"),
        ({"dpi_warn": 50}, "dpi_warn must be >= dpi_target"),
        ({"dpi": 300}, "unknown keys: dpi"),
    ],
)
def test_invalid_values(profile_dict, patch, fragment):
    with pytest.raises(PreflightError) as info:
        Profile.from_dict({**profile_dict, **patch})
    assert info.value.code == "PROFILE_INVALID"
    assert fragment in info.value.message


def test_missing_key(profile_dict):
    data = dict(profile_dict)
    del data["bleed_in"]
    with pytest.raises(PreflightError, match="missing keys: bleed_in"):
        Profile.from_dict(data)


def test_not_an_object():
    with pytest.raises(PreflightError, match="JSON object"):
        Profile.from_dict([1, 2])


def test_bad_json(tmp_path):
    path = tmp_path / "p.json"
    path.write_text("{not json")
    with pytest.raises(PreflightError, match="not valid JSON"):
        Profile.load(path)


def test_missing_file(tmp_path):
    with pytest.raises(PreflightError) as info:
        Profile.load(tmp_path / "nope.json")
    assert info.value.code == "PROFILE_INVALID"


def test_nan_rejected(tmp_path, profile_dict):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({**profile_dict, "dpi_target": float("nan")}))
    with pytest.raises(PreflightError, match="finite"):
        Profile.load(path)
