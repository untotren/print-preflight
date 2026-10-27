import re

from print_preflight import ERROR_CODES, REASON_CODES

from conftest import ROOT

README = (ROOT / "README.md").read_text()


def documented_rows():
    # Table rows look like: | `CODE` | severity | ... |
    return dict(re.findall(r"^\| `([A-Z_]+)` \| (\w+) \|", README, flags=re.M))


def test_every_reason_code_documented_with_severity():
    rows = documented_rows()
    for code, severity in REASON_CODES.items():
        assert rows.get(code) == severity, code


def test_every_error_code_documented():
    rows = documented_rows()
    for code in ERROR_CODES:
        assert rows.get(code) == "error", code


def test_exit_codes_documented():
    for line in ("| 0 | pass", "| 1 | warn", "| 2 | fail", "| 3 | error"):
        assert line in README
