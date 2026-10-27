import json
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).parent
sys.path.insert(0, str(TESTS / "fixtures"))

import make_fixtures  # noqa: E402

PROFILE_PATH = TESTS / "fixtures" / "profile.json"


@pytest.fixture(scope="session")
def fixtures(tmp_path_factory):
    return make_fixtures.generate(tmp_path_factory.mktemp("fixtures"))


@pytest.fixture(scope="session")
def profile_path():
    return PROFILE_PATH


@pytest.fixture(scope="session")
def profile_dict():
    return json.loads(PROFILE_PATH.read_text())
