"""Command-line interface: ``print-preflight check IMAGE --profile P.json``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .checks import check
from .profile import PreflightError

EXIT_CODES = {"pass": 0, "warn": 1, "fail": 2}
EXIT_ERROR = 3


def to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2) + "\n"


def to_text(report: dict[str, Any]) -> str:
    if report["status"] == "error":
        return f"status: error\nerror: {report['error']}\nmessage: {report['message']}\n"
    centering = report["centering_delta_px"]
    edges = report["edge_coverage"]
    lines = [
        f"status: {report['status']}",
        f"effective_dpi: {report['effective_dpi']}",
        f"aspect_delta: {report['aspect_delta']}",
        f"coverage_ratio: {report['coverage_ratio']}",
        "centering_delta_px: " + ("none" if centering is None else f"x={centering['x']} y={centering['y']}"),
        "edge_coverage: " + " ".join(f"{k}={v}" for k, v in edges.items()),
        "reasons: " + (", ".join(report["reasons"]) or "none"),
    ]
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="print-preflight", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    chk = sub.add_parser("check", help="check one raster image against a print profile")
    chk.add_argument("image", help="PNG, JPEG or TIFF file")
    chk.add_argument("--profile", required=True, help="target profile JSON")
    fmt = chk.add_mutually_exclusive_group()
    fmt.add_argument("--json", dest="fmt", action="store_const", const="json", help="print JSON report")
    fmt.add_argument("--text", dest="fmt", action="store_const", const="text", help="print text report (default)")
    chk.add_argument("--out", help="also write the JSON report to this path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse exits 2 on usage errors, which would collide with "fail".
        return 0 if exc.code == 0 else EXIT_ERROR

    try:
        report = check(args.image, args.profile)
        code = EXIT_CODES[report["status"]]
    except PreflightError as exc:
        report = {"status": "error", "error": exc.code, "message": exc.message}
        code = EXIT_ERROR

    if args.out:
        try:
            Path(args.out).write_text(to_json(report), encoding="utf-8")
        except OSError as exc:
            print(f"print-preflight: cannot write {args.out}: {exc}", file=sys.stderr)
            return EXIT_ERROR

    sys.stdout.write(to_json(report) if args.fmt == "json" else to_text(report))
    return code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
