import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
STANDARD_PROFILE = TESTS / "profiles" / "standard.json"
GOLDEN_DIR = TESTS / "golden"


def _load_fixture_script():
    spec = importlib.util.spec_from_file_location("make_fixtures", ROOT / "scripts" / "make_fixtures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


make_fixtures = _load_fixture_script()


@pytest.fixture(scope="session")
def fixtures(tmp_path_factory):
    """name -> path of every procedurally generated fixture image."""
    return make_fixtures.generate(tmp_path_factory.mktemp("fixtures"))


@pytest.fixture(scope="session")
def standard_profile_path():
    return STANDARD_PROFILE


@pytest.fixture(scope="session")
def standard_profile():
    from print_preflight import load_profile

    return load_profile(STANDARD_PROFILE)
