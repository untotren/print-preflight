from __future__ import annotations

from pathlib import Path

import pytest

import make_fixtures

TESTS = Path(__file__).parent
PROFILES = TESTS / "profiles"
GOLDEN = TESTS / "golden"


@pytest.fixture(scope="session")
def fixture_paths(tmp_path_factory) -> dict[str, Path]:
    return make_fixtures.build(tmp_path_factory.mktemp("fixtures"))
