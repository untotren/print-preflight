"""Golden JSON reports for every generated fixture against every profile.

Regenerate after an intentional change with: UPDATE_GOLDENS=1 pytest tests/test_golden.py
"""

import json
import os

import pytest

from conftest import GOLDEN, PROFILES, make_fixtures
from print_preflight import check_image, load_profile
from print_preflight.cli import to_json

CASES = [(f, p.stem) for f in make_fixtures.FIXTURES for p in sorted(PROFILES.glob("*.json"))]


@pytest.mark.parametrize("fixture,profile", CASES, ids=[f"{f}-{p}" for f, p in CASES])
def test_golden_report(fixture, profile, fixture_paths, profile_paths):
    report = check_image(fixture_paths[fixture], load_profile(profile_paths[profile]))
    golden = GOLDEN / f"{fixture}__{profile}.json"
    if os.environ.get("UPDATE_GOLDENS") == "1":
        golden.write_text(to_json(report), encoding="utf-8")
    assert golden.exists(), f"missing golden {golden.name}; run with UPDATE_GOLDENS=1"
    assert to_json(report) == golden.read_text(encoding="utf-8")


def test_no_stale_goldens():
    expected = {f"{f}__{p}.json" for f, p in CASES}
    actual = {p.name for p in GOLDEN.glob("*.json") if "__" in p.name}
    assert actual == expected


# Spot checks so the goldens' key outcomes are reviewable without opening JSON.
EXPECTED = {
    ("solid.png", "bleed"): ("pass", []),
    ("solid.jpg", "bleed"): ("pass", []),
    ("solid_cmyk.tif", "bleed"): ("pass", []),
    ("solid_lowres.png", "bleed"): ("warn", ["DPI_BELOW_WARN"]),
    ("solid_tiny.png", "bleed"): ("fail", ["DPI_BELOW_TARGET"]),
    ("solid_square.png", "bleed"): ("fail", ["ASPECT_MISMATCH"]),
    ("blank.png", "bleed"): ("fail", ["NO_CONTENT"]),
    ("checkerboard.png", "bleed"): ("warn", ["EDGE_COVERAGE_LOW"]),
    ("checkerboard.tif", "bleed"): ("warn", ["EDGE_COVERAGE_LOW"]),
    ("bordered.png", "bleed"): ("fail", ["BLEED_NOT_REACHED", "EDGE_COVERAGE_LOW"]),
    ("bordered.png", "flat"): ("pass", []),
    ("transparent_margin.png", "flat"): ("warn", ["SAFE_MARGIN_VIOLATION"]),
    ("palette_transparent.png", "flat"): ("pass", []),
    ("off_centre.png", "flat"): ("warn", ["OFF_CENTER"]),
}


@pytest.mark.parametrize("key", sorted(EXPECTED), ids=lambda k: f"{k[0]}-{k[1]}")
def test_expected_outcomes(key, fixture_paths, profile_paths):
    fixture, profile = key
    report = check_image(fixture_paths[fixture], load_profile(profile_paths[profile]))
    assert (report["status"], report["reasons"]) == EXPECTED[key]


def test_every_reason_code_is_exercised_by_goldens():
    from print_preflight.reasons import REASONS

    seen = set()
    for path in GOLDEN.glob("*__*.json"):
        seen.update(json.loads(path.read_text())["reasons"])
    assert seen == {r.code for r in REASONS}
