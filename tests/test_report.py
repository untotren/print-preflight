"""Library and CLI behaviour against generated fixtures and golden reports."""

import json
import os
from pathlib import Path

import pytest
from PIL import Image

from print_preflight import PreflightError, preflight
from print_preflight.cli import main

GOLDEN = Path(__file__).parent / "golden"
UPDATE = os.environ.get("PRINT_PREFLIGHT_UPDATE_GOLDEN") == "1"
REPORT_KEYS = {
    "status",
    "effective_dpi",
    "aspect_delta",
    "coverage_ratio",
    "centering_delta_px",
    "edge_coverage",
    "reasons",
}
NAMES = ["solid", "checkerboard", "bordered", "transparent_margin", "off_centre"]


@pytest.mark.parametrize("name", NAMES)
def test_golden_report(fixtures, profile_dict, name):
    report = preflight(fixtures[name], profile_dict)
    golden = GOLDEN / f"{name}.json"
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if UPDATE:
        golden.write_text(rendered)
    assert set(report) == REPORT_KEYS
    assert rendered == golden.read_text()


def test_fixture_generation_is_deterministic(fixtures, tmp_path):
    import make_fixtures

    again = make_fixtures.generate(tmp_path)
    for name in ("solid", "bordered", "transparent_margin", "off_centre"):  # lossless formats
        assert again[name].read_bytes() == fixtures[name].read_bytes()


@pytest.mark.parametrize(
    "name, code", [("solid", 0), ("checkerboard", 1), ("bordered", 1), ("transparent_margin", 2)]
)
def test_cli_exit_codes(fixtures, profile_path, name, code, capsys):
    assert main(["check", str(fixtures[name]), "--profile", str(profile_path), "--json"]) == code
    report = json.loads(capsys.readouterr().out)
    assert report == json.loads((GOLDEN / f"{name}.json").read_text())


def test_cli_text_output(fixtures, profile_path, capsys):
    assert main(["check", str(fixtures["bordered"]), "--profile", str(profile_path), "--text"]) == 1
    out = capsys.readouterr().out
    assert "status: WARN" in out
    assert "effective_dpi: 100.0" in out
    assert "reasons: DPI_BELOW_WARN" in out


def test_cli_defaults_to_text(fixtures, profile_path, capsys):
    assert main(["check", str(fixtures["solid"]), "--profile", str(profile_path)]) == 0
    assert "status: PASS" in capsys.readouterr().out


def test_cli_out_file(fixtures, profile_path, tmp_path, capsys):
    out = tmp_path / "report.json"
    main(["check", str(fixtures["solid"]), "--profile", str(profile_path), "--out", str(out)])
    assert json.loads(out.read_text()) == json.loads((GOLDEN / "solid.json").read_text())


def test_cli_writes_nothing_without_out(fixtures, profile_path, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["check", str(fixtures["solid"]), "--profile", str(profile_path), "--json"])
    assert list(tmp_path.iterdir()) == []


def test_cli_missing_image_is_error(profile_path, tmp_path, capsys):
    code = main(["check", str(tmp_path / "nope.png"), "--profile", str(profile_path), "--json"])
    assert code == 3
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "error"
    assert report["reasons"] == ["IMAGE_UNREADABLE"]


def test_cli_bad_profile_is_error(fixtures, tmp_path, capsys):
    bad = tmp_path / "p.json"
    bad.write_text("{}")
    assert main(["check", str(fixtures["solid"]), "--profile", str(bad), "--json"]) == 3
    assert json.loads(capsys.readouterr().out)["reasons"] == ["PROFILE_INVALID"]


def test_cli_usage_error_exits_3(capsys):
    with pytest.raises(SystemExit) as info:
        main(["check", "x.png"])  # --profile missing
    assert info.value.code == 3


def test_unsupported_format(profile_dict, tmp_path):
    path = tmp_path / "img.bmp"
    Image.new("RGB", (400, 600)).save(path)
    with pytest.raises(PreflightError) as info:
        preflight(path, profile_dict)
    assert info.value.code == "IMAGE_UNSUPPORTED"


def test_not_an_image(profile_dict, tmp_path):
    path = tmp_path / "img.png"
    path.write_bytes(b"definitely not a png")
    with pytest.raises(PreflightError) as info:
        preflight(path, profile_dict)
    assert info.value.code == "IMAGE_UNREADABLE"
