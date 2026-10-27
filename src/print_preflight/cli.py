"""Command-line interface: ``print-preflight check IMAGE --profile P.json``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .analysis import SIDES, preflight
from .errors import PreflightError
from .profile import load_profile
from .reasons import REASONS

EXIT_CODES = {"pass": 0, "warn": 1, "fail": 2}
EXIT_ERROR = 3


def report_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2) + "\n"


def report_text(report: dict[str, Any]) -> str:
    img = report["image"]
    req = report["required_px"]
    lines = [
        f"status: {report['status'].upper()}",
        f"image: {img['width_px']} x {img['height_px']} px",
        f"effective_dpi: {report['effective_dpi']:.2f}"
        f" (target needs {req['target']['width']} x {req['target']['height']} px,"
        f" warn needs {req['warn']['width']} x {req['warn']['height']} px)",
        f"aspect_delta: {report['aspect_delta']:.6f}",
        f"coverage_ratio: {report['coverage_ratio']:.4f}",
    ]
    centering = report["centering_delta_px"]
    lines.append(
        "centering_delta_px: n/a" if centering is None else f"centering_delta_px: x={centering['x']:+g} y={centering['y']:+g}"
    )
    must = set(report["must_bleed"])
    edges = ", ".join(
        f"{side}={report['edge_coverage'][side]:.4f}{'*' if side in must else ''}" for side in SIDES
    )
    lines.append(f"edge_coverage: {edges}" + ("  (* must bleed)" if must else ""))
    if report["reasons"]:
        lines.append("reasons:")
        for code in report["reasons"]:
            sev, text = REASONS[code]
            lines.append(f"  [{sev}] {code}: {text}")
    else:
        lines.append("reasons: none")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="print-preflight", description="Deterministic raster preflight for print.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="check an image against a target profile")
    check.add_argument("image", help="PNG, JPEG or TIFF file")
    check.add_argument("--profile", required=True, help="target profile JSON file")
    fmt = check.add_mutually_exclusive_group()
    fmt.add_argument("--json", dest="format", action="store_const", const="json", help="print the JSON report")
    fmt.add_argument("--text", dest="format", action="store_const", const="text", help="print a text summary (default)")
    check.add_argument("--out", help="also write the JSON report to this path")
    check.set_defaults(format="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse exits 2 on usage errors; 2 means "fail" here, so map to 3.
        return 0 if exc.code == 0 else EXIT_ERROR

    try:
        profile = load_profile(args.profile)
        report = preflight(args.image, profile)
    except PreflightError as exc:
        print(f"print-preflight: error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.out:
        try:
            Path(args.out).write_text(report_json(report), encoding="utf-8")
        except OSError as exc:
            print(f"print-preflight: error: cannot write {args.out}: {exc.strerror or exc}", file=sys.stderr)
            return EXIT_ERROR

    sys.stdout.write(report_json(report) if args.format == "json" else report_text(report))
    return EXIT_CODES[report["status"]]
