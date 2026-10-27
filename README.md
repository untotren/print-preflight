# print-preflight

A deterministic raster preflight library and command-line interface for print-ready artwork reports.

`print_preflight` checks a PNG, JPEG or TIFF file against a print profile and reports whether it is
ready for print. It needs only Pillow. It makes no network or model calls, uploads nothing, and writes
nothing except the optional `--out` report.

## Install

```sh
pip install .            # library + `print-preflight` command
pip install '.[test]'    # adds pytest and hypothesis
```

## Command line

```sh
print-preflight check IMAGE --profile P.json [--json | --text] [--out REPORT.json]
python -m print_preflight check IMAGE --profile P.json --json
```

* `--text` (default) prints a human-readable summary; `--json` prints the JSON report.
* `--out PATH` also writes the JSON report to `PATH`, whichever format goes to stdout.
* On an error, a message `print-preflight: error: CODE: message` goes to stderr. With `--json`,
  `{"status": "error", "error": {"code": ..., "message": ...}}` is also printed to stdout.

### Exit codes

| Exit | Meaning |
| ---- | ------- |
| 0 | pass: no reason codes |
| 1 | warn: only `warn`-severity reason codes |
| 2 | fail: at least one `fail`-severity reason code |
| 3 | error: no report could be produced (see error codes); this includes command-line usage errors |

## Library

```python
from print_preflight import load_profile, check_image, analyze, Profile, PreflightError

profile = load_profile("profile.json")           # or Profile.from_dict({...})
report = check_image("art.png", profile)         # or analyze(pil_image, profile)
report["status"], report["reasons"]
```

`PreflightError.code` holds one of the error codes below. `measure_resolution(width_px, height_px,
profile)` runs just the DPI and aspect checks without pixel data.

## Profile

```json
{
  "print_width_in": 8.5,
  "print_height_in": 11,
  "dpi_target": 240,
  "dpi_warn": 300,
  "bleed_in": 0.125,
  "safe_margin_in": 0.25,
  "aspect_tolerance": 0.01,
  "edge_coverage_min": 0.95
}
```

| Field | Meaning |
| ----- | ------- |
| `print_width_in`, `print_height_in` | Trim size in inches (> 0). |
| `bleed_in` | Bleed added on every side (>= 0). The image is expected to cover the full **canvas**: trim + 2 x bleed on each axis. |
| `dpi_target` | Minimum resolution (> 0). Below it the image fails. |
| `dpi_warn` | Recommended resolution (>= `dpi_target`). Below it the image warns. |
| `safe_margin_in` | Distance inside the trim line that content should not end in (>= 0). |
| `aspect_tolerance` | Allowed relative aspect difference (>= 0), e.g. `0.01` = 1 %. |
| `edge_coverage_min` | Minimum fraction (0..1) of a bleeding edge band that must be content. |
| `background_rgb` | Optional, default `[255, 255, 255]`: paper colour treated as background in opaque images. |
| `background_tolerance` | Optional, default `8`: integer 0..255; a pixel within this distance of `background_rgb` on every channel is background. |
| `centering_tolerance` | Optional, default `0.01`: allowed offset of the content-box centre as a fraction of the image width / height. |

Unknown fields are rejected (`PROFILE_INVALID`) so typos do not pass silently.

## Report

```json
{
  "status": "pass",
  "effective_dpi": 150.22,
  "aspect_delta": 0.000423,
  "coverage_ratio": 1.0,
  "centering_delta_px": {"x": 0, "y": 0},
  "edge_coverage": {"bottom": 1.0, "left": 1.0, "right": 1.0, "top": 1.0},
  "reasons": [],
  "image_px": {"height": 263, "width": 338},
  "required_px": {"target": [225, 175], "warn": [338, 263]},
  "content_box_px": [0, 0, 338, 263],
  "margins_px": {"bottom": 0, "left": 0, "right": 0, "top": 0},
  "background_mode": "color"
}
```

| Key | Meaning |
| --- | ------- |
| `status` | `pass`, `warn` or `fail`: the most severe reason code. |
| `effective_dpi` | `min(width_px / canvas_width_in, height_px / canvas_height_in)`, floored to 2 decimals. |
| `aspect_delta` | `abs((width_px / height_px) / (canvas_width_in / canvas_height_in) - 1)`, ceiled to 6 decimals. |
| `coverage_ratio` | Content-box area / image area, floored to 4 decimals. |
| `centering_delta_px` | Content-box centre minus image centre, in pixels (multiples of 0.5; negative = left/up). `null` if there is no content. |
| `edge_coverage` | For each side, the fraction of the edge band that is content, floored to 4 decimals. The band is `ceil(bleed_in x px-per-inch)` pixels deep (at least 1). |
| `reasons` | Reason codes in the canonical order of the table below. |
| `image_px` | Image size. |
| `required_px` | Minimum `[width, height]` in pixels for `dpi_target` and `dpi_warn`: `ceil(canvas_in x dpi)`. |
| `content_box_px` | `[left, top, right, bottom]` of the content (right/bottom exclusive), or `null`. |
| `margins_px` | Distance from each side of the content box to the image edge, or `null`. |
| `background_mode` | `alpha` or `color`; see "Content detection". |

### Content detection

* If the image has an alpha channel (or palette transparency) and at least one pixel is not fully
  opaque, **alpha mode** is used: fully transparent pixels are background, everything else is content.
* Otherwise **color mode** is used: a pixel is background when every RGB channel is within
  `background_tolerance` of `background_rgb`.

The content box is the bounding box of all content pixels. Pixel scale on each axis is
`image_px / canvas_in`, which converts `bleed_in` and `safe_margin_in` into pixels.

### Reason codes

| Code | Severity | Raised when |
| ---- | -------- | ----------- |
| `DPI_BELOW_TARGET` | fail | Width or height in pixels is below `ceil(canvas_in x dpi_target)`, i.e. effective DPI < `dpi_target`. |
| `DPI_BELOW_WARN` | warn | Not below target, but width or height is below `ceil(canvas_in x dpi_warn)`. |
| `ASPECT_MISMATCH` | fail | `aspect_delta` > `aspect_tolerance` (a delta equal to the tolerance passes). |
| `CONTENT_EMPTY` | fail | No content pixel was found. |
| `BLEED_SHORT` | fail | On some side the content box stops `d` px from the image edge with `0 < d <= bleed_px`: art reaches the trim but not the canvas edge, so a trim shift exposes paper. |
| `SAFE_MARGIN_INTRUSION` | warn | On some side `bleed_px < d < bleed_px + safe_px`: content ends inside the safe margin. |
| `EDGE_COVERAGE_LOW` | warn | On a side the content box touches (`d = 0`, art that must bleed), that side's `edge_coverage` < `edge_coverage_min`. |
| `OFF_CENTER` | warn | `abs(centering_delta_px.x) > centering_tolerance x width_px` or the same for y. |

### Error codes

These produce exit code 3 and no report.

| Code | Severity | Raised when |
| ---- | -------- | ----------- |
| `PROFILE_UNREADABLE` | error | The profile file is missing, unreadable or not valid JSON. |
| `PROFILE_INVALID` | error | The profile has missing, unknown, non-numeric or out-of-range fields. |
| `IMAGE_NOT_FOUND` | error | The image path does not exist or is not a file. |
| `IMAGE_UNREADABLE` | error | The image cannot be decoded (corrupt, truncated, decompression bomb, zero size). |
| `IMAGE_FORMAT_UNSUPPORTED` | error | The file is not PNG, JPEG or TIFF, or its pixel mode cannot be converted. |
| `OUTPUT_UNWRITABLE` | error | The `--out` file cannot be written. |
| `USAGE` | error | Invalid command line (missing arguments, unknown command, `--json` with `--text`). |

### Rounding

All decisions are made with exact rational arithmetic. JSON numbers in the profile are read through
their shortest decimal form, so `0.1` means exactly one tenth. Reported numbers are rounded in the
direction that keeps them consistent with the decision: `effective_dpi` and `edge_coverage` are
floored and `aspect_delta` is ceiled. So comparing a reported value with a profile threshold that
has no more decimals than the report always agrees with the reason codes. For example, an image
1 px short of the requirement can never report `effective_dpi` equal to `dpi_target`.

## Development

```sh
pip install -e '.[test]'
python -m pytest
```

The suite is deterministic: fixtures (solid, checkerboard, bordered, transparent-margin, off-centre
and others) are generated from code by `scripts/make_fixtures.py` into a temporary directory. The
Hypothesis property tests on the DPI and aspect rounding boundaries run with `derandomize=True`. Every
fixture's CLI JSON output is compared byte-for-byte with `tests/golden/*.json`. After an intentional
change, regenerate them with `UPDATE_GOLDEN=1 python -m pytest tests/test_golden.py` and review the diff.

To look at the fixtures: `python scripts/make_fixtures.py /some/dir`.

## License

MIT
