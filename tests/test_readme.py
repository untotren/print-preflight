"""Every reason code must be documented in the README table."""

import re
from pathlib import Path

from print_preflight.reasons import REASONS, markdown_table

README = Path(__file__).resolve().parents[1] / "README.md"
START, END = "<!-- reason-codes:start -->", "<!-- reason-codes:end -->"


def readme_table() -> str:
    text = README.read_text(encoding="utf-8")
    assert START in text and END in text
    return text.split(START, 1)[1].split(END, 1)[0].strip("\n") + "\n"


def test_readme_table_matches_reasons_module():
    assert readme_table() == markdown_table(), "regenerate with: python -c 'from print_preflight.reasons import markdown_table; print(markdown_table())'"


def test_every_code_documented_once():
    codes = re.findall(r"^\| `([A-Z_]+)` \|", readme_table(), re.M)
    assert codes == [r.code for r in REASONS]


def test_codes_are_unique_and_severities_valid():
    assert len({r.code for r in REASONS}) == len(REASONS)
    assert {r.severity for r in REASONS} <= {"fail", "warn"}
