"""Command-line interface: ``print-preflight check IMAGE --profile P.json``.

Exit codes: 0 pass, 1 warn, 2 fail, 3 error (including usage errors).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence, TextIO

from . import __version__
from .checks import REASON_CODES, check_image
from .errors import PreflightError
from .profile import load_profile

EXIT_CODES = {"pass": 0, "warn": 1, "fail": 2}
EXIT_ERROR = 3

REASON_TEXT = {
    "DPI_BELOW_TARGET": "pixel dimensions are below what dpi_target requires",
    "DPI_BELOW_WARN": "pixel dimensions are below what dpi_warn requires",
    "ASPECT_MISMATCH": "aspect ratio differs from the canvas by more than aspect_tolerance",
    "CONTENT_EMPTY": "no non-background content was found",
    "BLEED_SHORT": "content passes the trim line but stops short of the canvas edge",
    "SAFE_MARGIN_INTRUSION": "content ends inside the safe margin",
    "EDGE_COVERAGE_LOW": "a bleeding edge band is not covered enough by content",
    "OFF_CENTER": "content box centre is offset by more than centering_tolerance",
}


class _Parser(argparse.ArgumentParser):
    """argparse exits 2 on usage errors, which would collide with "fail"."""

    def error(self, message: str):  # type: ignore[override]
        self.print_usage(sys.stderr)
        self.exit(EXIT_ERROR, f"{self.prog}: error: USAGE: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="print-preflight", description="Preflight raster artwork for print.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    check = sub.add_parser("check", help="check one image against a profile")
    check.add_argument("image", metavar="IMAGE", help="PNG, JPEG or TIFF file")
    check.add_argument("--profile", required=True, metavar="P.json", help="target profile JSON")
    fmt = check.add_mutually_exclusive_group()
    fmt.add_argument("--json", dest="format", action="store_const", const="json", help="print the JSON report")
    fmt.add_argument("--text", dest="format", action="store_const", const="text", help="print a text summary (default)")
    check.add_argument("--out", metavar="PATH", help="also write the JSON report to PATH")
    check.set_defaults(format="text")
    return parser


def dumps(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def format_text(report: dict[str, Any], image: str) -> str:
    def num(value: Any) -> str:
        return "n/a" if value is None else str(value)

    centre = report["centering_delta_px"]
    edges = report["edge_coverage"]
    lines = [
        f"{image}: {report['status'].upper()}",
        f"  pixels          {report['image_px']['width']} x {report['image_px']['height']}"
        f" (need {'x'.join(map(str, report['required_px']['target']))} for target,"
        f" {'x'.join(map(str, report['required_px']['warn']))} for warn)",
        f"  effective dpi   {report['effective_dpi']}",
        f"  aspect delta    {report['aspect_delta']}",
        f"  coverage ratio  {report['coverage_ratio']}",
        f"  centering (px)  " + ("n/a" if centre is None else f"x={centre['x']} y={centre['y']}"),
        "  edge coverage   " + " ".join(f"{side}={num(edges[side])}" for side in ("top", "right", "bottom", "left")),
    ]
    if report["reasons"]:
        lines.append("  reasons:")
        for code in report["reasons"]:
            lines.append(f"    {REASON_CODES[code].upper():4} {code}: {REASON_TEXT[code]}")
    else:
        lines.append("  reasons: none")
    return "\n".join(lines) + "\n"


def _error(exc: PreflightError, as_json: bool, stdout: TextIO, stderr: TextIO) -> int:
    stderr.write(f"print-preflight: error: {exc.code}: {exc.message}\n")
    if as_json:
        stdout.write(dumps({"status": "error", "error": {"code": exc.code, "message": exc.message}}))
    return EXIT_ERROR


def main(argv: Sequence[str] | None = None, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_ERROR

    as_json = args.format == "json"
    try:
        profile = load_profile(args.profile)
        report = check_image(args.image, profile)
        if args.out:
            try:
                Path(args.out).write_text(dumps(report), encoding="utf-8")
            except OSError as exc:
                raise PreflightError("OUTPUT_UNWRITABLE", f"cannot write {args.out}: {exc}") from exc
    except PreflightError as exc:
        return _error(exc, as_json, stdout, stderr)

    stdout.write(dumps(report) if as_json else format_text(report, args.image))
    return EXIT_CODES[report["status"]]


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
