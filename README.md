# print-preflight

A deterministic raster preflight library and command-line interface for print-ready artwork reports.

`print_preflight` checks a local PNG, JPEG or TIFF against a target print
profile. It reports resolution, aspect ratio, bleed/safe-margin coverage, edge
coverage and centering. It needs only Pillow. It makes no network or model
calls and uploads nothing. The only file it writes is the optional `--out`
report.

## Install

```sh
pip install .            # or: pip install -e '.[test]'
```

## CLI

```sh
print-preflight check IMAGE --profile P.json [--json|--text] [--out REPORT.json]
python -m print_preflight check IMAGE --profile P.json --json
```

`--text` is the default output. `--out` also writes the JSON report to a file.

| Exit code | Meaning |
|---|---|
| 0 | `pass` |
| 1 | `warn` |
| 2 | `fail` |
| 3 | error: unreadable or unsupported image, invalid profile, unwritable `--out`, or a usage error |

When `--json` is given and an error occurs, stdout holds
`{"status": "error", "error": {"code": ..., "message": ...}}`. In every mode
the error is also printed to stderr.

## Library

```python
from print_preflight import check, analyze, load_profile, Profile, PreflightError

report = check("art.png", "profile.json")          # profile: path, dict or Profile
report = analyze(pil_image, {"print_width_in": 4, ...})
```

`PreflightError.code` holds one of the error codes listed below.

## Profile

```json
{
  "print_width_in": 4,
  "print_height_in": 3,
  "dpi_target": 100,
  "dpi_warn": 120,
  "bleed_in": 0.25,
  "safe_margin_in": 0.25,
  "aspect_tolerance": 0.01,
  "edge_coverage_min": 0.9
}
```

* `print_width_in` / `print_height_in`: the trim (finished) size.
* `bleed_in`: the bleed on each side. The image is mapped onto the **bleed
  canvas**, which is `(print_width_in + 2·bleed_in) × (print_height_in + 2·bleed_in)`.
* `safe_margin_in`: an inset inside the trim line. Content that does not bleed
  should stay inside it.
* `dpi_target`: the minimum resolution. An image below it **fails**.
  `dpi_warn` must be `>= dpi_target`. An image at or above `dpi_target` but
  below `dpi_warn` **warns**.
* `aspect_tolerance`: the maximum allowed relative aspect error (inclusive).
* `edge_coverage_min`: the minimum non-background fraction of each bleeding edge band, from 0 to 1.

All fields are required, and unknown fields are rejected. Numbers are handled
as exact decimals: JSON `0.01` and the Python float `0.01` both mean exactly
1/100. That keeps threshold comparisons free of floating-point drift.

## Report

```json
{
  "status": "pass | warn | fail",
  "effective_dpi": 120.0,
  "aspect_delta": 0.0,
  "coverage_ratio": 1.0,
  "centering_delta_px": {"x": 0.0, "y": 0.0},
  "edge_coverage": {"top": 1.0, "right": 1.0, "bottom": 1.0, "left": 1.0},
  "reasons": []
}
```

* `effective_dpi`: `min(width_px / canvas_width_in, height_px / canvas_height_in)`,
  which is the resolution of the limiting axis when the image covers the bleed
  canvas. It is rounded **down** to 2 decimals.
* `aspect_delta`: `|(width_px / height_px) / (canvas_width_in / canvas_height_in) − 1|`.
  It is rounded **up** to 6 decimals.
* `coverage_ratio`: the area of the content box inside the trim box, divided by
  the trim box area. It is rounded down to 6 decimals.
* `centering_delta_px`: the offset of the content box's centre from the image
  centre, in pixels. Positive values mean right or down.
* `edge_coverage`: for each side, the fraction of the edge band that is
  non-background. The band is the bleed strip, and is at least 1 px thick. It
  is rounded down to 6 decimals.
* `reasons`: reason codes in the fixed order of the table below.
* `status`: `fail` if any reason has fail severity, else `warn` if any reason
  has warn severity, else `pass`.

Rounding is conservative. A failing value is never displayed as if it passes.
For thresholds with at most 2 (DPI) or 6 (aspect) decimals, the displayed value
gives the same verdict as the exact one.

### Background and content

A pixel is **background** if it is fully transparent (alpha 0), or if its R, G
and B channels are all `>= 250` (unprinted paper white). Every other pixel is
**content**. The content box is the bounding box of all content pixels.

For each side, the distance `d` from the image edge to the content box is
compared with the bleed line and the safe line, both converted to pixels on
that axis:

* If `d == 0` or `d` is less than the bleed width, the side **bleeds**. A
  bleeding side must reach the image edge (`d == 0`), or `BLEED_INCOMPLETE` is
  raised. Its edge band must be at least `edge_coverage_min` content, or
  `EDGE_COVERAGE_LOW` is raised.
* If the side does not bleed, it must satisfy `d >= bleed + safe_margin`, or
  `SAFE_MARGIN_VIOLATION` is raised. Content exactly on the safe line passes.
* On an axis where neither side bleeds, the content box centre must be within
  `max(1 px, 1% of the dimension)` of the image centre, or `OFF_CENTER` is
  raised.

## Reason codes

| Code | Severity | Meaning |
|---|---|---|
| `DPI_BELOW_TARGET` | fail | Effective DPI is below `dpi_target`. The image has fewer pixels than `ceil(canvas_in × dpi_target)` on at least one axis. |
| `DPI_BELOW_WARN` | warn | Effective DPI is at or above `dpi_target` but below `dpi_warn`. |
| `ASPECT_MISMATCH` | fail | `aspect_delta` is greater than `aspect_tolerance`. |
| `ASPECT_ROTATED` | fail | The aspect is out of tolerance as given, but within tolerance when rotated 90°, so the orientation is probably wrong. This code replaces `ASPECT_MISMATCH`. |
| `NO_CONTENT` | fail | Every pixel is background (transparent or near-white). |
| `BLEED_INCOMPLETE` | fail | Content crosses the trim line on some side but stops short of the bleed edge, which leaves a white sliver after trimming. |
| `SAFE_MARGIN_VIOLATION` | warn | On some side, non-bleeding content lies between the trim line and the safe line. |
| `EDGE_COVERAGE_LOW` | warn | On some side, the content bleeds but its edge band is less than `edge_coverage_min` non-background. |
| `OFF_CENTER` | warn | On an axis without bleed, the content box centre is more than `max(1 px, 1%)` from the image centre. |

## Error codes (exit 3)

| Code | Meaning |
|---|---|
| `IMAGE_NOT_FOUND` | The image path does not exist. |
| `IMAGE_UNREADABLE` | The image cannot be decoded (corrupt, a directory, or a decompression bomb). |
| `UNSUPPORTED_FORMAT` | The file is a readable image but not PNG, JPEG or TIFF. |
| `PROFILE_NOT_FOUND` | The profile path does not exist. |
| `PROFILE_UNREADABLE` | The profile file cannot be read. |
| `PROFILE_INVALID` | The profile is not valid JSON, or a field is missing, unknown, non-numeric, non-finite or out of range. |
| `OUTPUT_UNWRITABLE` | The `--out` file cannot be written. |

## Determinism

Images are converted to RGBA after EXIF orientation is applied, and multi-frame
TIFFs use their first frame. All geometry uses exact rational arithmetic, so the
same image and profile always produce byte-identical JSON.

## Tests

```sh
pip install -e '.[test]'
pytest
```

* `scripts/make_fixtures.py OUTDIR` procedurally generates the fixtures: solid,
  checkerboard, bordered, transparent-margin, off-centre, bleed-short, blank,
  low-res, tiny and rotated. It also writes JPEG and TIFF copies of solid. The
  test session runs it into a temporary directory, so no binary fixtures are
  committed.
* `tests/golden/*.json` holds the golden reports against
  `tests/profiles/standard.json`. To regenerate them, run
  `UPDATE_GOLDEN=1 pytest tests/test_golden.py` and review the diff.
* `tests/test_aspect.py` and `tests/test_dpi.py` hold Hypothesis property tests
  for the rounding and tolerance boundaries.
