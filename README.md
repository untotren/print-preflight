# print-preflight

A deterministic raster preflight library and command-line interface for print-ready artwork reports.

`print_preflight` checks a local PNG, JPEG or TIFF against a target print profile and
produces a JSON report. It depends only on Pillow, makes no network or model calls,
uploads nothing, and writes nothing except the optional `--out` JSON file.

## Install

```sh
pip install -e .            # library + `print-preflight` command
pip install -e '.[test]'    # plus pytest and hypothesis
```

## CLI

```sh
print-preflight check IMAGE --profile P.json [--json|--text] [--out REPORT.json]
python -m print_preflight check IMAGE --profile P.json
```

`--text` (default) prints a human summary; `--json` prints the report. `--out` additionally
writes the JSON report to a file.

| Exit code | Meaning |
|---|---|
| 0 | `pass` |
| 1 | `warn` |
| 2 | `fail` |
| 3 | error: unreadable/unsupported image, invalid profile, usage error, or `--out` not writable |

## Library

```python
from print_preflight import load_profile, preflight, check_image, Profile

profile = load_profile("profile.json")          # or Profile.from_dict({...})
report = preflight("art.png", profile)          # from disk
report = check_image(pil_image, profile)        # from an in-memory PIL image
```

Errors raise `PreflightError` (subclasses `ProfileError`, `ImageLoadError`).

## Profile

```json
{
  "print_width_in": 4,
  "print_height_in": 6,
  "dpi_target": 300,
  "dpi_warn": 350,
  "bleed_in": 0.125,
  "safe_margin_in": 0.125,
  "aspect_tolerance": 0.01,
  "edge_coverage_min": 0.9
}
```

| Key | Required | Meaning |
|---|---|---|
| `print_width_in`, `print_height_in` | yes | Trim size in inches (> 0). |
| `dpi_target` | yes | Pixel dimensions below those required at this density **fail**. |
| `dpi_warn` | yes | Pixel dimensions below those required at this density (but meeting `dpi_target`) **warn**. Set it above `dpi_target` to get a warning band; if it is ≤ `dpi_target` no DPI warning can occur. |
| `bleed_in` | yes | Bleed added to every side (≥ 0). The image is expected to cover the **bleed box**: `(print_width_in + 2·bleed_in) × (print_height_in + 2·bleed_in)`. |
| `safe_margin_in` | yes | Safe margin inside the trim line (≥ 0). |
| `aspect_tolerance` | yes | Maximum allowed relative aspect deviation, in `[0, 1)`. |
| `edge_coverage_min` | yes | Minimum edge-band coverage for sides that must bleed, in `[0, 1]`. |
| `background` | no | Paper colour, `"#rrggbb"` or `[r, g, b]`. Default white. |
| `background_tolerance` | no | Per-channel difference (0–255) at or below which a pixel counts as background. Default `8`. |
| `centering_tolerance_in` | no | Allowed offset of the content-box centre. Default `0.0625`. |
| `require_bleed` | no | If `true`, every side must bleed. Default `false`. |

Unknown keys are rejected (exit 3), so typos are not silently ignored. Numbers are read
through their decimal text (`0.1` is exactly 1/10) and all decisions use exact rational
arithmetic.

## How the checks work

**Resolution.** Required pixels per axis are `ceil(bleed_box_inches × dpi)`. An image fails
(`DPI_BELOW_TARGET`) if either dimension is below the `dpi_target` requirement, otherwise
warns (`DPI_BELOW_WARN`) if either is below the `dpi_warn` requirement. `effective_dpi` is
`min(width_px / bleed_width_in, height_px / bleed_height_in)`.

**Aspect.** `aspect_delta = |(width_px / height_px) / (bleed_width_in / bleed_height_in) − 1|`.
`ASPECT_MISMATCH` if it exceeds `aspect_tolerance`.

**Content box.** A pixel is *content* when its alpha is > 0 and some RGB channel differs from
`background` by more than `background_tolerance`. The content box is the bounding box of all
content pixels. The image is mapped onto the bleed box per axis (`px/in = width_px /
bleed_width_in`, likewise for height); the trim line lies `round(bleed_in · px/in)` pixels from
each image edge and the safe line `round((bleed_in + safe_margin_in) · px/in)` pixels in
(round half up).

For each side, with `d` the distance in pixels from the image edge to the content box:

* `d` < trim distance (or `d = 0` when there is no bleed): the content crosses the trim line, so
  that side **must bleed**. If `d > 0` the art stops short of the bleed edge → `BLEED_SHORT`.
* otherwise, if `d` < safe distance: the content stops inside the safe margin →
  `SAFE_MARGIN_VIOLATION`.
* with `require_bleed`, every side must bleed and any `d > 0` → `BLEED_MISSING`.

**Edge coverage (bands).** Each side has an edge band: the outer bleed strip, `trim distance`
pixels deep (at least 1 px, at most the image size). Top/bottom bands span the full width,
left/right bands the full height, so corners count toward two bands. `edge_coverage[side]` is
the fraction of band pixels that are content. It is reported for all four sides; for every side
that must bleed, coverage below `edge_coverage_min` → `EDGE_COVERAGE_LOW` (equal passes).

**Centring.** `centering_delta_px = {x: (left + right − width) / 2, y: (top + bottom − height) / 2}`
(content-box centre minus image centre; box edges are exclusive). `OFF_CENTRE` when either
component's magnitude exceeds `centering_tolerance_in` converted to pixels on that axis.

**Coverage ratio.** `coverage_ratio` is the area of the content box inside the trim box divided
by the trim box area.

## Report

```json
{
  "status": "warn",
  "effective_dpi": 80.0,
  "aspect_delta": 0.0,
  "coverage_ratio": 1.0,
  "centering_delta_px": {"x": 0.0, "y": 0.0},
  "edge_coverage": {"top": 0.9824, "right": 0.7, "bottom": 1.0, "left": 1.0},
  "reasons": ["EDGE_COVERAGE_LOW"],
  "image": {"width_px": 340, "height_px": 500},
  "required_px": {"target": {"width": 298, "height": 438}, "warn": {"width": 340, "height": 500}},
  "content_box_px": [0, 0, 340, 500],
  "edge_band_px": {"x": 10, "y": 10},
  "must_bleed": ["top", "right", "bottom", "left"]
}
```

* `status`: `fail` if any fail-severity reason, else `warn` if any warn-severity reason, else `pass`.
* Rounding (display only; decisions use exact values): `effective_dpi` is **floored** to 2
  decimals, so it never overstates resolution; `aspect_delta` is rounded half-even to 6 decimals;
  `coverage_ratio` and `edge_coverage` values are rounded half-even to 4 decimals.
* `centering_delta_px` and `content_box_px` (`[left, top, right, bottom]`, right/bottom exclusive)
  are `null` when there is no content.
* `reasons` are listed in the order of the table below, without duplicates.

## Reason codes

| Code | Severity | Meaning |
|---|---|---|
| `DPI_BELOW_TARGET` | fail | Width or height is below the pixels required at `dpi_target`. |
| `DPI_BELOW_WARN` | warn | Meets `dpi_target` but width or height is below the pixels required at `dpi_warn`. |
| `ASPECT_MISMATCH` | fail | `aspect_delta` exceeds `aspect_tolerance`. |
| `CONTENT_EMPTY` | fail | No content pixels (everything is transparent or background); geometry checks are skipped. |
| `BLEED_MISSING` | fail | `require_bleed` is set and the content does not reach the image edge on at least one side. |
| `BLEED_SHORT` | warn | Content crosses the trim line but stops short of the bleed edge on at least one side. |
| `EDGE_COVERAGE_LOW` | warn | A side that must bleed has edge-band coverage below `edge_coverage_min`. |
| `SAFE_MARGIN_VIOLATION` | warn | Content stops between the trim line and the safe line on at least one side. |
| `OFF_CENTRE` | warn | The content-box centre is offset by more than `centering_tolerance_in`. |

## Tests

```sh
python -m pytest
```

Fixtures (solid, checkerboard, bordered, transparent-margin, off-centre, and more) are drawn by
`tests/fixtures/make_fixtures.py` into a temporary directory at test time; run
`python tests/fixtures/make_fixtures.py OUT_DIR` to inspect them. Golden reports live in
`tests/golden/`; regenerate after an intended change with
`PREFLIGHT_UPDATE_GOLDEN=1 python -m pytest tests/test_golden.py`. Property tests (hypothesis,
derandomised) cover DPI and aspect rounding boundaries.
