import re

from conftest import ROOT
from print_preflight import REASONS


def test_every_reason_code_is_documented():
    readme = (ROOT / "README.md").read_text()
    documented = set(re.findall(r"^\| `([A-Z_]+)` \| (?:fail|warn) \|", readme, re.M))
    assert documented == set(REASONS)


def test_documented_severities_match():
    readme = (ROOT / "README.md").read_text()
    for code, (sev, _) in REASONS.items():
        assert f"| `{code}` | {sev} |" in readme
