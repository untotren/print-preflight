"""``print-preflight check IMAGE --profile P.json [--json|--text] [--out R.json]``

Exit codes: 0 pass, 1 warn, 2 fail, 3 error (including usage errors).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .core import check
from .errors import PreflightError
from .reasons import REASONS

EXIT_CODES = {"pass": 0, "warn": 1, "fail": 2}
EXIT_ERROR = 3


class _Parser(argparse.ArgumentParser):
    # argparse exits 2 on usage errors, which would collide with "fail".
    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        self.exit(EXIT_ERROR, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="print-preflight", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    p = sub.add_parser("check", help="check an image against a print profile")
    p.add_argument("image", help="PNG, JPEG or TIFF file")
    p.add_argument("--profile", required=True, help="target profile JSON file")
    fmt = p.add_mutually_exclusive_group()
    fmt.add_argument("--json", dest="fmt", action="store_const", const="json",
                     help="print the report as JSON")
    fmt.add_argument("--text", dest="fmt", action="store_const", const="text",
                     help="print a human-readable report (default)")
    p.add_argument("--out", help="also write the JSON report to this path")
    p.set_defaults(fmt="text")
    return parser


def to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2) + "\n"


def to_text(report: dict[str, Any]) -> str:
    c = report["centering_delta_px"]
    e = report["edge_coverage"]
    lines = [
        f"status: {report['status']}",
        f"effective_dpi: {report['effective_dpi']}",
        f"aspect_delta: {report['aspect_delta']}",
        f"coverage_ratio: {report['coverage_ratio']}",
        f"centering_delta_px: x={c['x']} y={c['y']}",
        "edge_coverage: " + " ".join(f"{k}={v}" for k, v in e.items()),
    ]
    if report["reasons"]:
        lines.append("reasons:")
        for code in report["reasons"]:
            sev, desc = REASONS[code]
            lines.append(f"  - {code} ({sev}): {desc}")
    else:
        lines.append("reasons: none")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = check(args.image, args.profile)
        if args.out:
            try:
                Path(args.out).write_text(to_json(report), encoding="utf-8")
            except OSError as exc:
                raise PreflightError("OUTPUT_UNWRITABLE", f"cannot write {args.out}: {exc}") from None
    except PreflightError as exc:
        if args.fmt == "json":
            sys.stdout.write(to_json({"status": "error",
                                      "error": {"code": exc.code, "message": exc.message}}))
        print(f"print-preflight: error: {exc.code}: {exc.message}", file=sys.stderr)
        return EXIT_ERROR
    sys.stdout.write(to_json(report) if args.fmt == "json" else to_text(report))
    return EXIT_CODES[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
