"""Golden JSON reports for every fixture, produced through the CLI.

Regenerate after an intentional change with ``UPDATE_GOLDEN=1 python -m pytest
tests/test_golden.py`` and review the diff.
"""

import io
import json
import os

import pytest

from print_preflight.cli import EXIT_CODES, main

from conftest import GOLDEN_DIR, make_fixtures

UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"


@pytest.mark.parametrize("name", sorted(make_fixtures.FIXTURES))
def test_golden_report(fixtures, standard_profile_path, name):
    out = io.StringIO()
    code = main(["check", str(fixtures[name]), "--profile", str(standard_profile_path), "--json"], stdout=out)
    golden = GOLDEN_DIR / f"{name}.json"
    if UPDATE:
        golden.write_text(out.getvalue())
    assert golden.exists(), f"missing golden report {golden.name}; run with UPDATE_GOLDEN=1"
    assert out.getvalue() == golden.read_text()
    assert code == EXIT_CODES[json.loads(golden.read_text())["status"]]


def test_no_stale_goldens():
    assert sorted(p.name for p in GOLDEN_DIR.glob("*.json")) == sorted(f"{n}.json" for n in make_fixtures.FIXTURES)
