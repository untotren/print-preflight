"""CLI behaviour, exit codes, --out, and input errors."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest
from PIL import Image

from conftest import PROFILES, TESTS
from print_preflight import PreflightError, check, load_profile
from print_preflight.cli import main

BLEED = str(PROFILES / "bleed.json")


def run(argv, capsys):
    code = main(argv)
    return code, capsys.readouterr().out


@pytest.mark.parametrize("name,code", [
    ("solid.png", 0), ("low_res.png", 1), ("blank.png", 2), ("bordered.png", 2),
])
def test_exit_codes(fixture_paths, name, code, capsys):
    assert run(["check", str(fixture_paths[name]), "--profile", BLEED], capsys)[0] == code


def test_text_is_default_output(fixture_paths, capsys):
    code, out = run(["check", str(fixture_paths["off_centre.png"]), "--profile", BLEED], capsys)
    assert code == 2
    assert out.splitlines()[0] == "status: fail"
    assert "centering_delta_px: x=45.0 y=0.0" in out
    assert out.splitlines()[-1] == "reasons: EDGE_COVERAGE_LOW, OFF_CENTER"


def test_out_writes_json_only_there(fixture_paths, tmp_path, capsys):
    out_file = tmp_path / "r.json"
    code, out = run(["check", str(fixture_paths["solid.png"]), "--profile", BLEED, "--text",
                     "--out", str(out_file)], capsys)
    assert code == 0 and out.startswith("status: pass")
    assert json.loads(out_file.read_text())["status"] == "pass"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["r.json"]


def test_json_and_text_are_exclusive(fixture_paths, capsys):
    assert main(["check", str(fixture_paths["solid.png"]), "--profile", BLEED, "--json", "--text"]) == 3


def test_usage_error_is_exit_3(capsys):
    assert main(["check"]) == 3
    assert main([]) == 3


def test_missing_image(tmp_path, capsys):
    code, out = run(["check", str(tmp_path / "nope.png"), "--profile", BLEED, "--json"], capsys)
    assert code == 3
    assert json.loads(out)["error"] == "IMAGE_UNREADABLE"


def test_not_an_image(tmp_path, capsys):
    bad = tmp_path / "x.png"
    bad.write_bytes(b"not an image")
    code, out = run(["check", str(bad), "--profile", BLEED, "--json"], capsys)
    assert (code, json.loads(out)["error"]) == (3, "IMAGE_UNREADABLE")


def test_unsupported_format(tmp_path, capsys):
    gif = tmp_path / "a.gif"
    Image.new("RGB", (4, 4)).save(gif)
    code, out = run(["check", str(gif), "--profile", BLEED], capsys)
    assert code == 3 and "error: UNSUPPORTED_FORMAT" in out


@pytest.mark.parametrize("body,fragment", [
    ("{", "not valid JSON"),
    ("[]", "JSON object"),
    ('{"print_width_in": 1}', "missing fields"),
    (json.dumps(dict(json.loads((PROFILES / "bleed.json").read_text()), dpi_target=0)), "dpi_target"),
    (json.dumps(dict(json.loads((PROFILES / "bleed.json").read_text()), bleed_in=-1)), "bleed_in"),
    (json.dumps(dict(json.loads((PROFILES / "bleed.json").read_text()), dpi_warn="300")), "dpi_warn"),
    (json.dumps(dict(json.loads((PROFILES / "bleed.json").read_text()), edge_coverage_min=1.5)), "<= 1"),
    (json.dumps(dict(json.loads((PROFILES / "bleed.json").read_text()), bogus=1)), "unknown"),
    (json.dumps(dict(json.loads((PROFILES / "bleed.json").read_text()), background_rgb=[1, 2])), "background_rgb"),
])
def test_invalid_profiles(tmp_path, body, fragment, fixture_paths, capsys):
    p = tmp_path / "p.json"
    p.write_text(body)
    with pytest.raises(PreflightError) as exc:
        load_profile(p)
    assert exc.value.code == "PROFILE_INVALID" and fragment in exc.value.message
    assert main(["check", str(fixture_paths["solid.png"]), "--profile", str(p)]) == 3


def test_missing_profile(fixture_paths, tmp_path, capsys):
    assert main(["check", str(fixture_paths["solid.png"]), "--profile", str(tmp_path / "none.json")]) == 3


def test_exif_orientation_is_applied(tmp_path):
    img = Image.new("RGB", (255, 330), (200, 30, 40))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 CW on display -> 330 x 255
    path = tmp_path / "rot.jpg"
    img.save(path, exif=exif, quality=95)
    assert check(path, PROFILES / "bleed.json")["status"] == "pass"


def test_module_entry_point(fixture_paths):
    proc = subprocess.run(
        [sys.executable, "-m", "print_preflight", "check", str(fixture_paths["low_res.png"]),
         "--profile", BLEED, "--json"],
        capture_output=True, text=True, check=False,
        env={**os.environ, "PYTHONPATH": str(TESTS.parent / "src")},
    )
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["reasons"] == ["DPI_BELOW_WARN"]


def test_every_code_documented_in_readme():
    from print_preflight import REASONS

    readme = (TESTS.parent / "README.md").read_text(encoding="utf-8")
    for code in [*REASONS, "IMAGE_UNREADABLE", "UNSUPPORTED_FORMAT", "PROFILE_INVALID"]:
        assert f"| `{code}` |" in readme, code
