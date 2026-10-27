import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from print_preflight.cli import main

SRC = Path(__file__).resolve().parents[1] / "src"


@pytest.mark.parametrize(
    "fixture,profile,code",
    [
        ("solid.png", "bleed", 0),
        ("checkerboard.png", "bleed", 1),
        ("solid_tiny.png", "bleed", 2),
    ],
)
def test_exit_codes(fixture, profile, code, fixture_paths, profile_paths, capsys):
    assert main(["check", str(fixture_paths[fixture]), "--profile", str(profile_paths[profile])]) == code


def test_json_output_and_out_file(fixture_paths, profile_paths, tmp_path, capsys):
    out = tmp_path / "report.json"
    rc = main(["check", str(fixture_paths["off_centre.png"]), "--profile", str(profile_paths["flat"]), "--json", "--out", str(out)])
    assert rc == 1
    stdout = capsys.readouterr().out
    assert json.loads(stdout)["reasons"] == ["OFF_CENTER"]
    assert out.read_text() == stdout


def test_text_output_is_default(fixture_paths, profile_paths, capsys):
    main(["check", str(fixture_paths["bordered.png"]), "--profile", str(profile_paths["bleed"])])
    text = capsys.readouterr().out
    assert text.startswith("status: FAIL\n")
    assert "  BLEED_NOT_REACHED (fail)\n" in text
    assert "  EDGE_COVERAGE_LOW (warn)\n" in text
    assert main(["check", str(fixture_paths["solid.png"]), "--profile", str(profile_paths["bleed"]), "--text"]) == 0
    assert "reasons: none" in capsys.readouterr().out


def test_text_output_without_content(fixture_paths, profile_paths, capsys):
    main(["check", str(fixture_paths["blank.png"]), "--profile", str(profile_paths["bleed"])])
    assert "centering delta: n/a" in capsys.readouterr().out


def test_no_files_written_without_out(fixture_paths, profile_paths, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["check", str(fixture_paths["solid.png"]), "--profile", str(profile_paths["bleed"]), "--json"])
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["check"],
        ["check", "x.png"],
        ["check", "x.png", "--profile", "p.json", "--json", "--text"],
        ["bogus"],
    ],
)
def test_usage_errors_exit_3(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 3


def test_missing_image_exit_3(profile_paths, tmp_path, capsys):
    assert main(["check", str(tmp_path / "nope.png"), "--profile", str(profile_paths["bleed"])]) == 3
    assert "image not found" in capsys.readouterr().err


def test_unsupported_format_exit_3(profile_paths, tmp_path, capsys):
    from PIL import Image

    gif = tmp_path / "a.gif"
    Image.new("RGB", (10, 10)).save(gif)
    assert main(["check", str(gif), "--profile", str(profile_paths["bleed"])]) == 3
    assert "unsupported image format GIF" in capsys.readouterr().err


def test_not_an_image_exit_3(profile_paths, tmp_path, capsys):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    assert main(["check", str(bad), "--profile", str(profile_paths["bleed"])]) == 3


def test_bad_profile_exit_3(fixture_paths, tmp_path, capsys):
    prof = tmp_path / "p.json"
    prof.write_text("{")
    assert main(["check", str(fixture_paths["solid.png"]), "--profile", str(prof)]) == 3
    assert "not valid JSON" in capsys.readouterr().err
    assert main(["check", str(fixture_paths["solid.png"]), "--profile", str(tmp_path / "missing.json")]) == 3


def test_unwritable_out_exit_3(fixture_paths, profile_paths, tmp_path, capsys):
    out = tmp_path / "no" / "such" / "dir" / "r.json"
    assert main(["check", str(fixture_paths["solid.png"]), "--profile", str(profile_paths["bleed"]), "--out", str(out)]) == 3


def test_module_entry_point(fixture_paths, profile_paths):
    env = dict(os.environ, PYTHONPATH=str(SRC))
    proc = subprocess.run(
        [sys.executable, "-m", "print_preflight", "check", str(fixture_paths["checkerboard.png"]), "--profile", str(profile_paths["bleed"]), "--json"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 1, proc.stderr
    assert json.loads(proc.stdout)["status"] == "warn"
