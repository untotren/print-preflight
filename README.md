# print-preflight

A deterministic raster preflight library and command-line interface for print-ready artwork reports.

`print_preflight` checks a local PNG, JPEG or TIFF against a target print profile and
reports whether it will print cleanly: resolution, aspect ratio, bleed, safe margin,
edge coverage and centering. It depends only on Pillow, never touches the network and
writes nothing except the optional `--out` report.

## Install

```sh
pip install .            # library + print-preflight command
pip install '.[test]'    # adds pytest and hypothesis
```

## Command line

```sh
print-preflight check IMAGE --profile P.json [--json | --text] [--out REPORT.json]
python -m print_preflight check IMAGE --profile P.json      # same thing
```

`--text` (the default) prints a summary; `--json` prints the JSON report. `--out`
additionally writes the JSON report to a file; it is the only file the tool writes.

| Exit code | Meaning |
| --- | --- |
| 0 | `pass` |
| 1 | `warn` |
| 2 | `fail` |
| 3 | error: bad arguments, unreadable/invalid profile, missing/unsupported/corrupt image, unwritable `--out` |

## Library

```python
from print_preflight import check_image, load_profile, analyze, Profile

report = check_image("art.tif", load_profile("profile.json"))
report = analyze(pil_image, Profile.from_dict({...}))   # already-open image
```

Errors raise `print_preflight.PreflightError` (`ProfileError` or `ImageError`).

## Profile

```json
{
  "print_width_in": 4,
  "print_height_in": 6,
  "dpi_target": 240,
  "dpi_warn": 300,
  "bleed_in": 0.125,
  "safe_margin_in": 0.125,
  "aspect_tolerance": 0.01,
  "edge_coverage_min": 0.95
}
```

| Field | Meaning |
| --- | --- |
| `print_width_in`, `print_height_in` | Trim size in inches (> 0). |
| `dpi_target` | Minimum acceptable density; below it the report fails. |
| `dpi_warn` | Comfortable density (>= `dpi_target`); between the two the report warns. |
| `bleed_in` | Bleed added on every side. The image must cover the **canvas**: trim + 2 x bleed on each axis. |
| `safe_margin_in` | Margin inside the trim line that non-bleeding art must stay within. |
| `aspect_tolerance` | Allowed relative aspect error, e.g. `0.01` = 1 %. |
| `edge_coverage_min` | Minimum non-background fraction (0-1) of each edge band for bleeding art. |
| `must_bleed` *(optional)* | Whether the art must bleed. Default: `bleed_in > 0`. |
| `background_rgb` *(optional)* | Paper colour, default `[255, 255, 255]`. |
| `background_tolerance` *(optional)* | Per-channel tolerance (0-255) for background, default `8`. |
| `centering_tolerance_in` *(optional)* | Allowed content-box centre offset, default `0.0625` (1/16 in). |

Unknown fields are rejected. Numbers are read as exact decimals, so `8.5` means
exactly 17/2 and boundary comparisons never suffer binary floating-point error.

## Checks

Pixels are scaled to the canvas independently per axis: `sx = width_px / canvas_width_in`,
`sy = height_px / canvas_height_in`.

- **Resolution.** The required pixel count on an axis is `ceil(canvas_in x dpi)`. The image
  fails if either axis is below the `dpi_target` count and warns if either is below the
  `dpi_warn` count. A pixel count exactly at the requirement passes.
- **Aspect.** `aspect_delta = |(width_px / height_px) / (canvas_w / canvas_h) - 1|`; it fails
  when strictly greater than `aspect_tolerance`.
- **Content box.** A pixel is *background* if it is fully transparent, or if every channel is
  within `background_tolerance` of `background_rgb`; everything else is content. The content
  box is the bounding box of content pixels (`[left, top, right, bottom]`, right/bottom
  exclusive). EXIF orientation is applied first; CMYK, palette and 16-bit images are
  converted to RGB(A) with Pillow's standard conversions.
- **Bleed** (when `must_bleed`). The content box must touch all four image edges.
- **Edge coverage.** Each edge band is `max(1, ceil(bleed_in x s))` pixels deep (1 px when
  there is no bleed); `edge_coverage` is the content fraction of each band. It is always
  reported and gates the result only when `must_bleed`.
- **Safe margin** (when not `must_bleed`). The content box must lie inside the image inset by
  `bleed_in + safe_margin_in` on every side. For bleeding art the safe margin cannot be
  checked from pixels (it concerns text and logos), so it is not gated.
- **Centering.** `centering_delta_px` is the content-box centre minus the image centre
  (positive = right / down, half-pixel resolution); it warns when either axis exceeds
  `centering_tolerance_in x s`.

The status is `fail` if any fail-severity reason is present, otherwise `warn` if any
warn-severity reason is present, otherwise `pass`.

## Report

```json
{
  "schema_version": 1,
  "status": "warn",
  "reasons": ["OFF_CENTER"],
  "effective_dpi": 50.0,
  "aspect_delta": 0.0,
  "coverage_ratio": 0.136752,
  "centering_delta_px": {"x": -32.5, "y": -72.5},
  "edge_coverage": {"top": 0.0, "right": 0.0, "bottom": 0.0, "left": 0.0},
  "content_box": [30, 40, 130, 140],
  "must_bleed": false,
  "image": {"format": "PNG", "mode": "RGB", "width_px": 225, "height_px": 325},
  "required_px": {"target": {"width": 180, "height": 260}, "warn": {"width": 225, "height": 325}}
}
```

| Field | Meaning |
| --- | --- |
| `status` | `pass`, `warn` or `fail`. |
| `reasons` | Reason codes (below), in the table's order. Empty on `pass`. |
| `effective_dpi` | `min(sx, sy)`, rounded half-up to 2 places. |
| `aspect_delta` | Relative aspect error, rounded half-up to 6 places. |
| `coverage_ratio` | Area of the content box inside the trim box divided by the trim-box area (6 places). |
| `centering_delta_px` | `{x, y}` offset of the content-box centre, or `null` with no content. |
| `edge_coverage` | Content fraction of each edge band, `top`/`right`/`bottom`/`left` (6 places). |
| `content_box` | `[left, top, right, bottom]` in pixels, or `null`. |
| `must_bleed` | Effective `must_bleed` setting. |
| `image` | Detected format, Pillow mode and pixel size (after EXIF orientation). |
| `required_px` | Pixel counts needed for `dpi_target` and `dpi_warn`. |

JSON output uses sorted keys and two-space indentation, so identical inputs give
byte-identical reports. Rounding is for display only; every pass/warn/fail decision
uses exact rational arithmetic.

## Reason codes

<!-- reason-codes:start -->
| Code | Severity | Meaning |
| --- | --- | --- |
| `DPI_BELOW_TARGET` | fail | Pixel width or height is below the count `dpi_target` requires for the full canvas (trim + 2 x `bleed_in`). |
| `DPI_BELOW_WARN` | warn | Pixel dimensions meet `dpi_target` but the width or height is below the count `dpi_warn` requires. |
| `ASPECT_MISMATCH` | fail | Image aspect ratio differs from the canvas aspect ratio by more than `aspect_tolerance` (relative; a delta equal to the tolerance passes). |
| `NO_CONTENT` | fail | Every pixel is background (transparent, or within `background_tolerance` of `background_rgb`); coverage, bleed, margin and centering checks are skipped. |
| `BLEED_NOT_REACHED` | fail | Art must bleed but the content box does not reach every image edge, so unprinted paper can show after trimming. |
| `EDGE_COVERAGE_LOW` | warn | Art must bleed but at least one edge band has a non-background fraction below `edge_coverage_min`. |
| `SAFE_MARGIN_VIOLATION` | warn | Art does not bleed and the content box extends outside the safe area (inset `bleed_in + safe_margin_in` from each image edge). |
| `OFF_CENTER` | warn | The content box centre is offset from the image centre by more than `centering_tolerance_in` on at least one axis. |
<!-- reason-codes:end -->

This table is generated from `src/print_preflight/reasons.py`; `tests/test_readme.py`
fails if they drift apart. Regenerate it with:

```sh
PYTHONPATH=src python -c 'from print_preflight.reasons import markdown_table; print(markdown_table(), end="")'
```

## Test fixtures

Fixtures are drawn procedurally by a committed script; no binary images are checked in.

```sh
python tests/fixtures/make_fixtures.py OUTDIR
```

| Fixture | Content |
| --- | --- |
| `solid.png`, `solid.jpg`, `solid_cmyk.tif` | Full-bleed solid colour (RGB PNG, JPEG, CMYK TIFF). |
| `solid_lowres.png` | Solid colour at exactly the 40 dpi target (warn band). |
| `solid_tiny.png` | Solid colour well below the target density. |
| `solid_square.png` | Square image against a portrait canvas. |
| `blank.png` | Plain white: no content. |
| `checkerboard.png`, `checkerboard.tif` | 15 px black/white checks: reaches every edge but covers about half of each band. |
| `bordered.png` | Blue art inside a 25 px white border (exactly the flat profile's safe margin). |
| `transparent_margin.png` | Opaque art inside a 10 px fully transparent margin (black RGB under alpha 0). |
| `palette_transparent.png` | Palette image with a transparent index around the art. |
| `off_centre.png` | 100 x 100 px box at (30, 40) on white. |

Two profiles in `tests/fixtures/profiles/` describe the same 4.5 x 6.5 in canvas:
`bleed.json` (4 x 6 in trim + 0.25 in bleed, must bleed) and `flat.json` (no bleed,
0.5 in safe margin). Golden reports for every fixture x profile pair live in
`tests/golden/`, along with pixel hashes that pin the generator's output.

## Tests

```sh
pip install '.[test]'
python -m pytest
```

The suite generates fixtures into a temporary directory, compares reports with the
goldens, runs Hypothesis property tests on the DPI and aspect rounding boundaries, and
exercises the CLI and profile validation. After an intentional change to the report
or fixtures, regenerate goldens with `UPDATE_GOLDENS=1 python -m pytest` and review the diff.
