"""Golden JSON reports for every generated fixture.

Regenerate with ``UPDATE_GOLDEN=1 pytest tests/test_golden.py`` and review the diff.
"""

import json
import os

import pytest

from conftest import GOLDEN, make_fixtures
from print_preflight import check
from print_preflight.cli import to_json

NAMES = list(make_fixtures.FIXTURES)


@pytest.mark.parametrize("name", NAMES)
def test_golden_report(name, fixtures, standard_profile_path):
    actual = to_json(check(fixtures[name], standard_profile_path))
    golden = GOLDEN / f"{name}.json"
    if os.environ.get("UPDATE_GOLDEN"):
        golden.write_text(actual)
    assert actual == golden.read_text()


def test_every_golden_has_a_fixture():
    assert sorted(p.stem for p in GOLDEN.glob("*.json")) == sorted(NAMES)


@pytest.mark.parametrize("variant", ["solid-jpeg", "solid-tiff"])
def test_other_formats_match_png(variant, fixtures, standard_profile_path):
    assert check(fixtures[variant], standard_profile_path) == check(fixtures["solid"], standard_profile_path)


def test_reports_are_deterministic(fixtures, standard_profile_path):
    a = [check(fixtures[n], standard_profile_path) for n in NAMES]
    b = [check(fixtures[n], standard_profile_path) for n in NAMES]
    assert a == b


def test_report_shape(fixtures, standard_profile_path):
    report = check(fixtures["checkerboard"], standard_profile_path)
    assert list(report) == ["status", "effective_dpi", "aspect_delta", "coverage_ratio",
                            "centering_delta_px", "edge_coverage", "reasons"]
    assert list(report["edge_coverage"]) == ["top", "right", "bottom", "left"]
    json.dumps(report)  # serialisable
