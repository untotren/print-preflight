"""Golden JSON reports for every generated fixture under both profiles.

Regenerate after an intentional change with:
    PRINT_PREFLIGHT_UPDATE_GOLDEN=1 python -m pytest tests/test_golden.py
"""

from __future__ import annotations

import json
import os

import pytest

import make_fixtures
from conftest import GOLDEN, PROFILES
from print_preflight import check
from print_preflight.cli import EXIT_CODES, main, to_json

CASES = [(name, prof) for name in make_fixtures.FIXTURES for prof in ("bleed", "nobleed")]


def golden_path(name: str, prof: str):
    return GOLDEN / f"{name.replace('.', '_')}__{prof}.json"


@pytest.mark.parametrize("name,prof", CASES)
def test_report_matches_golden(fixture_paths, name, prof):
    report = check(fixture_paths[name], PROFILES / f"{prof}.json")
    path = golden_path(name, prof)
    if os.environ.get("PRINT_PREFLIGHT_UPDATE_GOLDEN"):
        path.write_text(to_json(report), encoding="utf-8")
    assert to_json(report) == path.read_text(encoding="utf-8")


@pytest.mark.parametrize("name,prof", CASES)
def test_cli_json_and_exit_code_match_golden(fixture_paths, name, prof, capsys):
    code = main(["check", str(fixture_paths[name]), "--profile", str(PROFILES / f"{prof}.json"), "--json"])
    expected = json.loads(golden_path(name, prof).read_text(encoding="utf-8"))
    assert json.loads(capsys.readouterr().out) == expected
    assert code == EXIT_CODES[expected["status"]]


def test_report_is_deterministic(fixture_paths):
    runs = [check(fixture_paths["checkerboard.png"], PROFILES / "bleed.json") for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]


def test_fixture_script_is_byte_stable(tmp_path):
    a = make_fixtures.build(tmp_path / "a")
    b = make_fixtures.build(tmp_path / "b")
    for name in make_fixtures.FIXTURES:
        assert a[name].read_bytes() == b[name].read_bytes(), name
