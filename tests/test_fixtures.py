"""The committed fixture generator must be deterministic and lossless."""

import hashlib
import json
import os
import subprocess
import sys

import pytest
from PIL import Image

from conftest import GOLDEN, TESTS, make_fixtures

HASHES = GOLDEN / "fixture_pixels.json"


def pixel_digest(im: Image.Image) -> str:
    h = hashlib.sha256(f"{im.mode}:{im.size}".encode())
    h.update(im.tobytes())
    if im.mode == "P":
        h.update(bytes(im.getpalette()))
    return h.hexdigest()


def test_builders_match_pixel_hashes():
    digests = {name: pixel_digest(make_fixtures.build(name)) for name in sorted(make_fixtures.FIXTURES)}
    if os.environ.get("UPDATE_GOLDENS") == "1":
        HASHES.write_text(json.dumps(digests, indent=2, sort_keys=True) + "\n")
    assert digests == json.loads(HASHES.read_text())


@pytest.mark.parametrize("name", make_fixtures.LOSSLESS)
def test_lossless_files_round_trip(name, fixture_paths):
    with Image.open(fixture_paths[name]) as im:
        im.load()
        assert im.tobytes() == make_fixtures.build(name).tobytes()


def test_generator_writes_every_fixture(tmp_path):
    paths = make_fixtures.write_all(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(make_fixtures.FIXTURES)
    expected = {"png": "PNG", "jpg": "JPEG", "tif": "TIFF"}
    for name, path in paths.items():
        with Image.open(path) as im:
            assert im.format == expected[name.rsplit(".", 1)[1]]


def test_generator_cli(tmp_path):
    proc = subprocess.run([sys.executable, str(TESTS / "fixtures" / "make_fixtures.py"), str(tmp_path)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert len(proc.stdout.splitlines()) == len(make_fixtures.FIXTURES)
    proc = subprocess.run([sys.executable, str(TESTS / "fixtures" / "make_fixtures.py")], capture_output=True, text=True)
    assert proc.returncode == 2
    assert "Usage" in proc.stderr
