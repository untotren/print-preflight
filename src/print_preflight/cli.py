"""Command-line interface: ``print-preflight check IMAGE --profile P.json``.

Exit codes: 0 pass, 1 warn, 2 fail, 3 error (including usage errors).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import check_image
from .errors import PreflightError
from .profile import load_profile
from .reasons import BY_CODE

EXIT_CODES = {"pass": 0, "warn": 1, "fail": 2}
EXIT_ERROR = 3


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # argparse would exit 2, which means "fail" here
        self.print_usage(sys.stderr)
        self.exit(EXIT_ERROR, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="print-preflight", description="Deterministic raster preflight for print artwork.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    check = sub.add_parser("check", help="check an image against a target profile")
    check.add_argument("image", metavar="IMAGE", help="PNG, JPEG or TIFF file")
    check.add_argument("--profile", required=True, metavar="P.json", help="target profile JSON")
    fmt = check.add_mutually_exclusive_group()
    fmt.add_argument("--json", dest="output", action="store_const", const="json", help="print the JSON report")
    fmt.add_argument("--text", dest="output", action="store_const", const="text", help="print a text summary (default)")
    check.add_argument("--out", metavar="FILE", help="also write the JSON report to FILE")
    check.set_defaults(output="text")
    return parser


def to_json(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def to_text(report: dict) -> str:
    img = report["image"]
    req = report["required_px"]
    edge = report["edge_coverage"]
    centre = report["centering_delta_px"]
    lines = [
        f"status: {report['status'].upper()}",
        f"image: {img['width_px']}x{img['height_px']} px ({img['format']}, {img['mode']})",
        f"effective dpi: {report['effective_dpi']:.2f}"
        f" (needs {req['target']['width']}x{req['target']['height']} px for target,"
        f" {req['warn']['width']}x{req['warn']['height']} px for warn)",
        f"aspect delta: {report['aspect_delta']:.6f}",
        f"coverage ratio: {report['coverage_ratio']:.6f}",
        "centering delta: " + ("n/a" if centre is None else f"x={centre['x']:+g} px, y={centre['y']:+g} px"),
        "edge coverage: " + ", ".join(f"{k}={edge[k]:.6f}" for k in ("top", "right", "bottom", "left")),
        f"must bleed: {'yes' if report['must_bleed'] else 'no'}",
    ]
    if report["reasons"]:
        lines.append("reasons:")
        lines += [f"  {code} ({BY_CODE[code].severity})" for code in report["reasons"]]
    else:
        lines.append("reasons: none")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        profile = load_profile(args.profile)
        report = check_image(args.image, profile)
    except PreflightError as exc:
        print(f"print-preflight: error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.out:
        try:
            Path(args.out).write_text(to_json(report), encoding="utf-8")
        except OSError as exc:
            print(f"print-preflight: error: cannot write {args.out}: {exc.strerror or exc}", file=sys.stderr)
            return EXIT_ERROR

    sys.stdout.write(to_json(report) if args.output == "json" else to_text(report))
    return EXIT_CODES[report["status"]]
