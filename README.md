# print-preflight

A deterministic raster preflight library and command-line interface for print-ready artwork reports.

Runs locally on PNG, JPEG and TIFF files using Pillow only: no network, no model
calls, no uploads, and no file writes except the optional `--out` report.

> Status: **T1** — package skeleton and the pixel-dimension / DPI check. The
> aspect, bleed/safe-margin coverage, edge-coverage and centering checks are not
> implemented yet; their report fields are `null` until they land.

## Install

```sh
pip install -e .            # library + CLI
pip install -e '.[test]'    # plus pytest and hypothesis
```

## CLI

```sh
print-preflight check IMAGE --profile P.json [--json | --text] [--out REPORT.json]
```

- `--text` (default) prints a human-readable summary; `--json` prints the report as JSON.
- `--out` additionally writes the JSON report to the given path.

| Exit code | Meaning |
|-----------|---------|
| 0 | `pass` |
| 1 | `warn` |
| 2 | `fail` |
| 3 | error: unreadable/unsupported image, invalid profile, bad arguments, or `--out` not writable |

On error the JSON output is `{"status": "error", "reasons": [CODE], "message": "..."}`.

## Library

```python
from print_preflight import preflight, Profile, PreflightError

report = preflight("art.png", Profile.load("profile.json"))  # or pass a dict
```

`preflight` raises `PreflightError` (with a `.code` from the table below) when it
cannot produce a report.

## Profile

```json
{
  "print_width_in": 8.5,
  "print_height_in": 11,
  "dpi_target": 300,
  "dpi_warn": 360,
  "bleed_in": 0.125,
  "safe_margin_in": 0.25,
  "aspect_tolerance": 0.01,
  "edge_coverage_min": 0.98
}
```

All keys are required and must be finite numbers; unknown keys are rejected.
`print_width_in`, `print_height_in`, `dpi_target`, `dpi_warn` must be > 0;
`bleed_in`, `safe_margin_in`, `aspect_tolerance` must be >= 0;
`edge_coverage_min` must be within [0, 1].

`dpi_target` is the hard minimum (below it the check **fails**); `dpi_warn` is the
comfortable resolution (below it the check **warns**). Therefore `dpi_warn` must be
`>= dpi_target`; set them equal to disable the warning band.

## Report

```json
{
  "status": "pass | warn | fail",
  "effective_dpi": 150.154,
  "aspect_delta": null,
  "coverage_ratio": null,
  "centering_delta_px": null,
  "edge_coverage": null,
  "reasons": []
}
```

`status` is the most severe result of all checks. `reasons` lists the codes of
every check that did not pass, in check order.

### DPI check

The image is expected to cover the full **canvas**: trim size plus `bleed_in` on
every side, i.e. `(print_width_in + 2·bleed_in) × (print_height_in + 2·bleed_in)`.
Embedded DPI metadata is ignored; resolution is derived from pixels and the canvas.

- Required pixels at a DPI `d` are `ceil(canvas_in × d)` per axis, computed with
  exact decimal arithmetic (so 8.5 in × 300 dpi requires exactly 2550 px).
- An image meets `d` iff both axes have at least the required pixels.
- `effective_dpi` is `min(width_px / canvas_width_in, height_px / canvas_height_in)`,
  rounded to 3 decimal places for display only; the status is decided on exact values.

## Reason codes

| Code | Severity | Meaning |
|------|----------|---------|
| `DPI_BELOW_TARGET` | fail | Width or height is below `ceil(canvas_in × dpi_target)` pixels. |
| `DPI_BELOW_WARN` | warn | Meets `dpi_target` but width or height is below `ceil(canvas_in × dpi_warn)` pixels. |
| `PROFILE_INVALID` | error | Profile file unreadable, not JSON, or a key is missing, unknown, or out of range. |
| `IMAGE_UNREADABLE` | error | Image file missing, unreadable, or not a recognisable image. |
| `IMAGE_UNSUPPORTED` | error | Image decoded but is not PNG, JPEG, or TIFF. |

## Tests

```sh
python -m pytest
```

Fixture images (solid, checkerboard, bordered, transparent-margin, off-centre) are
generated at test time by the committed script `tests/fixtures/make_fixtures.py`
(`python tests/fixtures/make_fixtures.py OUTDIR` to inspect them). Reports are
compared with golden files in `tests/golden/`; after an intentional change,
regenerate them with `PRINT_PREFLIGHT_UPDATE_GOLDEN=1 python -m pytest` and review
the diff. DPI rounding boundaries are covered by hypothesis property tests.
