"""Golden JSON reports for every generated fixture.

Regenerate after an intended behaviour change with:
    PREFLIGHT_UPDATE_GOLDEN=1 python -m pytest tests/test_golden.py
"""

from __future__ import annotations

import json
import os

import pytest

from conftest import GOLDEN_DIR
from fixtures.make_fixtures import FIXTURES
from print_preflight import preflight
from print_preflight.cli import report_json

EXPECTED = {
    "solid.png": ("pass", []),
    "checkerboard.png": ("warn", ["EDGE_COVERAGE_LOW"]),
    "bordered.png": ("pass", []),
    "transparent_margin.png": ("warn", ["BLEED_SHORT", "EDGE_COVERAGE_LOW"]),
    "transparent_safe.png": ("warn", ["SAFE_MARGIN_VIOLATION"]),
    "off_centre.png": ("warn", ["OFF_CENTRE"]),
    "notched_edge.png": ("warn", ["EDGE_COVERAGE_LOW"]),
    "low_res.png": ("fail", ["DPI_BELOW_TARGET"]),
    "below_warn.png": ("warn", ["DPI_BELOW_WARN"]),
    "wrong_aspect.png": ("fail", ["ASPECT_MISMATCH"]),
    "blank.png": ("fail", ["CONTENT_EMPTY"]),
    "solid.jpg": ("pass", []),
    "bordered.tif": ("pass", []),
}


def test_expectations_cover_all_fixtures():
    assert set(EXPECTED) == set(FIXTURES)


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_golden_report(name, fixture_paths, profile):
    report = preflight(fixture_paths[name], profile)
    status, reasons = EXPECTED[name]
    assert (report["status"], report["reasons"]) == (status, reasons)

    golden = GOLDEN_DIR / (name.replace(".", "_") + ".json")
    if os.environ.get("PREFLIGHT_UPDATE_GOLDEN"):
        golden.parent.mkdir(exist_ok=True)
        golden.write_text(report_json(report), encoding="utf-8")
    assert report == json.loads(golden.read_text(encoding="utf-8"))


def test_reports_are_deterministic(fixture_paths, profile):
    for name in sorted(FIXTURES):
        first = report_json(preflight(fixture_paths[name], profile))
        second = report_json(preflight(fixture_paths[name], profile))
        assert first == second
