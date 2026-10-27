"""Command-line interface: ``print-preflight check IMAGE --profile P.json``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .core import preflight
from .errors import PreflightError
from .profile import Profile

EXIT_CODES = {"pass": 0, "warn": 1, "fail": 2, "error": 3}


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # usage errors exit 3, not argparse's default 2
        self.print_usage(sys.stderr)
        self.exit(EXIT_CODES["error"], f"{self.prog}: error: {message}\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="print-preflight")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    check = sub.add_parser("check", help="check a raster image against a print profile")
    check.add_argument("image", metavar="IMAGE")
    check.add_argument("--profile", required=True, metavar="P.json")
    fmt = check.add_mutually_exclusive_group()
    fmt.add_argument("--json", dest="format", action="store_const", const="json")
    fmt.add_argument("--text", dest="format", action="store_const", const="text")
    check.add_argument("--out", metavar="REPORT.json", help="also write the JSON report here")
    check.set_defaults(format="text")
    return parser


def _to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def _to_text(report: dict[str, Any]) -> str:
    lines = [f"status: {report['status'].upper()}"]
    if "message" in report:
        lines.append(f"error: {report['message']}")
    for key in ("effective_dpi", "aspect_delta", "coverage_ratio", "centering_delta_px", "edge_coverage"):
        if key in report:
            value = report[key]
            lines.append(f"{key}: {'n/a' if value is None else value}")
    lines.append("reasons: " + (", ".join(report["reasons"]) or "none"))
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        report = preflight(args.image, Profile.load(args.profile))
    except PreflightError as exc:
        report = {"status": "error", "reasons": [exc.code], "message": exc.message}

    rendered = _to_json(report) if args.format == "json" else _to_text(report)
    sys.stdout.write(rendered)
    if args.out:
        try:
            Path(args.out).write_text(_to_json(report), encoding="utf-8")
        except OSError as exc:
            print(f"print-preflight: cannot write --out file: {exc}", file=sys.stderr)
            return EXIT_CODES["error"]
    return EXIT_CODES[report["status"]]
