from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.make_fixtures import generate
from print_preflight import load_profile

TESTS = Path(__file__).parent
PROFILE_PATH = TESTS / "fixtures" / "profile.json"
GOLDEN_DIR = TESTS / "golden"


@pytest.fixture(scope="session")
def fixture_paths(tmp_path_factory) -> dict[str, Path]:
    return generate(tmp_path_factory.mktemp("fixtures"))


@pytest.fixture(scope="session")
def profile():
    return load_profile(PROFILE_PATH)
