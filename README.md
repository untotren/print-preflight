# print-preflight

A deterministic raster preflight library and command-line interface for print-ready artwork reports.

It checks a local PNG, JPEG or TIFF against a target print profile and reports
resolution, aspect ratio, content-box coverage, edge (bleed) coverage and
centering. Pillow is the only dependency. No network, no model calls, no
uploads, and nothing is written except the optional `--out` JSON report.

## Install and test

```sh
pip install -e '.[test]'
python -m pytest
```

Test fixtures (solid, checkerboard, bordered, transparent-margin, off-centre,
and resolution/aspect variants) are generated at test time by
`scripts/make_fixtures.py`; you can also write them out with
`python scripts/make_fixtures.py OUTDIR`. Golden reports live in
`tests/golden/`; regenerate them after an intentional change with
`PRINT_PREFLIGHT_UPDATE_GOLDEN=1 python -m pytest tests/test_golden.py`.

## CLI

```sh
print-preflight check IMAGE --profile P.json [--json | --text] [--out REPORT.json]
```

`--text` (the default) prints a human-readable summary, `--json` prints the
report as JSON. `--out` additionally writes the JSON report to a file.

| Exit | Meaning |
|------|---------|
| 0 | `pass` |
| 1 | `warn` |
| 2 | `fail` |
| 3 | error: unreadable/unsupported image, invalid profile, or bad usage |

On error the report is `{"status": "error", "error": CODE, "message": ...}`.

## Library

```python
from print_preflight import check, load_profile

report = check("art.png", load_profile("profile.json"))  # or a dict / path
```

`check` also accepts an open Pillow image. Input problems raise
`print_preflight.PreflightError` with a `.code` from the error table below.

## Profile

```json
{
  "print_width_in": 8.0,
  "print_height_in": 10.0,
  "dpi_target": 150,
  "dpi_warn": 300,
  "bleed_in": 0.125,
  "safe_margin_in": 0.125,
  "aspect_tolerance": 0.01,
  "edge_coverage_min": 0.98
}
```

| Field | Meaning |
|-------|---------|
| `print_width_in`, `print_height_in` | Trim size in inches. |
| `bleed_in` | Bleed on each side. The image must cover the **canvas** = trim + 2 × bleed. |
| `dpi_target` | Resolution the image must reach; below it is a **fail**. |
| `dpi_warn` | Resolution below which a **warn** is raised. Set it above `dpi_target` to get a warning band; if it is ≤ `dpi_target` it never fires. |
| `safe_margin_in` | Inset inside the trim line that non-bleeding content should stay within. |
| `aspect_tolerance` | Maximum allowed `aspect_delta` (inclusive). |
| `edge_coverage_min` | Minimum fraction (0–1, inclusive) of each bleed band that must be content when `bleed_in > 0`. |

Optional fields:

| Field | Default | Meaning |
|-------|---------|---------|
| `background_rgb` | `[255, 255, 255]` | Paper colour; pixels this colour are not content. |
| `background_tolerance` | `16` | A pixel is content if any RGB channel differs from `background_rgb` by **more** than this. |
| `alpha_threshold` | `0` | A pixel is content only if its alpha is **greater** than this. |
| `centering_tolerance_in` | `0.0625` | Allowed offset of the content-box centre from the canvas centre, per axis. |

Profile numbers are interpreted by their decimal form (`8.1` means exactly
81/10), and all comparisons are done with exact rational arithmetic.

## Report

```json
{
  "status": "warn",
  "effective_dpi": 150.0,
  "aspect_delta": 0.0,
  "coverage_ratio": 0.2566,
  "centering_delta_px": {"x": 45.0, "y": 0.0},
  "edge_coverage": {"top": 0.0, "right": 0.0, "bottom": 0.0, "left": 0.0},
  "reasons": ["OFF_CENTER"]
}
```

| Key | Meaning |
|-----|---------|
| `status` | `fail` if any fail reason, else `warn` if any warn reason, else `pass`. |
| `effective_dpi` | `min(width_px / canvas_width_in, height_px / canvas_height_in)`, truncated to 2 decimals (never rounded up). |
| `aspect_delta` | `abs((width_px / height_px) / (canvas_w / canvas_h) - 1)`, rounded half-even to 6 decimals. This rounded value is what is compared with `aspect_tolerance`. |
| `coverage_ratio` | Content bounding-box area ÷ image area, truncated to 4 decimals. |
| `centering_delta_px` | `{x, y}` offset of the content-box centre from the image centre in pixels (positive = right / down; may be a half pixel). `null` when there is no content. |
| `edge_coverage` | For each of `top`, `right`, `bottom`, `left`: fraction of that edge band that is content, truncated to 4 decimals. The band is `ceil(bleed_in × ppi)` pixels deep (at least 1), using the axis's pixels-per-inch. |
| `reasons` | Reason codes, in the order listed below. |

### Content detection

A pixel is **content** when it is visible (alpha > `alpha_threshold`) and
differs from `background_rgb` by more than `background_tolerance`. The
**content box** is the bounding box of all content pixels. Art whose content
box touches all four image edges is *full-bleed*; the safe-margin and
centering checks are skipped for it. EXIF orientation is applied before
measuring, and only the first frame of multi-page files is checked.

### Reason codes

| Code | Severity | Raised when |
|------|----------|-------------|
| `DPI_BELOW_TARGET` | fail | Width or height in pixels is below `ceil(canvas_in × dpi_target)`. |
| `DPI_BELOW_WARN` | warn | Not `DPI_BELOW_TARGET`, but width or height is below `ceil(canvas_in × dpi_warn)`. |
| `ASPECT_MISMATCH` | fail | `aspect_delta > aspect_tolerance`. |
| `CONTENT_EMPTY` | fail | No content pixels at all (blank or fully transparent image). Content-box checks below are skipped. |
| `EDGE_COVERAGE_LOW` | fail | `bleed_in > 0` and any edge band's coverage is below `edge_coverage_min` — the art will not reach the trim edge. |
| `CONTENT_OUTSIDE_SAFE` | warn | Art is not full-bleed and its content box comes closer to an image edge than `bleed_in + safe_margin_in`. |
| `OFF_CENTER` | warn | Art is not full-bleed and the content-box centre is more than `centering_tolerance_in` from the image centre on either axis. |

### Error codes (exit 3)

| Code | Raised when |
|------|-------------|
| `IMAGE_UNREADABLE` | The image file is missing or cannot be decoded. |
| `UNSUPPORTED_FORMAT` | The file decodes but is not PNG, JPEG or TIFF. |
| `PROFILE_INVALID` | The profile is missing, not JSON, lacks a field, has an unknown field, or has an out-of-range value. |
