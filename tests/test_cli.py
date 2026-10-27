import json
import subprocess
import sys

import pytest

from conftest import ROOT, GOLDEN
from print_preflight.cli import main

EXPECTED_EXIT = {"solid": 0, "bordered": 0, "checkerboard": 1, "low-res": 1,
                 "transparent-margin": 1, "off-centre": 1, "tiny": 2, "rotated": 2,
                 "bleed-short": 2, "blank": 2}


@pytest.mark.parametrize("name,code", EXPECTED_EXIT.items())
def test_exit_codes_and_json(name, code, fixtures, standard_profile_path, capsys):
    rc = main(["check", str(fixtures[name]), "--profile", str(standard_profile_path), "--json"])
    out = capsys.readouterr().out
    assert rc == code
    assert out == (GOLDEN / f"{name}.json").read_text()


def test_text_output(fixtures, standard_profile_path, capsys):
    rc = main(["check", str(fixtures["checkerboard"]), "--profile", str(standard_profile_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert out.startswith("status: warn\n")
    assert "EDGE_COVERAGE_LOW (warn)" in out
    assert "edge_coverage: top=0.5 right=0.5 bottom=0.5 left=0.5" in out


def test_out_writes_json(fixtures, standard_profile_path, tmp_path, capsys):
    out = tmp_path / "report.json"
    rc = main(["check", str(fixtures["tiny"]), "--profile", str(standard_profile_path),
               "--text", "--out", str(out)])
    assert rc == 2
    assert out.read_text() == (GOLDEN / "tiny.json").read_text()
    assert capsys.readouterr().out.startswith("status: fail")


def test_missing_image_is_error(standard_profile_path, tmp_path, capsys):
    rc = main(["check", str(tmp_path / "x.png"), "--profile", str(standard_profile_path), "--json"])
    assert rc == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "IMAGE_NOT_FOUND"


def test_garbage_image_is_error(standard_profile_path, tmp_path, capsys):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    assert main(["check", str(bad), "--profile", str(standard_profile_path)]) == 3
    assert "IMAGE_UNREADABLE" in capsys.readouterr().err


def test_unsupported_format_is_error(standard_profile_path, tmp_path, capsys):
    from PIL import Image
    gif = tmp_path / "a.gif"
    Image.new("RGB", (10, 10)).save(gif)
    assert main(["check", str(gif), "--profile", str(standard_profile_path)]) == 3
    assert "UNSUPPORTED_FORMAT" in capsys.readouterr().err


def test_invalid_profile_is_error(fixtures, tmp_path, capsys):
    p = tmp_path / "p.json"
    p.write_text("{}")
    assert main(["check", str(fixtures["solid"]), "--profile", str(p)]) == 3
    assert "PROFILE_INVALID" in capsys.readouterr().err


def test_unwritable_out_is_error(fixtures, standard_profile_path, tmp_path):
    rc = main(["check", str(fixtures["solid"]), "--profile", str(standard_profile_path),
               "--out", str(tmp_path / "missing-dir" / "r.json")])
    assert rc == 3


@pytest.mark.parametrize("argv", [[], ["check"], ["check", "a.png"],
                                  ["check", "a.png", "--profile", "p", "--json", "--text"]])
def test_usage_errors_exit_3(argv):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 3


def test_module_entry_point(fixtures, standard_profile_path):
    proc = subprocess.run(
        [sys.executable, "-m", "print_preflight", "check", str(fixtures["solid"]),
         "--profile", str(standard_profile_path), "--json"],
        capture_output=True, text=True, cwd=ROOT, env={"PYTHONPATH": str(ROOT / "src")},
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["status"] == "pass"


def test_no_files_written_without_out(fixtures, standard_profile_path, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["check", str(fixtures["solid"]), "--profile", str(standard_profile_path), "--json"])
    assert list(tmp_path.iterdir()) == []
