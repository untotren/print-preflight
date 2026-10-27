import importlib.util
from pathlib import Path

import pytest

TESTS = Path(__file__).parent
PROFILES = TESTS / "fixtures" / "profiles"
GOLDEN = TESTS / "golden"


def _load_generator():
    spec = importlib.util.spec_from_file_location("make_fixtures", TESTS / "fixtures" / "make_fixtures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


make_fixtures = _load_generator()


@pytest.fixture(scope="session")
def generator():
    return make_fixtures


@pytest.fixture(scope="session")
def fixture_paths(tmp_path_factory):
    return make_fixtures.write_all(tmp_path_factory.mktemp("fixtures"))


@pytest.fixture(scope="session")
def profile_paths():
    return {p.stem: p for p in sorted(PROFILES.glob("*.json"))}
