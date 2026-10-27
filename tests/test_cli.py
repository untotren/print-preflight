from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import PROFILE_PATH, TESTS
from print_preflight import REASONS
from print_preflight.cli import main

SRC = TESTS.parent / "src"


@pytest.mark.parametrize(
    "name, code",
    [("solid.png", 0), ("off_centre.png", 1), ("checkerboard.png", 1), ("low_res.png", 2), ("blank.png", 2)],
)
def test_exit_codes(fixture_paths, name, code, capsys):
    assert main(["check", str(fixture_paths[name]), "--profile", str(PROFILE_PATH)]) == code
    assert capsys.readouterr().out.startswith("status: ")


def test_json_output_matches_golden(fixture_paths, capsys):
    assert main(["check", str(fixture_paths["notched_edge.png"]), "--profile", str(PROFILE_PATH), "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    golden = json.loads((TESTS / "golden" / "notched_edge_png.json").read_text())
    assert out == golden


def test_text_output(fixture_paths, capsys):
    main(["check", str(fixture_paths["transparent_margin.png"]), "--profile", str(PROFILE_PATH), "--text"])
    out = capsys.readouterr().out
    assert "status: WARN" in out
    assert "[warn] BLEED_SHORT" in out
    assert "edge_coverage: top=0.4853*, right=0.4900*" in out


def test_out_writes_json_only_there(fixture_paths, tmp_path, capsys):
    out = tmp_path / "report.json"
    assert main(["check", str(fixture_paths["solid.png"]), "--profile", str(PROFILE_PATH), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["status"] == "pass"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["report.json"]


def test_json_and_text_are_exclusive(fixture_paths, capsys):
    argv = ["check", str(fixture_paths["solid.png"]), "--profile", str(PROFILE_PATH), "--json", "--text"]
    assert main(argv) == 3


@pytest.mark.parametrize("argv", [[], ["check"], ["check", "x.png"], ["bogus"]])
def test_usage_errors_exit_3(argv, capsys):
    assert main(argv) == 3


def test_missing_image_exit_3(tmp_path, capsys):
    assert main(["check", str(tmp_path / "nope.png"), "--profile", str(PROFILE_PATH)]) == 3
    assert "image not found" in capsys.readouterr().err


def test_not_an_image_exit_3(tmp_path, capsys):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    assert main(["check", str(bad), "--profile", str(PROFILE_PATH)]) == 3


def test_unsupported_format_exit_3(tmp_path, capsys):
    from PIL import Image

    gif = tmp_path / "a.gif"
    Image.new("RGB", (10, 10)).save(gif, "GIF")
    assert main(["check", str(gif), "--profile", str(PROFILE_PATH)]) == 3
    assert "unsupported image format" in capsys.readouterr().err


@pytest.mark.parametrize(
    "profile_text",
    [
        "{not json",
        "[]",
        '{"print_width_in": 4}',
        json.dumps({**json.loads(PROFILE_PATH.read_text()), "dpi_target": 0}),
        json.dumps({**json.loads(PROFILE_PATH.read_text()), "typo_key": 1}),
        json.dumps({**json.loads(PROFILE_PATH.read_text()), "edge_coverage_min": 1.5}),
        json.dumps({**json.loads(PROFILE_PATH.read_text()), "bleed_in": "0.125"}),
    ],
)
def test_bad_profile_exit_3(fixture_paths, tmp_path, profile_text, capsys):
    p = tmp_path / "p.json"
    p.write_text(profile_text)
    assert main(["check", str(fixture_paths["solid.png"]), "--profile", str(p)]) == 3
    assert "error:" in capsys.readouterr().err


def test_module_entrypoint(fixture_paths):
    proc = subprocess.run(
        [sys.executable, "-m", "print_preflight", "check", str(fixture_paths["low_res.png"]),
         "--profile", str(PROFILE_PATH), "--json"],
        capture_output=True, text=True, env={"PYTHONPATH": str(SRC)}, check=False,
    )
    assert proc.returncode == 2
    assert json.loads(proc.stdout)["reasons"] == ["DPI_BELOW_TARGET"]


def test_fixture_script_runs(tmp_path):
    script = TESTS / "fixtures" / "make_fixtures.py"
    proc = subprocess.run([sys.executable, str(script), str(tmp_path)], capture_output=True, text=True, check=True)
    assert len(proc.stdout.splitlines()) == len(list(tmp_path.iterdir())) == 13


def test_every_reason_code_documented_in_readme():
    readme = (TESTS.parent / "README.md").read_text()
    for code, (severity, _) in REASONS.items():
        assert f"`{code}`" in readme, code
        assert f"| `{code}` | {severity} |" in readme, code
