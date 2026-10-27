import io
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from print_preflight.cli import main

from conftest import ROOT


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    code = main(argv, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


@pytest.mark.parametrize(
    "name, code",
    [("solid.png", 0), ("solid_lowres.png", 1), ("checkerboard.png", 1), ("solid_tiny.png", 2), ("blank.png", 2)],
)
def test_exit_codes(fixtures, standard_profile_path, name, code):
    assert run(["check", str(fixtures[name]), "--profile", str(standard_profile_path)])[0] == code


def test_text_is_default(fixtures, standard_profile_path):
    args = ["check", str(fixtures["solid_lowres.png"]), "--profile", str(standard_profile_path)]
    code, out, err = run(args)
    assert code == 1 and err == ""
    assert out.splitlines()[0].endswith(": WARN")
    assert "WARN DPI_BELOW_WARN" in out
    assert run(args + ["--text"])[1] == out


def test_json_output(fixtures, standard_profile_path):
    code, out, _ = run(["check", str(fixtures["solid_tiny.png"]), "--profile", str(standard_profile_path), "--json"])
    report = json.loads(out)
    assert code == 2
    assert report["status"] == "fail"
    assert report["reasons"] == ["DPI_BELOW_TARGET"]


def test_out_writes_same_json(fixtures, standard_profile_path, tmp_path):
    out_file = tmp_path / "report.json"
    args = ["check", str(fixtures["bordered.png"]), "--profile", str(standard_profile_path)]
    code, stdout, _ = run(args + ["--json", "--out", str(out_file)])
    assert code == 0
    assert out_file.read_text() == stdout
    # --out is independent of the stdout format.
    out_file.unlink()
    code, stdout, _ = run(args + ["--out", str(out_file)])
    assert json.loads(out_file.read_text())["status"] == "pass"
    assert "PASS" in stdout


def test_out_unwritable(fixtures, standard_profile_path, tmp_path):
    code, out, err = run(
        ["check", str(fixtures["solid.png"]), "--profile", str(standard_profile_path), "--json",
         "--out", str(tmp_path / "missing-dir" / "r.json")]
    )
    assert code == 3
    assert json.loads(out)["error"]["code"] == "OUTPUT_UNWRITABLE"


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["check"],
        ["check", "x.png"],
        ["frobnicate", "x.png", "--profile", "p.json"],
        ["check", "x.png", "--profile", "p.json", "--json", "--text"],
    ],
)
def test_usage_errors_exit_3(argv, capsys):
    assert main(argv) == 3
    assert "USAGE" in capsys.readouterr().err


def test_help_exits_0(capsys):
    assert main(["--help"]) == 0
    assert main(["check", "--help"]) == 0
    assert "--profile" in capsys.readouterr().out


def test_missing_image_error(standard_profile_path, tmp_path):
    code, out, err = run(["check", str(tmp_path / "nope.png"), "--profile", str(standard_profile_path), "--json"])
    assert code == 3
    assert json.loads(out) == {
        "status": "error",
        "error": {"code": "IMAGE_NOT_FOUND", "message": f"no such image file: {tmp_path / 'nope.png'}"},
    }
    assert "IMAGE_NOT_FOUND" in err


def test_text_mode_error_goes_to_stderr_only(standard_profile_path, tmp_path):
    code, out, err = run(["check", str(tmp_path / "nope.png"), "--profile", str(standard_profile_path)])
    assert (code, out) == (3, "")
    assert err.startswith("print-preflight: error: IMAGE_NOT_FOUND")


@pytest.mark.parametrize("content, code", [("{", "PROFILE_UNREADABLE"), ('{"dpi_target": 300}', "PROFILE_INVALID")])
def test_bad_profile(fixtures, tmp_path, content, code):
    profile = tmp_path / "p.json"
    profile.write_text(content)
    exit_code, out, _ = run(["check", str(fixtures["solid.png"]), "--profile", str(profile), "--json"])
    assert exit_code == 3
    assert json.loads(out)["error"]["code"] == code


def test_unsupported_format(standard_profile_path, tmp_path):
    gif = tmp_path / "a.gif"
    Image.new("RGB", (8, 8)).save(gif)
    code, out, _ = run(["check", str(gif), "--profile", str(standard_profile_path), "--json"])
    assert code == 3
    assert json.loads(out)["error"]["code"] == "IMAGE_FORMAT_UNSUPPORTED"


def test_no_writes_and_no_network(fixtures, standard_profile_path, tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    before = {p: p.stat().st_mtime_ns for p in Path(fixtures["solid.png"]).parent.iterdir()}
    for path in fixtures.values():
        run(["check", str(path), "--profile", str(standard_profile_path), "--json"])
        run(["check", str(path), "--profile", str(standard_profile_path), "--text"])
    assert list(work.iterdir()) == []
    assert {p: p.stat().st_mtime_ns for p in Path(fixtures["solid.png"]).parent.iterdir()} == before


def test_module_entry_point(fixtures, standard_profile_path):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "-m", "print_preflight", "check", str(fixtures["off_centre.png"]),
         "--profile", str(standard_profile_path), "--json"],
        capture_output=True, text=True, env=env, check=False,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["reasons"] == ["OFF_CENTER"]

    usage = subprocess.run(
        [sys.executable, "-m", "print_preflight", "check"], capture_output=True, text=True, env=env, check=False
    )
    assert usage.returncode == 3
